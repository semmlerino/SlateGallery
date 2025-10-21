"""Gallery generation - extracted identically from original SlateGallery.py"""

import os
from collections.abc import Callable
from typing import Optional, TypedDict, Union

from jinja2 import Environment, FileSystemLoader

from utils.logging_config import log_function, logger


# Type definitions for gallery data structures
class _ImageDataRequired(TypedDict):
    """Required fields for image data."""
    original_path: str


class _ImageDataOptional(TypedDict, total=False):
    """Optional fields for image data."""
    thumbnail: str
    thumbnail_600: str
    thumbnail_1200: str
    thumbnails: dict[str, str]
    focal_length: Optional[float]
    orientation: int
    filename: str
    date_taken: Optional[str]
    web_path: str  # Added during gallery generation


class ImageData(_ImageDataRequired, _ImageDataOptional):
    """Type definition for image data dictionary.

    Required fields: original_path
    Optional fields: thumbnail, thumbnails, focal_length, orientation, filename, date_taken, web_path
    """


class SlateData(TypedDict):
    """Type definition for slate data dictionary."""
    slate: str
    images: list[ImageData]


class FocalLengthData(TypedDict):
    """Type definition for focal length data dictionary."""
    value: float
    count: int


class DateData(TypedDict):
    """Type definition for date data dictionary."""
    value: str  # YYYY-MM-DD format
    count: int
    display_date: str  # DD/MM/YY format

# ----------------------------- HTML Gallery Generation -----------------------------


@log_function
def generate_html_gallery(
    gallery_data: list[SlateData],
    focal_length_data: list[FocalLengthData],
    date_data: list[DateData],
    template_path: str,
    output_dir: str,
    allowed_root_dirs: Union[str, list[str]],
    status_callback: Callable[[str], None],
    lazy_loading: bool = True,
) -> bool:
    """Generate HTML gallery from processed data.

    Args:
        gallery_data: List of slate data with images
        focal_length_data: Focal length statistics
        date_data: Date statistics
        template_path: Path to Jinja2 template
        output_dir: Directory to write output HTML
        allowed_root_dirs: Single root directory or list of allowed root directories for security validation
        status_callback: Callback function for status updates
        lazy_loading: Whether to enable lazy loading of images

    Returns:
        True if successful, False otherwise
    """
    try:
        # Normalize allowed_root_dirs to a list for uniform handling
        if isinstance(allowed_root_dirs, str):
            real_allowed_roots = [os.path.realpath(allowed_root_dirs)]
        else:
            real_allowed_roots = [os.path.realpath(d) for d in allowed_root_dirs]

        # Process image paths
        for slate in gallery_data:
            for image in slate["images"]:
                original_path = image["original_path"]
                try:
                    # Verify path is within one of the allowed root directories
                    real_original_path = os.path.realpath(original_path)

                    # Check if path starts with any of the allowed roots
                    is_allowed = any(real_original_path.startswith(real_root) for real_root in real_allowed_roots)

                    if not is_allowed:
                        allowed_dirs_str = ", ".join(real_allowed_roots)
                        logger.error(f"Image path {original_path} is outside of allowed directories: {allowed_dirs_str}")
                        status_callback(f"Skipping image outside of allowed directories: {original_path}")
                        continue

                    # Use absolute path with forward slashes for web
                    absolute_path = os.path.abspath(original_path)
                    web_path = "file://" + absolute_path.replace("\\", "/")
                    image["web_path"] = web_path

                except Exception as e:
                    logger.error(f"Error processing image {original_path}: {e}", exc_info=True)
                    status_callback(f"Error processing image {original_path}: {e}")
                    continue

        # Load and render template
        env = Environment(loader=FileSystemLoader(os.path.dirname(template_path)), autoescape=True)
        template = env.get_template(os.path.basename(template_path))

        try:
            output_html = template.render(gallery=gallery_data, focal_lengths=focal_length_data, dates=date_data, lazy_loading=lazy_loading)
        except Exception as e:
            status_callback(f"Error rendering template: {e}")
            logger.error(f"Error rendering template: {e}", exc_info=True)
            return False

        # Create output directory if needed
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")
            except Exception as e:
                status_callback(f"Error creating output directory: {e}")
                logger.error(f"Error creating output directory: {e}", exc_info=True)
                return False

        # Write the HTML file
        try:
            html_file_path = os.path.join(output_dir, "index.html")
            with open(html_file_path, "wb") as f:
                _ = f.write(output_html.encode("utf-8"))
            status_callback(f"Gallery generated at {os.path.abspath(html_file_path)}")
            logger.info(f"Gallery generated at {os.path.abspath(html_file_path)}")
            return True
        except Exception as e:
            status_callback(f"Error writing HTML file: {e}")
            logger.error(f"Error writing HTML file: {e}", exc_info=True)
            return False

    except Exception as e:
        status_callback(f"Error generating gallery: {e}")
        logger.error(f"Error generating gallery: {e}", exc_info=True)
        return False
