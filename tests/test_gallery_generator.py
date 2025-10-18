"""Improved gallery generator tests using real callbacks instead of mocks."""

import tempfile
from pathlib import Path

import pytest
from jinja2 import TemplateError

from src.core.gallery_generator import generate_html_gallery


class StatusCollector:
    """Real status callback collector for testing."""
    
    def __init__(self):
        self.messages = []
        self.call_count = 0
    
    def __call__(self, message):
        """Act as a callable to collect status messages."""
        self.messages.append(message)
        self.call_count += 1
    
    def has_message(self, substring):
        """Check if any message contains the substring."""
        return any(substring in msg for msg in self.messages)
    
    def clear(self):
        """Clear collected messages."""
        self.messages = []
        self.call_count = 0


class TestGenerateHtmlGalleryImproved:
    """Test HTML gallery generation with real components."""
    
    @pytest.fixture
    def gallery_setup(self, tmp_path):
        """Set up real directories and templates for testing."""
        # Create directory structure
        root_dir = tmp_path / "photos"
        output_dir = tmp_path / "output"
        template_dir = tmp_path / "templates"
        
        root_dir.mkdir()
        template_dir.mkdir()
        
        # Create a real template file
        template_file = template_dir / "gallery.html"
        template_file.write_text('''<!DOCTYPE html>
<html>
<head><title>Photo Gallery</title></head>
<body>
    <h1>Gallery</h1>
    <div class="filters">
        {% for focal in focal_lengths %}
        <button data-focal="{{ focal.value }}">{{ focal.value }}mm ({{ focal.count }})</button>
        {% endfor %}
        {% for date in dates %}
        <button data-date="{{ date.value }}">{{ date.value }} ({{ date.count }})</button>
        {% endfor %}
    </div>
    <div class="gallery">
        {% for slate in gallery %}
        <section class="slate" data-slate="{{ slate.slate }}">
            <h2>{{ slate.slate }}</h2>
            {% for image in slate.images %}
            <div class="image">
                <img src="{{ image.web_path }}" alt="{{ image.filename }}"
                     data-focal="{{ image.focal_length }}" 
                     data-orientation="{{ image.orientation }}"
                     data-date="{{ image.date_taken }}">
            </div>
            {% endfor %}
        </section>
        {% endfor %}
    </div>
</body>
</html>''')
        
        # Create some real test images in root_dir
        from PIL import Image
        for i in range(3):
            img_path = root_dir / f"test_{i}.jpg"
            img = Image.new('RGB', (100, 100), color=(i*50, 100, 150))
            img.save(img_path)
        
        return {
            'root_dir': str(root_dir),
            'output_dir': str(output_dir),
            'template_path': str(template_file),
            'images': [str(root_dir / f"test_{i}.jpg") for i in range(3)]
        }
    
    @pytest.fixture
    def status_collector(self):
        """Create a real status collector."""
        return StatusCollector()
    
    @pytest.fixture
    def sample_gallery_data(self, gallery_setup):
        """Create realistic gallery data."""
        return [
            {
                'slate': 'vacation_2024',
                'images': [
                    {
                        'original_path': gallery_setup['images'][0],
                        'filename': 'test_0.jpg',
                        'web_path': '../photos/test_0.jpg',
                        'focal_length': 35.0,
                        'orientation': 'landscape',
                        'date_taken': '2024-01-15T10:30:00'
                    },
                    {
                        'original_path': gallery_setup['images'][1],
                        'filename': 'test_1.jpg',
                        'web_path': '../photos/test_1.jpg',
                        'focal_length': 50.0,
                        'orientation': 'portrait',
                        'date_taken': '2024-01-15T14:20:00'
                    }
                ]
            },
            {
                'slate': 'family_2024',
                'images': [
                    {
                        'original_path': gallery_setup['images'][2],
                        'filename': 'test_2.jpg',
                        'web_path': '../photos/test_2.jpg',
                        'focal_length': 35.0,
                        'orientation': 'landscape',
                        'date_taken': '2024-02-10T09:00:00'
                    }
                ]
            }
        ]
    
    def test_generate_html_gallery_basic(self, gallery_setup, sample_gallery_data, status_collector):
        """Test basic gallery generation with real files and callbacks."""
        focal_data = [
            {'value': 35.0, 'count': 2},
            {'value': 50.0, 'count': 1}
        ]
        date_data = [
            {'value': '2024-01-15', 'count': 2},
            {'value': '2024-02-10', 'count': 1}
        ]
        
        success = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=focal_data,
            date_data=date_data,
            template_path=gallery_setup['template_path'],
            output_dir=gallery_setup['output_dir'],
            root_dir=gallery_setup['root_dir'],
            status_callback=status_collector
        )
        
        # Verify success
        assert success is True
        
        # Verify status messages were collected
        assert status_collector.call_count > 0
        assert status_collector.has_message("Gallery generated at")
        
        # Verify output file exists and contains expected content
        output_file = Path(gallery_setup['output_dir']) / 'index.html'
        assert output_file.exists()
        
        content = output_file.read_text()
        assert 'vacation_2024' in content
        assert 'family_2024' in content
        assert '35.0mm (2)' in content or '35mm (2)' in content
        assert '50.0mm (1)' in content or '50mm (1)' in content
        assert 'test_0.jpg' in content
        assert 'test_1.jpg' in content
        assert 'test_2.jpg' in content
    
    def test_generate_html_gallery_empty_data(self, gallery_setup, status_collector):
        """Test gallery generation with empty data."""
        success = generate_html_gallery(
            gallery_data=[],
            focal_length_data=[],
            date_data=[],
            template_path=gallery_setup['template_path'],
            output_dir=gallery_setup['output_dir'],
            root_dir=gallery_setup['root_dir'],
            status_callback=status_collector
        )
        
        assert success is True
        assert status_collector.has_message("Gallery generated at")
        
        # Output file should exist but have no gallery items
        output_file = Path(gallery_setup['output_dir']) / 'index.html'
        assert output_file.exists()
        
        content = output_file.read_text()
        assert '<section class="slate"' not in content
    
    def test_generate_html_gallery_creates_output_directory(self, gallery_setup, status_collector):
        """Test that output directory is created if it doesn't exist."""
        # Use non-existent output directory
        new_output = str(Path(gallery_setup['output_dir']).parent / 'new_output')
        
        assert not Path(new_output).exists()
        
        success = generate_html_gallery(
            gallery_data=[],
            focal_length_data=[],
            date_data=[],
            template_path=gallery_setup['template_path'],
            output_dir=new_output,
            root_dir=gallery_setup['root_dir'],
            status_callback=status_collector
        )
        
        assert success is True
        assert Path(new_output).exists()
    
    def test_generate_html_gallery_invalid_template(self, gallery_setup, status_collector, caplog):
        """Test handling of invalid template with real template error."""
        # Create template with syntax error
        bad_template = Path(gallery_setup['template_path']).parent / 'bad.html'
        bad_template.write_text('{{ unclosed_variable')
        
        success = generate_html_gallery(
            gallery_data=[],
            focal_length_data=[],
            date_data=[],
            template_path=str(bad_template),
            output_dir=gallery_setup['output_dir'],
            root_dir=gallery_setup['root_dir'],
            status_callback=status_collector
        )
        
        # Should fail gracefully
        assert success is False
        
        # Should log the template error
        assert "template" in caplog.text.lower() or "error" in caplog.text.lower()
    
    def test_generate_html_gallery_nonexistent_template(self, gallery_setup, status_collector, caplog):
        """Test handling of nonexistent template file."""
        nonexistent = str(Path(gallery_setup['template_path']).parent / 'nonexistent.html')
        
        success = generate_html_gallery(
            gallery_data=[],
            focal_length_data=[],
            date_data=[],
            template_path=nonexistent,
            output_dir=gallery_setup['output_dir'],
            root_dir=gallery_setup['root_dir'],
            status_callback=status_collector
        )
        
        assert success is False
        assert "error" in caplog.text.lower()
    
    def test_generate_html_gallery_unicode_handling(self, gallery_setup, status_collector):
        """Test unicode characters in gallery data."""
        unicode_data = [
            {
                'slate': '写真_collection',
                'images': [
                    {
                        'original_path': gallery_setup['images'][0],
                        'filename': 'фото.jpg',
                        'web_path': '../photos/фото.jpg',
                        'focal_length': 50.0,
                        'orientation': 'landscape',
                        'date_taken': None
                    }
                ]
            }
        ]
        
        success = generate_html_gallery(
            gallery_data=unicode_data,
            focal_length_data=[],
            date_data=[],
            template_path=gallery_setup['template_path'],
            output_dir=gallery_setup['output_dir'],
            root_dir=gallery_setup['root_dir'],
            status_callback=status_collector
        )
        
        assert success is True
        
        output_file = Path(gallery_setup['output_dir']) / 'index.html'
        content = output_file.read_text(encoding='utf-8')
        assert '写真_collection' in content
        assert 'фото.jpg' in content
    
    def test_generate_html_gallery_concurrent_callbacks(self, gallery_setup, sample_gallery_data):
        """Test that multiple callbacks can be used concurrently."""
        collectors = [StatusCollector() for _ in range(3)]
        
        for collector in collectors:
            success = generate_html_gallery(
                gallery_data=sample_gallery_data,
                focal_length_data=[],
                date_data=[],
                template_path=gallery_setup['template_path'],
                output_dir=gallery_setup['output_dir'],
                root_dir=gallery_setup['root_dir'],
                status_callback=collector
            )
            assert success is True
        
        # Each collector should have received messages
        for collector in collectors:
            assert collector.call_count > 0
            assert collector.has_message("Gallery generated at")
    
    def test_status_callback_exception_handling(self, gallery_setup, sample_gallery_data, caplog):
        """Test that exceptions in status callback don't break generation."""
        def faulty_callback(message):
            if "Processing" in message:
                raise ValueError("Intentional callback error")
        
        # Should complete despite callback errors
        success = generate_html_gallery(
            gallery_data=sample_gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=gallery_setup['template_path'],
            output_dir=gallery_setup['output_dir'],
            root_dir=gallery_setup['root_dir'],
            status_callback=faulty_callback
        )
        
        # Generation should still succeed
        assert success is True
        
        # Output file should exist
        output_file = Path(gallery_setup['output_dir']) / 'index.html'
        assert output_file.exists()


class TestGalleryGeneratorIntegration:
    """Integration tests with real file system operations."""
    
    def test_large_gallery_generation(self, tmp_path):
        """Test generation with many images."""
        from PIL import Image
        
        # Set up directories
        root_dir = tmp_path / "large_gallery"
        output_dir = tmp_path / "output"
        root_dir.mkdir()
        
        # Create template
        template_file = tmp_path / "template.html"
        template_file.write_text('''<!DOCTYPE html>
<html><body>
{% for slate in gallery %}
    <h2>{{ slate.slate }}</h2>
    <p>{{ slate.images|length }} images</p>
{% endfor %}
<p>Total slates: {{ gallery|length }}</p>
</body></html>''')
        
        # Create multiple slates with many images
        gallery_data = []
        for slate_idx in range(5):
            slate_dir = root_dir / f"slate_{slate_idx}"
            slate_dir.mkdir()
            
            images = []
            for img_idx in range(20):
                img_path = slate_dir / f"img_{img_idx}.jpg"
                img = Image.new('RGB', (50, 50), 'blue')
                img.save(img_path)
                
                images.append({
                    'original_path': str(img_path),
                    'filename': f'img_{img_idx}.jpg',
                    'web_path': f'../slate_{slate_idx}/img_{img_idx}.jpg',
                    'focal_length': 35.0 + img_idx,
                    'orientation': 'landscape' if img_idx % 2 == 0 else 'portrait',
                    'date_taken': f'2024-01-{img_idx+1:02d}T10:00:00'
                })
            
            gallery_data.append({
                'slate': f'slate_{slate_idx}',
                'images': images
            })
        
        # Generate gallery
        collector = StatusCollector()
        success = generate_html_gallery(
            gallery_data=gallery_data,
            focal_length_data=[],
            date_data=[],
            template_path=str(template_file),
            output_dir=str(output_dir),
            root_dir=str(root_dir),
            status_callback=collector
        )
        
        assert success is True
        
        # Verify output
        output_file = output_dir / 'index.html'
        content = output_file.read_text()
        assert 'Total slates: 5' in content
        assert '20 images' in content