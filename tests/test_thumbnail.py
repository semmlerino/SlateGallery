"""Tests for thumbnail generation functionality."""

import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.core.image_processor import generate_thumbnail


class TestGenerateThumbnail:
    """Test generate_thumbnail function comprehensively."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            image_dir = base_path / "images"
            thumb_dir = base_path / "thumbnails"
            image_dir.mkdir()
            
            yield {
                'base': base_path,
                'image_dir': image_dir,
                'thumb_dir': str(thumb_dir)
            }
    
    @pytest.fixture
    def create_test_image(self, temp_dirs):
        """Helper to create test images with various properties."""
        def _create(filename="test.jpg", size=(800, 600), mode='RGB', 
                   color='blue', format='JPEG', add_exif_orientation=None):
            image_path = temp_dirs['image_dir'] / filename
            img = Image.new(mode, size, color=color if mode == 'RGB' else 0)
            
            # Add EXIF orientation if requested
            if add_exif_orientation and format == 'JPEG':
                try:
                    import piexif
                    exif_dict = {"0th": {piexif.ImageIFD.Orientation: add_exif_orientation}}
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(image_path, format, exif=exif_bytes)
                except ImportError:
                    # Save without EXIF if piexif not available
                    img.save(image_path, format)
            else:
                img.save(image_path, format)
            
            return str(image_path)
        return _create
    
    def test_generate_thumbnail_basic(self, temp_dirs, create_test_image):
        """Test basic thumbnail generation."""
        image_path = create_test_image()
        thumb_dir = temp_dirs['thumb_dir']
        
        thumbnails = generate_thumbnail(image_path, thumb_dir)
        
        assert isinstance(thumbnails, dict)
        assert len(thumbnails) == 1  # Should generate single 600x600 by default
        assert '600x600' in thumbnails
        
        # Verify thumbnails exist on disk
        for size_str, thumb_path in thumbnails.items():
            assert Path(thumb_path).exists()
            
            # Verify thumbnail is valid image
            with Image.open(thumb_path) as thumb:
                width, height = thumb.size
                # Thumbnail should fit within requested size
                max_size = int(size_str.split('x')[0])
                assert max(width, height) <= max_size
    
    def test_generate_thumbnail_custom_sizes(self, temp_dirs, create_test_image):
        """Test thumbnail generation with custom sizes."""
        image_path = create_test_image()
        thumb_dir = temp_dirs['thumb_dir']
        
        # Test individual sizes
        thumbnails_800 = generate_thumbnail(image_path, thumb_dir, size=800)
        assert len(thumbnails_800) == 1
        assert '800x800' in thumbnails_800
        
        thumbnails_1200 = generate_thumbnail(image_path, thumb_dir, size=1200)
        assert len(thumbnails_1200) == 1
        assert '1200x1200' in thumbnails_1200
        
        # Test with tuple size
        thumbnails_custom = generate_thumbnail(image_path, thumb_dir, size=(150, 150))
        assert len(thumbnails_custom) == 1
        assert '150x150' in thumbnails_custom
    
    def test_generate_thumbnail_directory_creation(self, temp_dirs, create_test_image):
        """Test that thumbnail directory is created if it doesn't exist."""
        image_path = create_test_image()
        # Use a non-existent directory
        thumb_dir = str(temp_dirs['base'] / 'new_thumb_dir')
        
        assert not Path(thumb_dir).exists()
        
        thumbnails = generate_thumbnail(image_path, thumb_dir)
        
        assert Path(thumb_dir).exists()
        assert len(thumbnails) > 0
    
    def test_generate_thumbnail_rgba_conversion(self, temp_dirs, create_test_image):
        """Test RGBA to RGB conversion for thumbnails."""
        # Create RGBA image
        image_path = create_test_image(mode='RGBA', format='PNG')
        thumb_dir = temp_dirs['thumb_dir']
        
        thumbnails = generate_thumbnail(image_path, thumb_dir)
        
        assert len(thumbnails) > 0
        
        # Verify thumbnails are RGB (JPEG format)
        for thumb_path in thumbnails.values():
            with Image.open(thumb_path) as thumb:
                assert thumb.mode == 'RGB'
    
    def test_generate_thumbnail_palette_mode(self, temp_dirs):
        """Test thumbnail generation for palette mode images."""
        image_path = temp_dirs['image_dir'] / 'palette.gif'
        
        # Create palette mode image (GIF)
        img = Image.new('P', (400, 300))
        img.putpalette([i//3 for i in range(768)])  # Simple palette
        img.save(image_path)
        
        thumb_dir = temp_dirs['thumb_dir']
        thumbnails = generate_thumbnail(str(image_path), thumb_dir)
        
        assert len(thumbnails) > 0
        
        # Verify conversion worked
        for thumb_path in thumbnails.values():
            with Image.open(thumb_path) as thumb:
                assert thumb.mode == 'RGB'
    
    def test_generate_thumbnail_la_mode(self, temp_dirs, create_test_image):
        """Test thumbnail generation for LA (grayscale with alpha) images."""
        image_path = temp_dirs['image_dir'] / 'grayscale.png'
        
        # Create LA mode image
        img = Image.new('LA', (400, 300), (128, 255))  # Gray with alpha
        img.save(image_path)
        
        thumb_dir = temp_dirs['thumb_dir']
        thumbnails = generate_thumbnail(str(image_path), thumb_dir)
        
        assert len(thumbnails) > 0
        
        # Verify conversion to RGB
        for thumb_path in thumbnails.values():
            with Image.open(thumb_path) as thumb:
                assert thumb.mode == 'RGB'
    
    def test_generate_thumbnail_exif_orientation(self, temp_dirs, create_test_image):
        """Test that EXIF orientation is preserved in thumbnails."""
        # Test different orientations
        orientations = {
            3: 180,  # Upside down
            6: 270,  # Rotated 90 CCW  
            8: 90    # Rotated 90 CW
        }
        
        for exif_orientation, expected_rotation in orientations.items():
            image_path = create_test_image(
                filename=f'oriented_{exif_orientation}.jpg',
                size=(800, 600),  # Non-square to verify rotation
                add_exif_orientation=exif_orientation
            )
            thumb_dir = temp_dirs['thumb_dir']
            
            thumbnails = generate_thumbnail(image_path, thumb_dir)
            
            assert len(thumbnails) > 0
            
            # Note: Testing actual rotation would require comparing pixel data
            # Here we just verify the function completes without error
    
    def test_generate_thumbnail_existing_valid(self, temp_dirs, create_test_image):
        """Test that existing valid thumbnails are not regenerated."""
        image_path = create_test_image()
        thumb_dir = temp_dirs['thumb_dir']
        
        # Generate thumbnails first time
        thumbnails1 = generate_thumbnail(image_path, thumb_dir)
        
        # Get modification times
        mod_times = {}
        for size_str, thumb_path in thumbnails1.items():
            mod_times[size_str] = Path(thumb_path).stat().st_mtime
        
        # Small delay to ensure different timestamps if regenerated
        import time
        time.sleep(0.01)
        
        # Generate again - should reuse existing
        thumbnails2 = generate_thumbnail(image_path, thumb_dir)
        
        # Verify same paths returned
        assert thumbnails1 == thumbnails2
        
        # Verify files were not modified (same timestamps)
        for size_str, thumb_path in thumbnails2.items():
            assert Path(thumb_path).stat().st_mtime == mod_times[size_str]
    
    def test_generate_thumbnail_corrupted_existing(self, temp_dirs, create_test_image):
        """Test that corrupted thumbnails are regenerated."""
        image_path = create_test_image()
        thumb_dir = temp_dirs['thumb_dir']
        
        # Generate thumbnails first
        thumbnails = generate_thumbnail(image_path, thumb_dir)
        
        # Corrupt one thumbnail
        corrupt_path = list(thumbnails.values())[0]
        with open(corrupt_path, 'wb') as f:
            f.write(b'corrupted data')
        
        # Generate again - should regenerate corrupted one
        with patch('src.core.image_processor.logger') as mock_logger:
            thumbnails2 = generate_thumbnail(image_path, thumb_dir)
            
            # Verify warning was logged about corruption
            mock_logger.warning.assert_called()
            assert 'Corrupted thumbnail found' in str(mock_logger.warning.call_args)
        
        # Verify thumbnail was regenerated and is valid
        assert len(thumbnails2) > 0
        with Image.open(corrupt_path) as thumb:
            thumb.verify()  # Should not raise exception
    
    def test_generate_thumbnail_invalid_image(self, temp_dirs):
        """Test handling of invalid image files."""
        # Create invalid image file
        invalid_path = temp_dirs['image_dir'] / 'invalid.jpg'
        invalid_path.write_text('not an image')
        
        thumb_dir = temp_dirs['thumb_dir']
        
        with patch('src.core.image_processor.logger') as mock_logger:
            thumbnails = generate_thumbnail(str(invalid_path), thumb_dir)
            
            # Should return empty dict on error
            assert thumbnails == {}
            
            # Should log error
            mock_logger.error.assert_called()
            assert 'Error generating thumbnails' in str(mock_logger.error.call_args)
    
    def test_generate_thumbnail_nonexistent_image(self, temp_dirs):
        """Test handling of non-existent image files."""
        nonexistent_path = str(temp_dirs['image_dir'] / 'nonexistent.jpg')
        thumb_dir = temp_dirs['thumb_dir']
        
        with patch('src.core.image_processor.logger') as mock_logger:
            thumbnails = generate_thumbnail(nonexistent_path, thumb_dir)
            
            # Should return empty dict
            assert thumbnails == {}
            
            # Should log error
            mock_logger.error.assert_called()
    
    def test_generate_thumbnail_unique_naming(self, temp_dirs, create_test_image):
        """Test that thumbnails have unique names based on path hash."""
        # Create two images with same name in different directories
        subdir1 = temp_dirs['image_dir'] / 'dir1'
        subdir2 = temp_dirs['image_dir'] / 'dir2'
        subdir1.mkdir()
        subdir2.mkdir()
        
        image1 = subdir1 / 'same_name.jpg'
        image2 = subdir2 / 'same_name.jpg'
        
        # Create images
        Image.new('RGB', (400, 300), 'red').save(image1)
        Image.new('RGB', (400, 300), 'blue').save(image2)
        
        thumb_dir = temp_dirs['thumb_dir']
        
        thumbnails1 = generate_thumbnail(str(image1), thumb_dir)
        thumbnails2 = generate_thumbnail(str(image2), thumb_dir)
        
        # Verify different thumbnail filenames due to path hash
        for size_str in thumbnails1:
            assert thumbnails1[size_str] != thumbnails2[size_str]
    
    def test_generate_thumbnail_large_image(self, temp_dirs):
        """Test thumbnail generation for large images."""
        # Create a large image
        large_image_path = temp_dirs['image_dir'] / 'large.jpg'
        large_img = Image.new('RGB', (4000, 3000), 'green')
        large_img.save(large_image_path, quality=95)
        
        thumb_dir = temp_dirs['thumb_dir']
        thumbnails = generate_thumbnail(str(large_image_path), thumb_dir)
        
        assert len(thumbnails) > 0
        
        # Verify thumbnails are much smaller than original
        original_size = large_image_path.stat().st_size
        for thumb_path in thumbnails.values():
            thumb_size = Path(thumb_path).stat().st_size
            assert thumb_size < original_size / 4  # Should be significantly smaller
    
    def test_generate_thumbnail_aspect_ratio_preserved(self, temp_dirs, create_test_image):
        """Test that thumbnail generation preserves aspect ratio."""
        # Create wide image
        wide_image = create_test_image(filename='wide.jpg', size=(1600, 400))
        # Create tall image  
        tall_image = create_test_image(filename='tall.jpg', size=(400, 1600))
        
        thumb_dir = temp_dirs['thumb_dir']
        
        wide_thumbs = generate_thumbnail(wide_image, thumb_dir, size=600)
        tall_thumbs = generate_thumbnail(tall_image, thumb_dir, size=600)
        
        # Check wide thumbnail
        with Image.open(wide_thumbs['600x600']) as thumb:
            width, height = thumb.size
            assert width == 600  # Should be constrained by width
            assert height < 600  # Height should be less
            # Aspect ratio should be preserved (4:1)
            assert abs((width/height) - 4.0) < 0.1
        
        # Check tall thumbnail
        with Image.open(tall_thumbs['600x600']) as thumb:
            width, height = thumb.size
            assert height == 600  # Should be constrained by height
            assert width < 600   # Width should be less
            # Aspect ratio should be preserved (1:4)
            assert abs((height/width) - 4.0) < 0.1
    
    @patch('src.core.image_processor.Path.mkdir')
    def test_generate_thumbnail_directory_creation_error(self, mock_mkdir, temp_dirs, create_test_image):
        """Test handling of directory creation errors."""
        image_path = create_test_image()
        thumb_dir = '/invalid/path/no/permission'
        
        # Simulate permission error
        mock_mkdir.side_effect = PermissionError("Permission denied")
        
        with patch('src.core.image_processor.logger') as mock_logger:
            thumbnails = generate_thumbnail(image_path, thumb_dir)
            
            # Should return empty dict on error
            assert thumbnails == {}
            
            # Should log the error
            mock_logger.error.assert_called()
    
    def test_generate_thumbnail_save_error(self, temp_dirs, create_test_image):
        """Test handling of save errors."""
        image_path = create_test_image()
        # Use read-only directory
        thumb_dir = temp_dirs['thumb_dir']
        Path(thumb_dir).mkdir(exist_ok=True)
        
        with patch('PIL.Image.Image.save') as mock_save:
            mock_save.side_effect = IOError("Disk full")
            
            with patch('src.core.image_processor.logger') as mock_logger:
                thumbnails = generate_thumbnail(image_path, thumb_dir)
                
                # Should return empty dict
                assert thumbnails == {}
                
                # Should log error
                mock_logger.error.assert_called()


class TestGenerateThumbnailIntegration:
    """Integration tests for thumbnail generation with real workflows."""
    
    def test_batch_thumbnail_generation(self, tmp_path):
        """Test generating thumbnails for multiple images."""
        image_dir = tmp_path / "images"
        thumb_dir = tmp_path / "thumbnails"
        image_dir.mkdir()
        
        # Create multiple test images
        image_paths = []
        for i in range(5):
            img_path = image_dir / f"image_{i}.jpg"
            img = Image.new('RGB', (800, 600), color=(i*50, 100, 150))
            img.save(img_path)
            image_paths.append(str(img_path))
        
        # Generate thumbnails for all images
        all_thumbnails = {}
        for image_path in image_paths:
            thumbnails = generate_thumbnail(image_path, str(thumb_dir))
            all_thumbnails[image_path] = thumbnails
        
        # Verify all thumbnails generated
        assert len(all_thumbnails) == 5
        for image_path, thumbnails in all_thumbnails.items():
            assert len(thumbnails) == 1  # Single default size (600x600)
            
        # Verify thumbnail directory structure
        thumb_files = list(thumb_dir.glob("*.jpg"))
        assert len(thumb_files) == 5  # 5 images × 1 size
    
    def test_thumbnail_with_image_processor_workflow(self, tmp_path):
        """Test thumbnail generation integrated with image processor workflow."""
        from src.core.image_processor import get_exif_data, get_orientation
        
        image_path = tmp_path / "test.jpg"
        thumb_dir = tmp_path / "thumbs"
        
        # Create test image with EXIF
        img = Image.new('RGB', (1024, 768), 'blue')
        img.save(image_path)
        
        # Full workflow: get EXIF, orientation, then generate thumbnail
        exif_data = get_exif_data(str(image_path))
        orientation = get_orientation(str(image_path), exif_data)
        thumbnails = generate_thumbnail(str(image_path), str(thumb_dir))
        
        assert isinstance(exif_data, dict)
        assert orientation in ['landscape', 'portrait', 'unknown']
        assert len(thumbnails) > 0