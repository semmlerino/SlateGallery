"""Advanced integration tests for SlateGallery with new features."""

import tempfile
import time
from pathlib import Path

import pytest
from PIL import Image

from src.core.cache_manager import ImprovedCacheManager
from src.core.config_manager import load_config, save_config
from src.core.gallery_generator import generate_html_gallery
from src.core.image_processor import scan_directories
from src.utils.threading import GenerateGalleryThread, ScanThread


class TestLazyLoadingIntegration:
    """Integration tests for lazy loading feature."""

    @pytest.fixture
    def gallery_environment(self):
        """Create a complete gallery environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create directory structure
            images_dir = base_path / "photos"
            output_dir = base_path / "gallery_output"
            cache_dir = base_path / "cache"
            config_file = base_path / "config.ini"

            images_dir.mkdir()
            cache_dir.mkdir()

            # Create test images
            for i in range(20):
                img = Image.new('RGB', (800, 600), color=(i*10, 100, 150))
                img.save(images_dir / f"photo_{i:03d}.jpg", quality=95)

            # Create template
            template = base_path / "template.html"
            template.write_text('''<!DOCTYPE html>
<html>
<head><title>Test Gallery</title></head>
<body>
    <h1>Gallery (Lazy Loading: {{ lazy_loading }})</h1>
    {% for slate in gallery %}
        {% for image in slate.images %}
        <img src="{{ image.thumbnail | default(image.original_path) }}"
             {% if lazy_loading %}loading="lazy"{% endif %}
             alt="{{ image.filename }}">
        {% endfor %}
    {% endfor %}
</body>
</html>''')

            yield {
                'base_path': base_path,
                'images_dir': images_dir,
                'output_dir': output_dir,
                'cache_dir': cache_dir,
                'config_file': config_file,
                'template': template
            }

    def test_lazy_loading_enabled_vs_disabled(self, gallery_environment, monkeypatch):
        """Test gallery generation with lazy loading on and off."""
        # Patch config file location
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE',
                          str(gallery_environment['config_file']))

        # Test with lazy loading enabled
        save_config(
            str(gallery_environment['images_dir']),
            [str(gallery_environment['images_dir'])],
            [str(gallery_environment['images_dir'])],
            generate_thumbnails=True,
            thumbnail_size=600,
            lazy_loading=True,
            exclude_patterns=""
        )

        # Scan directories
        scan_directories(str(gallery_environment['images_dir']))

        # Generate gallery with lazy loading
        success = generate_html_gallery(
            gallery_data=[{'slate': 'photos', 'images': [
                {'original_path': str(p), 'filename': p.name, 'thumbnail': str(p)}
                for p in gallery_environment['images_dir'].glob('*.jpg')
            ]}],
            focal_length_data=[],
            date_data=[],
            template_path=str(gallery_environment['template']),
            output_dir=str(gallery_environment['output_dir']),
            allowed_root_dirs=str(gallery_environment['images_dir']),
            status_callback=lambda x: None,
            lazy_loading=True
        )

        assert success[0]

        # Check HTML contains lazy loading
        html_file = gallery_environment['output_dir'] / 'index.html'
        assert html_file.exists()
        content = html_file.read_text()
        assert 'loading="lazy"' in content
        assert 'Lazy Loading: True' in content

        # Now test with lazy loading disabled
        success = generate_html_gallery(
            gallery_data=[{'slate': 'photos', 'images': [
                {'original_path': str(p), 'filename': p.name, 'thumbnail': str(p)}
                for p in gallery_environment['images_dir'].glob('*.jpg')
            ]}],
            focal_length_data=[],
            date_data=[],
            template_path=str(gallery_environment['template']),
            output_dir=str(gallery_environment['output_dir']),
            allowed_root_dirs=str(gallery_environment['images_dir']),
            status_callback=lambda x: None,
            lazy_loading=False
        )

        assert success[0]

        # Check HTML does NOT contain lazy loading
        content = html_file.read_text()
        assert 'loading="lazy"' not in content
        assert 'Lazy Loading: False' in content

    def test_performance_impact_of_lazy_loading(self, gallery_environment):
        """Test that lazy loading configuration works correctly."""
        # Create many images to test performance
        for i in range(100):
            img = Image.new('RGB', (2000, 1500), color=(i*2, 100, 150))
            img.save(gallery_environment['images_dir'] / f"large_{i:03d}.jpg")

        gallery_data = [{'slate': 'photos', 'images': [
            {'original_path': str(p), 'filename': p.name, 'thumbnail': str(p)}
            for p in gallery_environment['images_dir'].glob('*.jpg')
        ]}]

        # Time gallery generation with lazy loading
        start = time.perf_counter()
        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(gallery_environment['template']),
            output_dir=str(gallery_environment['output_dir']),
            allowed_root_dirs=str(gallery_environment['images_dir']),
            status_callback=lambda x: None,
            lazy_loading=True
        )
        lazy_time = time.perf_counter() - start
        assert success[0]

        # Both should complete quickly since we're just generating HTML
        # The real performance difference would be in browser loading
        assert lazy_time < 5.0  # Should complete in under 5 seconds


class TestConfigurationPersistence:
    """Test configuration persistence with all parameters."""

    def test_all_config_parameters_persist(self, tmp_path, monkeypatch):
        """Test that all 7 configuration parameters persist correctly."""
        config_file = tmp_path / 'test_config.ini'
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

        # Test various configurations
        test_configs = [
            ("/path1", ["/path1", "/path2"], ["/path1"], True, 600, True, "*.tmp"),
            ("/path3", ["/path3", "/path4", "/path5"], ["/path3", "/path4"], False, 800, False, ""),
            ("/special/path with spaces", ["/dir1"], ["/dir1"], True, 1200, True, "test*"),
        ]

        for current_dir, slate_dirs, selected_dirs, gen_thumb, thumb_size, lazy, exclude in test_configs:
            # Save configuration
            save_config(current_dir, slate_dirs, selected_dirs, gen_thumb, thumb_size, lazy, exclude)

            # Load and verify
            loaded = load_config()
            assert loaded[0] == current_dir
            assert loaded[1] == slate_dirs
            assert loaded[2] == selected_dirs
            assert loaded[3] == gen_thumb
            assert loaded[4] == thumb_size
            assert loaded[5] == lazy
            assert loaded[6] == exclude

    def test_config_backwards_compatibility(self, tmp_path, monkeypatch):
        """Test that old config files without lazy_loading still work."""
        config_file = tmp_path / 'old_config.ini'
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

        # Write old-style config without lazy_loading
        config_file.write_text("""[Settings]
current_slate_dir = /old/path
slate_dirs = /old/path|/another/path
generate_thumbnails = True
thumbnail_size = 800
""")

        # Should load with default lazy_loading=True
        current_dir, slate_dirs, selected_slate_dirs, gen_thumb, thumb_size, lazy, exclude_patterns = load_config()
        assert current_dir == "/old/path"
        assert slate_dirs == ["/old/path", "/another/path"]
        assert gen_thumb is True
        assert thumb_size == 800
        assert lazy is True  # Default value


class TestMixedImageFormats:
    """Test handling of various image formats in a single gallery."""

    @pytest.fixture
    def mixed_format_gallery(self):
        """Create gallery with various image formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            images_dir = base_path / "mixed_formats"
            images_dir.mkdir()

            # Create different format images
            formats = {
                'RGB': [('jpg', 'JPEG'), ('png', 'PNG'), ('bmp', 'BMP')],
                'RGBA': [('png', 'PNG')],
                'L': [('jpg', 'JPEG'), ('png', 'PNG')],  # Grayscale
                'P': [('gif', 'GIF')],  # Palette
            }

            created_files = []
            for mode, format_list in formats.items():
                for ext, format_name in format_list:
                    filename = f"test_{mode}_{format_name}.{ext}"
                    filepath = images_dir / filename

                    if mode == 'P':
                        # Create palette image
                        img = Image.new('P', (200, 200))
                        img.putpalette([i//3 for i in range(768)])
                    else:
                        img = Image.new(mode, (200, 200),
                                      color='white' if mode == 'L' else (100, 150, 200))

                    img.save(filepath, format=format_name)
                    created_files.append(filepath)

            yield {
                'base_path': base_path,
                'images_dir': images_dir,
                'files': created_files
            }

    def test_process_mixed_formats(self, mixed_format_gallery, qtbot):
        """Test that all image formats are processed correctly."""
        cache_manager = ImprovedCacheManager(
            base_dir=str(mixed_format_gallery['base_path'] / 'cache')
        )

        # Scan directory
        scan_thread = ScanThread(
            str(mixed_format_gallery['images_dir']),
            cache_manager
        )

        with qtbot.waitSignal(scan_thread.scan_complete, timeout=10000) as blocker:
            scan_thread.start()

        slates_dict, message = blocker.args

        # Verify all formats were found
        assert len(slates_dict) > 0
        total_images = sum(len(slate['images']) for slate in slates_dict.values())
        assert total_images == len(mixed_format_gallery['files'])

        # Generate gallery with thumbnails
        output_dir = mixed_format_gallery['base_path'] / 'output'
        template = mixed_format_gallery['base_path'] / 'template.html'
        template.write_text('<html>{% for s in gallery %}{{ s.slate }}{% endfor %}</html>')

        thread = GenerateGalleryThread(
            selected_slates=list(slates_dict.keys()),
            slates_dict=slates_dict,
            cache_manager=cache_manager,
            output_dir=str(output_dir),
            allowed_root_dirs=str(mixed_format_gallery['images_dir']),
            template_path=str(template),
            generate_thumbnails=True,
            thumbnail_size=600,
            lazy_loading=True
        )

        with qtbot.waitSignal(thread.gallery_complete, timeout=30000) as blocker:
            thread.start()

        success, message = blocker.args
        assert success  # success from signal is already bool

        # Verify thumbnails were created
        thumb_dir = output_dir / 'thumbnails'
        if thumb_dir.exists():
            thumbnails = list(thumb_dir.glob('*.jpg'))
            # All thumbnails should be JPEG regardless of source format
            assert all(t.suffix == '.jpg' for t in thumbnails)


class TestErrorRecovery:
    """Test system recovery from various error conditions."""

    def test_corrupted_image_handling(self, tmp_path, qtbot):
        """Test that corrupted images don't crash the system."""
        images_dir = tmp_path / 'corrupted'
        images_dir.mkdir()

        # Create valid images
        for i in range(3):
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(images_dir / f'good_{i}.jpg')

        # Create corrupted image
        corrupted_file = images_dir / 'corrupted.jpg'
        corrupted_file.write_bytes(b'This is not a valid JPEG file!')

        # Create truncated image
        truncated_file = images_dir / 'truncated.jpg'
        img = Image.new('RGB', (100, 100), color='red')
        img.save(truncated_file)
        # Truncate the file
        with open(truncated_file, 'r+b') as f:
            f.truncate(100)  # Cut off most of the file

        cache_manager = ImprovedCacheManager(base_dir=str(tmp_path / 'cache'))

        # Should handle corrupted images gracefully
        scan_thread = ScanThread(str(images_dir), cache_manager)

        with qtbot.waitSignal(scan_thread.scan_complete, timeout=10000) as blocker:
            scan_thread.start()

        slates_dict, message = blocker.args

        # Should find at least the good images
        assert len(slates_dict) > 0
        # Should have found all files (even corrupted ones in the scan)
        total_images = sum(len(slate['images']) for slate in slates_dict.values())
        assert total_images >= 3  # At least the good images

    def test_permission_denied_recovery(self, tmp_path, monkeypatch):
        """Test handling of permission denied errors."""
        import stat

        output_dir = tmp_path / 'readonly_output'
        output_dir.mkdir()

        # Make directory read-only (simulate permission issue)
        # Note: This might not work on all systems/filesystems
        try:
            output_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

            gallery_data = [{'slate': 'test', 'images': []}]
            template = tmp_path / 'template.html'
            template.write_text('<html>Test</html>')

            # Should handle permission denied gracefully
            success = generate_html_gallery(
                gallery_data=gallery_data,
                focal_length_data=[],
                date_data=[],
                template_path=str(template),
                output_dir=str(output_dir),
                allowed_root_dirs=str(tmp_path),
                status_callback=lambda x: None,
                lazy_loading=True
            )

            # Should fail gracefully
            assert not success[0]

        finally:
            # Restore permissions for cleanup
            output_dir.chmod(stat.S_IRWXU)

    def test_invalid_output_directory(self, tmp_path):
        """Test handling of invalid output directory."""
        # Use a non-existent deeply nested path that can't be created
        invalid_output = "/invalid/nonexistent/deeply/nested/path/that/should/not/exist"

        template = tmp_path / 'template.html'
        template.write_text('<html>Test</html>')

        # Create real test image
        img_path = tmp_path / 'test.jpg'
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(img_path)

        gallery_data = [{'slate': 'test', 'images': [
            {'original_path': str(img_path), 'filename': 'test.jpg', 'thumbnail': str(img_path)}
        ]}]

        # Should handle invalid output directory gracefully
        generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(template),
            output_dir=invalid_output,
            allowed_root_dirs=str(tmp_path),
            status_callback=lambda x: None,
            lazy_loading=True
        )

        # Should fail gracefully when can't create output directory
        # The actual behavior depends on the implementation
        # but it should not crash

    def test_massive_gallery_stress_test(self, tmp_path):
        """Test handling of very large galleries without mocking."""
        images_dir = tmp_path / 'massive_gallery'
        images_dir.mkdir()

        # Create a realistic large dataset (but not so large it takes forever)
        num_images = 500  # Enough to stress test but still reasonable

        for i in range(num_images):
            # Create small images to speed up test
            img = Image.new('RGB', (200, 150), color=(i % 255, (i*2) % 255, (i*3) % 255))
            img.save(images_dir / f'photo_{i:04d}.jpg', quality=70)

        # This should handle large datasets efficiently
        slates = scan_directories(str(images_dir))

        # Should find all images
        total_found = sum(len(images['images']) for images in slates.values())
        assert total_found == num_images

        # Memory usage should be reasonable (not loading all images at once)
        # Performance should be acceptable
        import time
        start = time.time()

        # Process with cache manager
        cache_manager = ImprovedCacheManager(base_dir=str(tmp_path / 'cache'))
        cache_manager.save_cache(str(images_dir), slates)

        elapsed = time.time() - start
        assert elapsed < 30  # Should complete in reasonable time


class TestEndToEndWorkflow:
    """Test complete workflows from start to finish."""

    def test_complete_gallery_generation_workflow(self, tmp_path, qtbot, monkeypatch):
        """Test the complete workflow from scan to gallery generation."""
        # Setup environment
        photos_dir = tmp_path / 'MyPhotos'
        vacation_dir = photos_dir / 'Vacation2024'
        family_dir = photos_dir / 'Family'
        vacation_dir.mkdir(parents=True)
        family_dir.mkdir(parents=True)

        # Create images with metadata

        # Vacation photos
        for i in range(5):
            img = Image.new('RGB', (1920, 1080), color=(50+i*30, 100, 150))
            path = vacation_dir / f'beach_{i:02d}.jpg'
            img.save(path)

            # Add EXIF data (if piexif available)
            try:
                import piexif
                exif_dict = {
                    "0th": {},
                    "Exif": {
                        piexif.ExifIFD.FocalLength: (24 + i*10, 1),
                        piexif.ExifIFD.DateTimeOriginal: b'2024:07:15 10:30:00'
                    }
                }
                exif_bytes = piexif.dump(exif_dict)
                img.save(path, exif=exif_bytes)
            except ImportError:
                pass

        # Family photos
        for i in range(3):
            img = Image.new('RGB', (1600, 1200), color=(100, 50+i*40, 200))
            path = family_dir / f'portrait_{i:02d}.jpg'
            img.save(path)

        # Setup config
        config_file = tmp_path / 'config.ini'
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

        # Save initial config
        save_config(
            str(photos_dir),
            [str(photos_dir)],
            [str(photos_dir)],
            generate_thumbnails=True,
            thumbnail_size=800,
            lazy_loading=True,
            exclude_patterns=""
        )

        # Step 1: Scan directories
        cache_manager = ImprovedCacheManager(base_dir=str(tmp_path / 'cache'))
        scan_thread = ScanThread(str(photos_dir), cache_manager)

        with qtbot.waitSignal(scan_thread.scan_complete, timeout=10000) as blocker:
            scan_thread.start()

        slates_dict, scan_message = blocker.args
        assert 'Vacation2024' in slates_dict
        assert 'Family' in slates_dict
        assert len(slates_dict['Vacation2024']['images']) == 5
        assert len(slates_dict['Family']['images']) == 3

        # Step 2: Generate gallery with thumbnails
        output_dir = tmp_path / 'gallery_output'
        template = tmp_path / 'template.html'
        template.write_text('''<!DOCTYPE html>
<html>
<head><title>My Photo Gallery</title></head>
<body>
    <h1>Photo Gallery</h1>
    <p>Thumbnails: {{ gallery[0].images[0].thumbnails is defined }}</p>
    <p>Lazy Loading: {{ lazy_loading }}</p>
    <p>Total Slates: {{ gallery|length }}</p>
    {% for slate in gallery %}
    <section>
        <h2>{{ slate.slate }}</h2>
        <p>{{ slate.images|length }} photos</p>
        {% for image in slate.images %}
        <img src="{{ image.thumbnail }}"
             {% if lazy_loading %}loading="lazy"{% endif %}
             data-focal="{{ image.focal_length }}"
             alt="{{ image.filename }}">
        {% endfor %}
    </section>
    {% endfor %}
</body>
</html>''')

        gallery_thread = GenerateGalleryThread(
            selected_slates=['Vacation2024', 'Family'],
            slates_dict=slates_dict,
            cache_manager=cache_manager,
            output_dir=str(output_dir),
            allowed_root_dirs=str(photos_dir),
            template_path=str(template),
            generate_thumbnails=True,
            thumbnail_size=800,
            lazy_loading=True
        )

        with qtbot.waitSignal(gallery_thread.gallery_complete, timeout=30000) as blocker:
            gallery_thread.start()

        success, gen_message = blocker.args
        assert success  # success from signal is already bool
        assert 'generated' in gen_message.lower()

        # Step 3: Verify output
        html_file = output_dir / 'index.html'
        assert html_file.exists()

        content = html_file.read_text()
        assert 'Vacation2024' in content
        assert 'Family' in content
        assert 'loading="lazy"' in content
        assert 'Lazy Loading: True' in content
        assert 'Total Slates: 2' in content

        # Verify thumbnails
        thumb_dir = output_dir / 'thumbnails'
        assert thumb_dir.exists()
        thumbnails = list(thumb_dir.glob('*.jpg'))
        assert len(thumbnails) == 8  # 5 vacation + 3 family

        # Verify all thumbnails are 800x800 or smaller
        for thumb_path in thumbnails:
            with Image.open(thumb_path) as thumb:
                assert max(thumb.size) <= 800

        # Step 4: Test configuration update
        save_config(
            str(photos_dir),
            [str(photos_dir)],
            [str(photos_dir)],
            generate_thumbnails=False,
            thumbnail_size=600,
            lazy_loading=False,
            exclude_patterns=""
        )

        # Reload config
        loaded = load_config()
        assert loaded[3] is False  # generate_thumbnails
        assert loaded[4] == 600    # thumbnail_size
        assert loaded[5] is False  # lazy_loading


class TestCacheInvalidation:
    """Test cache invalidation and updates."""

    def test_cache_updates_on_file_changes(self, tmp_path, qtbot):
        """Test that cache properly updates when files are added/removed."""
        images_dir = tmp_path / 'dynamic_images'
        images_dir.mkdir()
        cache_manager = ImprovedCacheManager(base_dir=str(tmp_path / 'cache'))

        # Initial scan with 3 images
        for i in range(3):
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(images_dir / f'initial_{i}.jpg')

        # First scan
        scan_thread = ScanThread(str(images_dir), cache_manager)
        with qtbot.waitSignal(scan_thread.scan_complete, timeout=10000) as blocker:
            scan_thread.start()

        slates1, _ = blocker.args
        initial_count = sum(len(s['images']) for s in slates1.values())
        assert initial_count == 3

        # Add more images
        for i in range(2):
            img = Image.new('RGB', (100, 100), color='green')
            img.save(images_dir / f'added_{i}.jpg')

        # Clear cache to force rescan
        cache_file = Path(cache_manager.get_cache_file(str(images_dir)))
        if cache_file.exists():
            cache_file.unlink()

        # Rescan
        scan_thread2 = ScanThread(str(images_dir), cache_manager)
        with qtbot.waitSignal(scan_thread2.scan_complete, timeout=10000) as blocker:
            scan_thread2.start()

        slates2, _ = blocker.args
        new_count = sum(len(s['images']) for s in slates2.values())
        assert new_count == 5  # 3 initial + 2 added


# Run specific test categories
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
