"""Shared fixtures and utilities for tests to reduce duplication."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image


class StatusCollector:
    """Reusable status callback collector for testing."""

    def __init__(self):
        self.messages = []
        self.call_count = 0

    def __call__(self, message):
        """Act as a callable to collect status messages."""
        self.messages.append(message)
        self.call_count += 1

    def has_message(self, substring):
        """Check if any message contains the substring."""
        return any(substring.lower() in msg.lower() for msg in self.messages)

    def clear(self):
        """Clear collected messages."""
        self.messages = []
        self.call_count = 0


def create_test_image(path, size=(100, 100), mode='RGB', color='blue',
                     focal_length=None, date_taken=None, orientation=None):
    """Create a test image with optional EXIF data.

    Args:
        path: Path to save the image
        size: Tuple of (width, height)
        mode: PIL image mode (RGB, RGBA, L, P, etc.)
        color: Color for RGB mode or value for other modes
        focal_length: Optional focal length for EXIF
        date_taken: Optional datetime for EXIF
        orientation: Optional EXIF orientation (1-8)

    Returns:
        str: Path to the created image
    """
    path = Path(path)

    # Create the image
    if mode == 'RGB':
        img = Image.new(mode, size, color=color)
    elif mode == 'RGBA':
        img = Image.new(mode, size, color=(0, 0, 0, 0))
    elif mode == 'L':
        img = Image.new(mode, size, color=128)
    elif mode == 'P':
        img = Image.new(mode, size)
        img.putpalette([i//3 for i in range(768)])
    else:
        img = Image.new(mode, size)

    # Add EXIF data if requested and format supports it
    if (focal_length or date_taken or orientation) and path.suffix.lower() in ['.jpg', '.jpeg']:
        try:
            import piexif
            exif_dict = {"0th": {}, "Exif": {}}

            if orientation:
                exif_dict["0th"][piexif.ImageIFD.Orientation] = orientation

            if focal_length:
                exif_dict["Exif"][piexif.ExifIFD.FocalLength] = (int(focal_length), 1)

            if date_taken:
                date_str = date_taken.strftime('%Y:%m:%d %H:%M:%S')
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode('utf-8')
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_str.encode('utf-8')
                exif_dict["0th"][piexif.ImageIFD.DateTime] = date_str.encode('utf-8')

            exif_bytes = piexif.dump(exif_dict)
            img.save(path, 'JPEG', exif=exif_bytes, quality=95)
        except ImportError:
            # piexif not available, save without EXIF
            img.save(path, 'JPEG', quality=95)
    else:
        # Determine format from extension
        format_map = {
            '.png': 'PNG',
            '.gif': 'GIF',
            '.bmp': 'BMP',
            '.tiff': 'TIFF',
            '.tif': 'TIFF'
        }
        format = format_map.get(path.suffix.lower(), 'JPEG')
        img.save(path, format)

    return str(path)


@pytest.fixture
def temp_image_dir():
    """Create a temporary directory with test images."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)

        # Create subdirectories
        (base_path / "slate1").mkdir()
        (base_path / "slate2").mkdir()

        # Create test images
        create_test_image(base_path / "slate1" / "img1.jpg", focal_length=35)
        create_test_image(base_path / "slate1" / "img2.png")
        create_test_image(base_path / "slate2" / "img3.jpg", focal_length=50)

        yield base_path


@pytest.fixture
def gallery_template(tmp_path):
    """Create a standard gallery HTML template."""
    template_file = tmp_path / "gallery_template.html"
    template_file.write_text('''<!DOCTYPE html>
<html>
<head>
    <title>Photo Gallery</title>
    <style>
        .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
        .image { position: relative; }
        .image img { width: 100%; height: auto; }
    </style>
</head>
<body>
    <h1>Photo Gallery</h1>

    <div class="filters">
        {% if focal_lengths %}
        <h3>Focal Lengths:</h3>
        {% for focal in focal_lengths %}
        <button data-focal="{{ focal.value }}">{{ focal.value }}mm ({{ focal.count }})</button>
        {% endfor %}
        {% endif %}

        {% if dates %}
        <h3>Dates:</h3>
        {% for date in dates %}
        <button data-date="{{ date.value }}">{{ date.value }} ({{ date.count }})</button>
        {% endfor %}
        {% endif %}
    </div>

    <div class="gallery">
        {% for slate in gallery %}
        <section class="slate">
            <h2>{{ slate.slate }}</h2>
            {% for image in slate.images %}
            <div class="image">
                <img src="{{ image.web_path }}"
                     alt="{{ image.filename }}"
                     data-focal="{{ image.focal_length }}"
                     data-orientation="{{ image.orientation }}"
                     data-date="{{ image.date_taken }}">
                <p>{{ image.filename }}</p>
            </div>
            {% endfor %}
        </section>
        {% endfor %}
    </div>
</body>
</html>''')
    return str(template_file)


@pytest.fixture
def status_collector():
    """Create a status collector for callbacks."""
    return StatusCollector()


@pytest.fixture
def sample_gallery_data():
    """Create sample gallery data structure."""
    return [
        {
            'slate': 'vacation_2024',
            'images': [
                {
                    'original_path': '/photos/vacation/beach.jpg',
                    'filename': 'beach.jpg',
                    'web_path': '../photos/vacation/beach.jpg',
                    'focal_length': 24.0,
                    'orientation': 'landscape',
                    'date_taken': '2024-07-15T10:30:00'
                },
                {
                    'original_path': '/photos/vacation/sunset.jpg',
                    'filename': 'sunset.jpg',
                    'web_path': '../photos/vacation/sunset.jpg',
                    'focal_length': 35.0,
                    'orientation': 'landscape',
                    'date_taken': '2024-07-15T18:45:00'
                }
            ]
        }
    ]


@pytest.fixture
def real_cache_manager(tmp_path):
    """Create a real cache manager with temporary directory."""
    from src.core.cache_manager import ImprovedCacheManager
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return ImprovedCacheManager(base_dir=str(cache_dir))


@pytest.fixture
def test_config_env(tmp_path, monkeypatch):
    """Set up test environment for config testing."""
    config_dir = tmp_path / '.slate_gallery'
    config_dir.mkdir()
    config_file = config_dir / 'config.ini'

    # Monkeypatch the CONFIG_FILE path
    monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

    return config_file


def create_corrupted_image_file(path, corruption_type='truncated'):
    """Create various types of corrupted image files for testing.

    Args:
        path: Path to save the corrupted file
        corruption_type: Type of corruption ('truncated', 'invalid_header', 'random')

    Returns:
        str: Path to the corrupted file
    """
    path = Path(path)

    if corruption_type == 'truncated':
        # JPEG header followed by truncated data
        path.write_bytes(b'\xFF\xD8\xFF\xE0' + b'\x00' * 100)
    elif corruption_type == 'invalid_header':
        # Invalid magic bytes
        path.write_bytes(b'NOTANIMAGE' + b'\x00' * 1000)
    elif corruption_type == 'random':
        # Random binary data
        import random
        path.write_bytes(bytes(random.randint(0, 255) for _ in range(1000)))
    else:
        # Default: incomplete JPEG
        path.write_bytes(b'\xFF\xD8\xFF')

    return str(path)


def assert_thread_cleanup(thread, timeout=1000):
    """Helper to ensure Qt thread is properly cleaned up.

    Args:
        thread: QThread instance
        timeout: Maximum time to wait for thread to finish (ms)
    """
    if thread.isRunning():
        thread.quit()
        if not thread.wait(timeout):
            # Force terminate if still running
            thread.terminate()
            thread.wait()


# Test data generators

def generate_test_slates(base_dir, num_slates=3, images_per_slate=5):
    """Generate test slate directories with images.

    Args:
        base_dir: Base directory to create slates in
        num_slates: Number of slate directories to create
        images_per_slate: Number of images per slate

    Returns:
        dict: Slate structure compatible with SlateGallery
    """
    base_dir = Path(base_dir)
    slates = {}

    for i in range(num_slates):
        slate_name = f"slate_{i:02d}"
        slate_dir = base_dir / slate_name
        slate_dir.mkdir(parents=True, exist_ok=True)

        images = []
        for j in range(images_per_slate):
            img_path = slate_dir / f"img_{j:03d}.jpg"
            create_test_image(
                img_path,
                size=(200, 150),
                focal_length=24 + j * 10,
                date_taken=datetime(2024, 1, i+1, 10, j*10)
            )
            images.append(str(img_path))

        slates[slate_name] = {'images': images}

    return slates


def generate_large_test_dataset(base_dir, num_images=100):
    """Generate a large dataset for performance testing.

    Args:
        base_dir: Base directory for images
        num_images: Total number of images to create

    Returns:
        list: List of image paths
    """
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    images = []
    for i in range(num_images):
        # Vary image properties
        size = (100 + i % 100, 100 + i % 100)
        focal = 24 + (i % 10) * 5
        date = datetime(2024, 1 + i % 12, 1 + i % 28)

        img_path = base_dir / f"perf_test_{i:04d}.jpg"
        create_test_image(img_path, size=size, focal_length=focal, date_taken=date)
        images.append(str(img_path))

    return images
