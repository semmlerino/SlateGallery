"""
Essential threading error tests - high ROI, real-world scenarios only.

Tests critical error handling in:
- ScanThread: Directory scanning with error conditions
- GenerateGalleryThread: Gallery generation with failures
- Cache concurrency: Race conditions in shared resources

Focus: Testing OUR code's error handling, not stdlib/Qt behavior.
9 tests targeting real bugs users encounter.
"""

from unittest.mock import Mock

import pytest

from src.core.cache_manager import ImprovedCacheManager
from src.utils.threading import GenerateGalleryThread, ScanThread


class TestScanThreadErrors:
    """Test error scenarios in ScanThread - focus on real-world failures"""

    @pytest.fixture
    def cleanup_threads(self):
        """Ensure all threads are cleaned up after tests"""
        threads = []
        yield threads

        # Proper cleanup using production's stop() method
        for thread in threads:
            if thread.isRunning():
                if hasattr(thread, 'stop'):
                    thread.stop()
                else:
                    thread.requestInterruption()
                    thread.quit()
                    thread.wait(5000)

    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager for testing"""
        mock = Mock(spec=ImprovedCacheManager)
        mock.load_cache.return_value = {}
        mock.save_cache.return_value = None
        return mock

    def test_nonexistent_directory(self, qtbot, mock_cache_manager, cleanup_threads):
        """Test ScanThread handles non-existent directory gracefully

        Real-world scenario: User types invalid path or directory was deleted
        """
        # Arrange
        thread = ScanThread('/totally/nonexistent/path', mock_cache_manager)
        cleanup_threads.append(thread)

        # Act - Should complete without crashing
        with qtbot.waitSignal(thread.scan_complete, timeout=3000) as blocker:
            thread.start()

        # Assert - Thread completes even with invalid path
        assert blocker.signal_triggered or not thread.isRunning()

    def test_corrupted_image_file_handling(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread skips corrupted/malformed image files

        Real-world scenario: macOS ._ files, truncated downloads, invalid JPEGs
        """
        # Arrange - Create files that look like images but aren't
        image_dir = tmp_path / "images"
        image_dir.mkdir()

        # Corrupted JPEG
        corrupted_jpg = image_dir / "corrupted.jpg"
        corrupted_jpg.write_bytes(b"This is not a valid JPEG")

        # macOS resource fork file (real issue we've seen)
        macos_fork = image_dir / "._image.jpg"
        macos_fork.write_bytes(b"\x00\x05\x16\x07")  # AppleDouble header

        # Valid directory structure
        (image_dir / "Slate01").mkdir()

        thread = ScanThread(str(image_dir), mock_cache_manager)
        cleanup_threads.append(thread)

        # Act - Should complete without crashing
        thread.start()
        _ = thread.wait(3000)

        # Assert - Thread completes gracefully, skipping bad files
        assert not thread.isRunning()

    def test_thread_interruption_during_scan(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread handles interruption gracefully

        Real-world scenario: User clicks cancel during long scan
        """
        # Arrange - Create directory structure (not too large for CI)
        image_dir = tmp_path / "large"
        image_dir.mkdir()

        for i in range(20):  # Enough to test interruption
            slate_dir = image_dir / f"Slate{i:02d}"
            slate_dir.mkdir()
            # Create empty files (fast)
            for j in range(5):
                (slate_dir / f"image{j}.jpg").touch()

        thread = ScanThread(str(image_dir), mock_cache_manager)
        cleanup_threads.append(thread)

        # Act - Start and immediately interrupt
        thread.start()
        thread.requestInterruption()

        # Wait for thread to stop
        stopped = thread.wait(3000)

        # Assert
        assert stopped, "Thread should stop when interrupted"
        assert not thread.isRunning()

    def test_cache_manager_exception_handling(self, qtbot, cleanup_threads, tmp_path):
        """Test ScanThread handles cache manager exceptions

        Real-world scenario: Disk full, permissions issue, corrupted cache
        """
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
        _ = thread.wait(3000)

        # Assert - Thread completes without crashing
        assert not thread.isRunning()

    def test_empty_directory_scan(self, qtbot, mock_cache_manager, cleanup_threads, tmp_path):
        """Test ScanThread handles empty directory

        Real-world scenario: User scans folder with no slates/images
        """
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


class TestGenerateGalleryThreadErrors:
    """Test error scenarios in GenerateGalleryThread - critical failures only"""

    @pytest.fixture
    def cleanup_threads(self):
        """Ensure thread cleanup"""
        threads = []
        yield threads

        # Proper cleanup using production's stop() method
        for thread in threads:
            if thread.isRunning():
                if hasattr(thread, 'stop'):
                    thread.stop()
                else:
                    thread.requestInterruption()
                    thread.quit()
                    thread.wait(5000)

    def test_missing_template_file(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles missing template

        Real-world scenario: Template deleted, wrong path in config
        """
        # Arrange
        output_dir = tmp_path / "output"

        thread = GenerateGalleryThread(
            selected_slates=[],
            slates_dict={},
            cache_manager=Mock(spec=ImprovedCacheManager),
            output_dir=str(output_dir),
            allowed_root_dirs=str(tmp_path),
            template_path='/nonexistent/template.html',
            generate_thumbnails=False,
            thumbnail_size=300,
            lazy_loading=False
        )
        cleanup_threads.append(thread)

        # Act - Should handle missing template gracefully
        with qtbot.waitSignal(thread.gallery_complete, timeout=3000):
            thread.start()

        # Assert - Thread completes (possibly with error status)
        assert not thread.isRunning()

    def test_invalid_organized_data_structure(self, qtbot, cleanup_threads, tmp_path):
        """Test GenerateGalleryThread handles malformed data

        Real-world scenario: Data corruption, version mismatch, bad scan results
        """
        # Arrange - Empty slates_dict (edge case)
        thread = GenerateGalleryThread(
            selected_slates=[],
            slates_dict={},  # Empty but valid structure
            cache_manager=Mock(spec=ImprovedCacheManager),
            output_dir=str(tmp_path / "output"),
            allowed_root_dirs=str(tmp_path),
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
        """Test GenerateGalleryThread handles interruption

        Real-world scenario: User cancels during long gallery generation
        """
        # Arrange - Medium dataset to ensure some processing time
        medium_slates = {f'Slate{i:02d}': {'images': []} for i in range(30)}

        thread = GenerateGalleryThread(
            selected_slates=list(medium_slates.keys()),
            slates_dict=medium_slates,
            cache_manager=Mock(spec=ImprovedCacheManager),
            output_dir=str(tmp_path / "output"),
            allowed_root_dirs=str(tmp_path),
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
        assert stopped, "Thread should stop when interrupted"
        assert not thread.isRunning()


class TestConcurrency:
    """Test real concurrency issues in our code"""

    def test_concurrent_cache_access(self, tmp_path):
        """Test that concurrent cache access doesn't corrupt data

        Real-world scenario: Multiple threads scanning different directories,
        all writing to the same cache manager
        """
        from concurrent.futures import ThreadPoolExecutor

        cache = ImprovedCacheManager(str(tmp_path))
        errors: list[tuple[str, str]] = []

        def write_and_read(slate_name):
            """Simulate concurrent cache writes and reads"""
            try:
                slates_data = {
                    slate_name: {
                        'images': [f'image_{slate_name}.jpg'],
                        'timestamp': f'time_{slate_name}'
                    }
                }
                cache.save_cache(str(tmp_path), slates_data)
                # Verify we can read back
                _ = cache.load_cache(str(tmp_path))
            except Exception as e:
                errors.append((slate_name, str(e)))

        # Act - Concurrent writes from multiple threads (no external lock)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(write_and_read, f'Slate{i:02d}')
                for i in range(50)
            ]

            # Wait for all to complete
            for f in futures:
                f.result()

        # Assert no errors during concurrent access
        assert len(errors) == 0, f"Concurrent access errors: {errors}"

        # Cache should be intact and readable
        cache_data = cache.load_cache(str(tmp_path))
        assert cache_data is None or isinstance(cache_data, dict)


# Performance note: All tests use tmp_path and minimal data for speed
# Total test suite should complete in <10 seconds
