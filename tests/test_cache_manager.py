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
        invalid_data = {"test": {1, 2, 3}}  # sets aren't JSON serializable

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

        result = cache_manager.process_images_batch(image_paths, _callback=test_callback)

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
        for _i in range(5):
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


class TestCompositeCacheOperations:
    """Tests for multi-directory composite cache operations."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create cache manager with temporary directory."""
        return ImprovedCacheManager(base_dir=temp_cache_dir)

    @pytest.fixture
    def temp_image_dirs(self):
        """Create multiple temp directories simulating slate directories."""
        with tempfile.TemporaryDirectory() as base:
            dirs = []
            for i in range(3):
                dir_path = os.path.join(base, f"slate_{i}")
                os.makedirs(dir_path)
                dirs.append(dir_path)
            yield dirs

    # === get_composite_cache_file tests ===

    def test_composite_cache_file_consistent_hash(self, cache_manager):
        """Same directories generate same cache file."""
        dirs1 = ["/path/to/a", "/path/to/b", "/path/to/c"]
        dirs2 = ["/path/to/a", "/path/to/b", "/path/to/c"]

        file1 = cache_manager.get_composite_cache_file(dirs1)
        file2 = cache_manager.get_composite_cache_file(dirs2)

        assert file1 == file2
        assert file1.endswith(".json")
        assert "composite_" in file1

    def test_composite_cache_file_order_independent(self, cache_manager):
        """Different order generates same cache file (order-independent)."""
        dirs1 = ["/path/to/a", "/path/to/b", "/path/to/c"]
        dirs2 = ["/path/to/c", "/path/to/a", "/path/to/b"]

        file1 = cache_manager.get_composite_cache_file(dirs1)
        file2 = cache_manager.get_composite_cache_file(dirs2)

        assert file1 == file2  # Should be identical due to sorting

    def test_composite_cache_file_different_dirs(self, cache_manager):
        """Different directories generate different cache files."""
        dirs1 = ["/path/to/a", "/path/to/b"]
        dirs2 = ["/path/to/a", "/path/to/c"]

        file1 = cache_manager.get_composite_cache_file(dirs1)
        file2 = cache_manager.get_composite_cache_file(dirs2)

        assert file1 != file2

    # === save_composite_cache tests ===

    def test_save_composite_cache_creates_file(self, temp_cache_dir):
        """Save composite cache creates file with correct structure."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/path/to/dir1", "/path/to/dir2"]
        slates = {
            "slate1": {"images": [{"path": "/img1.jpg"}, {"path": "/img2.jpg"}]},
            "slate2": {"images": [{"path": "/img3.jpg"}]}
        }

        cache_manager.save_composite_cache(dirs, slates)

        cache_file = cache_manager.get_composite_cache_file(dirs)
        assert os.path.exists(cache_file)

    def test_save_composite_cache_metadata_structure(self, temp_cache_dir, temp_image_dirs):
        """Metadata is correctly saved with all required fields."""
        import json
        import time

        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = temp_image_dirs[:2]  # Use real temp dirs for mtime
        slates = {"slate": {"images": [{"path": "/img.jpg"}]}}

        before_save = time.time()
        cache_manager.save_composite_cache(dirs, slates)
        after_save = time.time()

        cache_file = cache_manager.get_composite_cache_file(dirs)
        with open(cache_file) as f:
            data = json.load(f)

        metadata = data["_metadata"]
        assert metadata["version"] == 2
        assert before_save <= metadata["scan_time"] <= after_save
        assert metadata["file_count"] == 1  # 1 image total
        assert metadata["root_dirs"] == sorted(dirs)
        assert isinstance(metadata["dir_mtime"], (int, float))

    def test_save_composite_cache_counts_images(self, temp_cache_dir):
        """File count correctly counts images across all slates."""
        import json

        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/a", "/b"]
        slates = {
            "slate1": {"images": [{"path": f"/img{i}.jpg"} for i in range(5)]},
            "slate2": {"images": [{"path": f"/img{i}.jpg"} for i in range(3)]},
            "slate3": {"images": []}  # Empty slate
        }

        cache_manager.save_composite_cache(dirs, slates)

        with open(cache_manager.get_composite_cache_file(dirs)) as f:
            data = json.load(f)

        assert data["_metadata"]["file_count"] == 8

    def test_save_composite_cache_handles_invalid_slates(self, temp_cache_dir):
        """Invalid slate types don't crash file counting."""
        import json

        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/a"]
        slates = {
            "valid_slate": {"images": [{"path": "/img.jpg"}]},
            "invalid_slate": "not a dict",
            "slate_no_images": {"name": "test"}
        }

        cache_manager.save_composite_cache(dirs, slates)

        with open(cache_manager.get_composite_cache_file(dirs)) as f:
            data = json.load(f)

        # Should count only valid images
        assert data["_metadata"]["file_count"] == 1

    # === load_composite_cache tests ===

    def test_load_composite_cache_success(self, temp_cache_dir):
        """Load valid composite cache returns slates without metadata."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/a", "/b"]
        original_slates = {
            "slate1": {"images": [{"path": "/img1.jpg"}]},
            "slate2": {"images": [{"path": "/img2.jpg"}]}
        }

        cache_manager.save_composite_cache(dirs, original_slates)
        loaded = cache_manager.load_composite_cache(dirs)

        assert loaded == original_slates
        assert "_metadata" not in loaded

    def test_load_composite_cache_not_exists(self, cache_manager):
        """Load non-existent cache returns None."""
        dirs = ["/nonexistent/a", "/nonexistent/b"]

        loaded = cache_manager.load_composite_cache(dirs)

        assert loaded is None

    def test_load_composite_cache_corrupted_json(self, temp_cache_dir):
        """Load corrupted JSON returns None."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/a"]
        cache_file = cache_manager.get_composite_cache_file(dirs)

        # Write corrupted JSON
        with open(cache_file, 'w') as f:
            f.write('{"invalid": json syntax')

        loaded = cache_manager.load_composite_cache(dirs)

        assert loaded is None

    # === validate_composite_cache tests ===

    def test_validate_composite_cache_fresh(self, temp_cache_dir, temp_image_dirs):
        """Validate recently saved cache with existing directories returns True."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = temp_image_dirs[:2]  # Use actual temp directories
        slates = {"slate": {"images": []}}

        cache_manager.save_composite_cache(dirs, slates)
        is_valid = cache_manager.validate_composite_cache(dirs)

        assert is_valid is True

    def test_validate_composite_cache_not_exists(self, cache_manager):
        """Validate non-existent cache returns False."""
        dirs = ["/nonexistent/a", "/nonexistent/b"]

        is_valid = cache_manager.validate_composite_cache(dirs)

        assert is_valid is False

    def test_validate_composite_cache_dir_deleted(self, temp_cache_dir):
        """Cache invalid if a directory no longer exists."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)

        # Create temp dir, save cache, then let it be deleted
        with tempfile.TemporaryDirectory() as temp_dir:
            dirs = [temp_dir]
            slates = {"slate": {"images": []}}
            cache_manager.save_composite_cache(dirs, slates)
            # temp_dir still exists here

        # Now temp_dir is deleted - cache should be invalid
        is_valid = cache_manager.validate_composite_cache(dirs)
        assert is_valid is False

    def test_validate_composite_cache_dir_modified(self, temp_cache_dir):
        """Cache invalid if directory mtime increased."""
        import time

        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            dirs = [temp_dir]
            slates = {"slate": {"images": []}}

            # Save cache
            cache_manager.save_composite_cache(dirs, slates)

            # Modify directory by creating a file (updates dir mtime)
            time.sleep(0.1)  # Ensure mtime changes
            new_file = os.path.join(temp_dir, "newfile.txt")
            with open(new_file, 'w') as f:
                f.write("test")

            # Cache should be invalid now
            is_valid = cache_manager.validate_composite_cache(dirs)
            assert is_valid is False

    def test_validate_composite_cache_no_metadata(self, temp_cache_dir):
        """Cache invalid if metadata is missing (old format)."""
        import json

        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            dirs = [temp_dir]
            cache_file = cache_manager.get_composite_cache_file(dirs)

            # Write cache without metadata
            with open(cache_file, 'w') as f:
                json.dump({"slate": {"images": []}}, f)

            is_valid = cache_manager.validate_composite_cache(dirs)
            assert is_valid is False

    def test_validate_composite_cache_dir_order_independent(self, temp_cache_dir):
        """Cache valid even if directory order differs."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)

        with (
            tempfile.TemporaryDirectory() as temp_dir1,
            tempfile.TemporaryDirectory() as temp_dir2,
        ):
            dirs1 = [temp_dir1, temp_dir2]
            dirs2 = [temp_dir2, temp_dir1]  # Reversed order
            slates = {"slate": {"images": []}}

            # Save with dirs1 order
            cache_manager.save_composite_cache(dirs1, slates)

            # Validate with dirs2 order (reversed)
            is_valid = cache_manager.validate_composite_cache(dirs2)
            assert is_valid is True

    # === Integration / roundtrip tests ===

    def test_composite_cache_roundtrip(self, temp_cache_dir):
        """Save and load produces identical slates."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/a", "/b", "/c"]
        original = {
            "slate1": {
                "images": [
                    {"path": "/img1.jpg", "exif": {"focal_length": 50.0}},
                    {"path": "/img2.jpg", "exif": {"focal_length": 35.0}}
                ]
            },
            "slate2": {"images": []}
        }

        cache_manager.save_composite_cache(dirs, original)
        loaded = cache_manager.load_composite_cache(dirs)

        assert loaded == original

    def test_composite_cache_thread_safety(self, temp_cache_dir):
        """Multiple threads can load/save cache concurrently."""
        cache_manager = ImprovedCacheManager(base_dir=temp_cache_dir)
        dirs = ["/a", "/b"]
        slates = {"slate": {"images": [{"path": "/img.jpg"}]}}

        cache_manager.save_composite_cache(dirs, slates)

        results = []
        errors = []

        def load_cache():
            try:
                loaded = cache_manager.load_composite_cache(dirs)
                results.append(loaded)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=load_cache) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should have loaded the same data without errors
        assert len(errors) == 0
        assert len(results) == 5
        assert all(r == slates for r in results)
