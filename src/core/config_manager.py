"""Configuration handling - extracted identically from original SlateGallery.py"""

import codecs
import configparser
import os
import traceback

from utils.logging_config import log_function, logger

# ----------------------------- Configuration Handling -----------------------------

CONFIG_FILE = os.path.expanduser("~/.slate_gallery/config.ini")
CACHE_DIR = os.path.expanduser("~/.slate_gallery/cache")

config_dir = os.path.dirname(CONFIG_FILE)
if not os.path.isdir(config_dir):
    os.makedirs(config_dir)

if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)


@log_function
def load_config() -> tuple[str, list[str], list[str], bool, int, bool, str]:
    """Load configuration from config file.

    Returns:
        tuple containing:
        - current_slate_dir: Currently active directory (legacy)
        - slate_dirs: List of all cached directories
        - selected_slate_dirs: List of directories selected for scanning
        - generate_thumbnails: Whether to generate thumbnails
        - thumbnail_size: Thumbnail size (600, 800, or 1200)
        - lazy_loading: Whether lazy loading is enabled
        - exclude_patterns: Comma/semicolon-separated exclusion patterns
    """
    config = configparser.ConfigParser()
    slate_dirs: list[str] = []
    current_slate_dir: str = ""
    selected_slate_dirs: list[str] = []
    generate_thumbnails: bool = False  # Default to original behavior
    thumbnail_size: int = 600  # Default thumbnail size
    lazy_loading: bool = True  # Default to lazy loading enabled
    exclude_patterns: str = ""  # Default to no exclusions
    if os.path.exists(CONFIG_FILE):
        try:
            with codecs.open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.read_file(f)
            try:
                current_slate_dir = config.get("Settings", "current_slate_dir")
                logger.info(f"Loaded current_slate_dir from config: {current_slate_dir}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                current_slate_dir = ""
                logger.warning("current_slate_dir not found in config.")

            try:
                slate_dirs_str = config.get("Settings", "slate_dirs")
                slate_dirs = slate_dirs_str.split("|") if slate_dirs_str else []
                logger.info(f"Loaded slate_dirs from config: {slate_dirs}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                slate_dirs = []
                logger.warning("slate_dirs not found in config.")

            try:
                selected_slate_dirs_str = config.get("Settings", "selected_slate_dirs")
                selected_slate_dirs = selected_slate_dirs_str.split("|") if selected_slate_dirs_str else []
                # Filter out empty strings
                selected_slate_dirs = [d for d in selected_slate_dirs if d]
                logger.info(f"Loaded selected_slate_dirs from config: {selected_slate_dirs}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                # Backwards compatibility: default to current_slate_dir if it exists
                if current_slate_dir and os.path.exists(current_slate_dir):
                    selected_slate_dirs = [current_slate_dir]
                    logger.info(f"selected_slate_dirs not found in config, defaulting to [{current_slate_dir}]")
                else:
                    selected_slate_dirs = []
                    logger.info("selected_slate_dirs not found in config, defaulting to empty list.")

            try:
                generate_thumbnails = config.getboolean("Settings", "generate_thumbnails")
                logger.info(f"Loaded generate_thumbnails from config: {generate_thumbnails}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                generate_thumbnails = False
                logger.info("generate_thumbnails not found in config, defaulting to False.")

            try:
                thumbnail_size = config.getint("Settings", "thumbnail_size")
                # Validate the size is one of the allowed values
                if thumbnail_size not in [600, 800, 1200]:
                    thumbnail_size = 600
                    logger.warning("Invalid thumbnail_size in config, defaulting to 600.")
                else:
                    logger.info(f"Loaded thumbnail_size from config: {thumbnail_size}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                thumbnail_size = 600
                logger.info("thumbnail_size not found in config, defaulting to 600.")

            try:
                lazy_loading = config.getboolean("Settings", "lazy_loading")
                logger.info(f"Loaded lazy_loading from config: {lazy_loading}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                lazy_loading = True
                logger.info("lazy_loading not found in config, defaulting to True.")

            try:
                exclude_patterns = config.get("Settings", "exclude_patterns")
                logger.info(f"Loaded exclude_patterns from config: {exclude_patterns}")
            except (configparser.NoSectionError, configparser.NoOptionError):
                exclude_patterns = ""
                logger.info("exclude_patterns not found in config, defaulting to empty.")
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            logger.debug(traceback.format_exc())
            current_slate_dir = ""
            slate_dirs = []
            selected_slate_dirs = []
            generate_thumbnails = False
            thumbnail_size = 600
            lazy_loading = True
            exclude_patterns = ""
    else:
        current_slate_dir = ""
        slate_dirs = []
        selected_slate_dirs = []
        generate_thumbnails = False
        thumbnail_size = 600
        lazy_loading = True
        exclude_patterns = ""
        logger.warning("Config file not found. Using default settings.")
    return current_slate_dir, slate_dirs, selected_slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading, exclude_patterns


@log_function
def save_config(
    current_slate_dir: str,
    slate_dirs: list[str],
    selected_slate_dirs: list[str],
    generate_thumbnails: bool = False,
    thumbnail_size: int = 600,
    lazy_loading: bool = True,
    exclude_patterns: str = ""
) -> None:
    """Save configuration to config file.

    Args:
        current_slate_dir: Currently active directory (legacy)
        slate_dirs: List of all cached directories
        selected_slate_dirs: List of directories selected for scanning
        generate_thumbnails: Whether to generate thumbnails
        thumbnail_size: Thumbnail size (600, 800, or 1200)
        lazy_loading: Whether lazy loading is enabled
        exclude_patterns: Comma/semicolon-separated exclusion patterns
    """
    config = configparser.ConfigParser()
    if not config.has_section("Settings"):
        config.add_section("Settings")
    config.set("Settings", "current_slate_dir", current_slate_dir)
    config.set("Settings", "slate_dirs", "|".join(slate_dirs))
    config.set("Settings", "selected_slate_dirs", "|".join(selected_slate_dirs))
    config.set("Settings", "generate_thumbnails", str(generate_thumbnails))
    config.set("Settings", "thumbnail_size", str(thumbnail_size))
    config.set("Settings", "lazy_loading", str(lazy_loading))
    config.set("Settings", "exclude_patterns", exclude_patterns)
    try:
        with codecs.open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            config.write(configfile)
        logger.info(f"Configuration saved: current_slate_dir={current_slate_dir}, slate_dirs={slate_dirs}, selected_slate_dirs={selected_slate_dirs}, generate_thumbnails={generate_thumbnails}, thumbnail_size={thumbnail_size}, lazy_loading={lazy_loading}, exclude_patterns={exclude_patterns}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        logger.debug(traceback.format_exc())
