"""Test configuration for SlateGallery tests."""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Add tests directory to path for shared_fixtures
tests_path = Path(__file__).parent
sys.path.insert(0, str(tests_path))

# Import shared fixtures to make them available to all tests
from shared_fixtures import create_test_image  # noqa: E402


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory with test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)

        # Create some test image files using shared fixture
        (test_dir / "test_images").mkdir()
        create_test_image(test_dir / "test_images" / "image1.jpg")
        create_test_image(test_dir / "test_images" / "image2.png")
        create_test_image(test_dir / "test_images" / "image3.tiff")

        # Create config directory
        (test_dir / "config").mkdir()

        yield test_dir
