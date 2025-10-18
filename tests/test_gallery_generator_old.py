"""Unit tests for gallery_generator module with minimal mocking."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.gallery_generator import generate_html_gallery


class TestGenerateHtmlGallery:
    """Test HTML gallery generation with real template rendering."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create test directories
            template_dir = base_path / 'templates'
            template_dir.mkdir()
            output_dir = base_path / 'output'
            root_dir = base_path / 'root'
            root_dir.mkdir()
            
            yield {
                'base': base_path,
                'template_dir': template_dir,
                'output_dir': output_dir,
                'root_dir': root_dir
            }
    
    @pytest.fixture
    def simple_template(self, temp_dirs):
        """Create a simple HTML template for testing."""
        template_content = '''<!DOCTYPE html>
<html>
<head><title>Test Gallery</title></head>
<body>
    <h1>Gallery</h1>
    <div class="focal-lengths">
        {% for focal in focal_lengths %}
            <span>{{ focal.value }}mm ({{ focal.count }} photos)</span>
        {% endfor %}
    </div>
    <div class="dates">
        {% for date in dates %}
            <span>{{ date.value }} ({{ date.count }} photos)</span>
        {% endfor %}
    </div>
    {% for slate in gallery %}
        <div class="slate">
            <h2>{{ slate.slate }}</h2>
            {% for image in slate.images %}
                <div class="image">
                    <img src="{{ image.web_path }}" alt="{{ image.filename }}">
                    <p>Focal: {{ image.focal_length }}mm</p>
                    <p>Orientation: {{ image.orientation }}</p>
                    <p>Date: {{ image.date_taken }}</p>
                </div>
            {% endfor %}
        </div>
    {% endfor %}
</body>
</html>'''
        
        template_path = temp_dirs['template_dir'] / 'test_template.html'
        template_path.write_text(template_content)
        return str(template_path)
    
    @pytest.fixture
    def sample_gallery_data(self, temp_dirs):
        """Create sample gallery data for testing."""
        # Create actual image files to test path validation
        image1_path = temp_dirs['root_dir'] / 'image1.jpg'
        image2_path = temp_dirs['root_dir'] / 'subdir' / 'image2.png'
        
        image1_path.write_bytes(b'fake_image_data')
        (temp_dirs['root_dir'] / 'subdir').mkdir()
        image2_path.write_bytes(b'fake_image_data')
        
        return [
            {
                'slate': 'Test Slate 1',
                'images': [
                    {
                        'original_path': str(image1_path),
                        'focal_length': 35.0,
                        'orientation': 'landscape',
                        'filename': 'image1.jpg',
                        'date_taken': '2023-06-15T10:30:00'
                    }
                ]
            },
            {
                'slate': 'Test Slate 2',
                'images': [
                    {
                        'original_path': str(image2_path),
                        'focal_length': 50.0,
                        'orientation': 'portrait',
                        'filename': 'image2.png',
                        'date_taken': '2023-07-20T14:45:00'
                    }
                ]
            }
        ]
    
    def test_generate_html_gallery_basic(self, temp_dirs, simple_template, sample_gallery_data):
        """Test basic HTML gallery generation."""
        focal_length_data = [
            {'value': 35.0, 'count': 1},
            {'value': 50.0, 'count': 1}
        ]
        date_data = [
            {'value': '2023-06', 'count': 1},
            {'value': '2023-07', 'count': 1}
        ]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_length_data,
            date_data=date_data,
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is True
        
        # Check that HTML file was created
        html_file = temp_dirs['output_dir'] / 'index.html'
        assert html_file.exists()
        
        # Check HTML content
        html_content = html_file.read_text()
        assert 'Test Gallery' in html_content
        assert 'Test Slate 1' in html_content
        assert 'Test Slate 2' in html_content
        assert '35.0mm (1 photos)' in html_content
        assert '50.0mm (1 photos)' in html_content
        assert 'landscape' in html_content
        assert 'portrait' in html_content
        
        # Check status callback was called
        status_callback.assert_called()
    
    def test_generate_html_gallery_creates_output_directory(self, temp_dirs, simple_template, sample_gallery_data):
        """Test that output directory is created if it doesn't exist."""
        nonexistent_output = temp_dirs['base'] / 'new_output'
        focal_length_data = [{'value': 35.0, 'count': 2}]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(nonexistent_output),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is True
        assert nonexistent_output.exists()
        assert (nonexistent_output / 'index.html').exists()
    
    def test_generate_html_gallery_empty_data(self, temp_dirs, simple_template):
        """Test gallery generation with empty data."""
        focal_length_data = []
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=[],
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is True
        
        # Check HTML file was still created
        html_file = temp_dirs['output_dir'] / 'index.html'
        assert html_file.exists()
        
        # Should contain basic structure but no slates
        html_content = html_file.read_text()
        assert 'Test Gallery' in html_content
        assert 'Test Slate' not in html_content
    
    def test_generate_html_gallery_invalid_template(self, temp_dirs, sample_gallery_data):
        """Test gallery generation with invalid template."""
        invalid_template = temp_dirs['template_dir'] / 'invalid.html'
        invalid_template.write_text('{{ invalid_jinja_syntax }')
        
        focal_length_data = [{'value': 35.0, 'count': 2}]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=str(invalid_template),
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is False
        
        # Check error was reported via callback
        status_callback.assert_called()
        error_calls = [call for call in status_callback.call_args_list if 'Error' in str(call)]
        assert len(error_calls) > 0
    
    def test_generate_html_gallery_nonexistent_template(self, temp_dirs, sample_gallery_data):
        """Test gallery generation with nonexistent template."""
        nonexistent_template = str(temp_dirs['template_dir'] / 'nonexistent.html')
        focal_length_data = [{'value': 35.0, 'count': 1}]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=nonexistent_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is False
        status_callback.assert_called()
    
    def test_generate_html_gallery_path_security(self, temp_dirs, simple_template):
        """Test that images outside root directory are rejected for security."""
        # Create an image outside the root directory
        outside_image = temp_dirs['base'] / 'outside_image.jpg'
        outside_image.write_bytes(b'fake_image_data')
        
        malicious_gallery_data = [
            {
                'slate': 'Malicious Slate',
                'images': [
                    {
                        'original_path': str(outside_image),
                        'focal_length': 35.0,
                        'orientation': 'landscape',
                        'filename': 'outside_image.jpg'
                    }
                ]
            }
        ]
        
        focal_length_data = [{'value': 35.0, 'count': 1}]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=malicious_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        # Should still succeed but skip the outside image
        assert result is True
        
        # Check that the callback was called with a security warning
        warning_calls = [call for call in status_callback.call_args_list 
                        if 'outside of root directory' in str(call)]
        assert len(warning_calls) > 0
    
    def test_generate_html_gallery_web_path_generation(self, temp_dirs, simple_template, sample_gallery_data):
        """Test that web paths are generated correctly."""
        focal_length_data = [
            {'value': 35.0, 'count': 1},
            {'value': 50.0, 'count': 1}
        ]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is True
        
        # Check that web_path was added to images
        for slate in sample_gallery_data:
            for image in slate['images']:
                assert 'web_path' in image
                assert image['web_path'].startswith('file://')
                assert image['web_path'].endswith(image['filename'])
    
    def test_generate_html_gallery_unicode_handling(self, temp_dirs, simple_template):
        """Test gallery generation with unicode characters."""
        # Create image with unicode filename
        unicode_image = temp_dirs['root_dir'] / 'ñiño_café.jpg'
        unicode_image.write_bytes(b'fake_image_data')
        
        unicode_gallery_data = [
            {
                'slate': 'Ñiño Café Slate',
                'images': [
                    {
                        'original_path': str(unicode_image),
                        'focal_length': 35.0,
                        'orientation': 'landscape',
                        'filename': 'ñiño_café.jpg'
                    }
                ]
            }
        ]
        
        focal_length_data = [{'value': 35.0, 'count': 1}]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=unicode_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is True
        
        # Check HTML content contains unicode characters
        html_file = temp_dirs['output_dir'] / 'index.html'
        html_content = html_file.read_text(encoding='utf-8')
        assert 'Ñiño Café Slate' in html_content
        assert 'ñiño_café.jpg' in html_content
    
    def test_generate_html_gallery_focal_lengths_sorting(self, temp_dirs, simple_template, sample_gallery_data):
        """Test that focal lengths are handled properly in template."""
        # Test with focal length data structure
        focal_length_data = [
            {'value': 85.0, 'count': 2},
            {'value': 35.0, 'count': 3},
            {'value': 50.0, 'count': 1},
            {'value': 24.0, 'count': 4}
        ]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        assert result is True
        
        # Check that all focal lengths appear in HTML with counts
        html_file = temp_dirs['output_dir'] / 'index.html'
        html_content = html_file.read_text()
        
        for focal_data in focal_length_data:
            assert f'{focal_data["value"]}mm ({focal_data["count"]} photos)' in html_content
    
    def test_generate_html_gallery_error_during_processing(self, temp_dirs, simple_template):
        """Test gallery generation handles image processing errors gracefully."""
        # Create gallery data with an image inside root but that doesn't exist
        nonexistent_image = temp_dirs['root_dir'] / 'nonexistent.jpg'
        
        error_gallery_data = [
            {
                'slate': 'Error Slate',
                'images': [
                    {
                        'original_path': str(nonexistent_image),
                        'focal_length': 35.0,
                        'orientation': 'landscape',
                        'filename': 'nonexistent.jpg'
                    }
                ]
            }
        ]
        
        focal_length_data = [{'value': 35.0, 'count': 1}]
        status_callback = MagicMock()
        
        result = generate_html_gallery(
            gallery_data=error_gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=simple_template,
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=status_callback
        )
        
        # Should still succeed (graceful error handling)
        assert result is True
        
        # Check that processing completed without crashing
        assert (temp_dirs['output_dir'] / 'index.html').exists()
    
    def test_generate_html_gallery_permission_error_output(self, temp_dirs, simple_template, sample_gallery_data):
        """Test gallery generation handles output permission errors."""
        # Create a read-only directory to cause permission error
        readonly_output = temp_dirs['base'] / 'readonly_output'
        readonly_output.mkdir()
        readonly_output.chmod(0o444)  # Read-only
        
        focal_length_data = [{'value': 35.0, 'count': 1}]
        status_callback = MagicMock()
        
        try:
            result = generate_html_gallery(
                gallery_data=sample_gallery_data,
                focal_length_data=focal_length_data,
                date_data=[],
                template_path=simple_template,
                output_dir=str(readonly_output),
                root_dir=str(temp_dirs['root_dir']),
                status_callback=status_callback
            )
            
            # Should fail due to permission error
            assert result is False
            status_callback.assert_called()
        finally:
            # Restore permissions for cleanup
            readonly_output.chmod(0o755)


class TestGalleryGeneratorIntegration:
    """Integration tests for gallery generator with real templates."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create test directories
            template_dir = base_path / 'templates'
            template_dir.mkdir()
            output_dir = base_path / 'output'
            root_dir = base_path / 'images'
            root_dir.mkdir()
            
            yield {
                'base': base_path,
                'template_dir': template_dir,
                'output_dir': output_dir,
                'root_dir': root_dir
            }
    
    def test_full_gallery_generation_workflow(self, temp_dirs):
        """Test complete gallery generation with realistic data."""
        # Copy the actual template to temp directory
        actual_template = Path(__file__).parent.parent / 'templates' / 'gallery_template.html'
        if actual_template.exists():
            template_content = actual_template.read_text()
            test_template = temp_dirs['template_dir'] / 'gallery_template.html'
            test_template.write_text(template_content)
        else:
            # Fallback simple template if actual template not found
            test_template = temp_dirs['template_dir'] / 'simple_template.html'
            test_template.write_text('''<!DOCTYPE html>
<html><head><title>Gallery</title></head>
<body>
{% for slate in gallery %}
    <h2>{{ slate.slate }}</h2>
    {% for image in slate.images %}
        <img src="{{ image.web_path }}" alt="{{ image.filename }}">
    {% endfor %}
{% endfor %}
</body></html>''')
        
        # Create realistic test images
        image_paths = []
        for i in range(3):
            img_path = temp_dirs['root_dir'] / f'photo_{i+1}.jpg'
            img_path.write_bytes(b'fake_image_data')
            image_paths.append(img_path)
        
        # Create realistic gallery data
        gallery_data = [
            {
                'slate': 'Nature Photos',
                'images': [
                    {
                        'original_path': str(image_paths[0]),
                        'focal_length': 24.0,
                        'orientation': 'landscape',
                        'filename': 'photo_1.jpg'
                    },
                    {
                        'original_path': str(image_paths[1]),
                        'focal_length': 35.0,
                        'orientation': 'portrait',
                        'filename': 'photo_2.jpg'
                    }
                ]
            },
            {
                'slate': 'Urban Photos',
                'images': [
                    {
                        'original_path': str(image_paths[2]),
                        'focal_length': 50.0,
                        'orientation': 'landscape',
                        'filename': 'photo_3.jpg'
                    }
                ]
            }
        ]
        
        focal_length_data = [
            {'value': 24.0, 'count': 1},
            {'value': 35.0, 'count': 1},
            {'value': 50.0, 'count': 1}
        ]
        status_messages = []
        
        def capture_status(message):
            status_messages.append(message)
        
        # Generate gallery
        result = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=focal_length_data,
            date_data=[],
            template_path=str(test_template),
            output_dir=str(temp_dirs['output_dir']),
            root_dir=str(temp_dirs['root_dir']),
            status_callback=capture_status
        )
        
        # Verify success
        assert result is True
        assert len(status_messages) > 0
        assert any('Gallery generated' in msg for msg in status_messages)
        
        # Verify HTML output
        html_file = temp_dirs['output_dir'] / 'index.html'
        assert html_file.exists()
        
        html_content = html_file.read_text()
        assert 'Nature Photos' in html_content
        assert 'Urban Photos' in html_content
        assert 'photo_1.jpg' in html_content
        assert 'photo_2.jpg' in html_content
        assert 'photo_3.jpg' in html_content
        
        # Verify web paths were generated and added to image data
        for slate in gallery_data:
            for image in slate['images']:
                assert 'web_path' in image
                assert image['web_path'].startswith('file://')
        
        # For the full template, just verify basic structure exists
        # (the full template has complex JavaScript that doesn't include direct image paths in HTML)