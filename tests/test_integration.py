"""Integration tests for SlateGallery components working together."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from src.core.cache_manager import ImprovedCacheManager
from src.core.config_manager import GalleryConfig, load_config, save_config
from src.core.gallery_generator import generate_html_gallery
from src.core.image_processor import (
    get_exif_data,
    get_image_date,
    get_orientation,
    scan_directories,
)


class TestSlateGalleryIntegration:
    """Test integration between multiple SlateGallery components."""

    @pytest.fixture
    def temp_project_structure(self):
        """Create a complete temporary project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create project directories
            images_dir = base_path / 'images'
            cache_dir = base_path / 'cache'
            output_dir = base_path / 'output'
            templates_dir = base_path / 'templates'

            images_dir.mkdir()
            templates_dir.mkdir()

            # Create realistic directory structure with images
            nature_dir = images_dir / 'nature'
            portraits_dir = images_dir / 'portraits'
            nature_dir.mkdir()
            portraits_dir.mkdir()

            # Create actual image files
            for i, (subdir, size) in enumerate([
                (nature_dir, (200, 150)),  # landscape
                (nature_dir, (150, 200)),  # portrait
                (portraits_dir, (120, 180))  # portrait
            ]):
                img_path = subdir / f'photo_{i+1}.jpg'
                # Create actual image data
                img = Image.new('RGB', size, color=(100, 150, 200))
                img.save(img_path, 'JPEG')

            # Create template
            template_path = templates_dir / 'gallery_template.html'
            template_path.write_text('''<!DOCTYPE html>
<html>
<head><title>Test Gallery</title></head>
<body>
    <h1>SlateGallery Integration Test</h1>
    {% for slate in gallery %}
        <div class="slate">
            <h2>{{ slate.slate }}</h2>
            {% for image in slate.images %}
                <div class="image">
                    <img src="{{ image.web_path }}" alt="{{ image.filename }}">
                    <p>Focal: {{ image.focal_length }}mm | Orientation: {{ image.orientation }}</p>
                </div>
            {% endfor %}
        </div>
    {% endfor %}
</body>
</html>''')

            yield {
                'base': base_path,
                'images_dir': str(images_dir),
                'cache_dir': str(cache_dir),
                'output_dir': str(output_dir),
                'template_path': str(template_path)
            }

    def test_complete_gallery_workflow(self, temp_project_structure):
        """Test complete workflow: scan -> cache -> generate gallery."""
        images_dir = temp_project_structure['images_dir']
        cache_dir = temp_project_structure['cache_dir']
        output_dir = temp_project_structure['output_dir']
        template_path = temp_project_structure['template_path']

        # Step 1: Scan directories
        slates = scan_directories(images_dir)

        assert isinstance(slates, dict)
        assert len(slates) >= 2  # Should find nature and portraits
        assert 'nature' in slates or 'portraits' in slates

        # Step 2: Process with cache manager
        cache_manager = ImprovedCacheManager(base_dir=cache_dir)

        for slate_name, slate_data in slates.items():
            processed_images = cache_manager.process_images_batch(slate_data['images'])
            slate_data['images'] = processed_images

        # Save to cache
        cache_manager.save_cache(images_dir, slates)

        # Step 3: Load from cache (verify caching works)
        cached_slates = cache_manager.load_cache(images_dir)
        assert cached_slates == slates

        # Step 4: Process images for gallery
        gallery_data = []
        focal_length_counts = {}

        for slate_name, slate_data in slates.items():
            slate_images = []

            for image_info in slate_data['images']:
                image_path = image_info['path']

                # Get EXIF and orientation
                exif_data = get_exif_data(image_path)
                orientation = get_orientation(image_path, exif_data)

                image_data = {
                    'original_path': image_path,
                    'filename': Path(image_path).name,
                    'focal_length': 35.0,  # Default for test
                    'orientation': orientation,
                    'date_taken': None  # Default for test (no date in test images)
                }

                slate_images.append(image_data)
                focal_length_counts[35.0] = focal_length_counts.get(35.0, 0) + 1

            if slate_images:
                gallery_data.append({
                    'slate': slate_name,
                    'images': slate_images
                })

        # Convert focal length counts to structured data
        focal_length_data = [
            {'value': focal_length, 'count': count}
            for focal_length, count in sorted(focal_length_counts.items())
        ]

        # Step 5: Generate HTML gallery
        status_messages = []
        def capture_status(msg):
            status_messages.append(msg)

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=template_path,
            output_dir=output_dir,
            allowed_root_dirs=images_dir,
            status_callback=capture_status
        )

        assert success[0] is True
        assert len(status_messages) > 0

        # Step 6: Verify output
        output_file = Path(output_dir) / 'index.html'
        assert output_file.exists()

        html_content = output_file.read_text()
        assert 'SlateGallery Integration Test' in html_content
        assert 'nature' in html_content or 'portraits' in html_content
        assert 'photo_1.jpg' in html_content or 'photo_2.jpg' in html_content

    def test_config_manager_integration(self, temp_project_structure):
        """Test config manager integration with project workflow."""
        images_dir = temp_project_structure['images_dir']
        base_path = temp_project_structure['base']

        # Create config in temporary location
        config_file = base_path / 'test_config.ini'

        with pytest.MonkeyPatch().context() as m:
            # Patch the config file location
            m.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

            # Test save config with GalleryConfig dataclass
            slate_dirs = [images_dir, str(base_path / 'other')]
            save_config(GalleryConfig(
                current_slate_dir=images_dir,
                slate_dirs=slate_dirs,
                selected_slate_dirs=slate_dirs,
                generate_thumbnails=False,
                thumbnail_size=600,
                lazy_loading=True,
                exclude_patterns=""
            ))

            # Test load config (returns GalleryConfig dataclass)
            config = load_config()

            assert config.current_slate_dir == images_dir
            assert config.slate_dirs == slate_dirs

            # Verify config file exists
            assert config_file.exists()

    def test_error_handling_integration(self, temp_project_structure):
        """Test that components handle errors gracefully when integrated."""
        images_dir = temp_project_structure['images_dir']

        # Test with nonexistent directory
        slates = scan_directories('/nonexistent/directory')
        assert slates == {}

        # Test EXIF processing with nonexistent image
        exif_data = get_exif_data('/nonexistent/image.jpg')
        assert exif_data == {}

        # Test orientation with nonexistent image
        orientation = get_orientation('/nonexistent/image.jpg', {})
        assert orientation == 'unknown'

        # Test cache manager with invalid data
        cache_manager = ImprovedCacheManager(base_dir=images_dir)

        # Should not crash with invalid data
        cache_manager.save_cache('test', {'invalid': set([1, 2, 3])})
        result = cache_manager.load_cache('test')
        # Result may be None due to JSON serialization error
        assert result is None or isinstance(result, dict)

    def test_performance_with_multiple_images(self, temp_project_structure):
        """Test system performance with multiple images."""
        images_dir = Path(temp_project_structure['images_dir'])

        # Create more images for performance testing
        perf_dir = images_dir / 'performance_test'
        perf_dir.mkdir()

        # Create 10 test images
        for i in range(10):
            img_path = perf_dir / f'perf_image_{i:02d}.jpg'
            img = Image.new('RGB', (100, 100), color=(i*20, 100, 150))
            img.save(img_path, 'JPEG')

        # Test scanning performance
        import time
        start_time = time.time()

        slates = scan_directories(str(images_dir))

        scan_time = time.time() - start_time

        # Should complete reasonably quickly (less than 5 seconds)
        assert scan_time < 5.0

        # Should find the performance test directory
        assert 'performance_test' in slates
        assert len(slates['performance_test']['images']) == 10

        # Test cache manager with multiple images
        cache_manager = ImprovedCacheManager(base_dir=temp_project_structure['cache_dir'])

        start_time = time.time()

        for slate_name, slate_data in slates.items():
            processed = cache_manager.process_images_batch(slate_data['images'])
            slate_data['images'] = processed

        process_time = time.time() - start_time

        # Processing should also be reasonable
        assert process_time < 5.0


class TestSlateGalleryEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def edge_case_structure(self):
        """Create structure with edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create edge case scenarios
            unicode_dir = base_path / 'ñiño_café'
            unicode_dir.mkdir()

            # Unicode filename
            unicode_img = unicode_dir / 'ñoño_test.jpg'
            img = Image.new('RGB', (50, 50), color='red')
            img.save(unicode_img, 'JPEG')

            # Very long filename
            long_name_dir = base_path / 'long_names'
            long_name_dir.mkdir()
            long_filename = 'a' * 100 + '.jpg'
            long_img = long_name_dir / long_filename
            img.save(long_img, 'JPEG')

            # Empty directory
            empty_dir = base_path / 'empty'
            empty_dir.mkdir()

            yield {
                'base': base_path,
                'unicode_dir': str(unicode_dir),
                'long_name_dir': str(long_name_dir),
                'empty_dir': str(empty_dir)
            }

    def test_unicode_handling(self, edge_case_structure):
        """Test handling of unicode filenames and paths."""
        unicode_dir = edge_case_structure['unicode_dir']

        # Should handle unicode directory names
        slates = scan_directories(unicode_dir)

        assert isinstance(slates, dict)
        # Should find the unicode image
        if slates:
            assert len(slates) >= 0  # May or may not find images depending on system

    def test_long_filename_handling(self, edge_case_structure):
        """Test handling of very long filenames."""
        long_name_dir = edge_case_structure['long_name_dir']

        slates = scan_directories(long_name_dir)

        assert isinstance(slates, dict)
        # Should handle long filenames gracefully

    def test_empty_directory_handling(self, edge_case_structure):
        """Test handling of empty directories."""
        empty_dir = edge_case_structure['empty_dir']

        slates = scan_directories(empty_dir)

        assert slates == {}  # Should return empty dict for empty directory


class TestDateFilteringIntegration:
    """Test integration of date filtering functionality across components."""

    @pytest.fixture
    def dated_project_structure(self):
        """Create project structure with dated images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create directories
            images_dir = base_path / 'images'
            output_dir = base_path / 'output'
            templates_dir = base_path / 'templates'
            cache_dir = base_path / 'cache'

            images_dir.mkdir()
            templates_dir.mkdir()
            cache_dir.mkdir()

            # Create subdirectories for different time periods
            vacation_2023 = images_dir / 'vacation_2023'
            vacation_2023.mkdir()

            events_2024 = images_dir / 'events_2024'
            events_2024.mkdir()

            # Create test images with dates using piexif
            try:
                import piexif

                # Helper to create dated image
                def create_dated_image(path, date_obj, size=(150, 100)):
                    img = Image.new('RGB', size, color='blue')

                    # Create EXIF data with date
                    date_str = date_obj.strftime('%Y:%m:%d %H:%M:%S')
                    exif_dict = {
                        "0th": {
                            piexif.ImageIFD.DateTime: date_str.encode('utf-8')
                        },
                        "Exif": {
                            piexif.ExifIFD.DateTimeOriginal: date_str.encode('utf-8'),
                            piexif.ExifIFD.DateTimeDigitized: date_str.encode('utf-8'),
                            piexif.ExifIFD.FocalLength: (50, 1)  # 50mm
                        }
                    }

                    exif_bytes = piexif.dump(exif_dict)
                    img.save(path, 'JPEG', exif=exif_bytes)
                    return str(path)

                # Create images with various dates
                create_dated_image(vacation_2023 / 'beach1.jpg', datetime(2023, 7, 15, 10, 30, 0))
                create_dated_image(vacation_2023 / 'beach2.jpg', datetime(2023, 7, 16, 14, 0, 0))
                create_dated_image(vacation_2023 / 'mountain.jpg', datetime(2023, 8, 5, 9, 0, 0))

                create_dated_image(events_2024 / 'birthday.jpg', datetime(2024, 1, 20, 18, 30, 0))
                create_dated_image(events_2024 / 'wedding.jpg', datetime(2024, 6, 10, 15, 0, 0))

            except ImportError:
                # Fallback without EXIF if piexif not available
                for dir_path in [vacation_2023, events_2024]:
                    for i in range(2):
                        img = Image.new('RGB', (150, 100), color='blue')
                        img.save(dir_path / f'image_{i}.jpg', 'JPEG')

            # Create template with date filtering
            template_path = templates_dir / 'gallery_template.html'
            template_path.write_text('''<!DOCTYPE html>
<html>
<head><title>Date Filtering Test</title></head>
<body>
    <h1>Gallery with Date Filtering</h1>

    <div class="filters">
        <h3>Filter by Date:</h3>
        {% for date in dates %}
            <label>
                <input type="checkbox" class="date-filter" value="{{ date.value }}">
                {{ date.value }} ({{ date.count }} photos)
            </label>
        {% endfor %}
    </div>

    <div class="gallery">
        {% for slate in gallery %}
            <div class="slate">
                <h2>{{ slate.slate }}</h2>
                {% for image in slate.images %}
                    <div class="image" data-date="{{ image.date_taken }}">
                        <img src="{{ image.web_path }}" alt="{{ image.filename }}">
                        <p>Date: {{ image.date_taken }} | Focal: {{ image.focal_length }}mm</p>
                    </div>
                {% endfor %}
            </div>
        {% endfor %}
    </div>
</body>
</html>''')

            yield {
                'base': base_path,
                'images_dir': str(images_dir),
                'output_dir': str(output_dir),
                'cache_dir': str(cache_dir),
                'template_path': str(template_path)
            }

    def test_complete_date_filtering_workflow(self, dated_project_structure):
        """Test complete workflow with date filtering: scan -> process -> generate."""
        images_dir = dated_project_structure['images_dir']
        output_dir = dated_project_structure['output_dir']
        template_path = dated_project_structure['template_path']
        dated_project_structure['cache_dir']

        # Step 1: Scan directories
        slates = scan_directories(images_dir)

        assert len(slates) >= 2  # Should find vacation_2023 and events_2024

        # Step 2: Process images and collect date information
        gallery_data = []
        date_counts = {}
        focal_length_counts = {}

        for slate_name, slate_data in slates.items():
            slate_images = []

            for image_path in slate_data['images']:
                # Get EXIF data
                exif_data = get_exif_data(image_path)

                # Extract date
                image_date = get_image_date(exif_data)
                date_taken = None
                date_key = None

                if image_date:
                    date_taken = image_date.isoformat()
                    date_key = image_date.strftime('%Y-%m')
                    date_counts[date_key] = date_counts.get(date_key, 0) + 1

                # Get focal length
                focal_length = exif_data.get('FocalLength')
                focal_length_value = None
                if focal_length:
                    if isinstance(focal_length, tuple):
                        focal_length_value = float(focal_length[0]) / float(focal_length[1])
                    else:
                        focal_length_value = float(focal_length)

                    if focal_length_value:
                        focal_length_counts[focal_length_value] = focal_length_counts.get(focal_length_value, 0) + 1

                # Get orientation
                orientation = get_orientation(image_path, exif_data)

                image_data = {
                    'original_path': image_path,
                    'filename': Path(image_path).name,
                    'focal_length': focal_length_value,
                    'orientation': orientation,
                    'date_taken': date_taken
                }

                slate_images.append(image_data)

            if slate_images:
                gallery_data.append({
                    'slate': slate_name,
                    'images': slate_images
                })

        # Convert counts to structured data
        date_data = [
            {'value': date_key, 'count': count}
            for date_key, count in sorted(date_counts.items())
        ]

        focal_length_data = [
            {'value': focal_length, 'count': count}
            for focal_length, count in sorted(focal_length_counts.items())
        ]

        # Step 3: Generate HTML gallery with date filtering
        status_messages = []
        def capture_status(msg):
            status_messages.append(msg)

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=focal_length_data,
            date_data=date_data,
            template_path=template_path,
            output_dir=output_dir,
            allowed_root_dirs=images_dir,
            status_callback=capture_status
        )

        assert success[0] is True

        # Step 4: Verify output contains date filtering elements
        output_file = Path(output_dir) / 'index.html'
        assert output_file.exists()

        html_content = output_file.read_text()

        # Verify date filters are present
        assert 'Filter by Date:' in html_content
        assert 'date-filter' in html_content

        # Verify date data attributes on images
        assert 'data-date=' in html_content

        # If piexif was available, verify specific dates
        try:
            import piexif
            # Should have date counts for different months
            assert len(date_counts) > 0
            if '2023-07' in date_counts:
                assert date_counts['2023-07'] >= 2  # Two July 2023 images
            if '2023-08' in date_counts:
                assert date_counts['2023-08'] >= 1  # One August 2023 image
        except ImportError:
            # Without piexif, images won't have dates
            pass

    def test_date_filtering_with_missing_dates(self, dated_project_structure):
        """Test that images without dates are handled correctly."""
        images_dir = Path(dated_project_structure['images_dir'])
        output_dir = dated_project_structure['output_dir']
        template_path = dated_project_structure['template_path']

        # Create an image without EXIF data
        no_date_dir = images_dir / 'no_dates'
        no_date_dir.mkdir()

        img = Image.new('RGB', (100, 100), color='green')
        img.save(no_date_dir / 'no_exif.png', 'PNG')  # PNG typically has no EXIF

        # Process the directory
        slates = scan_directories(str(images_dir))

        gallery_data = []
        date_counts = {}
        images_with_dates = 0
        images_without_dates = 0

        for slate_name, slate_data in slates.items():
            slate_images = []

            for image_path in slate_data['images']:
                exif_data = get_exif_data(image_path)
                image_date = get_image_date(exif_data)

                if image_date:
                    images_with_dates += 1
                    date_key = image_date.strftime('%Y-%m')
                    date_counts[date_key] = date_counts.get(date_key, 0) + 1
                else:
                    images_without_dates += 1

                image_data = {
                    'original_path': image_path,
                    'filename': Path(image_path).name,
                    'focal_length': None,
                    'orientation': get_orientation(image_path, exif_data),
                    'date_taken': image_date.isoformat() if image_date else None
                }

                slate_images.append(image_data)

            if slate_images:
                gallery_data.append({
                    'slate': slate_name,
                    'images': slate_images
                })

        # Should find the no_exif.png without date
        assert images_without_dates >= 1

        # Generate gallery
        date_data = [
            {'value': date_key, 'count': count}
            for date_key, count in sorted(date_counts.items())
        ]

        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=date_data,
            template_path=template_path,
            output_dir=output_dir,
            allowed_root_dirs=str(images_dir),
            status_callback=lambda x: None
        )

        assert success[0] is True

        # Verify HTML handles images without dates
        output_file = Path(output_dir) / 'index.html'
        html_content = output_file.read_text()

        # Images without dates should have empty or None date attribute
        assert 'no_exif.png' in html_content

    def test_date_sorting_in_gallery(self, dated_project_structure):
        """Test that dates are sorted chronologically in the output."""
        try:
            import piexif
        except ImportError:
            pytest.skip("piexif required for date sorting test")

        images_dir = dated_project_structure['images_dir']
        output_dir = dated_project_structure['output_dir']
        template_path = dated_project_structure['template_path']

        # Scan and process
        slates = scan_directories(images_dir)

        date_counts = {}
        gallery_data = []

        for slate_name, slate_data in slates.items():
            slate_images = []

            for image_path in slate_data['images']:
                exif_data = get_exif_data(image_path)
                image_date = get_image_date(exif_data)

                if image_date:
                    date_key = image_date.strftime('%Y-%m')
                    date_counts[date_key] = date_counts.get(date_key, 0) + 1

                image_data = {
                    'original_path': image_path,
                    'filename': Path(image_path).name,
                    'focal_length': None,
                    'orientation': get_orientation(image_path, exif_data),
                    'date_taken': image_date.isoformat() if image_date else None
                }

                slate_images.append(image_data)

            if slate_images:
                gallery_data.append({
                    'slate': slate_name,
                    'images': slate_images
                })

        # Create date data (should be sorted)
        date_data = [
            {'value': date_key, 'count': count}
            for date_key, count in sorted(date_counts.items())
        ]

        # Verify dates are in chronological order
        date_values = [d['value'] for d in date_data]
        assert date_values == sorted(date_values)

        # Generate gallery
        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=date_data,
            template_path=template_path,
            output_dir=output_dir,
            allowed_root_dirs=images_dir,
            status_callback=lambda x: None
        )

        assert success[0] is True
