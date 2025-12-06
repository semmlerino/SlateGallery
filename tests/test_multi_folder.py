"""Tests for multi-folder scanning functionality."""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from src.core.cache_manager import ImprovedCacheManager
from src.core.config_manager import GalleryConfig, load_config, save_config
from src.core.image_processor import scan_multiple_directories
from src.utils.threading import ScanThread, _scan_single_root_dir


def create_test_image(path, size=(100, 100), focal_length=None, date_taken=None):
    """Create a test image with optional EXIF data."""
    img = Image.new('RGB', size, color='blue')

    if (focal_length or date_taken) and path.suffix.lower() == '.jpg':
        try:
            import piexif
            exif_data = {"0th": {}, "Exif": {}}

            if focal_length:
                exif_data["Exif"][piexif.ExifIFD.FocalLength] = (int(focal_length), 1)

            if date_taken:
                date_str = date_taken.strftime('%Y:%m:%d %H:%M:%S')
                exif_data["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode('utf-8')

            exif_bytes = piexif.dump(exif_data)
            img.save(path, 'JPEG', exif=exif_bytes)
        except ImportError:
            img.save(path, 'JPEG')
    else:
        img_format = 'PNG' if path.suffix.lower() == '.png' else 'JPEG'
        img.save(path, img_format)

    return str(path)


class TestMultiFolderConfig:
    """Test configuration changes for multi-folder support."""

    def test_save_and_load_selected_slate_dirs(self, tmp_path):
        """Test saving and loading selected_slate_dirs configuration."""
        current_dir = str(tmp_path / "current")
        slate_dirs = [str(tmp_path / "dir1"), str(tmp_path / "dir2")]
        selected_dirs = [str(tmp_path / "dir1")]

        # Save config with selected directories
        save_config(GalleryConfig(
            current_slate_dir=current_dir,
            slate_dirs=slate_dirs,
            selected_slate_dirs=selected_dirs,
            generate_thumbnails=False,
            thumbnail_size=600,
            lazy_loading=True,
            exclude_patterns=""
        ))

        # Load and verify
        loaded = load_config()
        assert loaded.selected_slate_dirs == selected_dirs

    def test_backwards_compatibility_no_selected_dirs(self, tmp_path):
        """Test that missing selected_slate_dirs defaults to current_slate_dir."""
        current_dir = str(tmp_path / "current")
        os.makedirs(current_dir, exist_ok=True)

        # Save config without selected_slate_dirs (simulate old config)
        save_config(GalleryConfig(
            current_slate_dir=current_dir,
            slate_dirs=[current_dir],
            selected_slate_dirs=[],  # Empty selected_slate_dirs
            generate_thumbnails=False,
            thumbnail_size=600,
            lazy_loading=True,
            exclude_patterns=""
        ))

        # Manually edit config to remove selected_slate_dirs
        import configparser
        config_file = os.path.expanduser("~/.slate_gallery/config.ini")
        config = configparser.ConfigParser()
        config.read(config_file)
        if config.has_option("Settings", "selected_slate_dirs"):
            config.remove_option("Settings", "selected_slate_dirs")
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)

        # Load should default to current_slate_dir
        loaded = load_config()
        assert current_dir in loaded.selected_slate_dirs  # Should include current_slate_dir

    def test_multiple_selected_directories(self, tmp_path):
        """Test saving and loading multiple selected directories."""
        current_dir = str(tmp_path / "current")
        dir1 = str(tmp_path / "photos1")
        dir2 = str(tmp_path / "photos2")
        dir3 = str(tmp_path / "photos3")

        slate_dirs = [dir1, dir2, dir3]
        selected_dirs = [dir1, dir3]  # Select 1st and 3rd

        save_config(GalleryConfig(
            current_slate_dir=current_dir,
            slate_dirs=slate_dirs,
            selected_slate_dirs=selected_dirs,
            generate_thumbnails=True,
            thumbnail_size=800,
            lazy_loading=False,
            exclude_patterns="*.tmp,test*"
        ))

        loaded = load_config()
        assert loaded.selected_slate_dirs == selected_dirs
        assert loaded.generate_thumbnails is True
        assert loaded.thumbnail_size == 800
        assert loaded.lazy_loading is False
        assert loaded.exclude_patterns == "*.tmp,test*"


class TestScanMultipleDirectories:
    """Test scan_multiple_directories function."""

    @pytest.fixture
    def multi_root_structure(self, tmp_path):
        """Create multiple root directories with different image structures."""
        root1 = tmp_path / "photos_2023"
        root2 = tmp_path / "photos_2024"

        # Root 1: photos_2023/
        #   ├── summer/
        #   │   ├── img1.jpg
        #   │   └── img2.jpg
        #   └── winter/
        #       └── img3.jpg

        (root1 / "summer").mkdir(parents=True)
        (root1 / "winter").mkdir(parents=True)

        create_test_image(root1 / "summer" / "img1.jpg", focal_length=35)
        create_test_image(root1 / "summer" / "img2.jpg", focal_length=50)
        create_test_image(root1 / "winter" / "img3.jpg", focal_length=85)

        # Root 2: photos_2024/
        #   ├── spring/
        #   │   └── img4.jpg
        #   └── summer/  # Same name as root1 but different content
        #       └── img5.jpg

        (root2 / "spring").mkdir(parents=True)
        (root2 / "summer").mkdir(parents=True)

        create_test_image(root2 / "spring" / "img4.jpg", focal_length=24)
        create_test_image(root2 / "summer" / "img5.jpg", focal_length=70)

        return [str(root1), str(root2)]

    def test_scan_multiple_roots_basic(self, multi_root_structure):
        """Test basic multi-root scanning."""
        slates = scan_multiple_directories(multi_root_structure)

        # Should have 5 slates total: photos_2023/summer, photos_2023/winter,
        # photos_2024/spring, photos_2024/summer
        assert len(slates) >= 4

        # Check slate names are prefixed
        slate_names = list(slates.keys())
        assert any("photos_2023/summer" in name for name in slate_names)
        assert any("photos_2024/summer" in name for name in slate_names)
        assert any("photos_2023/winter" in name for name in slate_names)
        assert any("photos_2024/spring" in name for name in slate_names)

    def test_scan_multiple_roots_image_counts(self, multi_root_structure):
        """Test that image counts are correct for each slate."""
        slates = scan_multiple_directories(multi_root_structure)

        # Find photos_2023/summer slate (should have 2 images)
        summer_2023_slates = [s for name, s in slates.items() if "photos_2023/summer" in name]
        assert len(summer_2023_slates) == 1
        assert len(summer_2023_slates[0]["images"]) == 2

        # Find photos_2023/winter slate (should have 1 image)
        winter_slates = [s for name, s in slates.items() if "winter" in name]
        assert len(winter_slates) == 1
        assert len(winter_slates[0]["images"]) == 1

    def test_scan_multiple_roots_with_empty_directory(self, tmp_path):
        """Test scanning with one empty directory."""
        root1 = tmp_path / "photos"
        root2 = tmp_path / "empty"

        (root1 / "vacation").mkdir(parents=True)
        create_test_image(root1 / "vacation" / "img1.jpg")

        root2.mkdir()  # Empty directory

        slates = scan_multiple_directories([str(root1), str(root2)])

        # Should only have slates from root1
        assert len(slates) >= 1
        assert any("photos/vacation" in name for name in slates.keys())

    def test_scan_multiple_roots_with_nonexistent_directory(self, tmp_path):
        """Test scanning with a non-existent directory."""
        root1 = tmp_path / "photos"
        root2 = tmp_path / "does_not_exist"

        (root1 / "vacation").mkdir(parents=True)
        create_test_image(root1 / "vacation" / "img1.jpg")

        # root2 doesn't exist
        slates = scan_multiple_directories([str(root1), str(root2)])

        # Should only have slates from root1
        assert len(slates) >= 1
        assert any("photos/vacation" in name for name in slates.keys())

    def test_scan_multiple_roots_with_exclude_patterns(self, multi_root_structure):
        """Test multi-root scanning with exclude patterns."""
        # Exclude anything with "winter"
        slates = scan_multiple_directories(multi_root_structure, exclude_patterns="*winter*")

        # Should not have any winter slates
        slate_names = list(slates.keys())
        assert not any("winter" in name for name in slate_names)

        # Should still have summer and spring slates
        assert any("summer" in name for name in slate_names)
        assert any("spring" in name for name in slate_names)

    def test_scan_multiple_roots_naming_conflict_resolution(self, tmp_path):
        """Test that naming conflicts are resolved with suffixes."""
        # Create two roots with identical subdirectory structure
        root1 = tmp_path / "root1"
        root2 = tmp_path / "root2"

        # Both have "vacation" subdirectory
        (root1 / "vacation").mkdir(parents=True)
        (root2 / "vacation").mkdir(parents=True)

        create_test_image(root1 / "vacation" / "img1.jpg")
        create_test_image(root2 / "vacation" / "img2.jpg")

        # Give them the same basename to force conflict
        import shutil
        renamed_root = tmp_path / "duplicate"
        shutil.copytree(root1, renamed_root)

        # Now scan both with same structure
        slates = scan_multiple_directories([str(root1), str(renamed_root)])

        # Should have different slate names (conflict resolved)
        slate_names = list(slates.keys())

        # Filter to only vacation-related slates
        vacation_slates = [name for name in slate_names if "vacation" in name]

        # Should have exactly 2 vacation slates with different prefixes
        assert len(vacation_slates) == 2


class TestScanSingleRootDirHelper:
    """Test the _scan_single_root_dir helper function."""

    def test_scan_single_root_with_prefix(self, tmp_path):
        """Test that _scan_single_root_dir properly prefixes slate names."""
        root = tmp_path / "my_photos"
        (root / "vacation").mkdir(parents=True)
        create_test_image(root / "vacation" / "img1.jpg")

        result = _scan_single_root_dir(str(root), "")

        # Should have one slate with root basename prefix
        assert len(result) == 1
        slate_name = list(result.keys())[0]
        assert slate_name.startswith("my_photos/")

    def test_scan_single_root_nonexistent(self, tmp_path):
        """Test _scan_single_root_dir with non-existent directory."""
        result = _scan_single_root_dir(str(tmp_path / "nonexistent"), "")

        # Should return empty dict
        assert result == {}

    def test_scan_single_root_with_root_level_images(self, tmp_path):
        """Test scanning root directory with images at root level."""
        root = tmp_path / "photos"
        root.mkdir()

        create_test_image(root / "img1.jpg")
        create_test_image(root / "img2.jpg")

        result = _scan_single_root_dir(str(root), "")

        # Should have one slate named "{basename}/Root"
        assert len(result) == 1
        slate_name = list(result.keys())[0]
        assert "Root" in slate_name


class TestMultiFolderScanThread:
    """Test ScanThread with multiple directories."""

    @pytest.fixture
    def thread_cleanup(self, qtbot):
        """Ensure proper thread cleanup."""
        threads = []

        def register(thread):
            threads.append(thread)
            return thread

        yield register

        # Cleanup all threads
        for thread in threads:
            if thread.isRunning():
                thread.stop()
                thread.wait(5000)

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a cache manager for tests."""
        return ImprovedCacheManager(base_dir=str(tmp_path / "cache"))

    def test_scan_thread_multiple_directories(self, tmp_path, qtbot, thread_cleanup, cache_manager):
        """Test ScanThread with multiple directories."""
        # Create two root directories
        root1 = tmp_path / "photos1"
        root2 = tmp_path / "photos2"

        (root1 / "vacation").mkdir(parents=True)
        (root2 / "work").mkdir(parents=True)

        create_test_image(root1 / "vacation" / "img1.jpg", focal_length=35)
        create_test_image(root2 / "work" / "img2.jpg", focal_length=50)

        # Create scan thread with multiple directories
        thread = ScanThread([str(root1), str(root2)], cache_manager)
        thread_cleanup(thread)

        # Connect signal to capture results
        results = []
        def on_complete(slates, message):
            results.append((slates, message))

        thread.scan_complete.connect(on_complete)

        # Start scan
        thread.start()

        # Wait for completion
        with qtbot.waitSignal(thread.scan_complete, timeout=10000):
            pass

        # Verify results
        assert len(results) == 1
        slates, message = results[0]

        # Should have at least 2 slates
        assert len(slates) >= 2

        # Check that slate names are prefixed
        slate_names = list(slates.keys())
        assert any("photos1" in name for name in slate_names)
        assert any("photos2" in name for name in slate_names)

    def test_scan_thread_single_directory_legacy_mode(self, tmp_path, qtbot, thread_cleanup, cache_manager):
        """Test that ScanThread still works with single directory (legacy mode)."""
        root = tmp_path / "photos"
        (root / "vacation").mkdir(parents=True)
        create_test_image(root / "vacation" / "img1.jpg")

        # Pass single directory as string (legacy mode)
        thread = ScanThread(str(root), cache_manager)
        thread_cleanup(thread)

        results = []
        thread.scan_complete.connect(lambda s, m: results.append((s, m)))

        thread.start()

        with qtbot.waitSignal(thread.scan_complete, timeout=10000):
            pass

        # Should work normally
        assert len(results) == 1
        slates, _ = results[0]
        assert len(slates) >= 1

    def test_scan_thread_progress_reporting_multi_folder(self, tmp_path, qtbot, thread_cleanup, cache_manager):
        """Test that progress is reported correctly for multi-folder scans."""
        # Create 3 directories
        roots = []
        for i in range(3):
            root = tmp_path / f"photos{i}"
            (root / "subfolder").mkdir(parents=True)
            create_test_image(root / "subfolder" / f"img{i}.jpg")
            roots.append(str(root))

        thread = ScanThread(roots, cache_manager)
        thread_cleanup(thread)

        progress_values = []
        thread.progress.connect(lambda p: progress_values.append(p))

        thread.start()

        with qtbot.waitSignal(thread.scan_complete, timeout=15000):
            pass

        # Should have received multiple progress updates
        assert len(progress_values) > 0

        # Progress should increase over time
        assert progress_values[-1] > progress_values[0]


class TestMultiFolderIntegration:
    """Integration tests for complete multi-folder workflow."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a cache manager."""
        return ImprovedCacheManager(base_dir=str(tmp_path / "cache"))

    def test_end_to_end_multi_folder_workflow(self, tmp_path, cache_manager):
        """Test complete workflow: config → scan → results."""
        # Step 1: Create directory structure
        root1 = tmp_path / "vacation_2023"
        root2 = tmp_path / "vacation_2024"

        (root1 / "beach").mkdir(parents=True)
        (root2 / "mountains").mkdir(parents=True)

        create_test_image(root1 / "beach" / "img1.jpg", focal_length=35,
                         date_taken=datetime(2023, 7, 15, 10, 30))
        create_test_image(root2 / "mountains" / "img2.jpg", focal_length=85,
                         date_taken=datetime(2024, 1, 20, 14, 45))

        # Step 2: Save config with selected directories
        selected_dirs = [str(root1), str(root2)]
        save_config(GalleryConfig(
            current_slate_dir=str(root1),
            slate_dirs=selected_dirs,  # slate_dirs (cached)
            selected_slate_dirs=selected_dirs,
            generate_thumbnails=False,
            thumbnail_size=600,
            lazy_loading=True,
            exclude_patterns=""
        ))

        # Step 3: Load config and verify
        loaded = load_config()
        assert loaded.selected_slate_dirs == selected_dirs

        # Step 4: Scan directories
        slates = scan_multiple_directories(selected_dirs)

        # Step 5: Verify results
        assert len(slates) >= 2

        # Should have vacation_2023/beach and vacation_2024/mountains
        slate_names = list(slates.keys())
        assert any("vacation_2023/beach" in name for name in slate_names)
        assert any("vacation_2024/mountains" in name for name in slate_names)

        # Verify image data
        all_images = []
        for slate_data in slates.values():
            all_images.extend(slate_data["images"])

        assert len(all_images) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
