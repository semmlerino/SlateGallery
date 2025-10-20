"""Logging configuration for SlateGallery - extracted identically from original."""

import logging
import logging.handlers
import os
import traceback
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

# Use typing_extensions for ParamSpec (Python 3.9 compatibility)
from typing_extensions import ParamSpec

# ----------------------------- Logging Configuration -----------------------------

LOG_FILE = os.path.expanduser("~/.slate_gallery/gallery_generator.log")

log_dir = os.path.dirname(LOG_FILE)
if not os.path.isdir(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger()
logger.setLevel(logging.INFO)  # Changed from DEBUG to reduce log spam

file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.INFO)  # Changed from DEBUG to reduce log spam


console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress verbose third-party library logging
logging.getLogger('piexif').setLevel(logging.WARNING)  # Suppress EXIF tag spam
logging.getLogger('PIL').setLevel(logging.WARNING)  # Suppress PIL debug messages

# ----------------------------- Logging Decorator -----------------------------

# Type variables for decorator that preserves function signatures
P = ParamSpec('P')
R = TypeVar('R')


def log_function(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to log function entry, exit, and exceptions.

    Args:
        func: The function to decorate. Can have any parameters and return type.

    Returns:
        A wrapped function with the same signature that logs entry, exit, and exceptions.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.debug(f"Entering function: {func.__name__}")
        # Avoid logging arguments during intensive tasks
        # logger.debug("Arguments: args={}, kwargs={}".format(args, kwargs))
        try:
            result: R = func(*args, **kwargs)
            logger.debug(f"Exiting function: {func.__name__}")
            # logger.debug("Return value: {}".format(result))
            return result
        except Exception as e:
            logger.error(f"Exception in function {func.__name__}: {e}")
            logger.debug(traceback.format_exc())
            raise  # Re-raise exception after logging

    return wrapper
