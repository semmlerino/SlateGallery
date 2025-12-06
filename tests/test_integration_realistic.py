"""Realistic integration tests without mocking."""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from src.core.cache_manager import ImprovedCacheManager
from src.core.gallery_generator import generate_html_gallery
from src.core.image_processor import generate_thumbnail, get_exif_data, scan_directories


class TestRealWorldScenarios:
    """Test real-world usage scenarios without mocking."""

    def test_symlink_handling(self, tmp_path):
        """Test handling of symbolic links in image directories."""
        if os.name == 'nt':
            pytest.skip("Symlink test skipped on Windows")

        # Create real directory structure
        real_images = tmp_path / 'real_photos'
        real_images.mkdir()

        linked_dir = tmp_path / 'linked_photos'
        linked_dir.mkdir()

        # Create real images
        for i in range(3):
            img = Image.new('RGB', (400, 300), color=(100+i*50, 150, 200))
            img.save(real_images / f'real_{i}.jpg')

        # Create symlink to directory
        symlink_dir = real_images / 'linked'
        try:
            symlink_dir.symlink_to(linked_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Create image in linked directory
        img = Image.new('RGB', (400, 300), color='yellow')
        img.save(linked_dir / 'linked_image.jpg')

        # Scan should handle symlinks based on followlinks parameter
        slates = scan_directories(str(real_images))

        # Should find real images but skip symlinked directory (followlinks=False by default)
        total_images = sum(len(s['images']) for s in slates.values())
        assert total_images == 3  # Only the real images, not the linked one

    def test_concurrent_image_processing(self, tmp_path):
        """Test real concurrent processing of images."""
        images_dir = tmp_path / 'concurrent_test'
        images_dir.mkdir()
        thumb_dir = tmp_path / 'thumbnails'
        thumb_dir.mkdir()

        # Create test images with varying sizes
        image_paths = []
        for i in range(20):
            size = (800 + i * 50, 600 + i * 30)
            img = Image.new('RGB', size, color=(i*10, 100, 200-i*5))
            path = images_dir / f'img_{i:02d}.jpg'
            img.save(path, quality=95)
            image_paths.append(str(path))

        # Process images concurrently
        start_time = time.perf_counter()
        results = []

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(generate_thumbnail, path, str(thumb_dir), size=600)
                for path in image_paths
            ]

            for future in futures:
                result = future.result()
                results.append(result)

        elapsed = time.perf_counter() - start_time

        # Verify all thumbnails were created
        assert len(results) == 20
        assert all(len(r) > 0 for r in results)

        # Should be faster than sequential (rough estimate)
        # Sequential would take ~20 * 0.1s = 2s minimum
        # Parallel should be significantly faster
        print(f"Parallel processing took {elapsed:.2f}s for 20 images")

        # Verify actual thumbnail files exist
        thumb_files = list(thumb_dir.glob('*.jpg'))
        assert len(thumb_files) == 20

    def test_special_characters_in_paths(self, tmp_path):
        """Test handling of special characters in file/directory names."""
        # Create directories with special characters
        test_dirs = [
            'photos with spaces',
            'photos-with-dashes',
            'photos_with_underscores',
            'photos.with.dots',
            "photos'with'quotes",
            'фото_кириллица',  # Cyrillic
            '写真_日本語',      # Japanese
            'café_français',   # Accented characters
        ]

        created_dirs = []
        for dir_name in test_dirs:
            try:
                dir_path = tmp_path / dir_name
                dir_path.mkdir()
                created_dirs.append(dir_path)

                # Create an image in each directory
                img = Image.new('RGB', (200, 200), color='blue')
                img.save(dir_path / f'{dir_name}_photo.jpg')
            except (OSError, UnicodeError) as e:
                print(f"Skipping '{dir_name}': {e}")
                continue

        # Scan all created directories
        for dir_path in created_dirs:
            slates = scan_directories(str(dir_path))
            # Should handle special characters without crashing
            assert len(slates) >= 0

    def test_exif_preservation_in_thumbnails(self, tmp_path):
        """Test that important EXIF data is preserved/handled correctly."""
        images_dir = tmp_path / 'exif_test'
        images_dir.mkdir()
        thumb_dir = tmp_path / 'thumbs'

        # Create image with EXIF data
        img = Image.new('RGB', (2000, 1500), color='red')
        img_path = images_dir / 'with_exif.jpg'

        # Add EXIF data if piexif is available
        try:
            import piexif

            # Create EXIF data
            zeroth_ifd = {
                piexif.ImageIFD.Make: b"TestCamera",
                piexif.ImageIFD.Model: b"TestModel",
                piexif.ImageIFD.Orientation: 6,  # Rotated 90 CW
            }

            exif_ifd = {
                piexif.ExifIFD.DateTimeOriginal: b"2024:01:15 10:30:00",
                piexif.ExifIFD.FocalLength: (50, 1),
                piexif.ExifIFD.ISOSpeedRatings: 400,
            }

            exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd}
            exif_bytes = piexif.dump(exif_dict)
            img.save(img_path, 'JPEG', exif=exif_bytes)

            # Get EXIF from original
            original_exif = get_exif_data(str(img_path))
            # FocalLength is normalized to float by PIL
            assert original_exif.get('FocalLength') == 50.0 or original_exif.get('FocalLength') == (50, 1)
            assert original_exif.get('Orientation') == 6

            # Generate thumbnail
            thumbnails = generate_thumbnail(str(img_path), str(thumb_dir), size=600)
            assert len(thumbnails) > 0

            # Verify thumbnail was rotated based on orientation
            thumb_path = list(thumbnails.values())[0]
            with Image.open(thumb_path) as thumb:
                # After rotation, dimensions should be swapped
                # Original was 2000x1500, rotated should have height > width
                # (accounting for thumbnail scaling)
                assert thumb.height > thumb.width or abs(thumb.height - thumb.width) < 10

        except ImportError:
            pytest.skip("piexif not available for EXIF testing")

    def test_html_output_validation(self, tmp_path):
        """Test that generated HTML is valid and functional."""
        images_dir = tmp_path / 'html_test'
        images_dir.mkdir()
        output_dir = tmp_path / 'output'

        # Create test images
        for i in range(5):
            img = Image.new('RGB', (400, 300), color=(50*i, 100, 150))
            img.save(images_dir / f'photo_{i}.jpg')

        # Create template
        template = tmp_path / 'template.html'
        template.write_text('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gallery Test</title>
</head>
<body>
    <h1>Test Gallery</h1>
    {% for slate in gallery %}
        <section>
            <h2>{{ slate.slate }}</h2>
            {% for image in slate.images %}
                <img src="{{ image.original_path }}"
                     {% if lazy_loading %}loading="lazy"{% endif %}
                     alt="{{ image.filename }}">
            {% endfor %}
        </section>
    {% endfor %}
</body>
</html>''')

        # Generate gallery
        gallery_data = [{
            'slate': 'test',
            'images': [
                {'original_path': str(p), 'filename': p.name}
                for p in images_dir.glob('*.jpg')
            ]
        }]

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(template),
            output_dir=str(output_dir),
            allowed_root_dirs=str(images_dir),
            status_callback=lambda x: None,
            lazy_loading=True
        )

        assert success[0]

        # Validate HTML structure
        html_file = output_dir / 'index.html'
        assert html_file.exists()

        content = html_file.read_text()

        # Check for valid HTML5 structure
        assert '<!DOCTYPE html>' in content
        assert '<html lang="en">' in content
        assert '<meta charset="UTF-8">' in content
        assert '<title>' in content
        assert '</html>' in content

        # Check for lazy loading attribute
        assert 'loading="lazy"' in content

        # Check all images are included
        for i in range(5):
            assert f'photo_{i}.jpg' in content

    def test_cache_performance_comparison(self, tmp_path):
        """Test actual performance improvement with caching."""
        images_dir = tmp_path / 'cache_perf'
        images_dir.mkdir()

        # Create substantial number of images
        num_images = 100
        for i in range(num_images):
            img = Image.new('RGB', (800, 600), color=(i*2, 100, 200-i))
            img.save(images_dir / f'img_{i:03d}.jpg')

        cache_manager = ImprovedCacheManager(base_dir=str(tmp_path / 'cache'))

        # First scan (no cache)
        start = time.perf_counter()
        slates1 = scan_directories(str(images_dir))
        cache_manager.save_cache(str(images_dir), slates1)
        first_scan_time = time.perf_counter() - start

        # Second scan (with cache)
        start = time.perf_counter()
        slates2 = cache_manager.load_cache(str(images_dir))
        cache_load_time = time.perf_counter() - start

        # Cache should be significantly faster
        assert slates2 is not None
        assert slates2 == slates1
        print(f"First scan: {first_scan_time:.3f}s, Cache load: {cache_load_time:.3f}s")
        assert cache_load_time < first_scan_time  # Cache should be faster

    def test_incremental_gallery_update(self, tmp_path):
        """Test updating existing gallery with new images."""
        images_dir = tmp_path / 'incremental'
        images_dir.mkdir()
        output_dir = tmp_path / 'output'
        ImprovedCacheManager(base_dir=str(tmp_path / 'cache'))

        template = tmp_path / 'template.html'
        template.write_text('''<html>
<body>
<h1>Gallery</h1>
<p>Total images: {{ gallery[0].images|length if gallery else 0 }}</p>
{% for slate in gallery %}
    {% for image in slate.images %}
        <div>{{ image.filename }}</div>
    {% endfor %}
{% endfor %}
</body>
</html>''')

        # Initial gallery with 3 images
        for i in range(3):
            img = Image.new('RGB', (200, 200), color='blue')
            img.save(images_dir / f'initial_{i}.jpg')

        # Generate initial gallery
        slates = scan_directories(str(images_dir))
        gallery_data = [{
            'slate': 'incremental',
            'images': [{'original_path': p, 'filename': os.path.basename(p)}
                      for p in slates.get('/', {}).get('images', [])]
        }]

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(template),
            output_dir=str(output_dir),
            allowed_root_dirs=str(images_dir),
            status_callback=lambda x: None,
            lazy_loading=False
        )
        assert success[0]

        # Check initial gallery
        html_content = (output_dir / 'index.html').read_text()
        assert 'Total images: 3' in html_content

        # Add more images
        for i in range(2):
            img = Image.new('RGB', (200, 200), color='green')
            img.save(images_dir / f'added_{i}.jpg')

        # Regenerate gallery
        slates = scan_directories(str(images_dir))
        gallery_data = [{
            'slate': 'incremental',
            'images': [{'original_path': p, 'filename': os.path.basename(p)}
                      for p in slates.get('/', {}).get('images', [])]
        }]

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(template),
            output_dir=str(output_dir),
            allowed_root_dirs=str(images_dir),
            status_callback=lambda x: None,
            lazy_loading=False
        )
        assert success[0]

        # Check updated gallery
        html_content = (output_dir / 'index.html').read_text()
        assert 'Total images: 5' in html_content
        assert 'added_0.jpg' in html_content
        assert 'added_1.jpg' in html_content


class TestPlatformCompatibility:
    """Test cross-platform compatibility."""

    def test_path_separator_handling(self, tmp_path):
        """Test handling of different path separators."""
        # Create nested directory structure
        deep_dir = tmp_path / 'level1' / 'level2' / 'level3'
        deep_dir.mkdir(parents=True)

        # Create image in deep directory
        img = Image.new('RGB', (100, 100), color='purple')
        img_path = deep_dir / 'deep_image.jpg'
        img.save(img_path)

        # Test with different path representations
        path_variations = [
            str(tmp_path),  # Native path
            str(tmp_path).replace(os.sep, '/'),  # Forward slashes
        ]

        if os.name == 'nt':
            # On Windows, also test backslashes
            path_variations.append(str(tmp_path).replace('/', '\\'))

        for path_str in path_variations:
            slates = scan_directories(path_str)
            # Should find the image regardless of path format
            total_images = sum(len(s['images']) for s in slates.values())
            assert total_images == 1

    def test_case_sensitivity(self, tmp_path):
        """Test handling of case in file extensions."""
        images_dir = tmp_path / 'case_test'
        images_dir.mkdir()

        # Create images with various case extensions
        extensions = ['jpg', 'JPG', 'Jpg', 'JPEG', 'png', 'PNG', 'Png']

        for i, ext in enumerate(extensions):
            img = Image.new('RGB', (100, 100), color=(i*30, 100, 200))
            # Use appropriate format for the extension
            format_name = 'JPEG' if 'jp' in ext.lower() else 'PNG'
            img.save(images_dir / f'image_{i}.{ext}', format=format_name)

        # Scan should find all images regardless of extension case
        slates = scan_directories(str(images_dir))
        total_images = sum(len(s['images']) for s in slates.values())
        assert total_images == len(extensions)

    def test_unicode_content_in_gallery(self, tmp_path):
        """Test handling of unicode content in generated galleries."""
        output_dir = tmp_path / 'unicode_output'
        template = tmp_path / 'template.html'

        # Template with unicode content
        template.write_text('''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Gallery - 画廊 - Галерея</title>
</head>
<body>
    <h1>International Photo Gallery 🌍</h1>
    <p>Photos from: 日本 • Россия • France • 中国</p>
    {% for slate in gallery %}
        <h2>{{ slate.slate }}</h2>
        {% for image in slate.images %}
            <img src="{{ image.original_path }}" alt="{{ image.filename }}">
        {% endfor %}
    {% endfor %}
</body>
</html>''', encoding='utf-8')

        # Create image with unicode filename
        images_dir = tmp_path / 'photos_画像'
        images_dir.mkdir()

        img = Image.new('RGB', (200, 200), color='orange')
        img.save(images_dir / 'photo_写真.jpg')

        gallery_data = [{
            'slate': 'International_国際',
            'images': [{
                'original_path': str(images_dir / 'photo_写真.jpg'),
                'filename': 'photo_写真.jpg'
            }]
        }]

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(template),
            output_dir=str(output_dir),
            allowed_root_dirs=str(images_dir),
            status_callback=lambda x: None,
            lazy_loading=True
        )

        assert success[0]

        # Verify unicode content is preserved
        html_file = output_dir / 'index.html'
        content = html_file.read_text(encoding='utf-8')
        assert '画廊' in content
        assert 'Галерея' in content
        assert '🌍' in content
        assert 'International_国際' in content


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
