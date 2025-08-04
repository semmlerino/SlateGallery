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
def load_config():
    config = configparser.ConfigParser()
    slate_dirs = []
    current_slate_dir = ""
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
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            logger.debug(traceback.format_exc())
            current_slate_dir = ""
            slate_dirs = []
    else:
        current_slate_dir = ""
        slate_dirs = []
        logger.warning("Config file not found. Using default settings.")
    return current_slate_dir, slate_dirs


@log_function
def save_config(current_slate_dir, slate_dirs):
    config = configparser.ConfigParser()
    if not config.has_section("Settings"):
        config.add_section("Settings")
    config.set("Settings", "current_slate_dir", current_slate_dir)
    config.set("Settings", "slate_dirs", "|".join(slate_dirs))
    try:
        with codecs.open(CONFIG_FILE, "w", encoding="utf-8") as configfile:
            config.write(configfile)
        logger.info(f"Configuration saved: current_slate_dir={current_slate_dir}, slate_dirs={slate_dirs}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        logger.debug(traceback.format_exc())
