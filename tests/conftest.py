"""Test configuration for SlateGallery tests."""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory with test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)

        # Create some test image files (empty files for testing)
        (test_dir / "test_images").mkdir()
        (test_dir / "test_images" / "image1.jpg").write_bytes(b"fake_image_data")
        (test_dir / "test_images" / "image2.png").write_bytes(b"fake_image_data")
        (test_dir / "test_images" / "image3.tiff").write_bytes(b"fake_image_data")

        # Create config directory
        (test_dir / "config").mkdir()

        yield test_dir


@pytest.fixture
def mock_status_callback():
    """Mock status callback function that captures messages."""
    messages = []

    def callback(message):
        messages.append(message)

    callback.messages = messages
    return callback
