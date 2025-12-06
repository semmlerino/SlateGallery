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


@pytest.fixture
def thread_cleanup(qtbot):  # type: ignore[no-untyped-def]
    """Register Qt threads for automatic cleanup after test.

    Usage:
        def test_example(thread_cleanup):
            thread = thread_cleanup(ScanThread(...))
            thread.start()
            # Thread will be cleaned up automatically after test
    """
    from typing import Any

    threads: list[Any] = []

    def register(thread: Any) -> Any:
        """Register a thread for cleanup."""
        threads.append(thread)
        return thread

    yield register

    # Cleanup all registered threads (reverse order for safety)
    for thread in reversed(threads):
        if thread.isRunning():
            thread.quit()
            if not thread.wait(1000):  # 1 second timeout
                thread.terminate()
                thread.wait()

    # Process pending Qt events to ensure clean state
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication.instance()
    if app:
        app.processEvents()
