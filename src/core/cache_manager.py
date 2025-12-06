"""Cache manager - extracted identically from original SlateGallery.py

Supports EXIF caching (V2) with per-file mtime validation.
"""

import concurrent.futures
import hashlib
import json
import os
import threading
import time
from collections.abc import Callable, Sequence
from typing import Optional, cast

from utils.logging_config import log_function, logger

# Cache format version
# V1 (legacy): Only paths, no EXIF
# V2 (current): Paths + EXIF + per-file mtime
CACHE_VERSION = 2

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
                    cache_data: dict[str, object] = cast(dict[str, object], json.load(f))

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
            file_count = 0
            for s in slates.values():
                if not isinstance(s, dict):
                    continue
                images_obj = s.get("images")  # type: ignore[assignment]
                if isinstance(images_obj, list):
                    file_count += len(images_obj)  # type: ignore[arg-type]

            # Get max modification time across all directories
            dir_mtimes = [
                os.path.getmtime(d) for d in root_dirs if os.path.exists(d)
            ]
            max_mtime = max(dir_mtimes) if dir_mtimes else 0

            # Add metadata for cache validation
            cache_data = {
                "_metadata": {
                    "version": CACHE_VERSION,
                    "scan_time": time.time(),
                    "file_count": file_count,
                    "dir_mtime": max_mtime,
                    "root_dirs": sorted(root_dirs),
                },
                **slates,
            }

            with open(cache_file, "w") as f:
                json.dump(cache_data, f)
            logger.info(f"Saved V{CACHE_VERSION} composite cache for {len(root_dirs)} directories ({file_count} images)")
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
                cache_data: dict[str, object] = cast(dict[str, object], json.load(f))

            metadata_obj = cache_data.get("_metadata")
            if not isinstance(metadata_obj, dict):
                logger.info("Composite cache has no metadata (old format)")
                return False
            metadata = cast(dict[str, object], metadata_obj)

            # Check if directories match
            cached_dirs_obj = metadata.get("root_dirs")
            if not isinstance(cached_dirs_obj, list):
                logger.info("Composite cache has invalid root_dirs")
                return False
            # All elements are unknown, but it's a list, so we can iterate
            if sorted(str(d) for d in root_dirs) != sorted(str(d) for d in cached_dirs_obj):  # type: ignore[arg-type]
                logger.info("Composite cache directories don't match")
                return False

            # Check if any directory was modified
            dir_mtime_obj = metadata.get("dir_mtime")
            if not isinstance(dir_mtime_obj, (int, float)):
                logger.info("Composite cache has invalid dir_mtime")
                return False
            cached_mtime = float(dir_mtime_obj)
            for root_dir in root_dirs:
                if not os.path.exists(root_dir):
                    logger.info(f"Directory {root_dir} no longer exists")
                    return False
                if os.path.getmtime(root_dir) > cached_mtime:
                    logger.info(f"Directory {root_dir} modified since cache")
                    return False

            # Check file count hasn't changed (detects additions/deletions in subdirs)
            file_count_obj = metadata.get("file_count")
            if isinstance(file_count_obj, int):
                current_count = self._count_image_files_multi(root_dirs)
                if current_count != file_count_obj:
                    logger.info(f"Composite cache is stale (file count changed: {file_count_obj} -> {current_count})")
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
                    cache_data: dict[str, object] = cast(dict[str, object], json.load(f))

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
                cache_data: dict[str, object] = cast(dict[str, object], json.load(f))

            metadata_obj = cache_data.get("_metadata")
            if not isinstance(metadata_obj, dict):
                logger.info(f"Cache for {root_dir} has no metadata (old format)")
                return False
            metadata = cast(dict[str, object], metadata_obj)

            # Check directory modification time
            dir_mtime_obj = metadata.get("dir_mtime")
            if not isinstance(dir_mtime_obj, (int, float)):
                logger.info(f"Cache for {root_dir} has invalid dir_mtime")
                return False
            cached_mtime = float(dir_mtime_obj)
            if not os.path.exists(root_dir):
                logger.info(f"Directory {root_dir} no longer exists")
                return False

            current_mtime = os.path.getmtime(root_dir)
            if current_mtime > cached_mtime:
                logger.info(f"Cache for {root_dir} is stale (dir modified since scan)")
                return False

            # Check file count hasn't changed (detects additions/deletions in subdirs)
            file_count_obj = metadata.get("file_count")
            if isinstance(file_count_obj, int):
                current_count = self._count_image_files(root_dir)
                if current_count != file_count_obj:
                    logger.info(f"Cache for {root_dir} is stale (file count changed: {file_count_obj} -> {current_count})")
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
            file_count = 0
            for s in slates.values():
                if not isinstance(s, dict):
                    continue
                images_obj = s.get("images")  # type: ignore[assignment]
                if isinstance(images_obj, list):
                    file_count += len(images_obj)  # type: ignore[arg-type]

            # Get directory modification time
            dir_mtime = os.path.getmtime(root_dir) if os.path.exists(root_dir) else 0

            # Add metadata for cache validation
            cache_data = {
                "_metadata": {
                    "version": CACHE_VERSION,
                    "scan_time": time.time(),
                    "file_count": file_count,
                    "dir_mtime": dir_mtime,
                },
                **slates,
            }

            with open(cache_file, "w") as f:
                json.dump(cache_data, f)
            logger.info(f"Saved V{CACHE_VERSION} cache for directory: {root_dir} ({file_count} images)")
        except Exception as e:
            logger.error(f"Error saving cache for {root_dir}: {e}", exc_info=True)

    @log_function
    def process_images_batch(
        self, image_paths: Sequence[object], _callback: Optional[Callable[[int], None]] = None
    ) -> list[dict[str, object]]:
        """Process a batch of image paths (legacy, no EXIF caching).

        Args:
            image_paths: Sequence of image paths to process
            _callback: Optional progress callback (unused in current implementation)

        Returns:
            List of dictionaries containing image path information
        """
        logger.info(f"Processing batch of {len(image_paths)} images for scanning.")

        return [{"path": str(path)} for path in image_paths]

    @log_function
    def process_images_batch_with_exif(
        self,
        image_paths: Sequence[str],
        existing_cache: Optional[dict[str, dict[str, object]]] = None,
        _callback: Optional[Callable[[int], None]] = None,
    ) -> list[dict[str, object]]:
        """Process images with EXIF extraction and caching.

        Args:
            image_paths: Sequence of image file paths
            existing_cache: Previously cached slate data for incremental updates
            _callback: Optional progress callback

        Returns:
            List of image dictionaries with path, mtime, and exif data
        """
        from core.image_processor import get_exif_data

        # Build lookup of existing cached images by path
        cached_by_path: dict[str, dict[str, object]] = {}
        if existing_cache:
            for slate_data in existing_cache.values():
                # slate_data is already dict[str, object] from type annotation
                images = slate_data.get("images")
                if not isinstance(images, list):
                    continue
                for img in images:  # type: ignore[union-attr]
                    if not isinstance(img, dict):
                        continue
                    if "path" not in img:
                        continue
                    img_dict = cast(dict[str, object], img)
                    path_obj = img_dict.get("path")
                    if path_obj is not None:
                        cached_by_path[str(path_obj)] = img_dict

        results: list[dict[str, object]] = []
        to_process: list[tuple[str, float]] = []  # (path, mtime) for images needing EXIF

        # Check which images need EXIF extraction
        for path_obj in image_paths:
            path = str(path_obj)
            try:
                current_mtime = os.path.getmtime(path)
            except OSError:
                continue  # Skip inaccessible files

            cached = cached_by_path.get(path)
            if cached and cached.get("mtime") == current_mtime and "exif" in cached:
                # Cache hit: use cached EXIF data
                results.append({
                    "path": path,
                    "mtime": current_mtime,
                    "exif": cached["exif"],
                })
            else:
                # Cache miss: need to extract EXIF
                to_process.append((path, current_mtime))

        cache_hits = len(results)

        # Parallel EXIF extraction for cache misses
        if to_process:
            max_workers = min(len(to_process), self.max_workers * 2)  # I/O bound
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._extract_exif_for_cache, path, mtime, get_exif_data): path
                    for path, mtime in to_process
                }

                for completed, future in enumerate(
                    concurrent.futures.as_completed(futures), start=1
                ):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        path = futures[future]
                        logger.error(f"EXIF extraction failed for {path}: {e}")

                    if _callback:
                        _callback(int((completed / len(to_process)) * 100))

        # Sort results by path for consistent ordering
        results.sort(key=lambda x: str(x.get("path", "")))

        logger.info(
            f"Processed {len(results)} images ({cache_hits} cache hits, "
            f"{len(to_process)} EXIF extractions)"
        )
        return results

    def _extract_exif_for_cache(
        self,
        path: str,
        mtime: float,
        get_exif_data: Callable[[str], dict[str, object]],
    ) -> Optional[dict[str, object]]:
        """Extract EXIF data for a single image.

        Args:
            path: Image file path
            mtime: File modification time
            get_exif_data: Function to extract EXIF data

        Returns:
            Dictionary with path, mtime, and exif data, or None on error
        """
        try:
            exif = get_exif_data(path)
            # Convert EXIF to JSON-serializable format
            serializable_exif = self._make_exif_serializable(exif)
            return {
                "path": path,
                "mtime": mtime,
                "exif": serializable_exif,
            }
        except Exception as e:
            logger.error(f"Failed to extract EXIF for {path}: {e}")
            return None

    def _make_exif_serializable(self, exif: dict[str, object]) -> dict[str, object]:
        """Convert EXIF data to JSON-serializable format.

        Handles IFDRational, tuples, and other non-serializable types.
        """
        result: dict[str, object] = {}
        for key, value in exif.items():
            result[key] = self._convert_value(value)
        return result

    def _convert_value(self, value: object) -> object:
        """Recursively convert a value to JSON-serializable format."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, bytes):
            # Try to decode as UTF-8, otherwise convert to hex
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.hex()
        if isinstance(value, tuple):
            # Handle rational numbers (IFDRational, etc.) - common pattern is (numerator, denominator)
            tuple_len = len(value)  # type: ignore[arg-type]
            if tuple_len == 2:
                try:
                    # Try to convert to float for rational numbers
                    num = float(value[0])  # type: ignore[arg-type]
                    denom = float(value[1])  # type: ignore[arg-type]
                    if denom != 0:
                        return num / denom
                    return num
                except (ValueError, TypeError):
                    pass
            # Convert tuple elements recursively
            converted_list: list[object] = []
            for idx in range(tuple_len):
                v = value[idx]  # type: ignore[index]
                converted_list.append(self._convert_value(v))  # type: ignore[arg-type]
            return converted_list
        if isinstance(value, list):
            converted: list[object] = []
            list_len = len(value)  # type: ignore[arg-type]
            for idx in range(list_len):
                v = value[idx]  # type: ignore[index]
                converted.append(self._convert_value(v))  # type: ignore[arg-type]
            return converted
        if isinstance(value, dict):
            result_dict: dict[str, object] = {}
            for k, v in value.items():  # type: ignore[union-attr]
                key: str = str(k)  # type: ignore[arg-type]
                converted_val: object = self._convert_value(v)  # type: ignore[arg-type]
                result_dict[key] = converted_val
            return result_dict
        # For other types (IFDRational, etc.), try to get numeric value
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            # Handle Fraction-like objects
            try:
                if value.denominator != 0:  # type: ignore[union-attr]
                    return float(value.numerator) / float(value.denominator)  # type: ignore[union-attr]
                return float(value.numerator)  # type: ignore[union-attr]
            except (ValueError, TypeError, AttributeError):
                pass
        # Last resort: try to convert to float or string
        try:
            return float(value)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return str(value)

    @log_function
    def get_cache_version(self, root_dir: str) -> int:
        """Get the version of a cached directory.

        Returns:
            Cache version (1 for legacy, 2 for current), 0 if no cache
        """
        cache_file = self.get_cache_file(root_dir)
        if not os.path.exists(cache_file):
            return 0

        try:
            with open(cache_file) as f:
                cache_data: dict[str, object] = cast(dict[str, object], json.load(f))

            metadata_obj = cache_data.get("_metadata")
            if not isinstance(metadata_obj, dict):
                return 0
            metadata = cast(dict[str, object], metadata_obj)
            version_obj = metadata.get("version")
            if isinstance(version_obj, int):
                return version_obj
            return 1  # Default to V1 for legacy
        except Exception:
            return 0

    def _count_image_files(self, root_dir: str) -> int:
        """Quick count of image files for cache validation.

        Walks the directory tree and counts image files, skipping dot directories
        and macOS resource fork files.

        Args:
            root_dir: Root directory to scan

        Returns:
            Total count of image files
        """
        image_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"}
        count = 0
        try:
            for _dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
                # Skip dot directories (modifying in-place prevents descent)
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                for f in filenames:
                    # Skip macOS resource fork files
                    if f.startswith("._"):
                        continue
                    if os.path.splitext(f)[1].lower() in image_extensions:
                        count += 1
        except OSError as e:
            logger.warning(f"Error counting files in {root_dir}: {e}")
        return count

    def _count_image_files_multi(self, root_dirs: list[str]) -> int:
        """Count image files across multiple directories.

        Args:
            root_dirs: List of root directories to scan

        Returns:
            Total count of image files across all directories
        """
        return sum(self._count_image_files(d) for d in root_dirs)

    @log_function
    def shutdown(self) -> None:
        try:
            logger.info("ImprovedCacheManager shutdown completed.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
