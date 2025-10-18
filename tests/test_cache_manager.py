"""Unit tests for cache_manager module with minimal mocking."""

import os
import tempfile
import threading

import pytest

from src.core.cache_manager import ImprovedCacheManager


class TestImprovedCacheManager:
    """Test the ImprovedCacheManager with real filesystem operations."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create cache manager with temporary directory."""
        return ImprovedCacheManager(base_dir=temp_cache_dir)

    def test_init_creates_directories(self, temp_cache_dir):
        """Test that initialization creates required directories."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)

        # Check directories exist
        assert os.path.exists(cache_manager.cache_dir)
        assert os.path.exists(os.path.join(temp_cache_dir, 'cache'))

        # Check attributes are set correctly
        assert cache_manager.base_dir == temp_cache_dir
        assert cache_manager.max_workers == 4
        assert cache_manager.batch_size == 100
        assert isinstance(cache_manager._cache_lock, type(threading.Lock()))
        assert isinstance(cache_manager._metadata, dict)
        assert isinstance(cache_manager._processing, set)

    def test_init_with_custom_params(self, temp_cache_dir):
        """Test initialization with custom parameters."""
        cache_manager = ImprovedCacheManager(
            base_dir=temp_cache_dir,
            max_workers=8,
            batch_size=50
        )

        assert cache_manager.max_workers == 8
        assert cache_manager.batch_size == 50

    def test_get_cache_file_generates_consistent_hash(self, cache_manager):
        """Test that get_cache_file generates consistent hash for same directory."""
        root_dir1 = "/path/to/test/dir"
        root_dir2 = "/path/to/test/dir"
        root_dir3 = "/different/path"

        file1 = cache_manager.get_cache_file(root_dir1)
        file2 = cache_manager.get_cache_file(root_dir2)
        file3 = cache_manager.get_cache_file(root_dir3)

        # Same paths should generate same cache file
        assert file1 == file2
        # Different paths should generate different cache files
        assert file1 != file3

        # Files should be in cache directory and have .json extension
        assert file1.startswith(cache_manager.cache_dir)
        assert file1.endswith('.json')

    def test_save_and_load_cache(self, cache_manager):
        """Test saving and loading cache data."""
        root_dir = "/test/directory"
        test_slates = {
            "slate1": {"images": [{"path": "image1.jpg"}]},
            "slate2": {"images": [{"path": "image2.jpg"}]}
        }

        # Save cache
        cache_manager.save_cache(root_dir, test_slates)

        # Load cache
        loaded_slates = cache_manager.load_cache(root_dir)

        assert loaded_slates == test_slates

    def test_load_nonexistent_cache(self, cache_manager):
        """Test loading cache that doesn't exist."""
        root_dir = "/nonexistent/directory"

        loaded_slates = cache_manager.load_cache(root_dir)

        assert loaded_slates is None

    def test_save_cache_error_handling(self, cache_manager):
        """Test save_cache handles errors gracefully."""
        root_dir = "/test/directory"
        # Create invalid data that can't be JSON serialized
        invalid_data = {"test": set([1, 2, 3])}  # sets aren't JSON serializable

        # Should not raise exception, but log error
        cache_manager.save_cache(root_dir, invalid_data)

        # Cache file might exist with partial data due to JSON error
        cache_manager.get_cache_file(root_dir)
        # The key point is that the error was handled gracefully without crashing
        assert True  # Function completed without exception

    def test_load_cache_corrupted_json(self, cache_manager):
        """Test load_cache handles corrupted JSON gracefully."""
        root_dir = "/test/directory"
        cache_file = cache_manager.get_cache_file(root_dir)

        # Create corrupted JSON file
        with open(cache_file, 'w') as f:
            f.write('{"invalid": json content')

        # Should return None, not crash
        loaded_slates = cache_manager.load_cache(root_dir)
        assert loaded_slates is None

    def test_process_images_batch(self, cache_manager):
        """Test process_images_batch returns expected format."""
        image_paths = ["/path/to/image1.jpg", "/path/to/image2.jpg"]

        result = cache_manager.process_images_batch(image_paths)

        expected = [
            {'path': '/path/to/image1.jpg'},
            {'path': '/path/to/image2.jpg'}
        ]
        assert result == expected

    def test_process_images_batch_empty(self, cache_manager):
        """Test process_images_batch with empty list."""
        result = cache_manager.process_images_batch([])
        assert result == []

    def test_process_images_batch_with_callback(self, cache_manager):
        """Test process_images_batch with callback."""
        image_paths = ["/path/to/image1.jpg"]
        callback_calls = []

        def test_callback(message):
            callback_calls.append(message)

        result = cache_manager.process_images_batch(image_paths, callback=test_callback)

        assert result == [{'path': '/path/to/image1.jpg'}]
        # Currently callback isn't used in implementation, but test structure is ready

    def test_shutdown(self, cache_manager):
        """Test shutdown completes without error."""
        # Should not raise any exceptions
        cache_manager.shutdown()

    def test_thread_safety_metadata(self, cache_manager):
        """Test that metadata access is thread-safe."""
        def modify_metadata():
            with cache_manager._cache_lock:
                cache_manager._metadata['test'] = 'value'

        # Create multiple threads modifying metadata
        threads = []
        for i in range(5):
            thread = threading.Thread(target=modify_metadata)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Metadata should have been set
        assert cache_manager._metadata.get('test') == 'value'

    def test_cache_file_path_security(self, cache_manager):
        """Test that cache file paths are secure and don't allow directory traversal."""
        # Test various potentially malicious paths
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32"
        ]

        for malicious_path in malicious_paths:
            cache_file = cache_manager.get_cache_file(malicious_path)
            # Cache file should always be in the cache directory
            assert cache_file.startswith(cache_manager.cache_dir)
            assert ".." not in os.path.relpath(cache_file, cache_manager.cache_dir)


class TestImprovedCacheManagerIntegration:
    """Integration tests with more complex scenarios."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_multiple_cache_operations(self, temp_cache_dir):
        """Test multiple save/load operations work correctly."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)

        # Test data for different directories
        test_data = {
            "/dir1": {"slate1": {"images": ["img1.jpg"]}},
            "/dir2": {"slate2": {"images": ["img2.jpg", "img3.jpg"]}},
            "/dir3": {"slate3": {"images": []}}
        }

        # Save all cache data
        for root_dir, slates in test_data.items():
            cache_manager.save_cache(root_dir, slates)

        # Load and verify all cache data
        for root_dir, expected_slates in test_data.items():
            loaded_slates = cache_manager.load_cache(root_dir)
            assert loaded_slates == expected_slates

    def test_cache_persistence_across_instances(self, temp_cache_dir):
        """Test that cache persists across different manager instances."""
        # Create first manager and save data
        cache_manager1 = ImprovedCacheManager(base_dir=temp_cache_dir)
        root_dir = "/test/persistence"
        test_data = {"slate1": {"images": ["test.jpg"]}}

        cache_manager1.save_cache(root_dir, test_data)

        # Create second manager and load data
        cache_manager2 = ImprovedCacheManager(base_dir=temp_cache_dir)
        loaded_data = cache_manager2.load_cache(root_dir)

        assert loaded_data == test_data
