"""Improved config manager tests using real files instead of mocks."""

import os

import pytest

from src.core.config_manager import load_config, save_config


class TestConfigManagerImproved:
    """Test config manager with real files instead of mocks."""

    @pytest.fixture(autouse=True)
    def setup_config_env(self, tmp_path, monkeypatch):
        """Set up environment for real config file testing."""
        # Create a temporary config directory
        config_dir = tmp_path / '.slate_gallery'
        config_dir.mkdir()
        config_file = config_dir / 'config.ini'

        # Monkeypatch the CONFIG_FILE path once for all tests
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

        yield config_file

        # Cleanup is automatic with tmp_path

    def test_load_config_nonexistent_file(self, setup_config_env):
        """Test loading config when file doesn't exist."""
        # File doesn't exist yet
        assert not setup_config_env.exists()

        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        # Should return defaults
        assert current_dir == ""
        assert slate_dirs == []
        assert generate_thumbnails is False
        assert thumbnail_size == 600
        assert lazy_loading is True

        # Note: load_config doesn't create the file, only save_config does
        # This is the actual behavior of the implementation

    def test_save_and_load_config(self, setup_config_env):
        """Test saving and loading configuration with real file."""
        # Test data
        test_current_dir = "/test/current/dir"
        test_slate_dirs = ["/test/dir1", "/test/dir2", "/test/dir3"]
        test_generate_thumbnails = True
        test_thumbnail_size = 800
        test_lazy_loading = False

        # Save config
        save_config(test_current_dir, test_slate_dirs, test_generate_thumbnails, test_thumbnail_size, test_lazy_loading)

        # Verify file was created
        assert setup_config_env.exists()

        # Load config
        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        # Verify values
        assert current_dir == test_current_dir
        assert slate_dirs == test_slate_dirs
        assert generate_thumbnails == test_generate_thumbnails
        assert thumbnail_size == test_thumbnail_size
        assert lazy_loading == test_lazy_loading

    def test_save_config_empty_values(self, setup_config_env):
        """Test saving config with empty values."""
        save_config("", [], False, 600, True)

        # Verify file content directly
        content = setup_config_env.read_text()
        assert "current_slate_dir =" in content or "current_slate_dir = " in content
        assert "slate_dirs =" in content or "slate_dirs = " in content
        assert "generate_thumbnails = False" in content

    def test_save_config_single_directory(self, setup_config_env):
        """Test saving config with a single directory."""
        single_dir = "/single/directory"
        save_config(single_dir, [single_dir], True, 1200, True)

        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        assert current_dir == single_dir
        assert slate_dirs == [single_dir]
        assert generate_thumbnails is True
        assert thumbnail_size == 1200

    def test_save_config_special_characters(self, setup_config_env):
        """Test saving config with special characters in paths."""
        special_dir = "/path/with spaces/and-special_chars!@#"
        special_dirs = [special_dir, "/another/path with/spaces"]

        save_config(special_dir, special_dirs, False, 600, True)

        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        assert current_dir == special_dir
        assert slate_dirs == special_dirs
        assert generate_thumbnails is False
        assert thumbnail_size == 600

    def test_config_file_corruption_recovery(self, setup_config_env):
        """Test recovery from corrupted config file."""
        # Write corrupted content
        setup_config_env.write_text("This is not valid INI content\n[Invalid\nNo closing bracket")

        # Should handle gracefully and return defaults
        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        assert current_dir == ""
        assert slate_dirs == []
        assert generate_thumbnails is False
        assert thumbnail_size == 600

    def test_config_persistence_across_instances(self, setup_config_env):
        """Test that config persists across multiple load/save cycles."""
        # First save
        save_config("/first", ["/dir1", "/dir2"], True, 800, True)

        # Load and modify
        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()
        assert current_dir == "/first"

        # Second save with modifications
        slate_dirs.append("/dir3")
        save_config(current_dir, slate_dirs, False, thumbnail_size, True)

        # Final load
        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()
        assert slate_dirs == ["/dir1", "/dir2", "/dir3"]
        assert generate_thumbnails is False
        assert thumbnail_size == 800

    def test_unicode_in_config(self, setup_config_env):
        """Test unicode characters in configuration."""
        unicode_dir = "/写真/фото/Photos"
        unicode_dirs = [unicode_dir, "/café/naïve/path"]

        save_config(unicode_dir, unicode_dirs, True, 1200, False)

        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        assert current_dir == unicode_dir
        assert slate_dirs == unicode_dirs
        assert generate_thumbnails is True
        assert thumbnail_size == 1200

    def test_config_file_permissions(self, setup_config_env):
        """Test that config file is created with correct permissions."""
        save_config("/test", ["/test"], False, 600, True)

        # Check file exists and is readable/writable
        assert setup_config_env.exists()
        assert os.access(setup_config_env, os.R_OK)
        assert os.access(setup_config_env, os.W_OK)

    def test_concurrent_config_access(self, setup_config_env):
        """Test that concurrent access doesn't corrupt config."""
        import threading

        def write_config(thread_id):
            save_config(f"/thread_{thread_id}", [f"/dir_{thread_id}"], thread_id % 2 == 0, 600 + thread_id * 200, True)

        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=write_config, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Config should still be valid (last write wins)
        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()
        assert current_dir.startswith("/thread_")
        assert len(slate_dirs) == 1


class TestConfigManagerEdgeCases:
    """Test edge cases with real file operations."""

    @pytest.fixture
    def readonly_config(self, tmp_path):
        """Create a read-only config file."""
        config_file = tmp_path / 'readonly_config.ini'
        config_file.write_text("[Settings]\ncurrent_slate_dir = /readonly\n")
        config_file.chmod(0o444)  # Read-only
        return config_file

    def test_save_to_readonly_config(self, readonly_config, monkeypatch, caplog):
        """Test saving to read-only config file."""
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(readonly_config))

        # Attempt to save (should handle gracefully)
        save_config("/new", ["/new"], True, 800, True)

        # Check that error was logged
        assert "Permission" in caplog.text or "Error" in caplog.text

    def test_config_with_invalid_section(self, tmp_path, monkeypatch):
        """Test config with missing Settings section."""
        config_file = tmp_path / 'invalid_section.ini'
        config_file.write_text("[WrongSection]\nsome_key = value\n")

        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

        current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading = load_config()

        # Should return defaults
        assert current_dir == ""
        assert slate_dirs == []
        assert generate_thumbnails is False
        assert thumbnail_size == 600

        # Should create proper section on next save
        save_config("/test", ["/test"], True, 1200, False)

        # Verify Settings section was created
        content = config_file.read_text()
        assert "[Settings]" in content
