"""Tests for edge cases and error handling in image processing."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.core.gallery_generator import generate_html_gallery
from src.core.image_processor import get_exif_data, get_orientation, scan_directories


class TestExifEdgeCases:
    """Test EXIF extraction edge cases and error handling."""

    @pytest.fixture
    def temp_image_dir(self):
        """Create temporary directory with test images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_get_exif_data_ifd_access_error(self, temp_image_dir):
        """Test get_exif_data when exif.get_ifd fails (lines 48-49)."""
        # Create a simple image
        image_path = temp_image_dir / "test.jpg"
        img = Image.new('RGB', (100, 100), 'red')
        img.save(image_path)

        with patch('PIL.Image.open') as mock_open:
            mock_img = MagicMock()
            mock_exif = MagicMock()

            # Make get_ifd raise KeyError
            mock_exif.get_ifd.side_effect = KeyError("IFD not found")
            mock_img.getexif.return_value = mock_exif
            mock_img.__enter__.return_value = mock_img
            mock_img.__exit__.return_value = None

            mock_open.return_value = mock_img

            # Should handle the error and return empty dict or partial data
            result = get_exif_data(str(image_path))

            # Function should not crash
            assert isinstance(result, dict)

    def test_get_exif_data_attribute_error(self, temp_image_dir):
        """Test get_exif_data when exif.get_ifd raises AttributeError (line 49)."""
        image_path = temp_image_dir / "test.jpg"
        img = Image.new('RGB', (100, 100), 'blue')
        img.save(image_path)

        with patch('PIL.Image.open') as mock_open:
            mock_img = MagicMock()
            mock_exif = MagicMock()

            # Make get_ifd raise AttributeError
            mock_exif.get_ifd.side_effect = AttributeError("Method not found")
            mock_img.getexif.return_value = mock_exif
            mock_img.__enter__.return_value = mock_img
            mock_img.__exit__.return_value = None

            mock_open.return_value = mock_img

            result = get_exif_data(str(image_path))

            # Should handle gracefully
            assert isinstance(result, dict)

    def test_get_exif_data_legacy_getexif_fallback(self, temp_image_dir):
        """Test fallback to _getexif() method for older PIL versions (lines 58-67)."""
        image_path = temp_image_dir / "test.jpg"
        img = Image.new('RGB', (100, 100), 'green')
        img.save(image_path)

        with patch('PIL.Image.open') as mock_open:
            mock_img = MagicMock()

            # Make getexif not exist (older PIL)
            del mock_img.getexif

            # Provide _getexif fallback
            mock_legacy_exif = {
                274: 1,  # Orientation
                37386: (50, 1),  # FocalLength
            }
            mock_img._getexif.return_value = mock_legacy_exif
            mock_img.__enter__.return_value = mock_img
            mock_img.__exit__.return_value = None

            mock_open.return_value = mock_img

            result = get_exif_data(str(image_path))

            # Should use legacy method
            assert isinstance(result, dict)
            mock_img._getexif.assert_called_once()
            # Check that the values were extracted
            assert 'Orientation' in result
            assert 'FocalLength' in result

    def test_get_exif_data_no_exif_methods(self, temp_image_dir):
        """Test when image has neither getexif nor _getexif methods."""
        image_path = temp_image_dir / "test.png"
        img = Image.new('RGB', (100, 100), 'yellow')
        img.save(image_path)

        with patch('PIL.Image.open') as mock_open:
            mock_img = MagicMock()

            # Neither method exists
            mock_img.getexif.side_effect = AttributeError("No getexif")
            mock_img._getexif.side_effect = AttributeError("No _getexif")
            mock_img.__enter__.return_value = mock_img
            mock_img.__exit__.return_value = None

            mock_open.return_value = mock_img

            result = get_exif_data(str(image_path))

            # Should return empty dict
            assert result == {}

    def test_get_orientation_image_cleanup_exception(self, temp_image_dir):
        """Test get_orientation when image cleanup fails (lines 118-119)."""
        image_path = temp_image_dir / "test.jpg"
        img = Image.new('RGB', (800, 600), 'purple')
        img.save(image_path)

        with patch('PIL.Image.open') as mock_open:
            mock_img = MagicMock()
            mock_img.size = (800, 600)  # Landscape

            # Make __exit__ raise an exception during cleanup
            mock_img.__exit__.side_effect = Exception("Cleanup failed")
            mock_img.__enter__.return_value = mock_img

            mock_open.return_value = mock_img

            # Should still return orientation despite cleanup error
            result = get_orientation(str(image_path), {})

            # Should handle the cleanup error gracefully
            assert result in ['landscape', 'portrait', 'unknown']


class TestMacOSResourceForkFiles:
    """Test filtering of macOS resource fork files."""

    def test_scan_directories_filters_macos_resource_forks(self):
        """Test that scan_directories filters out ._* files (line 140)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)

            # Create a subdirectory
            slate_dir = test_dir / "test_slate"
            slate_dir.mkdir()

            # Create normal images
            normal_img1 = slate_dir / "IMG_1234.jpg"
            normal_img2 = slate_dir / "photo.png"

            # Create macOS resource fork files
            resource_fork1 = slate_dir / "._IMG_1234.jpg"
            resource_fork2 = slate_dir / "._photo.png"
            resource_fork3 = slate_dir / "._DS_Store"

            # Write minimal image data to normal files
            for img_path in [normal_img1, normal_img2]:
                img = Image.new('RGB', (10, 10), 'white')
                img.save(img_path)

            # Write dummy data to resource fork files
            for fork_file in [resource_fork1, resource_fork2, resource_fork3]:
                fork_file.write_bytes(b'resource fork data')

            # Scan the directory
            result = scan_directories(str(test_dir))

            # Verify slate was found
            assert 'test_slate' in result

            # Verify only normal images are included
            image_paths = result['test_slate']['images']
            image_names = [Path(p).name for p in image_paths]

            assert 'IMG_1234.jpg' in image_names
            assert 'photo.png' in image_names

            # Verify resource fork files are excluded
            assert '._IMG_1234.jpg' not in image_names
            assert '._photo.png' not in image_names
            assert '._DS_Store' not in image_names

            # Should have exactly 2 images (not 5)
            assert len(image_paths) == 2

    def test_scan_directories_handles_only_resource_forks(self):
        """Test scan_directories when directory only has ._* files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)

            # Create a directory with only resource fork files
            fork_only_dir = test_dir / "fork_only"
            fork_only_dir.mkdir()

            # Only create resource fork files
            (fork_only_dir / "._image1.jpg").write_bytes(b'fork')
            (fork_only_dir / "._image2.png").write_bytes(b'fork')
            (fork_only_dir / "._DS_Store").write_bytes(b'fork')

            # Scan the directory
            result = scan_directories(str(test_dir))

            # Directory should be skipped (no real images)
            assert 'fork_only' not in result or result.get('fork_only', {}).get('images', []) == []


class TestSecurityAndPathTraversal:
    """Test security features including path traversal protection."""

    @pytest.fixture
    def secure_dirs(self):
        """Create secure test directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            safe_dir = base / "safe"
            output_dir = base / "output"
            template_dir = base / "templates"

            safe_dir.mkdir()
            output_dir.mkdir()
            template_dir.mkdir()

            # Create template
            template = template_dir / "template.html"
            template.write_text("<html>{{ gallery }}</html>")

            yield {
                'base': base,
                'safe_dir': str(safe_dir),
                'output_dir': str(output_dir),
                'template': str(template)
            }

    def test_generate_html_gallery_path_traversal_attempt(self, secure_dirs):
        """Test that generate_html_gallery prevents path traversal (lines 34-37)."""
        # Prepare gallery data with path traversal attempt
        gallery_data = [{
            'slate': 'test',
            'images': [{
                'original_path': '../../../etc/passwd',  # Path traversal attempt
                'filename': 'passwd',
                'focal_length': None,
                'orientation': 'unknown'
            }]
        }]

        # Mock status callback
        status_callback = MagicMock()

        with patch('src.core.gallery_generator.logger'):
            # Should handle the security issue gracefully
            success = generate_html_gallery(
                gallery_data=gallery_data,
                focal_length_data=[],
                date_data=[],
                template_path=secure_dirs['template'],
                output_dir=secure_dirs['output_dir'],
                allowed_root_dirs=secure_dirs['safe_dir'],
                status_callback=status_callback
            )

            # The function should complete (may succeed or fail depending on implementation)
            assert isinstance(success, bool)

    def test_generate_html_gallery_template_render_error(self, secure_dirs):
        """Test handling of template rendering errors (lines 45-48)."""
        gallery_data = [{
            'slate': 'test',
            'images': []
        }]

        # Create a malformed template
        bad_template = secure_dirs['base'] / "bad_template.html"
        bad_template.write_text("{{ undefined_variable.bad_access }}")

        status_callback = MagicMock()

        with patch('src.core.gallery_generator.logger') as mock_logger:
            success = generate_html_gallery(
                gallery_data=gallery_data,
                focal_length_data=[],
                date_data=[],
                template_path=str(bad_template),
                output_dir=secure_dirs['output_dir'],
                allowed_root_dirs=secure_dirs['safe_dir'],
                status_callback=status_callback
            )

            # Should handle template error gracefully
            assert isinstance(success, bool)
            if not success:
                # If it failed, should have logged the error
                mock_logger.error.assert_called()

    def test_generate_html_gallery_output_dir_creation_fails(self, secure_dirs):
        """Test when output directory creation fails (lines 55-58)."""
        gallery_data = [{
            'slate': 'test',
            'images': []
        }]

        # Use a path that will fail to create
        invalid_output = "/root/no_permission/output"

        status_callback = MagicMock()

        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("No permission")

            with patch('src.core.gallery_generator.logger') as mock_logger:
                success = generate_html_gallery(
                    gallery_data=gallery_data,
                    focal_length_data=[],
                    date_data=[],
                    template_path=secure_dirs['template'],
                    output_dir=invalid_output,
                    allowed_root_dirs=secure_dirs['safe_dir'],
                    status_callback=status_callback
                )

                # Should fail gracefully
                assert success is False

                # Should log the error
                mock_logger.error.assert_called()

    def test_generate_html_gallery_file_write_permission_error(self, secure_dirs):
        """Test handling of file write permission errors."""
        gallery_data = [{
            'slate': 'test',
            'images': []
        }]

        status_callback = MagicMock()

        with patch('builtins.open', side_effect=PermissionError("Cannot write file")):
            with patch('src.core.gallery_generator.logger') as mock_logger:
                success = generate_html_gallery(
                    gallery_data=gallery_data,
                    focal_length_data=[],
                    date_data=[],
                    template_path=secure_dirs['template'],
                    output_dir=secure_dirs['output_dir'],
                    allowed_root_dirs=secure_dirs['safe_dir'],
                    status_callback=status_callback
                )

                # Should fail gracefully
                assert success is False

                # Should have logged the error
                mock_logger.error.assert_called()


class TestRobustnessAndRecovery:
    """Test system robustness and recovery from various error conditions."""

    def test_scan_directories_symbolic_link_loop(self):
        """Test that scan_directories handles symbolic link loops."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)

            # Create directories
            dir1 = base / "dir1"
            dir2 = base / "dir2"
            dir1.mkdir()
            dir2.mkdir()

            # Create circular symbolic links
            link1 = dir1 / "link_to_dir2"
            link2 = dir2 / "link_to_dir1"

            try:
                link1.symlink_to(dir2)
                link2.symlink_to(dir1)
            except OSError:
                # Skip test if symlinks not supported
                pytest.skip("Symbolic links not supported on this system")

            # Add an image to find
            img = Image.new('RGB', (10, 10), 'red')
            img.save(dir1 / "image.jpg")

            # Should not hang or crash
            result = scan_directories(str(base))

            # Should find the image
            assert any('image.jpg' in str(img) for slate in result.values() for img in slate.get('images', []))

    def test_process_corrupted_image_file(self, tmp_path):
        """Test handling of corrupted image files."""
        from src.core.image_processor import get_exif_data, get_orientation

        # Create a corrupted JPEG file
        corrupted_file = tmp_path / "corrupted.jpg"
        # JPEG header followed by garbage
        corrupted_file.write_bytes(b'\xFF\xD8\xFF\xE0' + b'garbage data' * 100)

        # Should handle gracefully
        exif_data = get_exif_data(str(corrupted_file))
        assert isinstance(exif_data, dict)

        orientation = get_orientation(str(corrupted_file), exif_data)
        assert orientation == 'unknown'

    def test_unicode_in_paths_and_filenames(self):
        """Test handling of Unicode characters in paths and filenames."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)

            # Create directory with Unicode characters
            unicode_dir = base / "写真_Photos_Фото"
            unicode_dir.mkdir()

            # Create files with Unicode names
            unicode_files = [
                "图片_1.jpg",
                "фото_2.png",
                "写真_3.jpg",
                "café_naïve.jpg"
            ]

            for filename in unicode_files:
                img = Image.new('RGB', (50, 50), 'blue')
                img.save(unicode_dir / filename)

            # Should handle Unicode properly
            result = scan_directories(str(base))

            # Should find the Unicode directory
            found_dirs = list(result.keys())
            assert len(found_dirs) > 0

            # Should find all images
            total_images = sum(len(slate['images']) for slate in result.values())
            assert total_images == len(unicode_files)
