"""Threading utilities - extracted identically from original SlateGallery.py"""

import contextlib
import multiprocessing
import os
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, Protocol, TypeVar, Union, cast, runtime_checkable

from PySide6 import QtCore
from PySide6.QtCore import Signal
from typing_extensions import override

from type_defs import (
    CachedImageInfo,
    DateData,
    ExifData,
    FocalLengthData,
    ImageData,
    ProcessedResults,
    ScanResults,
    ScanSlateData,
    SlateData,
)

from .logging_config import log_function, logger


@runtime_checkable
class CacheManagerProtocol(Protocol):
    """Protocol defining the interface for cache managers."""
    def process_images_batch(
        self, image_paths: Sequence[str], _callback: Optional[Callable[[int], None]] = None
    ) -> list[CachedImageInfo]:
        ...

    def process_images_batch_with_exif(
        self,
        image_paths: Sequence[str],
        existing_cache: Optional[ProcessedResults] = None,
        _callback: Optional[Callable[[int], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> list[CachedImageInfo]:
        ...

    def save_cache(self, root_dir: str, slates: ProcessedResults) -> None:
        ...

    def save_composite_cache(self, root_dirs: list[str], slates: ProcessedResults) -> None:
        ...


# ----------------------------- Parallel Processing Utility -----------------------------

# Type variables for generic parallel processing
T = TypeVar("T")  # Input item type
R = TypeVar("R")  # Result type


def process_items_parallel(
    items: Sequence[T],
    process_func: Callable[[T], Optional[R]],
    stop_event: threading.Event,
    *,
    progress_callback: Optional[Callable[[int], None]] = None,
    progress_start: int = 0,
    progress_end: int = 100,
    min_parallel_threshold: int = 3,
    max_workers: Optional[int] = None,
) -> tuple[list[R], bool]:
    """Process items in parallel with consistent stop-event handling.

    Encapsulates the common pattern of:
    - Sequential vs parallel decision based on item count
    - ThreadPoolExecutor setup with worker limit
    - Stop event checking and future cancellation
    - Progress calculation and reporting

    Args:
        items: Sequence of items to process
        process_func: Function to process each item, returns None to skip
        stop_event: Event to check for cancellation
        progress_callback: Optional callback for progress updates (receives percentage)
        progress_start: Starting progress percentage (default 0)
        progress_end: Ending progress percentage (default 100)
        min_parallel_threshold: Use sequential if fewer items (default 3)
        max_workers: Max worker threads (defaults to cpu_count)

    Returns:
        Tuple of (results list, was_cancelled bool)
        Results list contains only non-None returns from process_func
    """
    total = len(items)
    if total == 0:
        return [], False

    results: list[R] = []

    # Sequential path for small item counts (avoids ThreadPoolExecutor overhead)
    if total < min_parallel_threshold:
        for i, item in enumerate(items):
            if stop_event.is_set():
                return results, True

            result = process_func(item)
            if result is not None:
                results.append(result)

            if progress_callback:
                progress = progress_start + int(((i + 1) / total) * (progress_end - progress_start))
                progress_callback(progress)

        return results, False

    # Parallel path
    effective_max_workers = max_workers if max_workers else min(total, multiprocessing.cpu_count())
    completed_count = 0

    with ThreadPoolExecutor(max_workers=effective_max_workers) as executor:
        future_to_item: dict[Future[Optional[R]], T] = {
            executor.submit(process_func, item): item for item in items
        }

        for future in as_completed(future_to_item):
            if stop_event.is_set():
                # Cancel pending futures
                for pending_future in future_to_item:
                    pending_future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                return results, True

            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing item: {e}", exc_info=True)

            completed_count += 1
            if progress_callback:
                progress = progress_start + int((completed_count / total) * (progress_end - progress_start))
                progress_callback(progress)

    return results, False

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
        """Execute directory scan in three phases: scan, EXIF processing, cache save."""
        try:
            slates = self._scan_directories()
            if slates is None:
                return

            if not self._process_exif(slates):
                return

            # Note: slates has been mutated in-place from ScanResults to ProcessedResults
            self._save_cache(slates)  # pyright: ignore[reportArgumentType]
            self.scan_complete.emit(slates, "Scan complete.")
            logger.info("Scan completed.")
        except Exception as e:
            error_message: str = f"Error during directory scan: {e}"
            logger.error(error_message, exc_info=True)
            self.scan_complete.emit({}, error_message)

    def _scan_directories(self) -> Optional[ScanResults]:
        """Phase 1: Scan directories for images.

        Returns:
            ScanResults dict if successful, None if cancelled
        """
        from core.image_processor import scan_directories

        logger.info(f"Starting directory scan for {len(self.root_dirs)} root directory(ies)...")

        # Single-directory mode
        if len(self.root_dirs) == 1:
            logger.info(f"Scanning single directory: {self.root_dirs[0]}")
            # scan_directories returns structurally compatible dict
            return scan_directories(self.root_dirs[0], self.exclude_patterns)  # pyright: ignore[reportReturnType]

        # Multi-directory concurrent scanning mode
        logger.info(f"Scanning {len(self.root_dirs)} directories concurrently...")
        max_workers = min(len(self.root_dirs), multiprocessing.cpu_count())

        merged_slates: dict[str, dict[str, list[str]]] = {}
        completed_dirs = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dir = {
                executor.submit(_scan_single_root_dir, root_dir, self.exclude_patterns): root_dir
                for root_dir in self.root_dirs
            }

            for future in as_completed(future_to_dir):
                if self._stop_event.is_set():
                    logger.info("Scan thread stopped by user request")
                    for pending_future in future_to_dir:
                        pending_future.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    self.scan_complete.emit({}, "Scan cancelled.")
                    return None

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
                    progress = int((completed_dirs / len(self.root_dirs)) * 50)
                    self.progress.emit(progress)
                    logger.info(f"Completed scan of {root_dir} ({completed_dirs}/{len(self.root_dirs)})")
                except Exception as e:
                    logger.error(f"Error scanning {root_dir}: {e}", exc_info=True)
                    completed_dirs += 1

        logger.info(f"Concurrent scan complete: {len(merged_slates)} total slates from {len(self.root_dirs)} directories")
        # merged_slates is structurally compatible with ScanResults
        return merged_slates  # pyright: ignore[reportReturnType]

    def _process_exif(self, slates: ScanResults) -> bool:
        """Phase 2: Process EXIF data for all slates.

        Mutates slates in-place, converting ScanResults to ProcessedResults.

        Args:
            slates: Scan results to process

        Returns:
            True if completed, False if cancelled
        """
        total_slates: int = len(slates)
        logger.debug(f"Total slates to process: {total_slates}")

        if total_slates == 0:
            return True

        # Sequential path for small slate counts (avoids ThreadPoolExecutor overhead)
        if total_slates < 3:
            for processed_slates, (_slate, data) in enumerate(slates.items(), start=1):
                if self._stop_event.is_set():
                    logger.info("Scan thread stopped by user request")
                    self.scan_complete.emit({}, "Scan cancelled.")
                    return False

                image_paths = data.get("images", [])
                processed_images = self.cache_manager.process_images_batch_with_exif(
                    [str(p) for p in image_paths],
                    existing_cache=None,
                    _callback=lambda p: self.progress.emit(50 + int(p / 2)),
                    stop_event=self._stop_event,
                )
                data["images"] = processed_images  # pyright: ignore[reportGeneralTypeIssues]

                exif_progress: float = 50 + ((processed_slates / float(total_slates)) * 50)
                self.progress.emit(int(exif_progress))
                logger.debug(f"EXIF processing progress: {exif_progress:.2f}%")

            return True

        # Parallel slate processing for 3+ slates
        logger.info(f"Processing {total_slates} slates in parallel for EXIF extraction")
        max_slate_workers = min(total_slates, multiprocessing.cpu_count())
        logger.info(f"Using {max_slate_workers} workers for slate-level parallelism")

        def process_slate_exif(slate_item: tuple[str, ScanSlateData]) -> tuple[str, list[CachedImageInfo]]:
            """Process EXIF for a single slate (runs in worker thread)."""
            slate_name, slate_data = slate_item
            if self._stop_event.is_set():
                return (slate_name, [])

            image_paths = slate_data.get("images", [])
            processed_images = self.cache_manager.process_images_batch_with_exif(
                [str(p) for p in image_paths],
                existing_cache=None,
                _callback=None,
                stop_event=self._stop_event,
            )
            return (slate_name, processed_images)

        # Use process_items_parallel utility
        results, cancelled = process_items_parallel(
            list(slates.items()),
            process_slate_exif,
            self._stop_event,
            progress_callback=lambda p: self.progress.emit(p),
            progress_start=50,
            progress_end=100,
            min_parallel_threshold=3,
            max_workers=max_slate_workers,
        )

        if cancelled:
            logger.info("Scan thread stopped during parallel EXIF processing")
            self.scan_complete.emit({}, "Scan cancelled.")
            return False

        # Merge results back into slates dict
        for slate_name, processed_images in results:
            slates[slate_name]["images"] = processed_images  # pyright: ignore[reportGeneralTypeIssues]

        logger.info(f"Parallel EXIF processing complete: {len(results)} slates processed")
        return True

    def _save_cache(self, slates: ProcessedResults) -> None:
        """Phase 3: Save processed slates to cache.

        Args:
            slates: Processed results to save
        """
        if len(self.root_dirs) == 1:
            self.cache_manager.save_cache(self.root_dirs[0], slates)
        else:
            self.cache_manager.save_composite_cache(self.root_dirs, slates)


class GenerateGalleryThread(QtCore.QThread):
    gallery_complete: Signal = Signal(bool, str)  # type: ignore[misc]
    progress: Signal = Signal(int)  # type: ignore[misc]

    def __init__(
        self,
        selected_slates: list[str],
        slates_dict: ProcessedResults,
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
        self.slates_dict: ProcessedResults = slates_dict
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
        """Execute gallery generation in phases: process slates, generate HTML."""
        try:
            logger.info("Generating Gallery...")
            self.progress.emit(0)

            gallery_slates = self._process_all_slates()
            if gallery_slates is None:
                return

            self.progress.emit(80)

            success = self._generate_html(gallery_slates)
            self._emit_completion(success)

        except Exception as e:
            error_message: str = f"Error during gallery generation: {e}"
            logger.error(error_message, exc_info=True)
            self.gallery_complete.emit(False, error_message)

    def _process_single_slate(self, slate_name: str) -> Optional[SlateData]:
        """Process all images in a single slate.

        Args:
            slate_name: Name of the slate to process

        Returns:
            SlateData if slate has images, None otherwise
        """
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
                cached_exif: Optional[ExifData] = cast(ExifData, exif_val) if isinstance(exif_val, dict) else None
                image_data: Optional[ImageData] = self.process_image(image_path_val, cached_exif)
                if image_data is not None:
                    slate_images.append(image_data)

        if slate_images:
            return {"slate": slate_name, "images": slate_images}
        return None

    def _process_all_slates(self) -> Optional[list[SlateData]]:
        """Phase 1: Process all selected slates.

        Returns:
            List of SlateData if successful, None if cancelled
        """
        gallery_slates: list[SlateData] = []
        total_slates: int = len(self.selected_slates)
        logger.info(f"Total slates selected: {total_slates}")

        if total_slates == 0:
            return gallery_slates

        # Sequential path for small slate counts (avoids overhead)
        if total_slates < 3:
            for processed_count, slate in enumerate(self.selected_slates, start=1):
                if self._stop_event.is_set():
                    logger.info("Gallery generation thread stopped by user request")
                    self.gallery_complete.emit(False, "Gallery generation cancelled.")
                    return None

                result = self._process_single_slate(slate)
                if result is not None:
                    gallery_slates.append(result)

                progress: float = (processed_count / float(total_slates)) * 80
                self.progress.emit(int(progress))
                logger.info(f"Metadata extraction progress: {progress:.2f}%")

            return gallery_slates

        # Parallel slate processing for 3+ slates
        logger.info(f"Processing {total_slates} slates in parallel for gallery generation")
        max_slate_workers = min(total_slates, multiprocessing.cpu_count())
        logger.info(f"Using {max_slate_workers} workers for slate-level parallelism")

        results, cancelled = process_items_parallel(
            self.selected_slates,
            self._process_single_slate,
            self._stop_event,
            progress_callback=lambda p: self.progress.emit(p),
            progress_start=0,
            progress_end=80,
            min_parallel_threshold=3,
            max_workers=max_slate_workers,
        )

        if cancelled:
            logger.info("Gallery generation stopped during parallel slate processing")
            self.gallery_complete.emit(False, "Gallery generation cancelled.")
            return None

        logger.info(f"Parallel slate processing complete: {len(results)} slates processed")
        return results

    def _generate_html(self, gallery_slates: list[SlateData]) -> bool:
        """Phase 2: Generate HTML gallery from processed slates.

        Args:
            gallery_slates: List of processed slate data

        Returns:
            True if successful, False otherwise
        """
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
        return success

    def _emit_completion(self, success: bool) -> None:
        """Emit completion signal with appropriate message.

        Args:
            success: Whether gallery generation succeeded
        """
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
                    cached_exif_val: Optional[ExifData] = cast(ExifData, exif_val) if isinstance(exif_val, dict) else None
                    if cached_exif_val is not None:
                        cache_hits += 1
                    future_to_image[
                        executor.submit(self.process_image, img_path_val, cached_exif_val)
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
        self, image_path: str, cached_exif: Optional[ExifData] = None
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
            exif: ExifData = cached_exif if cached_exif is not None else get_exif_data(image_path)
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
