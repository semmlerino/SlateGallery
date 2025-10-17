"""Threading utilities - extracted identically from original SlateGallery.py"""

import multiprocessing
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from PySide6 import QtCore
from PySide6.QtCore import Signal

from .logging_config import log_function, logger

# ----------------------------- Worker Threads -----------------------------


class ScanThread(QtCore.QThread):
    scan_complete = Signal(dict, str)
    progress = Signal(int)

    def __init__(self, root_dir, cache_manager):
        super().__init__()
        self.root_dir = str(root_dir)
        self.cache_manager = cache_manager

    @log_function
    def run(self):
        try:
            # Import here to avoid circular imports
            from core.image_processor import scan_directories

            logger.info("Starting directory scan...")
            slates = scan_directories(self.root_dir)

            processed_slates = 0
            total_slates = len(slates)
            logger.debug(f"Total slates to process: {total_slates}")

            for _slate, data in slates.items():
                image_paths = data["images"]
                processed_images = self.cache_manager.process_images_batch(
                    image_paths, callback=lambda p: self.progress.emit(int(p))
                )
                data["images"] = processed_images

                processed_slates += 1
                if total_slates > 0:
                    progress = (processed_slates / float(total_slates)) * 100
                else:
                    progress = 100
                self.progress.emit(int(progress))
                logger.debug(f"Scan progress: {progress:.2f}%")

            # Save the scanned slates to cache
            self.cache_manager.save_cache(self.root_dir, slates)

            self.scan_complete.emit(slates, "Scan complete.")
            logger.info("Scan completed.")
        except Exception as e:
            error_message = f"Error during directory scan: {e}"
            logger.error(error_message, exc_info=True)
            self.scan_complete.emit({}, error_message)


class GenerateGalleryThread(QtCore.QThread):
    gallery_complete = Signal(bool, str)
    progress = Signal(int)

    def __init__(
        self, selected_slates, slates_dict, cache_manager, output_dir, root_dir, template_path, generate_thumbnails, thumbnail_size=600, lazy_loading=True
    ):
        super().__init__()
        self.selected_slates = selected_slates
        self.slates_dict = slates_dict
        self.cache_manager = cache_manager
        self.output_dir = output_dir
        self.root_dir = root_dir
        self.template_path = template_path
        self.generate_thumbnails = generate_thumbnails
        self.thumbnail_size = thumbnail_size
        self.lazy_loading = lazy_loading

        # Lock for thread-safe operations
        self.focal_length_lock = threading.Lock()
        self.focal_length_counts = {}

        # Date-related data structures
        self.date_lock = threading.Lock()
        self.date_counts = {}  # Format: "YYYY-MM-DD": count

        # Thumbnail directory
        self.thumb_dir = os.path.join(output_dir, "thumbnails")

        # Thread pool for parallel image processing
        # For I/O-bound operations (reading files, EXIF extraction), we can use more workers
        # Use 2x CPU count for I/O operations, capped at 16 to avoid overwhelming the system
        self.max_workers = min(multiprocessing.cpu_count() * 2, 16)
        logger.info(f"Using {self.max_workers} workers for parallel image processing")

    def run(self):
        try:
            logger.info("Generating Gallery...")
            self.progress.emit(0)

            gallery_slates = []
            total_slates = len(self.selected_slates)
            processed_slates = 0
            logger.info(f"Total slates selected: {total_slates}")

            for slate in self.selected_slates:
                images = self.slates_dict.get(slate, {}).get("images", [])

                # Always use parallel processing for better performance
                # Even without thumbnails, we still need to extract EXIF data in parallel
                if len(images) > 1:
                    slate_images = self.process_images_parallel(images)
                else:
                    # Only use sequential for single image (rare case)
                    slate_images = []
                    for image in images:
                        # Skip macOS resource fork files
                        if os.path.basename(image["path"]).startswith("._"):
                            logger.debug(f"Skipping macOS resource fork file: {image['path']}")
                            continue
                        image_data = self.process_image(image["path"])
                        if image_data is not None:
                            slate_images.append(image_data)

                if slate_images:
                    gallery_slates.append({"slate": slate, "images": slate_images})

                processed_slates += 1
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
            focal_length_data = [
                {"value": focal_length, "count": count}
                for focal_length, count in sorted(self.focal_length_counts.items())
            ]

            # Convert date counts to structured data sorted by date
            date_data = [
                {"value": date_key, "count": count, "display_date": self._format_date_for_display(date_key)}
                for date_key, count in sorted(self.date_counts.items())
            ]

            success = generate_html_gallery(
                gallery_slates,
                focal_length_data,
                date_data,
                self.template_path,
                self.output_dir,
                self.root_dir,
                self.emit_status,
                self.lazy_loading,
            )
            if success:
                message = "Gallery generated."
                self.progress.emit(100)
                logger.info(message)
                self.gallery_complete.emit(True, message)
            else:
                message = "Gallery generation failed."
                logger.warning(message)
                self.gallery_complete.emit(False, message)

        except Exception as e:
            error_message = f"Error during gallery generation: {e}"
            logger.error(error_message, exc_info=True)
            self.gallery_complete.emit(False, error_message)

    def process_images_parallel(self, images):
        """Process multiple images in parallel using ThreadPoolExecutor."""
        import time
        start_time = time.perf_counter()

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all image processing tasks (skip macOS resource fork files)
            future_to_image = {
                executor.submit(self.process_image, img["path"]): img["path"]
                for img in images
                if not os.path.basename(img["path"]).startswith("._")
            }

            # Collect results as they complete
            for future in as_completed(future_to_image):
                try:
                    image_data = future.result()
                    if image_data is not None:
                        results.append(image_data)
                except Exception as e:
                    image_path = future_to_image[future]
                    logger.error(f"Error processing image {image_path} in parallel: {e}")

        # Sort results to maintain original order
        results.sort(key=lambda x: x.get("filename", ""))

        # Log performance metrics
        elapsed_time = time.perf_counter() - start_time
        images_per_second = len(results) / elapsed_time if elapsed_time > 0 else 0
        logger.info(f"Processed {len(results)} images in {elapsed_time:.2f}s ({images_per_second:.1f} images/sec) using {self.max_workers} workers")

        return results

    def process_image(self, image_path):
        try:
            # Skip macOS resource fork files (._*)
            if os.path.basename(image_path).startswith("._"):
                logger.debug(f"Skipping macOS resource fork file: {image_path}")
                return None

            # Import here to avoid circular imports
            from core.image_processor import generate_thumbnail, get_exif_data, get_image_date, get_orientation

            exif = get_exif_data(image_path)
            focal_length = exif.get("FocalLength", None)
            focal_length_value = None

            if focal_length:
                if isinstance(focal_length, tuple):
                    try:
                        focal_length_value = float(focal_length[0]) / float(focal_length[1])
                    except Exception as e:
                        logger.warning(f"Invalid focal length tuple for {image_path}: {e}")
                else:
                    try:
                        focal_length_value = float(focal_length)
                    except Exception as e:
                        logger.warning(f"Invalid focal length value for {image_path}: {e}")

            orientation = get_orientation(image_path, exif)
            filename = os.path.basename(image_path)

            # Extract date information
            image_date = get_image_date(exif)
            date_taken = None
            date_key = None

            if image_date:
                date_taken = image_date.isoformat()  # ISO format for HTML data attribute
                date_key = image_date.strftime("%Y-%m-%d")  # YYYY-MM-DD format for grouping

                # Count photos by day
                with self.date_lock:
                    self.date_counts[date_key] = self.date_counts.get(date_key, 0) + 1

            if focal_length_value:
                with self.focal_length_lock:
                    self.focal_length_counts[focal_length_value] = (
                        self.focal_length_counts.get(focal_length_value, 0) + 1
                    )

            # Generate thumbnails if enabled
            thumbnails = {}
            thumbnail_path = image_path  # Default to original
            if self.generate_thumbnails:
                thumbnails = generate_thumbnail(image_path, self.thumb_dir, size=self.thumbnail_size)
                logger.debug(f"Generated {len(thumbnails)} thumbnails for {filename}")
                # Get the single thumbnail path
                size_key = f"{self.thumbnail_size}x{self.thumbnail_size}"
                thumbnail_path = thumbnails.get(size_key, image_path)

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

    def _format_date_for_display(self, date_key):
        """Convert YYYY-MM-DD date key to DD/MM/YY display format."""
        try:
            date_obj = datetime.strptime(date_key, "%Y-%m-%d")
            return date_obj.strftime("%d/%m/%y")
        except ValueError as e:
            logger.warning(f"Failed to format date key '{date_key}': {e}")
            return date_key

    def emit_status(self, message):
        # Just log the status, don't emit completion signal
        logger.info(f"Gallery generation status: {message}")
