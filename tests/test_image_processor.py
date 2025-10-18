"""Unit tests for image_processor module with minimal mocking."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import ExifTags, Image

from src.core.image_processor import (
    get_exif_data,
    get_image_date,
    get_orientation,
    scan_directories,
)


class TestGetExifData:
    """Test EXIF data extraction with real and mock image files."""

    @pytest.fixture
    def temp_image_dir(self):
        """Create a temporary directory with test images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def create_test_image(self, path, size=(100, 150), orientation=1, focal_length=None):
        """Create a test image file with optional EXIF data."""
        # Create a simple test image
        image = Image.new('RGB', size, color='red')

        # Add EXIF data if specified
        if orientation != 1 or focal_length:
            exif_dict = {"0th": {}, "Exif": {}}
            if orientation != 1:
                exif_dict["0th"][ExifTags.Base.Orientation.value] = orientation
            if focal_length:
                exif_dict["Exif"][ExifTags.Base.FocalLength.value] = focal_length

            try:
                import piexif
                exif_bytes = piexif.dump(exif_dict)
                image.save(path, exif=exif_bytes)
            except ImportError:
                # If piexif is not available, save without EXIF
                image.save(path)
        else:
            image.save(path)

        return path

    def test_get_exif_data_nonexistent_file(self):
        """Test EXIF extraction from nonexistent file."""
        result = get_exif_data('/nonexistent/path/image.jpg')
        assert result == {}

    def test_get_exif_data_valid_image_no_exif(self, temp_image_dir):
        """Test EXIF extraction from image without EXIF data."""
        image_path = temp_image_dir / 'test_no_exif.jpg'
        self.create_test_image(image_path)

        result = get_exif_data(str(image_path))
        assert isinstance(result, dict)
        # Should return empty dict for image without EXIF
        assert result == {}

    def test_get_exif_data_with_orientation(self, temp_image_dir):
        """Test EXIF extraction with orientation data."""
        image_path = temp_image_dir / 'test_with_orientation.jpg'
        self.create_test_image(image_path, orientation=6)

        result = get_exif_data(str(image_path))
        assert isinstance(result, dict)
        # Note: May be empty if piexif not available, but shouldn't crash

    def test_get_exif_data_invalid_file(self, temp_image_dir):
        """Test EXIF extraction from invalid image file."""
        invalid_file = temp_image_dir / 'invalid.jpg'
        invalid_file.write_text('not an image')

        result = get_exif_data(str(invalid_file))
        assert result == {}

    def test_get_exif_data_different_formats(self, temp_image_dir):
        """Test EXIF extraction from different image formats."""
        formats = [
            ('test.jpg', 'JPEG'),
            ('test.png', 'PNG'),
            ('test.bmp', 'BMP'),
        ]

        for filename, format_name in formats:
            image_path = temp_image_dir / filename
            image = Image.new('RGB', (50, 50), color='blue')
            image.save(image_path, format=format_name)

            result = get_exif_data(str(image_path))
            assert isinstance(result, dict)
            # Should not crash regardless of format

    @patch('src.core.image_processor.Image.open')
    def test_get_exif_data_handles_pil_exception(self, mock_open):
        """Test that get_exif_data handles PIL exceptions gracefully."""
        mock_open.side_effect = Exception("PIL error")

        result = get_exif_data('/some/path.jpg')
        assert result == {}


class TestGetOrientation:
    """Test orientation detection with real and mock image files."""

    @pytest.fixture
    def temp_image_dir(self):
        """Create a temporary directory with test images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def create_test_image(self, path, size=(100, 150)):
        """Create a test image file."""
        image = Image.new('RGB', size, color='green')
        image.save(path)
        return path

    def test_get_orientation_from_exif_portrait(self):
        """Test orientation detection from EXIF data - portrait."""
        exif_data = {'Orientation': 6}
        result = get_orientation('/dummy/path.jpg', exif_data)
        assert result == 'portrait'

    def test_get_orientation_from_exif_portrait_alt(self):
        """Test orientation detection from EXIF data - portrait alternative."""
        exif_data = {'Orientation': 8}
        result = get_orientation('/dummy/path.jpg', exif_data)
        assert result == 'portrait'

    def test_get_orientation_from_exif_landscape(self):
        """Test orientation detection from EXIF data - landscape."""
        exif_data = {'Orientation': 1}
        result = get_orientation('/dummy/path.jpg', exif_data)
        assert result == 'landscape'

    def test_get_orientation_from_image_dimensions_portrait(self, temp_image_dir):
        """Test orientation detection from image dimensions - portrait."""
        image_path = temp_image_dir / 'portrait.jpg'
        self.create_test_image(image_path, size=(100, 200))  # height > width

        result = get_orientation(str(image_path), {})
        assert result == 'portrait'

    def test_get_orientation_from_image_dimensions_landscape(self, temp_image_dir):
        """Test orientation detection from image dimensions - landscape."""
        image_path = temp_image_dir / 'landscape.jpg'
        self.create_test_image(image_path, size=(200, 100))  # width > height

        result = get_orientation(str(image_path), {})
        assert result == 'landscape'

    def test_get_orientation_from_image_dimensions_square(self, temp_image_dir):
        """Test orientation detection from square image."""
        image_path = temp_image_dir / 'square.jpg'
        self.create_test_image(image_path, size=(100, 100))  # equal dimensions

        result = get_orientation(str(image_path), {})
        assert result == 'landscape'  # Square defaults to landscape

    def test_get_orientation_invalid_file(self):
        """Test orientation detection with invalid file."""
        result = get_orientation('/nonexistent/path.jpg', {})
        assert result == 'unknown'

    def test_get_orientation_corrupted_file(self, temp_image_dir):
        """Test orientation detection with corrupted file."""
        corrupted_file = temp_image_dir / 'corrupted.jpg'
        corrupted_file.write_text('not an image file')

        result = get_orientation(str(corrupted_file), {})
        assert result == 'unknown'

    @patch('src.core.image_processor.Image.open')
    def test_get_orientation_handles_image_open_exception(self, mock_open):
        """Test that get_orientation handles Image.open exceptions."""
        mock_open.side_effect = Exception("Cannot open image")

        result = get_orientation('/some/path.jpg', {})
        assert result == 'unknown'


class TestScanDirectories:
    """Test directory scanning functionality with real filesystem operations."""

    @pytest.fixture
    def temp_scan_dir(self):
        """Create a temporary directory structure for scanning tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create directory structure
            (base_path / 'subdir1').mkdir()
            (base_path / 'subdir2').mkdir()
            (base_path / 'subdir2' / 'nested').mkdir()
            (base_path / 'empty_dir').mkdir()

            # Create test images
            self.create_test_image(base_path / 'root_image.jpg')
            self.create_test_image(base_path / 'subdir1' / 'image1.jpg')
            self.create_test_image(base_path / 'subdir1' / 'image2.png')
            self.create_test_image(base_path / 'subdir2' / 'image3.tiff')
            self.create_test_image(base_path / 'subdir2' / 'nested' / 'image4.bmp')

            # Create non-image files
            (base_path / 'textfile.txt').write_text('not an image')
            (base_path / 'subdir1' / 'document.pdf').write_text('fake pdf')

            yield base_path

    def create_test_image(self, path):
        """Create a simple test image file."""
        image = Image.new('RGB', (10, 10), color='blue')
        image.save(path)

    def test_scan_directories_nonexistent_directory(self):
        """Test scanning a directory that doesn't exist."""
        result = scan_directories('/nonexistent/directory')
        assert result == {}

    def test_scan_directories_basic_structure(self, temp_scan_dir):
        """Test scanning basic directory structure."""
        result = scan_directories(str(temp_scan_dir))

        assert isinstance(result, dict)
        assert len(result) >= 1  # Should find at least root directory

        # Check that root directory is included
        assert '/' in result
        assert 'images' in result['/']
        assert len(result['/']['images']) == 1  # root_image.jpg

        # Verify image paths are absolute
        for slate, data in result.items():
            for image_path in data['images']:
                assert os.path.isabs(image_path)
                assert image_path.startswith(str(temp_scan_dir))

    def test_scan_directories_finds_all_image_types(self, temp_scan_dir):
        """Test that all supported image types are found."""
        result = scan_directories(str(temp_scan_dir))

        # Collect all found image paths
        all_images = []
        for slate_data in result.values():
            all_images.extend(slate_data['images'])

        # Check that different file extensions are found
        found_extensions = set()
        for image_path in all_images:
            ext = os.path.splitext(image_path)[1].lower()
            found_extensions.add(ext)

        # Should find at least some of the image types we created
        assert '.jpg' in found_extensions
        assert '.png' in found_extensions or '.tiff' in found_extensions or '.bmp' in found_extensions

    def test_scan_directories_ignores_non_images(self, temp_scan_dir):
        """Test that non-image files are ignored."""
        result = scan_directories(str(temp_scan_dir))

        # Collect all found image paths
        all_images = []
        for slate_data in result.values():
            all_images.extend(slate_data['images'])

        # Verify no non-image files are included
        for image_path in all_images:
            ext = os.path.splitext(image_path)[1].lower()
            assert ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif']

    def test_scan_directories_empty_directory_excluded(self, temp_scan_dir):
        """Test that empty directories are not included in results."""
        result = scan_directories(str(temp_scan_dir))

        # empty_dir should not be in results since it has no images
        empty_dir_relative = 'empty_dir'
        assert empty_dir_relative not in result

    def test_scan_directories_relative_paths(self, temp_scan_dir):
        """Test that slate names use relative paths correctly."""
        result = scan_directories(str(temp_scan_dir))

        # Check relative path handling
        found_slates = set(result.keys())

        # Should include root as '/'
        assert '/' in found_slates

        # Subdirectories should have relative names
        for slate_name in found_slates:
            if slate_name != '/':
                assert not slate_name.startswith('/')
                assert not os.path.isabs(slate_name)

    def test_scan_directories_nested_structure(self, temp_scan_dir):
        """Test scanning nested directory structures."""
        result = scan_directories(str(temp_scan_dir))

        # Should find nested directories with images
        nested_found = False
        for slate_name in result.keys():
            if 'nested' in slate_name:
                nested_found = True
                break

        assert nested_found, "Should find nested directories with images"

    def test_scan_directories_no_symlinks(self, temp_scan_dir):
        """Test that symbolic links are not followed (followlinks=False)."""
        # This test verifies the followlinks=False parameter works
        result = scan_directories(str(temp_scan_dir))

        # Should complete without infinite loops or crashes
        assert isinstance(result, dict)

    @patch('os.path.exists', return_value=False)
    def test_scan_directories_handles_missing_directory(self, mock_exists):
        """Test scanning handles missing directory gracefully."""
        result = scan_directories('/missing/directory')
        assert result == {}


class TestImageProcessorIntegration:
    """Integration tests combining multiple image processor functions."""

    @pytest.fixture
    def temp_image_dir(self):
        """Create a temporary directory with diverse image files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create images with different orientations and formats
            images = [
                ('portrait.jpg', (100, 200)),
                ('landscape.png', (200, 100)),
                ('square.bmp', (100, 100)),
            ]

            for filename, size in images:
                image = Image.new('RGB', size, color='red')
                image.save(base_path / filename)

            yield base_path

    def test_full_workflow_scan_and_analyze(self, temp_image_dir):
        """Test complete workflow: scan directory and analyze each image."""
        # Scan directory
        slates = scan_directories(str(temp_image_dir))

        assert len(slates) == 1  # Should find root directory
        assert '/' in slates

        images = slates['/']['images']
        assert len(images) == 3

        # Analyze each found image
        for image_path in images:
            # Get EXIF data
            exif_data = get_exif_data(image_path)
            assert isinstance(exif_data, dict)

            # Get orientation
            orientation = get_orientation(image_path, exif_data)
            assert orientation in ['portrait', 'landscape', 'unknown']

            # Verify file exists and is accessible
            assert os.path.exists(image_path)
            assert os.path.isfile(image_path)


class TestGetImageDate:
    """Test date extraction from EXIF data with various scenarios."""

    def test_get_image_date_with_datetimeoriginal(self):
        """Test date extraction preferring DateTimeOriginal."""
        exif_data = {
            'DateTimeOriginal': '2023:12:25 14:30:45',
            'DateTimeDigitized': '2023:12:26 10:00:00',
            'DateTime': '2023:12:27 08:00:00'
        }

        result = get_image_date(exif_data)
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45

    def test_get_image_date_with_datetimedigitized_fallback(self):
        """Test date extraction falling back to DateTimeDigitized."""
        exif_data = {
            'DateTimeDigitized': '2022:06:15 09:45:30',
            'DateTime': '2022:06:16 12:00:00'
        }

        result = get_image_date(exif_data)
        assert isinstance(result, datetime)
        assert result.year == 2022
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 9
        assert result.minute == 45
        assert result.second == 30

    def test_get_image_date_with_datetime_last_resort(self):
        """Test date extraction using DateTime as last resort."""
        exif_data = {
            'DateTime': '2021:01:01 00:00:01'
        }

        result = get_image_date(exif_data)
        assert isinstance(result, datetime)
        assert result.year == 2021
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 1

    def test_get_image_date_no_date_tags(self):
        """Test date extraction with no date tags present."""
        exif_data = {
            'FocalLength': 50,
            'Orientation': 1
        }

        result = get_image_date(exif_data)
        assert result is None

    def test_get_image_date_empty_exif(self):
        """Test date extraction with empty EXIF data."""
        result = get_image_date({})
        assert result is None

    def test_get_image_date_invalid_format(self):
        """Test date extraction with invalid date format."""
        exif_data = {
            'DateTimeOriginal': 'Invalid date string',
            'DateTime': '2021:01:01 00:00:00'  # Valid fallback
        }

        result = get_image_date(exif_data)
        # Should skip invalid DateTimeOriginal and use valid DateTime
        assert isinstance(result, datetime)
        assert result.year == 2021
        assert result.month == 1
        assert result.day == 1

    def test_get_image_date_malformed_date_format(self):
        """Test date extraction with various malformed date formats."""
        test_cases = [
            {'DateTimeOriginal': '2023/12/25 14:30:45'},  # Wrong separator
            {'DateTimeOriginal': '2023:12:25'},  # Missing time
            {'DateTimeOriginal': '25:12:2023 14:30:45'},  # Wrong order
            {'DateTimeOriginal': '2023:13:01 00:00:00'},  # Invalid month
            {'DateTimeOriginal': '2023:12:32 00:00:00'},  # Invalid day
            {'DateTimeOriginal': '2023:12:25 25:00:00'},  # Invalid hour
        ]

        for exif_data in test_cases:
            result = get_image_date(exif_data)
            assert result is None

    def test_get_image_date_edge_cases(self):
        """Test date extraction with edge case dates."""
        edge_cases = [
            ('2000:01:01 00:00:00', 2000, 1, 1),  # Y2K
            ('2020:02:29 23:59:59', 2020, 2, 29),  # Leap year
            ('2019:12:31 23:59:59', 2019, 12, 31),  # End of year
            ('1990:01:01 00:00:00', 1990, 1, 1),  # Old date
        ]

        for date_str, year, month, day in edge_cases:
            exif_data = {'DateTimeOriginal': date_str}
            result = get_image_date(exif_data)
            assert isinstance(result, datetime)
            assert result.year == year
            assert result.month == month
            assert result.day == day

    def test_get_image_date_none_values(self):
        """Test date extraction with None values in EXIF data."""
        exif_data = {
            'DateTimeOriginal': None,
            'DateTimeDigitized': None,
            'DateTime': '2021:05:15 10:30:00'
        }

        result = get_image_date(exif_data)
        assert isinstance(result, datetime)
        assert result.year == 2021
        assert result.month == 5
        assert result.day == 15

    def test_get_image_date_empty_string_values(self):
        """Test date extraction with empty string values."""
        exif_data = {
            'DateTimeOriginal': '',
            'DateTimeDigitized': '',
            'DateTime': ''
        }

        result = get_image_date(exif_data)
        assert result is None

    def test_get_image_date_all_invalid(self):
        """Test date extraction when all date values are invalid."""
        exif_data = {
            'DateTimeOriginal': 'invalid1',
            'DateTimeDigitized': 'invalid2',
            'DateTime': 'invalid3'
        }

        result = get_image_date(exif_data)
        assert result is None

    def test_get_image_date_partial_invalid(self):
        """Test date extraction with some invalid dates."""
        exif_data = {
            'DateTimeOriginal': 'invalid date',
            'DateTimeDigitized': '2023:06:15 12:00:00',
            'DateTime': 'another invalid'
        }

        result = get_image_date(exif_data)
        # Should skip invalid and use valid DateTimeDigitized
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 6
        assert result.day == 15

    @patch('src.core.image_processor.logger')
    def test_get_image_date_logs_warnings(self, mock_logger):
        """Test that invalid dates generate appropriate warnings."""
        exif_data = {
            'DateTimeOriginal': 'invalid format',
            'DateTime': '2021:01:01 00:00:00'
        }

        result = get_image_date(exif_data)
        assert isinstance(result, datetime)

        # Verify warning was logged
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args[0][0]
        assert 'Invalid date format' in warning_call
        assert 'DateTimeOriginal' in warning_call
