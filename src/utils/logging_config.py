"""Logging configuration for SlateGallery - extracted identically from original."""

import logging
import logging.handlers
import os
import traceback
from functools import wraps

# ----------------------------- Logging Configuration -----------------------------

LOG_FILE = os.path.expanduser("~/.slate_gallery/gallery_generator.log")

log_dir = os.path.dirname(LOG_FILE)
if not os.path.isdir(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)


console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ----------------------------- Logging Decorator -----------------------------


def log_function(func):
    """Decorator to log function entry, exit, and exceptions."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Entering function: {func.__name__}")
        # Avoid logging arguments during intensive tasks
        # logger.debug("Arguments: args={}, kwargs={}".format(args, kwargs))
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting function: {func.__name__}")
            # logger.debug("Return value: {}".format(result))
            return result
        except Exception as e:
            logger.error(f"Exception in function {func.__name__}: {e}")
            logger.debug(traceback.format_exc())
            raise  # Re-raise exception after logging

    return wrapper
