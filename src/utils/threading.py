"""Threading utilities - extracted identically from original SlateGallery.py"""

import multiprocessing
import os
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

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
        self, image_paths: Sequence[object], callback: Optional[Callable[[int], None]] = None
    ) -> list[dict[str, object]]:
        ...

    def save_cache(self, root_dir: str, slates: object) -> None:
        ...

# ----------------------------- Worker Threads -----------------------------


class ScanThread(QtCore.QThread):
    scan_complete: Signal = Signal(dict, str)  # type: ignore[misc]
    progress: Signal = Signal(int)  # type: ignore[misc]

    def __init__(self, root_dir: str, cache_manager: CacheManagerProtocol) -> None:
        super().__init__()
        self.root_dir: str = str(root_dir)
        self.cache_manager: CacheManagerProtocol = cache_manager
        self._is_running: bool = True

    def stop(self) -> None:
        """Gracefully stop the thread."""
        self._is_running = False
        _ = self.wait(5000)  # Wait max 5 seconds for thread to finish

    @log_function
    @override
    def run(self) -> None:
        try:
            # Import here to avoid circular imports
            from core.image_processor import scan_directories

            logger.info("Starting directory scan...")
            slates = scan_directories(self.root_dir)

            processed_slates: int = 0
            total_slates: int = len(slates) if isinstance(slates, dict) else 0
            logger.debug(f"Total slates to process: {total_slates}")

            if not isinstance(slates, dict):
                self.scan_complete.emit({}, "Invalid slates data.")
                return

            for _slate, data in slates.items():
                # Check if we should stop
                if not self._is_running:
                    logger.info("Scan thread stopped by user request")
                    self.scan_complete.emit({}, "Scan cancelled.")
                    return

                if not isinstance(data, dict):
                    continue

                image_paths = data.get("images", [])
                processed_images = self.cache_manager.process_images_batch(
                    image_paths, callback=lambda p: self.progress.emit(int(p))  # type: ignore[arg-type]
                )
                data["images"] = processed_images  # pyright: ignore[reportArgumentType]

                processed_slates += 1
                if total_slates > 0:
                    progress: float = (processed_slates / float(total_slates)) * 100
                else:
                    progress = 100
                self.progress.emit(int(progress))
                logger.debug(f"Scan progress: {progress:.2f}%")

            # Save the scanned slates to cache
            self.cache_manager.save_cache(self.root_dir, slates)

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
        root_dir: str,
        template_path: str,
        generate_thumbnails: bool,
        thumbnail_size: int = 600,
        lazy_loading: bool = True
    ) -> None:
        super().__init__()
        self.selected_slates: list[str] = selected_slates
        self.slates_dict: dict[str, object] = slates_dict
        self.cache_manager: CacheManagerProtocol = cache_manager
        self.output_dir: str = output_dir
        self.root_dir: str = root_dir
        self.template_path: str = template_path
        self.generate_thumbnails: bool = generate_thumbnails
        self.thumbnail_size: int = thumbnail_size
        self.lazy_loading: bool = lazy_loading
        self._is_running: bool = True

        # Lock for thread-safe operations
        self.focal_length_lock: threading.Lock = threading.Lock()
        self.focal_length_counts: dict[float, int] = {}

        # Date-related data structures
        self.date_lock: threading.Lock = threading.Lock()
        self.date_counts: dict[str, int] = {}  # Format: "YYYY-MM-DD": count

        # Thumbnail directory
        self.thumb_dir: str = os.path.join(output_dir, "thumbnails")

        # Thread pool for parallel image processing
        # For I/O-bound operations (reading files, EXIF extraction), we can use more workers
        # Use 2x CPU count for I/O operations, capped at 16 to avoid overwhelming the system
        self.max_workers: int = min(multiprocessing.cpu_count() * 2, 16)
        logger.info(f"Using {self.max_workers} workers for parallel image processing")

    def stop(self) -> None:
        """Gracefully stop the thread."""
        self._is_running = False
        _ = self.wait(5000)  # Wait max 5 seconds for thread to finish

    @override
    def run(self) -> None:
        try:
            logger.info("Generating Gallery...")
            self.progress.emit(0)

            gallery_slates: list[dict[str, object]] = []
            total_slates: int = len(self.selected_slates)
            processed_slates: int = 0
            logger.info(f"Total slates selected: {total_slates}")

            for slate in self.selected_slates:
                # Check if we should stop
                if not self._is_running:
                    logger.info("Gallery generation thread stopped by user request")
                    self.gallery_complete.emit(False, "Gallery generation cancelled.")
                    return

                slate_data = self.slates_dict.get(slate, {})
                images: list[object] = slate_data.get("images", []) if isinstance(slate_data, dict) else []  # type: ignore[arg-type]

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
                        image_path_val = image.get("path", "")
                        if not isinstance(image_path_val, str):
                            continue
                        if os.path.basename(image_path_val).startswith("._"):
                            logger.debug(f"Skipping macOS resource fork file: {image_path_val}")
                            continue
                        image_data: Optional[ImageData] = self.process_image(image_path_val)
                        if image_data is not None:
                            slate_images.append(image_data)

                if slate_images:
                    gallery_slates.append({"slate": slate, "images": slate_images})

                processed_slates += 1
                progress: float
                if total_slates > 0:
                    progress = (processed_slates / float(total_slates)) * 80
                else:
                    progress = 80
                self.progress.emit(int(progress))
                logger.info(f"Metadata extraction progress: {progress:.2f}%")

            self.progress.emit(80)
            # Import here to avoid circular imports
            from core.gallery_generator import generate_html_gallery

            # Convert focal length counts to structured data sorted by focal length value
            focal_length_data: list[FocalLengthData] = [
                {"value": focal_length, "count": count}
                for focal_length, count in sorted(self.focal_length_counts.items())
            ]

            # Convert date counts to structured data sorted by date
            date_data: list[DateData] = [
                {"value": date_key, "count": count, "display_date": self._format_date_for_display(date_key)}
                for date_key, count in sorted(self.date_counts.items())
            ]

            success: bool = generate_html_gallery(
                gallery_slates,  # pyright: ignore[reportArgumentType]
                focal_length_data,  # pyright: ignore[reportArgumentType]
                date_data,  # pyright: ignore[reportArgumentType]
                self.template_path,
                self.output_dir,
                self.root_dir,
                self.emit_status,
                self.lazy_loading,
            )
            if success:
                message: str = "Gallery generated."
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
        """Process multiple images in parallel using ThreadPoolExecutor."""
        import time
        start_time: float = time.perf_counter()

        results: list[ImageData] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all image processing tasks (skip macOS resource fork files)
            future_to_image: dict[Future[Optional[ImageData]], str] = {}
            for img in images:
                if not isinstance(img, dict):
                    continue
                img_path = img.get("path", "")
                if not isinstance(img_path, str):
                    continue
                if not os.path.basename(img_path).startswith("._"):
                    future_to_image[executor.submit(self.process_image, img_path)] = img_path

            # Collect results as they complete
            for future in as_completed(future_to_image):
                try:
                    image_data: Optional[ImageData] = future.result()
                    if image_data is not None:
                        results.append(image_data)
                except Exception as e:
                    image_path: str = future_to_image[future]
                    logger.error(f"Error processing image {image_path} in parallel: {e}")

        # Sort results to maintain original order
        results.sort(key=lambda x: str(x.get("filename", "")))

        # Log performance metrics
        elapsed_time: float = time.perf_counter() - start_time
        images_per_second: float = len(results) / elapsed_time if elapsed_time > 0 else 0
        logger.info(f"Processed {len(results)} images in {elapsed_time:.2f}s ({images_per_second:.1f} images/sec) using {self.max_workers} workers")

        return results

    def process_image(self, image_path: str) -> Optional[ImageData]:
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

            exif: dict[str, object] = get_exif_data(image_path)
            focal_length: object = exif.get("FocalLength", None)
            focal_length_value: Optional[float] = None

            if focal_length:
                if isinstance(focal_length, tuple):
                    try:
                        # Validate tuple structure and prevent division by zero
                        if len(focal_length) >= 2:
                            denominator = float(focal_length[1])
                            if denominator != 0:
                                focal_length_value = float(focal_length[0]) / denominator
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

            if focal_length_value is not None:
                with self.focal_length_lock:
                    self.focal_length_counts[focal_length_value] = (
                        self.focal_length_counts.get(focal_length_value, 0) + 1
                    )

            # Generate thumbnails if enabled
            thumbnails: dict[str, object] = {}
            thumbnail_path: str = image_path  # Default to original
            if self.generate_thumbnails:
                thumbnails = generate_thumbnail(image_path, self.thumb_dir, size=self.thumbnail_size)  # type: ignore[assignment]
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
