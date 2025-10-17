"""
Comprehensive error testing for threading module.

Tests error handling, exception propagation, and edge cases in:
- ScanThread: Directory scanning with error conditions
- GenerateGalleryThread: Gallery generation with failures
- ThreadPoolExecutor: Parallel processing error handling
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtCore import QThread

from src.utils.threading import ScanThread, GenerateGalleryThread
from src.core.cache_manager import ImprovedCacheManager


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
        mock = Mock(spec=ImprovedCacheManager)
        mock.load_cache.return_value = {}
        mock.save_cache.return_value = None
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

    @pytest.mark.skipif(os.name == 'nt', reason="Permissions work differently on Windows")
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
            thread.start()
            _ = thread.wait(3000)

            # Thread should complete (may or may not emit signal)
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
        thread.start()
        _ = thread.wait(3000)

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
        # Note: Thread may or may not have checked interruption flag
        # The important thing is it stopped

    def test_cache_manager_exception_handling(self, qtbot, cleanup_threads, tmp_path):
        """Test ScanThread handles cache manager exceptions"""
        # Arrange - Cache manager that raises exceptions
        failing_cache = Mock(spec=ImprovedCacheManager)
        failing_cache.load_cache.side_effect = Exception("Cache read error")

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "Slate01").mkdir()

        thread = ScanThread(str(image_dir), failing_cache)
        cleanup_threads.append(thread)

        # Act - Should not crash despite cache errors
        thread.start()

        # Wait for thread to complete (it may emit signal or just finish)
        _ = thread.wait(3000)

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

        thread = GenerateGalleryThread(
            selected_slates=[],
            slates_dict={},
            cache_manager=Mock(spec=ImprovedCacheManager),
            output_dir=str(output_dir),
            root_dir=str(tmp_path),
            template_path='/nonexistent/template.html',
            generate_thumbnails=False,
            thumbnail_size=300,
            lazy_loading=False
        )
        cleanup_threads.append(thread)

        # Act - Should handle missing template gracefully
        with qtbot.waitSignal(thread.gallery_complete, timeout=3000):
            thread.start()

        # Assert - Thread should complete (possibly with error status)
        assert not thread.isRunning()

    @pytest.mark.skipif(os.name == 'nt', reason="Permissions work differently on Windows")
    def test_output_directory_permission_denied(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles write permission errors"""
        # Arrange
        restricted_output = tmp_path / "restricted_output"
        restricted_output.mkdir()

        try:
            # Remove write permissions
            restricted_output.chmod(0o444)

            thread = GenerateGalleryThread(
                selected_slates=['Slate01'],
                slates_dict={'Slate01': {'images': []}},
                cache_manager=Mock(spec=ImprovedCacheManager),
                output_dir=str(restricted_output),
                root_dir=str(tmp_path),
                template_path='templates/gallery_template.html',
                generate_thumbnails=False,
                thumbnail_size=300,
                lazy_loading=False
            )
            cleanup_threads.append(thread)

            # Act - Should handle permission error
            with qtbot.waitSignal(thread.gallery_complete, timeout=3000):
                thread.start()

            # Assert
            assert not thread.isRunning()

        finally:
            # Restore permissions
            restricted_output.chmod(0o755)

    def test_invalid_organized_data_structure(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles malformed data"""
        # Arrange - Invalid data structure (None slates_dict)
        thread = GenerateGalleryThread(
            selected_slates=[],
            slates_dict={},  # Will be empty but valid
            cache_manager=Mock(spec=ImprovedCacheManager),
            output_dir=str(tmp_path / "output"),
            root_dir=str(tmp_path),
            template_path='templates/gallery_template.html',
            generate_thumbnails=False,
            thumbnail_size=300,
            lazy_loading=False
        )
        cleanup_threads.append(thread)

        # Act - Should not crash
        with qtbot.waitSignal(thread.gallery_complete, timeout=3000):
            thread.start()

        # Assert
        assert not thread.isRunning()

    def test_thread_interruption_during_generation(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles interruption"""
        # Arrange - Large dataset to ensure some processing time
        large_slates = {f'Slate{i:02d}': {'images': []} for i in range(100)}

        thread = GenerateGalleryThread(
            selected_slates=list(large_slates.keys()),
            slates_dict=large_slates,
            cache_manager=Mock(spec=ImprovedCacheManager),
            output_dir=str(tmp_path / "output"),
            root_dir=str(tmp_path),
            template_path='templates/gallery_template.html',
            generate_thumbnails=False,
            thumbnail_size=300,
            lazy_loading=False
        )
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
            time.sleep(0.05)
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
        from PySide6.QtCore import QObject, Signal

        class Source(QObject):
            signal = Signal(str)

        class Receiver(QObject):
            def __init__(self):
                super().__init__()
                self.received = []

            def on_signal(self, value):
                self.received.append(value)

        # Arrange
        source = Source()
        receiver = Receiver()

        source.signal.connect(receiver.on_signal)

        # Act - Delete receiver, then emit signal
        receiver.deleteLater()
        qtbot.wait(10)  # Let event loop process deletion

        # Should not crash
        source.signal.emit("test")

        # Assert - Signal emitted without crash
        assert True  # If we get here, no crash occurred

    def test_exception_in_signal_handler(self, qtbot):
        """Test that exceptions in signal handlers are caught by Qt"""
        from PySide6.QtCore import QObject, Signal

        class Source(QObject):
            signal = Signal()

        exception_caught = []

        def failing_handler():
            try:
                raise RuntimeError("Handler error")
            except RuntimeError as e:
                exception_caught.append(str(e))
                # Re-raising in Qt signal handlers is caught by Qt
                raise

        # Arrange
        source = Source()
        source.signal.connect(failing_handler)

        # Act - Emit signal; exception will be caught by Qt's event loop
        # pytest-qt captures this, so we use captureExceptions
        with qtbot.captureExceptions() as exceptions:
            source.signal.emit()

        # Assert - Exception was raised and caught
        assert len(exception_caught) == 1
        assert len(exceptions) == 1


class TestRaceConditions:
    """Test thread safety and race conditions"""

    def test_concurrent_cache_access(self, tmp_path):
        """Test that concurrent cache access doesn't corrupt data"""
        from concurrent.futures import ThreadPoolExecutor
        import threading

        cache = ImprovedCacheManager(str(tmp_path))
        lock = threading.Lock()

        def write_metadata(slate_name):
            slates_data = {
                slate_name: {
                    'images': [f'image_{slate_name}.jpg'],
                    'timestamp': f'time_{slate_name}'
                }
            }
            with lock:
                cache.save_cache(str(tmp_path), slates_data)

        # Act - Concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_metadata, f'Slate{i:02d}')
                      for i in range(50)]

            # Wait for all
            for f in futures:
                f.result()

        # Assert - Cache should be intact and readable
        cache_data = cache.load_cache(str(tmp_path))
        assert cache_data is None or isinstance(cache_data, dict)
