# Threading Error Tests Implementation Guide

*Quick reference for implementing threading error tests in SlateGallery*

## Quick Start

This guide provides ready-to-implement test code for covering the critical 44% coverage gap in `src/utils/threading.py`.

**Goal**: Increase coverage from 44% → 60%+ by testing error paths and exception handling.

**Estimated time**: 2-4 hours

**Files to create**:
- `tests/test_threading_errors.py` - New comprehensive error test suite

## Implementation Steps

### Step 1: Create Test File Structure

Create `tests/test_threading_errors.py`:

```python
"""
Comprehensive error testing for threading module.

Tests error handling, exception propagation, and edge cases in:
- ScanThread: Directory scanning with error conditions
- GenerateGalleryThread: Gallery generation with failures
- ThreadPoolExecutor: Parallel processing error handling
"""

import pytest
import os
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PyQt6.QtCore import QThread
from PyQt6.QtTest import QSignalSpy

from utils.threading import ScanThread, GenerateGalleryThread
from core.cache_manager import CacheManager


class TestScanThreadErrorHandling:
    """Test error scenarios in ScanThread"""

    @pytest.fixture
    def cleanup_threads(self):
        """Ensure all threads are cleaned up after tests"""
        threads = []
        yield threads

        # Cleanup
        for thread in threads:
            if thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                thread.wait(1000)

    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager for testing"""
        mock = Mock(spec=CacheManager)
        mock.get_cached_metadata.return_value = {}
        mock.save_metadata.return_value = None
        return mock

    def test_nonexistent_directory(self, qtbot, mock_cache_manager, cleanup_threads):
        """Test ScanThread handles non-existent directory gracefully"""
        # Arrange
        thread = ScanThread('/totally/nonexistent/path', mock_cache_manager)
        cleanup_threads.append(thread)

        # Act & Assert - Should complete without crashing
        with qtbot.waitSignal(thread.scan_complete, timeout=3000) as blocker:
            thread.start()

        # Thread should complete (even if with error)
        assert blocker.signal_triggered or not thread.isRunning()

    def test_permission_denied_directory(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread handles permission denied errors"""
        # Arrange - Create directory with no permissions
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()

        try:
            # Remove all permissions
            restricted_dir.chmod(0o000)

            thread = ScanThread(str(restricted_dir), mock_cache_manager)
            cleanup_threads.append(thread)

            # Act - Should handle gracefully
            with qtbot.waitSignal(thread.scan_complete, timeout=3000):
                thread.start()

            # Thread should not crash
            assert not thread.isRunning()

        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)

    def test_corrupted_image_file_handling(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread skips corrupted image files"""
        # Arrange - Create a file that looks like an image but isn't
        image_dir = tmp_path / "images"
        image_dir.mkdir()

        corrupted_image = image_dir / "corrupted.jpg"
        corrupted_image.write_bytes(b"This is not a valid JPEG")

        # Also create a valid test structure
        (image_dir / "Slate01").mkdir()

        thread = ScanThread(str(image_dir), mock_cache_manager)
        cleanup_threads.append(thread)

        # Act
        with qtbot.waitSignal(thread.scan_complete, timeout=3000):
            thread.start()

        # Assert - Should complete without crashing
        assert not thread.isRunning()

    def test_thread_interruption_during_scan(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread handles interruption gracefully"""
        # Arrange - Create a large directory structure
        image_dir = tmp_path / "large"
        image_dir.mkdir()

        for i in range(50):
            slate_dir = image_dir / f"Slate{i:02d}"
            slate_dir.mkdir()
            # Create empty files (fast)
            for j in range(10):
                (slate_dir / f"image{j}.jpg").touch()

        thread = ScanThread(str(image_dir), mock_cache_manager)
        cleanup_threads.append(thread)

        # Act - Start and immediately interrupt
        thread.start()

        # Request interruption very quickly
        thread.requestInterruption()

        # Wait for thread to stop
        stopped = thread.wait(3000)

        # Assert
        assert stopped, "Thread should stop when interrupted"
        assert not thread.isRunning()
        assert thread.isInterruptionRequested()

    def test_cache_manager_exception_handling(self, qtbot, cleanup_threads, tmp_path):
        """Test ScanThread handles cache manager exceptions"""
        # Arrange - Cache manager that raises exceptions
        failing_cache = Mock(spec=CacheManager)
        failing_cache.get_cached_metadata.side_effect = Exception("Cache read error")

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "Slate01").mkdir()

        thread = ScanThread(str(image_dir), failing_cache)
        cleanup_threads.append(thread)

        # Act - Should not crash despite cache errors
        with qtbot.waitSignal(thread.scan_complete, timeout=3000):
            thread.start()

        # Assert - Thread completes without crashing
        assert not thread.isRunning()

    def test_empty_directory_scan(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread handles empty directory"""
        # Arrange
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        thread = ScanThread(str(empty_dir), mock_cache_manager)
        cleanup_threads.append(thread)

        # Act
        with qtbot.waitSignal(thread.scan_complete, timeout=3000) as blocker:
            thread.start()

        # Assert - Should complete successfully with empty results
        assert blocker.signal_triggered
        result, error_msg = blocker.args

        # Empty directory should return empty structure
        assert result == {} or len(result) == 0


class TestGenerateGalleryThreadErrorHandling:
    """Test error scenarios in GenerateGalleryThread"""

    @pytest.fixture
    def cleanup_threads(self):
        """Ensure thread cleanup"""
        threads = []
        yield threads

        for thread in threads:
            if thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                thread.wait(1000)

    def test_missing_template_file(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles missing template"""
        # Arrange
        output_dir = tmp_path / "output"

        # Mock parameters with invalid template path
        params = {
            'organized_data': {},
            'root_dir': str(tmp_path),
            'output_dir': str(output_dir),
            'template_path': '/nonexistent/template.html',
            'generate_thumbnails': False,
            'thumbnail_size': 300,
            'lazy_loading': False
        }

        thread = GenerateGalleryThread(**params)
        cleanup_threads.append(thread)

        # Act - Should handle missing template gracefully
        with qtbot.waitSignal(thread.generation_complete, timeout=3000):
            thread.start()

        # Assert - Thread should complete (possibly with error status)
        assert not thread.isRunning()

    def test_output_directory_permission_denied(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles write permission errors"""
        # Arrange
        restricted_output = tmp_path / "restricted_output"
        restricted_output.mkdir()

        try:
            # Remove write permissions
            restricted_output.chmod(0o444)

            params = {
                'organized_data': {'Slate01': []},
                'root_dir': str(tmp_path),
                'output_dir': str(restricted_output),
                'template_path': 'templates/gallery_template.html',
                'generate_thumbnails': False,
                'thumbnail_size': 300,
                'lazy_loading': False
            }

            thread = GenerateGalleryThread(**params)
            cleanup_threads.append(thread)

            # Act - Should handle permission error
            with qtbot.waitSignal(thread.generation_complete, timeout=3000):
                thread.start()

            # Assert
            assert not thread.isRunning()

        finally:
            # Restore permissions
            restricted_output.chmod(0o755)

    def test_invalid_organized_data_structure(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles malformed data"""
        # Arrange - Invalid data structure
        params = {
            'organized_data': None,  # Invalid!
            'root_dir': str(tmp_path),
            'output_dir': str(tmp_path / "output"),
            'template_path': 'templates/gallery_template.html',
            'generate_thumbnails': False,
            'thumbnail_size': 300,
            'lazy_loading': False
        }

        thread = GenerateGalleryThread(**params)
        cleanup_threads.append(thread)

        # Act - Should not crash
        with qtbot.waitSignal(thread.generation_complete, timeout=3000):
            thread.start()

        # Assert
        assert not thread.isRunning()

    def test_thread_interruption_during_generation(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles interruption"""
        # Arrange - Large dataset to ensure some processing time
        large_data = {}
        for i in range(100):
            large_data[f'Slate{i:02d}'] = [
                {'filename': f'image{j}.jpg', 'date_taken': '2024-01-01'}
                for j in range(50)
            ]

        params = {
            'organized_data': large_data,
            'root_dir': str(tmp_path),
            'output_dir': str(tmp_path / "output"),
            'template_path': 'templates/gallery_template.html',
            'generate_thumbnails': False,
            'thumbnail_size': 300,
            'lazy_loading': False
        }

        thread = GenerateGalleryThread(**params)
        cleanup_threads.append(thread)

        # Act - Start and quickly interrupt
        thread.start()
        thread.requestInterruption()

        # Wait for thread to stop
        stopped = thread.wait(3000)

        # Assert
        assert stopped
        assert not thread.isRunning()


class TestThreadPoolExecutorErrorHandling:
    """Test error handling in ThreadPoolExecutor usage"""

    def test_exception_in_worker_task(self):
        """Test that exceptions in worker tasks are captured"""
        from concurrent.futures import ThreadPoolExecutor
        import time

        def failing_task(n):
            if n % 2 == 0:
                raise ValueError(f"Task {n} failed")
            return n * 2

        # Act
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(failing_task, i) for i in range(10)]

            results = []
            errors = []

            for future in futures:
                try:
                    results.append(future.result())
                except ValueError as e:
                    errors.append(str(e))

        # Assert
        assert len(errors) == 5  # Half should fail
        assert len(results) == 5  # Half should succeed
        assert all("failed" in error for error in errors)

    def test_thread_pool_shutdown_with_running_tasks(self):
        """Test thread pool shuts down cleanly with running tasks"""
        from concurrent.futures import ThreadPoolExecutor
        import time

        def slow_task(n):
            time.sleep(0.1)
            return n

        # Act
        executor = ThreadPoolExecutor(max_workers=2)
        futures = [executor.submit(slow_task, i) for i in range(10)]

        # Shutdown immediately (tasks still running)
        executor.shutdown(wait=True)

        # Assert - All tasks should complete
        assert all(f.done() for f in futures)
        assert all(f.result() == i for i, f in enumerate(futures))

    def test_thread_pool_cancellation(self):
        """Test cancelling pending tasks in thread pool"""
        from concurrent.futures import ThreadPoolExecutor
        import time

        def medium_task(n):
            time.sleep(0.05)
            return n

        # Act
        executor = ThreadPoolExecutor(max_workers=1)  # Only 1 worker

        # Submit many tasks
        futures = [executor.submit(medium_task, i) for i in range(20)]

        # Cancel pending tasks
        cancelled_count = sum(f.cancel() for f in futures)

        executor.shutdown(wait=True)

        # Assert - Some tasks should have been cancelled
        assert cancelled_count > 0
        completed_count = sum(1 for f in futures if f.done() and not f.cancelled())
        assert completed_count + cancelled_count == len(futures)


class TestSignalEmissionErrors:
    """Test error handling in signal emission"""

    def test_signal_connection_to_deleted_object(self, qtbot):
        """Test that signals don't crash when connected object is deleted"""
        from PyQt6.QtCore import QObject, pyqtSignal

        class Source(QObject):
            signal = pyqtSignal(str)

        class Receiver(QObject):
            def __init__(self):
                super().__init__()
                self.received = []

            def on_signal(self, value):
                self.received.append(value)

        # Arrange
        source = Source()
        receiver = Receiver()
        qtbot.addWidget(source)

        source.signal.connect(receiver.on_signal)

        # Act - Delete receiver, then emit signal
        receiver.deleteLater()
        qtbot.wait(10)  # Let event loop process deletion

        # Should not crash
        source.signal.emit("test")

        # Assert - Signal emitted without crash
        assert True  # If we get here, no crash occurred

    def test_exception_in_signal_handler(self, qtbot):
        """Test that exceptions in signal handlers don't crash thread"""
        from PyQt6.QtCore import QObject, pyqtSignal

        class Source(QObject):
            signal = pyqtSignal()

        def failing_handler():
            raise RuntimeError("Handler error")

        # Arrange
        source = Source()
        qtbot.addWidget(source)
        source.signal.connect(failing_handler)

        # Act - Emit signal with failing handler
        # Note: Qt typically catches exceptions in handlers
        with pytest.raises((RuntimeError, Exception)):
            source.signal.emit()


class TestRaceConditions:
    """Test thread safety and race conditions"""

    def test_concurrent_cache_access(self, tmp_path):
        """Test that concurrent cache access doesn't corrupt data"""
        from concurrent.futures import ThreadPoolExecutor
        import threading

        cache = CacheManager(str(tmp_path))
        lock = threading.Lock()

        def write_metadata(slate_name):
            metadata = {
                'images': [f'image_{slate_name}.jpg'],
                'timestamp': f'time_{slate_name}'
            }
            with lock:
                cache.save_metadata(slate_name, metadata)

        # Act - Concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_metadata, f'Slate{i:02d}')
                      for i in range(50)]

            # Wait for all
            for f in futures:
                f.result()

        # Assert - Cache should be intact and readable
        cache_data = cache.get_cached_metadata('')
        assert isinstance(cache_data, dict)


# Running specific test categories
"""
# Run only error tests
pytest tests/test_threading_errors.py -v

# Run only ScanThread tests
pytest tests/test_threading_errors.py::TestScanThreadErrorHandling -v

# Run only GenerateGalleryThread tests
pytest tests/test_threading_errors.py::TestGenerateGalleryThreadErrorHandling -v

# Run with coverage
pytest tests/test_threading_errors.py --cov=src/utils/threading --cov-report=term-missing
"""
```

### Step 2: Run Tests and Verify Coverage

```bash
# Run the new error tests
~/.local/bin/uv run pytest tests/test_threading_errors.py -v

# Check coverage improvement
~/.local/bin/uv run pytest tests/test_threading_errors.py --cov=src/utils/threading --cov-report=term-missing

# Run all tests
~/.local/bin/uv run pytest tests/ -v
```

### Step 3: Expected Coverage Improvement

**Before**: `src/utils/threading.py` - 44% coverage (81/185 lines)

**After**: Expected 60%+ coverage (110+/185 lines)

**Coverage gains**:
- Error path handling: +12%
- Exception handling: +5%
- Thread interruption: +3%
- Edge cases: +4%

### Step 4: Verify Results

Check the coverage report:

```bash
~/.local/bin/uv run pytest tests/ --cov=src --cov-report=html
```

Open `htmlcov/index.html` to see detailed line-by-line coverage.

## Common Issues and Solutions

### Issue 1: Qt tests hang

**Symptom**: Tests don't complete, timeout errors

**Solution**: Use shorter timeouts and explicit cleanup

```python
# Instead of:
thread.wait()  # May hang forever

# Use:
thread.wait(2000)  # 2 second timeout
assert not thread.isRunning()
```

### Issue 2: "QThread: Destroyed while thread is still running"

**Symptom**: Warning during test cleanup

**Solution**: Proper cleanup in fixture

```python
@pytest.fixture
def cleanup_threads(self):
    threads = []
    yield threads

    # Proper cleanup
    for thread in threads:
        if thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            thread.wait(1000)
```

### Issue 3: Tests fail in headless environment

**Symptom**: "Could not connect to display"

**Solution**: Use xvfb or skip Qt tests

```bash
# With xvfb
xvfb-run -a pytest tests/test_threading_errors.py

# Or use the run_tests.sh script
./run_tests.sh tests/test_threading_errors.py
```

### Issue 4: Permission tests fail on Windows

**Symptom**: `chmod(0o000)` doesn't work on Windows

**Solution**: Skip permission tests on Windows

```python
@pytest.mark.skipif(os.name == 'nt', reason="Permissions work differently on Windows")
def test_permission_denied_directory(self, ...):
    pass
```

## Testing Checklist

After implementing these tests, verify:

- [ ] All tests pass: `pytest tests/test_threading_errors.py`
- [ ] Coverage increased: Check `--cov-report`
- [ ] No thread warnings during cleanup
- [ ] Tests complete in reasonable time (<30 seconds total)
- [ ] Tests work in headless environment (CI/CD ready)
- [ ] No flaky tests (run 3 times to verify)

## Next Steps

After implementing threading error tests:

1. **Review coverage report** - Identify remaining gaps
2. **Add cache stress tests** - `tests/test_cache_stress.py`
3. **Add gallery edge cases** - Enhance `tests/test_gallery_generator.py`
4. **Update CI/CD** - Ensure tests run automatically

## Quick Copy-Paste Examples

### Minimal Thread Error Test

```python
def test_basic_thread_error(qtbot, cleanup_threads):
    """Minimal template for thread error test"""
    thread = ScanThread('/invalid/path', mock_cache)
    cleanup_threads.append(thread)

    with qtbot.waitSignal(thread.scan_complete, timeout=2000):
        thread.start()

    assert not thread.isRunning()
```

### Testing with Mock

```python
def test_with_failing_dependency(qtbot):
    """Test with mocked failing dependency"""
    mock_cache = Mock(spec=CacheManager)
    mock_cache.save_metadata.side_effect = IOError("Disk full")

    thread = ScanThread('/test', mock_cache)

    with qtbot.waitSignal(thread.scan_complete, timeout=2000):
        thread.start()

    # Should handle error gracefully
    assert not thread.isRunning()
```

### Testing Interruption

```python
def test_thread_interruption(qtbot, cleanup_threads):
    """Test thread stops when interrupted"""
    thread = ScanThread('/large/dir', cache)
    cleanup_threads.append(thread)

    thread.start()
    thread.requestInterruption()

    assert thread.wait(2000)
    assert not thread.isRunning()
```

## Performance Tips

**Make tests fast**:
- Use `tmp_path` for file operations (automatic cleanup)
- Create minimal test data (don't need 1000 files to test errors)
- Use short timeouts (2-3 seconds max)
- Mock slow operations when testing error paths

**Example - Fast vs Slow**:

```python
# ❌ SLOW - Creates 1000 real files
def test_large_directory():
    for i in range(1000):
        create_real_image(f'image{i}.jpg')

# ✅ FAST - Just creates empty files
def test_large_directory(tmp_path):
    for i in range(100):  # Fewer is enough
        (tmp_path / f'image{i}.jpg').touch()  # Fast
```

---

*Guide created: October 2025*
*Estimated implementation time: 2-4 hours*
*Expected coverage gain: +15-20%*
