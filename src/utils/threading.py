"""Threading utilities - extracted identically from original SlateGallery.py"""

import contextlib
import multiprocessing
import os
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, Protocol, Union, cast, runtime_checkable

from PySide6 import QtCore
from PySide6.QtCore import Signal
from typing_extensions import override

from .logging_config import log_function, logger

# Type aliases for better documentation (TypedDict imports cause circular dependencies)
# These match the TypedDict definitions in core.gallery_generator
# Note: Using object for values since the exact structure varies and is checked at runtime
ImageData = dict[str, object]
FocalLengthData = dict[str, object]  # Structure: {"value": float, "count": int}
DateData = dict[str, object]  # Structure: {"value": str, "count": int, "display_date": str}


@runtime_checkable
class CacheManagerProtocol(Protocol):
    """Protocol defining the interface for cache managers."""
    def process_images_batch(
        self, image_paths: Sequence[object], _callback: Optional[Callable[[int], None]] = None
    ) -> list[dict[str, object]]:
        ...

    def process_images_batch_with_exif(
        self,
        image_paths: Sequence[str],
        existing_cache: Optional[dict[str, dict[str, object]]] = None,
        _callback: Optional[Callable[[int], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> list[dict[str, object]]:
        ...

    def save_cache(self, root_dir: str, slates: object) -> None:
        ...

    def save_composite_cache(self, root_dirs: list[str], slates: object) -> None:
        ...

# ----------------------------- Worker Threads -----------------------------


def _scan_single_root_dir(root_dir: str, exclude_patterns: str) -> dict[str, dict[str, list[str]]]:
    """Module-level helper function for concurrent directory scanning.

    This function must be at module level (not nested) so ProcessPoolExecutor can pickle it.

    Args:
        root_dir: Root directory path to scan
        exclude_patterns: Comma/semicolon-separated exclusion patterns

    Returns:
        Dictionary with prefixed slate names mapped to slate data
    """
    from core.image_processor import scan_directories

    if not os.path.exists(root_dir):
        logger.warning(f"Skipping non-existent root directory: {root_dir}")
        return {}

    # Get basename for prefixing
    root_basename = os.path.basename(root_dir.rstrip(os.sep))
    if not root_basename:
        root_basename = root_dir.replace(os.sep, "_").strip("_") or "Root"

    logger.info(f"Scanning: {root_dir} (prefix: {root_basename})")

    # Scan this directory
    slates: dict[str, dict[str, list[str]]] = scan_directories(root_dir, exclude_patterns)

    # Prefix slate names to avoid conflicts between different roots
    prefixed_slates: dict[str, dict[str, list[str]]] = {}
    for slate_name, slate_data in slates.items():
        if slate_name == "/":
            prefixed_name = f"{root_basename}/Root"
        else:
            clean_slate_name = slate_name.lstrip("/")
            prefixed_name = f"{root_basename}/{clean_slate_name}"
        prefixed_slates[prefixed_name] = slate_data

    logger.debug(f"Completed scanning {root_dir}: {len(prefixed_slates)} slates")
    return prefixed_slates


class ScanThread(QtCore.QThread):
    scan_complete: Signal = Signal(dict, str)  # type: ignore[misc]
    progress: Signal = Signal(int)  # type: ignore[misc]

    def __init__(self, root_dirs: Union[str, list[str]], cache_manager: CacheManagerProtocol, exclude_patterns: str = "") -> None:
        """Initialize scan thread with one or more root directories.

        Args:
            root_dirs: Single directory path or list of directory paths to scan
            cache_manager: Cache manager for processing images
            exclude_patterns: Comma/semicolon-separated exclusion patterns
        """
        super().__init__()
        # Support both single directory (backwards compatibility) and multiple directories
        if isinstance(root_dirs, str):
            self.root_dirs: list[str] = [str(root_dirs)]
        else:
            self.root_dirs = [str(d) for d in root_dirs]
        self.cache_manager: CacheManagerProtocol = cache_manager
        self.exclude_patterns: str = exclude_patterns
        self._stop_event: threading.Event = threading.Event()

    def signal_stop(self) -> None:
        """Signal the thread to stop without waiting.

        This is useful when you want to stop multiple threads in parallel.
        Call this method on all threads first, then call wait() on each.
        """
        self._stop_event.set()

    def stop(self) -> None:
        """Gracefully stop the thread and wait for completion.

        Note: For multi-directory scans using ThreadPoolExecutor, already-running
        thread tasks may continue briefly after stop is called. The stop event
        prevents new work from starting and ensures clean thread termination.
        """
        self.signal_stop()
        if not self.wait(5000):  # Wait max 5 seconds for thread to finish
            logger.warning("ScanThread did not stop within timeout; some background processes may still be running")

    @log_function
    @override
    def run(self) -> None:
        try:
            from core.image_processor import scan_directories

            logger.info(f"Starting directory scan for {len(self.root_dirs)} root directory(ies)...")

            # Use appropriate scanning method based on number of directories
            if len(self.root_dirs) == 1:
                # Legacy single-directory mode
                logger.info(f"Scanning single directory: {self.root_dirs[0]}")
                slates = scan_directories(self.root_dirs[0], self.exclude_patterns)
            else:
                # Multi-directory concurrent scanning mode
                logger.info(f"Scanning {len(self.root_dirs)} directories concurrently...")

                # Limit concurrent scans to avoid overwhelming I/O
                max_workers = min(len(self.root_dirs), multiprocessing.cpu_count())

                # Execute concurrent scans using module-level helper function
                merged_slates: dict[str, dict[str, list[str]]] = {}
                completed_dirs = 0

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all scan tasks
                    future_to_dir = {
                        executor.submit(_scan_single_root_dir, root_dir, self.exclude_patterns): root_dir
                        for root_dir in self.root_dirs
                    }

                    # Process results as they complete
                    for future in as_completed(future_to_dir):
                        if self._stop_event.is_set():
                            logger.info("Scan thread stopped by user request")
                            # Cancel any pending futures (works on Python 3.9+, ignored on older)
                            for pending_future in future_to_dir:
                                pending_future.cancel()
                            # Shutdown executor without waiting for running tasks
                            executor.shutdown(wait=False, cancel_futures=True)
                            self.scan_complete.emit({}, "Scan cancelled.")
                            return

                        root_dir = future_to_dir[future]
                        try:
                            result_slates = future.result()

                            # Merge results, handling name conflicts
                            for slate_name, slate_data in result_slates.items():
                                original_name = slate_name
                                counter = 2
                                while slate_name in merged_slates:
                                    slate_name = f"{original_name}_{counter}"
                                    counter += 1
                                    logger.warning(f"Slate name conflict: renamed {original_name} to {slate_name}")
                                merged_slates[slate_name] = slate_data

                            completed_dirs += 1
                            progress = int((completed_dirs / len(self.root_dirs)) * 50)  # First 50% is scanning
                            self.progress.emit(progress)
                            logger.info(f"Completed scan of {root_dir} ({completed_dirs}/{len(self.root_dirs)})")
                        except Exception as e:
                            logger.error(f"Error scanning {root_dir}: {e}", exc_info=True)
                            completed_dirs += 1

                slates = merged_slates
                logger.info(f"Concurrent scan complete: {len(slates)} total slates from {len(self.root_dirs)} directories")

            # Process EXIF data for all slates (with caching)
            total_slates: int = len(slates)
            logger.debug(f"Total slates to process: {total_slates}")

            # Use parallel slate processing for 3+ slates, sequential for 1-2
            if total_slates < 3:
                # Sequential path for small slate counts (avoids ThreadPoolExecutor overhead)
                for processed_slates, (_slate, data) in enumerate(slates.items(), start=1):
                    # Check if we should stop
                    if self._stop_event.is_set():
                        logger.info("Scan thread stopped by user request")
                        self.scan_complete.emit({}, "Scan cancelled.")
                        return

                    image_paths = data.get("images", [])
                    # Use EXIF-aware processing to cache metadata
                    processed_images = self.cache_manager.process_images_batch_with_exif(
                        [str(p) for p in image_paths],
                        existing_cache=None,  # Fresh scan, no existing cache
                        _callback=lambda p: self.progress.emit(50 + int(p / 2)),  # Second 50% is EXIF processing
                        stop_event=self._stop_event,
                    )
                    data["images"] = processed_images  # pyright: ignore[reportArgumentType]

                    # Progress: 50-100% for EXIF processing
                    exif_progress: float = (
                        50 + ((processed_slates / float(total_slates)) * 50) if total_slates > 0 else 100
                    )
                    self.progress.emit(int(exif_progress))
                    logger.debug(f"EXIF processing progress: {exif_progress:.2f}%")
            else:
                # Parallel slate processing for 3+ slates
                logger.info(f"Processing {total_slates} slates in parallel for EXIF extraction")
                max_slate_workers = min(total_slates, multiprocessing.cpu_count())
                logger.info(f"Using {max_slate_workers} workers for slate-level parallelism")

                def process_slate_exif(slate_name: str, slate_data: object) -> tuple[str, list[dict[str, object]]]:
                    """Process EXIF for a single slate (runs in worker thread)."""
                    if self._stop_event.is_set():
                        return (slate_name, [])

                    if not isinstance(slate_data, dict):
                        return (slate_name, [])

                    slate_dict = cast(dict[str, object], slate_data)
                    image_paths_val = slate_dict.get("images", [])
                    if not isinstance(image_paths_val, list):
                        return (slate_name, [])
                    image_paths_list = cast(list[object], image_paths_val)

                    processed_images = self.cache_manager.process_images_batch_with_exif(
                        [str(p) for p in image_paths_list],
                        existing_cache=None,
                        _callback=None,  # No per-image callback in parallel mode
                        stop_event=self._stop_event,
                    )
                    return (slate_name, processed_images)

                completed_count = 0
                with ThreadPoolExecutor(max_workers=max_slate_workers) as executor:
                    # Submit all slate processing tasks
                    future_to_slate = {
                        executor.submit(process_slate_exif, slate_name, slate_data): slate_name
                        for slate_name, slate_data in slates.items()
                    }

                    # Collect results as they complete
                    for future in as_completed(future_to_slate):
                        if self._stop_event.is_set():
                            logger.info("Scan thread stopped during parallel EXIF processing")
                            for pending_future in future_to_slate:
                                pending_future.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            self.scan_complete.emit({}, "Scan cancelled.")
                            return

                        slate_name = future_to_slate[future]
                        try:
                            slate_name_result, processed_images = future.result()
                            slates[slate_name_result]["images"] = processed_images  # pyright: ignore[reportArgumentType]

                            completed_count += 1
                            exif_progress = 50 + ((completed_count / total_slates) * 50)
                            self.progress.emit(int(exif_progress))
                            logger.debug(f"Completed EXIF for slate {slate_name_result} ({completed_count}/{total_slates})")
                        except Exception as e:
                            logger.error(f"Error processing EXIF for slate {slate_name}: {e}", exc_info=True)
                            completed_count += 1

                logger.info(f"Parallel EXIF processing complete: {completed_count} slates processed")

            # Save the scanned slates to cache
            if len(self.root_dirs) == 1:
                self.cache_manager.save_cache(self.root_dirs[0], slates)
            else:
                self.cache_manager.save_composite_cache(self.root_dirs, slates)

            self.scan_complete.emit(slates, "Scan complete.")
            logger.info("Scan completed.")
        except Exception as e:
            error_message: str = f"Error during directory scan: {e}"
            logger.error(error_message, exc_info=True)
            self.scan_complete.emit({}, error_message)


class GenerateGalleryThread(QtCore.QThread):
    gallery_complete: Signal = Signal(bool, str)  # type: ignore[misc]
    progress: Signal = Signal(int)  # type: ignore[misc]

    def __init__(
        self,
        selected_slates: list[str],
        slates_dict: dict[str, object],
        cache_manager: CacheManagerProtocol,
        output_dir: str,
        allowed_root_dirs: Union[str, list[str]],
        template_path: str,
        generate_thumbnails: bool,
        thumbnail_size: int = 600,
        lazy_loading: bool = True
    ) -> None:
        """Initialize gallery generation thread.

        Args:
            selected_slates: List of slate names to include in gallery
            slates_dict: Dictionary of all available slates
            cache_manager: Cache manager for processing images
            output_dir: Directory to write output HTML
            allowed_root_dirs: Single root directory or list of allowed root directories for security validation
            template_path: Path to Jinja2 template
            generate_thumbnails: Whether to generate thumbnails
            thumbnail_size: Size of thumbnails (600, 800, or 1200)
            lazy_loading: Whether to enable lazy loading
        """
        super().__init__()
        self.selected_slates: list[str] = selected_slates
        self.slates_dict: dict[str, object] = slates_dict
        self.cache_manager: CacheManagerProtocol = cache_manager
        self.output_dir: str = output_dir
        self.allowed_root_dirs: Union[str, list[str]] = allowed_root_dirs
        self.template_path: str = template_path
        self.generate_thumbnails: bool = generate_thumbnails
        self.thumbnail_size: int = thumbnail_size
        self.lazy_loading: bool = lazy_loading
        self._stop_event: threading.Event = threading.Event()

        # Lock for thread-safe operations
        self.focal_length_lock: threading.Lock = threading.Lock()
        self.focal_length_counts: dict[float, int] = {}

        # Date-related data structures
        self.date_lock: threading.Lock = threading.Lock()
        self.date_counts: dict[str, int] = {}  # Format: "YYYY-MM-DD": count
        self.unknown_date_count: int = 0  # Count of images without EXIF date
        self.unknown_focal_length_count: int = 0  # Count of images without focal length

        # Thumbnail directory
        self.thumb_dir: str = os.path.join(output_dir, "thumbnails")

        # Thread pool for parallel image processing
        # For I/O-bound operations (reading files, EXIF extraction), we can use more workers
        # Use 2x CPU count for I/O operations, capped at 16 to avoid overwhelming the system
        self.max_workers: int = min(multiprocessing.cpu_count() * 2, 16)
        logger.info(f"Using {self.max_workers} workers for parallel image processing")

        # Track skipped images for user feedback (thread-safe)
        self.skipped_lock: threading.Lock = threading.Lock()
        self.skipped_images: int = 0

    def signal_stop(self) -> None:
        """Signal the thread to stop without waiting.

        This is useful when you want to stop multiple threads in parallel.
        Call this method on all threads first, then call wait() on each.
        """
        self._stop_event.set()

    def stop(self) -> None:
        """Gracefully stop the thread and wait for completion.

        Note: Image processing tasks in the ThreadPoolExecutor may continue briefly
        after stop is called. The stop event prevents new slates from being processed
        and ensures clean thread termination.
        """
        self.signal_stop()
        if not self.wait(5000):  # Wait max 5 seconds for thread to finish
            logger.warning("GenerateGalleryThread did not stop within timeout; some image processing may still be running")

    @override
    def run(self) -> None:
        try:
            logger.info("Generating Gallery...")
            self.progress.emit(0)

            gallery_slates: list[dict[str, object]] = []
            total_slates: int = len(self.selected_slates)
            logger.info(f"Total slates selected: {total_slates}")

            # Use parallel slate processing for 3+ slates, sequential for 1-2
            if total_slates < 3:
                # Sequential path for small slate counts (avoids overhead)
                for processed_slates, slate in enumerate(self.selected_slates, start=1):
                    # Check if we should stop
                    if self._stop_event.is_set():
                        logger.info("Gallery generation thread stopped by user request")
                        self.gallery_complete.emit(False, "Gallery generation cancelled.")
                        return

                    slate_data_val = self.slates_dict.get(slate)
                    images: list[object] = []
                    if isinstance(slate_data_val, dict):
                        images_val = cast(dict[str, object], slate_data_val).get("images")
                        if isinstance(images_val, list):
                            images = cast(list[object], images_val)

                    # Always use parallel processing for better performance
                    # Even without thumbnails, we still need to extract EXIF data in parallel
                    slate_images: list[ImageData]
                    if len(images) > 1:
                        slate_images = self.process_images_parallel(images)  # type: ignore[arg-type]
                    else:
                        # Only use sequential for single image (rare case)
                        slate_images = []
                        for image in images:
                            if not isinstance(image, dict):
                                continue
                            # Skip macOS resource fork files
                            image_dict = cast(dict[str, object], image)
                            image_path_val = image_dict.get("path")
                            if not isinstance(image_path_val, str):
                                continue
                            if os.path.basename(image_path_val).startswith("._"):
                                logger.debug(f"Skipping macOS resource fork file: {image_path_val}")
                                continue
                            # Get cached EXIF if available
                            exif_val = image_dict.get("exif")
                            cached_exif: Optional[dict[str, object]] = cast(dict[str, object], exif_val) if isinstance(exif_val, dict) else None
                            image_data: Optional[ImageData] = self.process_image(image_path_val, cached_exif)
                            if image_data is not None:
                                slate_images.append(image_data)

                    if slate_images:
                        gallery_slates.append({"slate": slate, "images": slate_images})

                    progress: float = (
                        (processed_slates / float(total_slates)) * 80 if total_slates > 0 else 80
                    )
                    self.progress.emit(int(progress))
                    logger.info(f"Metadata extraction progress: {progress:.2f}%")
            else:
                # Parallel slate processing for 3+ slates
                logger.info(f"Processing {total_slates} slates in parallel for gallery generation")
                max_slate_workers = min(total_slates, multiprocessing.cpu_count())
                logger.info(f"Using {max_slate_workers} workers for slate-level parallelism")

                def process_slate_images(slate_name: str) -> Optional[dict[str, object]]:
                    """Process all images in a single slate (runs in worker thread)."""
                    if self._stop_event.is_set():
                        return None

                    slate_data_val = self.slates_dict.get(slate_name)
                    images: list[object] = []
                    if isinstance(slate_data_val, dict):
                        images_val = cast(dict[str, object], slate_data_val).get("images")
                        if isinstance(images_val, list):
                            images = cast(list[object], images_val)

                    slate_images: list[ImageData]
                    if len(images) > 1:
                        slate_images = self.process_images_parallel(images)  # type: ignore[arg-type]
                    else:
                        # Sequential for single image
                        slate_images = []
                        for image in images:
                            if not isinstance(image, dict):
                                continue
                            image_dict = cast(dict[str, object], image)
                            image_path_val = image_dict.get("path")
                            if not isinstance(image_path_val, str):
                                continue
                            if os.path.basename(image_path_val).startswith("._"):
                                logger.debug(f"Skipping macOS resource fork file: {image_path_val}")
                                continue
                            exif_val = image_dict.get("exif")
                            cached_exif: Optional[dict[str, object]] = cast(dict[str, object], exif_val) if isinstance(exif_val, dict) else None
                            image_data_result: Optional[ImageData] = self.process_image(image_path_val, cached_exif)
                            if image_data_result is not None:
                                slate_images.append(image_data_result)

                    if slate_images:
                        return {"slate": slate_name, "images": slate_images}
                    return None

                completed_count = 0
                with ThreadPoolExecutor(max_workers=max_slate_workers) as executor:
                    # Submit all slate processing tasks
                    future_to_slate = {
                        executor.submit(process_slate_images, slate): slate
                        for slate in self.selected_slates
                    }

                    # Collect results as they complete
                    for future in as_completed(future_to_slate):
                        if self._stop_event.is_set():
                            logger.info("Gallery generation stopped during parallel slate processing")
                            for pending_future in future_to_slate:
                                pending_future.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            self.gallery_complete.emit(False, "Gallery generation cancelled.")
                            return

                        slate_name = future_to_slate[future]
                        try:
                            result = future.result()
                            if result is not None:
                                gallery_slates.append(result)

                            completed_count += 1
                            progress_val = (completed_count / total_slates) * 80
                            self.progress.emit(int(progress_val))
                            logger.info(f"Completed slate {slate_name} ({completed_count}/{total_slates})")
                        except Exception as e:
                            logger.error(f"Error processing slate {slate_name}: {e}", exc_info=True)
                            completed_count += 1

                logger.info(f"Parallel slate processing complete: {completed_count} slates processed")

            self.progress.emit(80)
            # Import here to avoid circular imports
            from core.gallery_generator import generate_html_gallery

            # Convert focal length counts to structured data sorted by focal length value
            focal_length_data: list[FocalLengthData] = [
                {"value": focal_length, "count": count}
                for focal_length, count in sorted(self.focal_length_counts.items())
            ]

            # Add "Unknown" option if there are images without focal length
            if self.unknown_focal_length_count > 0:
                focal_length_data.append({
                    "value": "unknown",  # type: ignore[typeddict-item]
                    "count": self.unknown_focal_length_count,
                })

            # Convert date counts to structured data sorted by date
            date_data: list[DateData] = [
                {"value": date_key, "count": count, "display_date": self._format_date_for_display(date_key)}
                for date_key, count in sorted(self.date_counts.items())
            ]

            # Add "Unknown Date" option if there are images without EXIF dates
            if self.unknown_date_count > 0:
                date_data.append({
                    "value": "unknown",
                    "count": self.unknown_date_count,
                    "display_date": "Unknown Date"
                })

            success, gallery_skipped = generate_html_gallery(
                gallery_slates,  # pyright: ignore[reportArgumentType]
                focal_length_data,  # pyright: ignore[reportArgumentType]
                date_data,  # pyright: ignore[reportArgumentType]
                self.template_path,
                self.output_dir,
                self.allowed_root_dirs,
                self.emit_status,
                self.lazy_loading,
            )
            self.skipped_images += gallery_skipped
            if success:
                if self.skipped_images > 0:
                    message: str = f"Gallery generated ({self.skipped_images} image(s) skipped due to errors)"
                else:
                    message = "Gallery generated."
                self.progress.emit(100)
                logger.info(message)
                self.gallery_complete.emit(True, message)
            else:
                message = "Gallery generation failed."
                logger.warning(message)
                self.gallery_complete.emit(False, message)

        except Exception as e:
            error_message: str = f"Error during gallery generation: {e}"
            logger.error(error_message, exc_info=True)
            self.gallery_complete.emit(False, error_message)

    def process_images_parallel(self, images: list[object]) -> list[ImageData]:
        """Process multiple images in parallel using ThreadPoolExecutor.

        Uses cached EXIF data when available to avoid redundant extraction.
        """
        import time
        start_time: float = time.perf_counter()

        results: list[ImageData] = []
        cache_hits = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all image processing tasks (skip macOS resource fork files)
            future_to_image: dict[Future[Optional[ImageData]], str] = {}
            for img in images:
                if not isinstance(img, dict):
                    continue
                img_dict = cast(dict[str, object], img)
                img_path_val = img_dict.get("path")
                if not isinstance(img_path_val, str):
                    continue
                if not os.path.basename(img_path_val).startswith("._"):
                    # Get cached EXIF if available (from V2 cache format)
                    exif_val = img_dict.get("exif")
                    cached_exif: Optional[dict[str, object]] = cast(dict[str, object], exif_val) if isinstance(exif_val, dict) else None
                    if cached_exif is not None:
                        cache_hits += 1
                    future_to_image[
                        executor.submit(self.process_image, img_path_val, cached_exif)
                    ] = img_path_val

            # Collect results as they complete
            for future in as_completed(future_to_image):
                # Check for stop request before processing each result
                if self._stop_event.is_set():
                    logger.info("Stop requested during parallel image processing")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break  # Return partial results

                try:
                    image_data: Optional[ImageData] = future.result()
                    if image_data is not None:
                        results.append(image_data)
                except Exception as e:
                    image_path: str = future_to_image[future]
                    logger.error(f"Error processing image {image_path} in parallel: {e}")
                    with self.skipped_lock:
                        self.skipped_images += 1

        # Sort results to maintain original order
        results.sort(key=lambda x: str(x.get("filename", "")))

        # Log performance metrics
        elapsed_time: float = time.perf_counter() - start_time
        images_per_second: float = len(results) / elapsed_time if elapsed_time > 0 else 0
        logger.info(
            f"Processed {len(results)} images in {elapsed_time:.2f}s "
            f"({images_per_second:.1f} images/sec, {cache_hits} EXIF cache hits) "
            f"using {self.max_workers} workers"
        )

        return results

    def process_image(
        self, image_path: str, cached_exif: Optional[dict[str, object]] = None
    ) -> Optional[ImageData]:
        """Process a single image for gallery generation.

        Args:
            image_path: Path to the image file
            cached_exif: Pre-cached EXIF data (optional, extracted if not provided)

        Returns:
            ImageData dictionary or None if processing fails
        """
        try:
            # Skip macOS resource fork files (._*)
            if os.path.basename(image_path).startswith("._"):
                logger.debug(f"Skipping macOS resource fork file: {image_path}")
                return None

            # Import here to avoid circular imports
            from core.image_processor import (
                generate_thumbnail,
                get_exif_data,
                get_image_date,
                get_orientation,
            )

            # Use cached EXIF if available, otherwise extract fresh
            exif: dict[str, object] = cached_exif if cached_exif is not None else get_exif_data(image_path)
            focal_length: object = exif.get("FocalLength")
            focal_length_value: Optional[float] = None

            if focal_length:
                if isinstance(focal_length, tuple):
                    try:
                        # Validate tuple structure and prevent division by zero
                        focal_tuple = cast(tuple[object, ...], focal_length)
                        if len(focal_tuple) >= 2:
                            numerator_val = focal_tuple[0]
                            denominator_val = focal_tuple[1]
                            denominator = float(cast(float, denominator_val)) if denominator_val is not None else 0.0
                            numerator = float(cast(float, numerator_val)) if numerator_val is not None else 0.0
                            if denominator != 0:
                                focal_length_value = numerator / denominator
                            else:
                                logger.warning(f"Invalid focal length (zero denominator): {focal_length} for {image_path}")
                        else:
                            logger.warning(f"Invalid focal length tuple length: {focal_length} for {image_path}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid focal length tuple for {image_path}: {e}")
                else:
                    try:
                        focal_length_value = float(focal_length)  # pyright: ignore[reportArgumentType]
                    except Exception as e:
                        logger.warning(f"Invalid focal length value for {image_path}: {e}")

            orientation: str = get_orientation(image_path, exif)
            filename: str = os.path.basename(image_path)

            # Extract date information
            image_date: Optional[datetime] = get_image_date(exif)
            date_taken: Optional[str] = None
            date_key: Optional[str] = None

            if image_date:
                date_taken = image_date.isoformat()  # ISO format for HTML data attribute
                date_key = image_date.strftime("%Y-%m-%d")  # YYYY-MM-DD format for grouping

                # Count photos by day
                with self.date_lock:
                    self.date_counts[date_key] = self.date_counts.get(date_key, 0) + 1
            else:
                # Track images without EXIF dates for "Unknown Date" filter
                with self.date_lock:
                    self.unknown_date_count += 1

            if focal_length_value is not None:
                with self.focal_length_lock:
                    self.focal_length_counts[focal_length_value] = (
                        self.focal_length_counts.get(focal_length_value, 0) + 1
                    )
            else:
                # Track images without focal length for "Unknown" filter
                with self.focal_length_lock:
                    self.unknown_focal_length_count += 1

            # Generate thumbnails if enabled
            thumbnails: dict[str, str] = {}
            thumbnail_path: str = image_path  # Default to original
            if self.generate_thumbnails:
                # Pass EXIF orientation to avoid redundant file read
                exif_orientation = exif.get("Orientation")
                exif_orientation_int: Optional[int] = None
                if exif_orientation is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        exif_orientation_int = int(str(exif_orientation))
                thumbnails = generate_thumbnail(
                    image_path, self.thumb_dir, size=self.thumbnail_size, orientation=exif_orientation_int
                )
                logger.debug(f"Generated {len(thumbnails)} thumbnails for {filename}")
                # Get the single thumbnail path
                size_key: str = f"{self.thumbnail_size}x{self.thumbnail_size}"
                thumb_val = thumbnails.get(size_key, image_path)
                thumbnail_path = str(thumb_val) if thumb_val else image_path

            return {
                "original_path": image_path,
                "thumbnail": thumbnail_path,  # Single thumbnail path
                "thumbnail_600": thumbnails.get("600x600", image_path),  # Legacy compatibility
                "thumbnail_1200": thumbnails.get("1200x1200", image_path),  # Legacy compatibility
                "thumbnails": thumbnails,  # All thumbnail paths
                "focal_length": focal_length_value,
                "orientation": orientation,
                "filename": filename,
                "date_taken": date_taken,
            }
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}", exc_info=True)
            return None

    def _format_date_for_display(self, date_key: str) -> str:
        """Convert YYYY-MM-DD date key to DD/MM/YY display format."""
        try:
            date_obj: datetime = datetime.strptime(date_key, "%Y-%m-%d")
            return date_obj.strftime("%d/%m/%y")
        except ValueError as e:
            logger.warning(f"Failed to format date key '{date_key}': {e}")
            return date_key

    def emit_status(self, message: str) -> None:
        # Just log the status, don't emit completion signal
        logger.info(f"Gallery generation status: {message}")
