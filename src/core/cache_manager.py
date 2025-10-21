"""Cache manager - extracted identically from original SlateGallery.py"""

import hashlib
import json
import os
import threading
from collections.abc import Callable, Sequence
from typing import Optional

from utils.logging_config import log_function, logger

# ----------------------------- ImprovedCacheManager Class -----------------------------


class ImprovedCacheManager:
    def __init__(self, base_dir: str = ".", max_workers: int = 4, batch_size: int = 100) -> None:
        self.base_dir: str = base_dir
        self.cache_dir: str = os.path.join(base_dir, "cache")
        self.thumb_dir: str = os.path.join(base_dir, "thumbnails")
        self.metadata_file: str = os.path.join(self.cache_dir, "metadata.json")

        self.max_workers: int = max_workers
        self.batch_size: int = batch_size
        self._cache_lock: threading.Lock = threading.Lock()
        self._metadata: dict[str, object] = {}
        self._processing: set[str] = set()

        self.ensure_directories()
        logger.debug(f"ImprovedCacheManager initialized with base_dir: {self.base_dir}")

    @log_function
    def ensure_directories(self) -> None:
        for directory in [self.cache_dir]:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    logger.info(f"Created directory: {directory}")
                except Exception as e:
                    logger.error(f"Error creating directory {directory}: {e}", exc_info=True)

    @log_function
    def get_cache_file(self, root_dir: str) -> str:
        # Create a unique name for the root_dir, e.g., hash
        dir_hash = hashlib.md5(root_dir.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{dir_hash}.json")

    @log_function
    def load_cache(self, root_dir: str) -> Optional[dict[str, object]]:
        cache_file = self.get_cache_file(root_dir)
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    slates: dict[str, object] = json.load(f)
                logger.info(f"Loaded slates from cache for directory: {root_dir}")
                return slates
            except Exception as e:
                logger.error(f"Error loading cache for {root_dir}: {e}", exc_info=True)
                return None
        else:
            logger.info(f"No cache found for directory: {root_dir}")
            return None

    @log_function
    def save_cache(self, root_dir: str, slates: dict[str, object]) -> None:
        cache_file = self.get_cache_file(root_dir)
        try:
            with open(cache_file, "w") as f:
                json.dump(slates, f)
            logger.info(f"Saved cache for directory: {root_dir}")
        except Exception as e:
            logger.error(f"Error saving cache for {root_dir}: {e}", exc_info=True)

    @log_function
    def process_images_batch(
        self, image_paths: Sequence[object], _callback: Optional[Callable[[int], None]] = None
    ) -> list[dict[str, object]]:
        """Process a batch of image paths.

        Args:
            image_paths: Sequence of image paths to process
            _callback: Optional progress callback (unused in current implementation)

        Returns:
            List of dictionaries containing image path information
        """
        logger.info(f"Processing batch of {len(image_paths)} images for scanning.")

        return [{"path": str(path)} for path in image_paths]

    @log_function
    def shutdown(self) -> None:
        try:
            logger.info("ImprovedCacheManager shutdown completed.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
