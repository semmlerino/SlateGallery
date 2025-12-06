"""Configuration handling - extracted identically from original SlateGallery.py

Uses lazy initialization to avoid crashes in read-only environments.
"""

import codecs
import configparser
import os
import traceback
from dataclasses import dataclass, field
from typing import Optional

from utils.logging_config import ensure_handlers_initialized, log_function, logger


@dataclass
class GalleryConfig:
    """Configuration settings for SlateGallery."""
    current_slate_dir: str = ""
    slate_dirs: list[str] = field(default_factory=list)
    selected_slate_dirs: list[str] = field(default_factory=list)
    generate_thumbnails: bool = False
    thumbnail_size: int = 600
    lazy_loading: bool = True
    exclude_patterns: str = ""

# ----------------------------- Configuration Handling -----------------------------

CONFIG_FILE = os.path.expanduser("~/.slate_gallery/config.ini")
CACHE_DIR = os.path.expanduser("~/.slate_gallery/cache")

# Module-level state for lazy initialization
_directories_initialized = False
_directories_error: Optional[str] = None


def _ensure_directories() -> bool:
    """Lazily create required directories on first use.

    Returns:
        True if directories are accessible, False otherwise
    """
    global _directories_initialized, _directories_error

    if _directories_initialized:
        return _directories_error is None

    ensure_handlers_initialized()  # Ensure logging is available

    try:
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir and not os.path.isdir(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        if not os.path.isdir(CACHE_DIR):
            os.makedirs(CACHE_DIR, exist_ok=True)

        _directories_error = None
    except (OSError, PermissionError) as e:
        _directories_error = str(e)
        logger.warning(f"Could not create config directories: {e}")

    _directories_initialized = True
    return _directories_error is None


@log_function
def load_config() -> GalleryConfig:
    """Load configuration from config file.

    Returns:
        GalleryConfig dataclass with all settings
    """
    _ensure_directories()  # Lazy initialization (tolerates failures)

    config = configparser.ConfigParser()
    result = GalleryConfig()
    if os.path.exists(CONFIG_FILE):
        try:
            with codecs.open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.read_file(f)
            try:
                result.current_slate_dir = config.get("Settings", "current_slate_dir")
                logger.info(f"Loaded current_slate_dir from config: {result.current_slate_dir}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                logger.warning("current_slate_dir not found in config.")

            try:
                slate_dirs_str = config.get("Settings", "slate_dirs")
                result.slate_dirs = slate_dirs_str.split("|") if slate_dirs_str else []
                logger.info(f"Loaded slate_dirs from config: {result.slate_dirs}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                logger.warning("slate_dirs not found in config.")

            try:
                selected_slate_dirs_str = config.get("Settings", "selected_slate_dirs")
                selected_dirs = selected_slate_dirs_str.split("|") if selected_slate_dirs_str else []
                # Filter out empty strings
                result.selected_slate_dirs = [d for d in selected_dirs if d]
                logger.info(f"Loaded selected_slate_dirs from config: {result.selected_slate_dirs}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                # Backwards compatibility: default to current_slate_dir if it exists
                if result.current_slate_dir and os.path.exists(result.current_slate_dir):
                    result.selected_slate_dirs = [result.current_slate_dir]
                    logger.info(f"selected_slate_dirs not found in config, defaulting to [{result.current_slate_dir}]")
                else:
                    logger.info("selected_slate_dirs not found in config, defaulting to empty list.")

            try:
                result.generate_thumbnails = config.getboolean("Settings", "generate_thumbnails")
                logger.info(f"Loaded generate_thumbnails from config: {result.generate_thumbnails}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                logger.info("generate_thumbnails not found in config, defaulting to False.")

            try:
                size = config.getint("Settings", "thumbnail_size")
                # Validate the size is one of the allowed values
                if size not in [600, 800, 1200]:
                    logger.warning("Invalid thumbnail_size in config, defaulting to 600.")
                else:
                    result.thumbnail_size = size
                    logger.info(f"Loaded thumbnail_size from config: {result.thumbnail_size}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                logger.info("thumbnail_size not found in config, defaulting to 600.")

            try:
                result.lazy_loading = config.getboolean("Settings", "lazy_loading")
                logger.info(f"Loaded lazy_loading from config: {result.lazy_loading}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                logger.info("lazy_loading not found in config, defaulting to True.")

            try:
                result.exclude_patterns = config.get("Settings", "exclude_patterns")
                logger.info(f"Loaded exclude_patterns from config: {result.exclude_patterns}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                logger.info("exclude_patterns not found in config, defaulting to empty.")
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            logger.debug(traceback.format_exc())
            # Return default config on error
            return GalleryConfig()
    else:
        logger.warning("Config file not found. Using default settings.")
    return result


@log_function
def save_config(cfg: GalleryConfig) -> None:
    """Save configuration to config file.

    Args:
        cfg: GalleryConfig dataclass with all settings
    """
    if not _ensure_directories():
        logger.error(f"Cannot save config: {_directories_error}")
        return  # Graceful failure when directories can't be created

    config = configparser.ConfigParser()
    if not config.has_section("Settings"):
        config.add_section("Settings")
    config.set("Settings", "current_slate_dir", cfg.current_slate_dir)
    config.set("Settings", "slate_dirs", "|".join(cfg.slate_dirs))
    config.set("Settings", "selected_slate_dirs", "|".join(cfg.selected_slate_dirs))
    config.set("Settings", "generate_thumbnails", str(cfg.generate_thumbnails))
    config.set("Settings", "thumbnail_size", str(cfg.thumbnail_size))
    config.set("Settings", "lazy_loading", str(cfg.lazy_loading))
    config.set("Settings", "exclude_patterns", cfg.exclude_patterns)
    try:
        with codecs.open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            config.write(configfile)
        logger.info(f"Configuration saved: {cfg}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        logger.debug(traceback.format_exc())
