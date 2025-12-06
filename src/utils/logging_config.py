"""Logging configuration for SlateGallery - extracted identically from original.

Uses lazy initialization to avoid crashes in read-only environments.
Uses a library-local logger instead of the root logger to avoid polluting host apps.
"""

import logging
import logging.handlers
import os
import traceback
from collections.abc import Callable
from functools import wraps
from typing import Optional, TypeVar

# Use typing_extensions for ParamSpec (Python 3.9 compatibility)
from typing_extensions import ParamSpec

# ----------------------------- Logging Configuration -----------------------------

LOG_FILE = os.path.expanduser("~/.slate_gallery/gallery_generator.log")

# Library-local logger (NOT root logger) to avoid polluting host applications
logger = logging.getLogger("slate_gallery")

# Module-level state for lazy initialization
_handlers_initialized = False
_initialization_error: Optional[str] = None


def ensure_handlers_initialized() -> None:
    """Lazily initialize logging handlers on first use.

    Thread-safe initialization that:
    - Creates log directory if needed (with error handling)
    - Sets up file and console handlers
    - Gracefully falls back to console-only on permission errors
    """
    global _handlers_initialized, _initialization_error

    if _handlers_initialized:
        return

    # Set base level
    logger.setLevel(logging.INFO)

    # Formatter for all handlers
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s")

    # Always add console handler (no filesystem access needed)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Try to add file handler (may fail in read-only environments)
    try:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir and not os.path.isdir(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        _initialization_error = f"File logging disabled: {e}"
        # Console handler is already added, continue without file logging

    # Suppress verbose third-party library logging
    logging.getLogger("piexif").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    _handlers_initialized = True

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
        ensure_handlers_initialized()  # Lazy initialization on first use
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
