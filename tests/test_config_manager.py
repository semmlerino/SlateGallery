"""Improved config manager tests using real files instead of mocks."""

import os

import pytest

from src.core.config_manager import GalleryConfig, load_config, save_config


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

        config = load_config()

        # Should return defaults
        assert config.current_slate_dir == ""
        assert config.slate_dirs == []
        assert config.generate_thumbnails is False
        assert config.thumbnail_size == 600
        assert config.lazy_loading is True

        # Note: load_config doesn't create the file, only save_config does
        # This is the actual behavior of the implementation

    def test_save_and_load_config(self, setup_config_env):
        """Test saving and loading configuration with real file."""
        # Test data
        test_config = GalleryConfig(
            current_slate_dir="/test/current/dir",
            slate_dirs=["/test/dir1", "/test/dir2", "/test/dir3"],
            selected_slate_dirs=["/test/dir1", "/test/dir2", "/test/dir3"],
            generate_thumbnails=True,
            thumbnail_size=800,
            lazy_loading=False,
            exclude_patterns=""
        )

        # Save config
        save_config(test_config)

        # Verify file was created
        assert setup_config_env.exists()

        # Load config
        loaded_config = load_config()

        # Verify values
        assert loaded_config.current_slate_dir == test_config.current_slate_dir
        assert loaded_config.slate_dirs == test_config.slate_dirs
        assert loaded_config.generate_thumbnails == test_config.generate_thumbnails
        assert loaded_config.thumbnail_size == test_config.thumbnail_size
        assert loaded_config.lazy_loading == test_config.lazy_loading

    def test_save_config_empty_values(self, setup_config_env):
        """Test saving config with empty values."""
        save_config(GalleryConfig())

        # Verify file content directly
        content = setup_config_env.read_text()
        assert "current_slate_dir =" in content or "current_slate_dir = " in content
        assert "slate_dirs =" in content or "slate_dirs = " in content
        assert "generate_thumbnails = False" in content

    def test_save_config_single_directory(self, setup_config_env):
        """Test saving config with a single directory."""
        single_dir = "/single/directory"
        config = GalleryConfig(
            current_slate_dir=single_dir,
            slate_dirs=[single_dir],
            selected_slate_dirs=[single_dir],
            generate_thumbnails=True,
            thumbnail_size=1200
        )
        save_config(config)

        loaded_config = load_config()

        assert loaded_config.current_slate_dir == single_dir
        assert loaded_config.slate_dirs == [single_dir]
        assert loaded_config.generate_thumbnails is True
        assert loaded_config.thumbnail_size == 1200

    def test_save_config_special_characters(self, setup_config_env):
        """Test saving config with special characters in paths."""
        special_dir = "/path/with spaces/and-special_chars!@#"
        special_dirs = [special_dir, "/another/path with/spaces"]

        config = GalleryConfig(
            current_slate_dir=special_dir,
            slate_dirs=special_dirs,
            selected_slate_dirs=special_dirs
        )
        save_config(config)

        loaded_config = load_config()

        assert loaded_config.current_slate_dir == special_dir
        assert loaded_config.slate_dirs == special_dirs
        assert loaded_config.generate_thumbnails is False
        assert loaded_config.thumbnail_size == 600

    def test_config_file_corruption_recovery(self, setup_config_env):
        """Test recovery from corrupted config file."""
        # Write corrupted content
        setup_config_env.write_text("This is not valid INI content\n[Invalid\nNo closing bracket")

        # Should handle gracefully and return defaults
        config = load_config()

        assert config.current_slate_dir == ""
        assert config.slate_dirs == []
        assert config.generate_thumbnails is False
        assert config.thumbnail_size == 600

    def test_config_persistence_across_instances(self, setup_config_env):
        """Test that config persists across multiple load/save cycles."""
        # First save
        config = GalleryConfig(
            current_slate_dir="/first",
            slate_dirs=["/dir1", "/dir2"],
            selected_slate_dirs=["/dir1", "/dir2"],
            generate_thumbnails=True,
            thumbnail_size=800
        )
        save_config(config)

        # Load and modify
        loaded_config = load_config()
        assert loaded_config.current_slate_dir == "/first"

        # Second save with modifications
        loaded_config.slate_dirs.append("/dir3")
        loaded_config.generate_thumbnails = False
        save_config(loaded_config)

        # Final load
        final_config = load_config()
        assert final_config.slate_dirs == ["/dir1", "/dir2", "/dir3"]
        assert final_config.generate_thumbnails is False
        assert final_config.thumbnail_size == 800

    def test_unicode_in_config(self, setup_config_env):
        """Test unicode characters in configuration."""
        unicode_dir = "/写真/фото/Photos"
        unicode_dirs = [unicode_dir, "/café/naïve/path"]

        config = GalleryConfig(
            current_slate_dir=unicode_dir,
            slate_dirs=unicode_dirs,
            selected_slate_dirs=unicode_dirs,
            generate_thumbnails=True,
            thumbnail_size=1200,
            lazy_loading=False
        )
        save_config(config)

        loaded_config = load_config()

        assert loaded_config.current_slate_dir == unicode_dir
        assert loaded_config.slate_dirs == unicode_dirs
        assert loaded_config.generate_thumbnails is True
        assert loaded_config.thumbnail_size == 1200

    def test_config_file_permissions(self, setup_config_env):
        """Test that config file is created with correct permissions."""
        save_config(GalleryConfig(current_slate_dir="/test", slate_dirs=["/test"], selected_slate_dirs=["/test"]))

        # Check file exists and is readable/writable
        assert setup_config_env.exists()
        assert os.access(setup_config_env, os.R_OK)
        assert os.access(setup_config_env, os.W_OK)

    def test_concurrent_config_access(self, setup_config_env):
        """Test that concurrent access doesn't corrupt config."""
        import threading

        def write_config(thread_id):
            config = GalleryConfig(
                current_slate_dir=f"/thread_{thread_id}",
                slate_dirs=[f"/dir_{thread_id}"],
                selected_slate_dirs=[f"/dir_{thread_id}"],
                generate_thumbnails=thread_id % 2 == 0,
                thumbnail_size=600 + thread_id * 200
            )
            save_config(config)

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
        config = load_config()
        assert config.current_slate_dir.startswith("/thread_")
        assert len(config.slate_dirs) == 1


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
        config = GalleryConfig(
            current_slate_dir="/new",
            slate_dirs=["/new"],
            selected_slate_dirs=["/new"],
            generate_thumbnails=True,
            thumbnail_size=800
        )
        save_config(config)

        # Check that error was logged
        assert "Permission" in caplog.text or "Error" in caplog.text

    def test_config_with_invalid_section(self, tmp_path, monkeypatch):
        """Test config with missing Settings section."""
        config_file = tmp_path / 'invalid_section.ini'
        config_file.write_text("[WrongSection]\nsome_key = value\n")

        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))

        config = load_config()

        # Should return defaults
        assert config.current_slate_dir == ""
        assert config.slate_dirs == []
        assert config.generate_thumbnails is False
        assert config.thumbnail_size == 600

        # Should create proper section on next save
        new_config = GalleryConfig(
            current_slate_dir="/test",
            slate_dirs=["/test"],
            selected_slate_dirs=["/test"],
            generate_thumbnails=True,
            thumbnail_size=1200,
            lazy_loading=False
        )
        save_config(new_config)

        # Verify Settings section was created
        content = config_file.read_text()
        assert "[Settings]" in content


class TestConfigManagerJSONSerialization:
    """Test JSON serialization for list values to handle pipe characters in paths."""

    @pytest.fixture(autouse=True)
    def setup_config_env(self, tmp_path, monkeypatch):
        """Set up environment for config file testing."""
        config_dir = tmp_path / '.slate_gallery'
        config_dir.mkdir()
        config_file = config_dir / 'config.ini'
        monkeypatch.setattr('src.core.config_manager.CONFIG_FILE', str(config_file))
        yield config_file

    def test_save_config_pipe_in_path(self, setup_config_env):
        """Test that paths containing pipe characters are handled correctly."""
        # Pipe character was previously used as delimiter - this would break
        pipe_path = "/path/with|pipe/character"
        paths_with_pipes = [pipe_path, "/another|path|multiple"]

        config = GalleryConfig(
            current_slate_dir=pipe_path,
            slate_dirs=paths_with_pipes,
            selected_slate_dirs=paths_with_pipes
        )
        save_config(config)

        # Load and verify
        loaded_config = load_config()

        assert loaded_config.current_slate_dir == pipe_path
        assert loaded_config.slate_dirs == paths_with_pipes
        assert loaded_config.selected_slate_dirs == paths_with_pipes

    def test_backwards_compatibility_pipe_format(self, setup_config_env):
        """Test that legacy pipe-delimited format still loads correctly."""
        # Write config file in legacy format (pipe-delimited)
        legacy_content = '''[Settings]
current_slate_dir = /test/dir
slate_dirs = /path/one|/path/two|/path/three
selected_slate_dirs = /path/one|/path/two
generate_thumbnails = True
thumbnail_size = 800
lazy_loading = True
exclude_patterns =
'''
        setup_config_env.write_text(legacy_content)

        # Load should still work
        loaded_config = load_config()

        assert loaded_config.current_slate_dir == "/test/dir"
        assert loaded_config.slate_dirs == ["/path/one", "/path/two", "/path/three"]
        assert loaded_config.selected_slate_dirs == ["/path/one", "/path/two"]
        assert loaded_config.generate_thumbnails is True
        assert loaded_config.thumbnail_size == 800

    def test_json_format_written_on_save(self, setup_config_env):
        """Test that new format uses JSON for list values."""
        config = GalleryConfig(
            current_slate_dir="/test",
            slate_dirs=["/path/one", "/path/two"],
            selected_slate_dirs=["/path/one"]
        )
        save_config(config)

        # Read raw file content
        content = setup_config_env.read_text()

        # Should use JSON format (starts with [ and ends with ])
        assert '["' in content  # JSON array notation
        assert '"]' in content

        # Should NOT use pipe delimiter in the actual content
        # (Note: checking that pipes aren't used as delimiters, not that they don't appear in paths)
        lines = content.split('\n')
        for line in lines:
            if line.startswith('slate_dirs =') or line.startswith('selected_slate_dirs ='):
                # The value should be valid JSON
                value = line.split('=', 1)[1].strip()
                import json
                parsed = json.loads(value)
                assert isinstance(parsed, list)

    def test_mixed_special_characters(self, setup_config_env):
        """Test paths with multiple special characters including pipes."""
        complex_paths = [
            "/path|with|pipes/and spaces/and-dashes",
            "/café|naïve|日本語/path",
            '/quotes"and\'apostrophes',
            "/backslash\\path|mixed"
        ]

        config = GalleryConfig(
            current_slate_dir=complex_paths[0],
            slate_dirs=complex_paths,
            selected_slate_dirs=complex_paths
        )
        save_config(config)

        loaded_config = load_config()

        assert loaded_config.slate_dirs == complex_paths
        assert loaded_config.selected_slate_dirs == complex_paths

    def test_empty_list_json_format(self, setup_config_env):
        """Test that empty lists serialize correctly."""
        config = GalleryConfig(
            current_slate_dir="",
            slate_dirs=[],
            selected_slate_dirs=[]
        )
        save_config(config)

        loaded_config = load_config()

        assert loaded_config.slate_dirs == []
        assert loaded_config.selected_slate_dirs == []

    def test_migration_from_legacy_to_json(self, setup_config_env):
        """Test that loading legacy format and saving migrates to JSON format."""
        # Write legacy format
        legacy_content = '''[Settings]
current_slate_dir = /test
slate_dirs = /path/one|/path/two
selected_slate_dirs = /path/one
generate_thumbnails = False
thumbnail_size = 600
lazy_loading = True
exclude_patterns =
'''
        setup_config_env.write_text(legacy_content)

        # Load and save
        loaded_config = load_config()
        save_config(loaded_config)

        # Verify new format
        content = setup_config_env.read_text()
        assert '["' in content  # JSON format
        assert '["/path/one", "/path/two"]' in content or '["/path/one","/path/two"]' in content.replace(' ', '')
