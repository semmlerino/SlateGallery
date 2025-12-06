"""Cache manager - extracted identically from original SlateGallery.py"""

import hashlib
import json
import os
import threading
import time
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
    def get_composite_cache_file(self, root_dirs: list[str]) -> str:
        """Generate cache filename for multiple directories.

        Args:
            root_dirs: List of root directories to cache together

        Returns:
            Path to composite cache file
        """
        # Sort directories for consistent key regardless of order
        sorted_dirs = sorted(root_dirs)
        combined = "|".join(sorted_dirs)
        composite_hash = hashlib.md5(combined.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"composite_{composite_hash}.json")

    @log_function
    def load_composite_cache(self, root_dirs: list[str]) -> Optional[dict[str, object]]:
        """Load cache for multiple directories.

        Args:
            root_dirs: List of root directories

        Returns:
            Dictionary of slates without _metadata, or None if cache doesn't exist
        """
        cache_file = self.get_composite_cache_file(root_dirs)
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cache_data: dict[str, object] = json.load(f)

                # Strip _metadata from returned slates
                slates = {k: v for k, v in cache_data.items() if k != "_metadata"}
                logger.info(f"Loaded composite cache for {len(root_dirs)} directories")
                return slates
            except Exception as e:
                logger.error(f"Error loading composite cache: {e}", exc_info=True)
                return None
        else:
            logger.info(f"No composite cache found for {len(root_dirs)} directories")
            return None

    @log_function
    def save_composite_cache(self, root_dirs: list[str], slates: dict[str, object]) -> None:
        """Save cache for multiple directories.

        Args:
            root_dirs: List of root directories
            slates: Dictionary of slates to cache
        """
        cache_file = self.get_composite_cache_file(root_dirs)
        try:
            # Count total images across all slates
            file_count = sum(
                len(s.get("images", [])) if isinstance(s, dict) else 0
                for s in slates.values()
            )

            # Get max modification time across all directories
            dir_mtimes = [
                os.path.getmtime(d) for d in root_dirs if os.path.exists(d)
            ]
            max_mtime = max(dir_mtimes) if dir_mtimes else 0

            # Add metadata for cache validation
            cache_data = {
                "_metadata": {
                    "scan_time": time.time(),
                    "file_count": file_count,
                    "dir_mtime": max_mtime,
                    "root_dirs": sorted(root_dirs),
                },
                **slates,
            }

            with open(cache_file, "w") as f:
                json.dump(cache_data, f)
            logger.info(f"Saved composite cache for {len(root_dirs)} directories ({file_count} images)")
        except Exception as e:
            logger.error(f"Error saving composite cache: {e}", exc_info=True)

    @log_function
    def validate_composite_cache(self, root_dirs: list[str]) -> bool:
        """Check if composite cache for directories is still valid.

        Args:
            root_dirs: List of root directories

        Returns:
            True if cache is valid, False if stale or missing
        """
        cache_file = self.get_composite_cache_file(root_dirs)
        if not os.path.exists(cache_file):
            return False

        try:
            with open(cache_file) as f:
                cache_data: dict[str, object] = json.load(f)

            metadata = cache_data.get("_metadata")
            if not metadata or not isinstance(metadata, dict):
                logger.info("Composite cache has no metadata (old format)")
                return False

            # Check if directories match
            cached_dirs = metadata.get("root_dirs", [])
            if sorted(root_dirs) != sorted(cached_dirs):
                logger.info("Composite cache directories don't match")
                return False

            # Check if any directory was modified
            cached_mtime = metadata.get("dir_mtime", 0)
            for root_dir in root_dirs:
                if not os.path.exists(root_dir):
                    logger.info(f"Directory {root_dir} no longer exists")
                    return False
                if os.path.getmtime(root_dir) > cached_mtime:
                    logger.info(f"Directory {root_dir} modified since cache")
                    return False

            return True
        except Exception as e:
            logger.error(f"Error validating composite cache: {e}", exc_info=True)
            return False

    @log_function
    def load_cache(self, root_dir: str) -> Optional[dict[str, object]]:
        """Load cache and strip metadata before returning.

        Returns:
            Dictionary of slates without _metadata, or None if cache doesn't exist
        """
        cache_file = self.get_cache_file(root_dir)
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cache_data: dict[str, object] = json.load(f)

                # Strip _metadata from returned slates
                slates = {k: v for k, v in cache_data.items() if k != "_metadata"}
                logger.info(f"Loaded slates from cache for directory: {root_dir}")
                return slates
            except Exception as e:
                logger.error(f"Error loading cache for {root_dir}: {e}", exc_info=True)
                return None
        else:
            logger.info(f"No cache found for directory: {root_dir}")
            return None

    @log_function
    def validate_cache(self, root_dir: str) -> bool:
        """Check if cache for directory is still valid.

        Validates by comparing directory modification time with cached timestamp.

        Returns:
            True if cache is valid, False if stale or missing metadata
        """
        cache_file = self.get_cache_file(root_dir)
        if not os.path.exists(cache_file):
            return False

        try:
            with open(cache_file) as f:
                cache_data: dict[str, object] = json.load(f)

            metadata = cache_data.get("_metadata")
            if not metadata or not isinstance(metadata, dict):
                logger.info(f"Cache for {root_dir} has no metadata (old format)")
                return False

            # Check directory modification time
            cached_mtime = metadata.get("dir_mtime", 0)
            if not os.path.exists(root_dir):
                logger.info(f"Directory {root_dir} no longer exists")
                return False

            current_mtime = os.path.getmtime(root_dir)
            if current_mtime > cached_mtime:
                logger.info(f"Cache for {root_dir} is stale (dir modified since scan)")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating cache for {root_dir}: {e}", exc_info=True)
            return False

    @log_function
    def save_cache(self, root_dir: str, slates: dict[str, object]) -> None:
        cache_file = self.get_cache_file(root_dir)
        try:
            # Count total images across all slates
            file_count = sum(
                len(s.get("images", [])) if isinstance(s, dict) else 0
                for s in slates.values()
            )

            # Get directory modification time
            dir_mtime = os.path.getmtime(root_dir) if os.path.exists(root_dir) else 0

            # Add metadata for cache validation
            cache_data = {
                "_metadata": {
                    "scan_time": time.time(),
                    "file_count": file_count,
                    "dir_mtime": dir_mtime,
                },
                **slates,
            }

            with open(cache_file, "w") as f:
                json.dump(cache_data, f)
            logger.info(f"Saved cache for directory: {root_dir} ({file_count} images)")
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
