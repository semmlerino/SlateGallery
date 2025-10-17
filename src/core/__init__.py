"""Core components for SlateGallery."""

from collections.abc import Callable

from .cache_manager import ImprovedCacheManager
from .config_manager import load_config as _load_config
from .config_manager import save_config as _save_config
from .gallery_generator import DateData, FocalLengthData, ImageData, SlateData
from .gallery_generator import generate_html_gallery as _generate_html_gallery
from .image_processor import get_exif_data as _get_exif_data
from .image_processor import get_orientation as _get_orientation
from .image_processor import scan_directories as _scan_directories


# Re-export with proper type annotations
def load_config() -> tuple[str, list[str], bool, int, bool]:
    """Load configuration from ~/.slate_gallery/config.ini.

    Returns:
        Tuple of (current_slate_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading)
    """
    return _load_config()


def save_config(
    current_slate_dir: str,
    slate_dirs: list[str],
    generate_thumbnails: bool = False,
    thumbnail_size: int = 600,
    lazy_loading: bool = True
) -> None:
    """Save configuration to ~/.slate_gallery/config.ini.

    Args:
        current_slate_dir: Current slate directory path
        slate_dirs: List of slate directory paths
        generate_thumbnails: Whether to generate thumbnails
        thumbnail_size: Thumbnail size (600, 800, or 1200)
        lazy_loading: Whether to enable lazy loading in gallery
    """
    _save_config(current_slate_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading)


def generate_html_gallery(
    gallery_data: list[SlateData],
    focal_length_data: list[FocalLengthData],
    date_data: list[DateData],
    template_path: str,
    output_dir: str,
    root_dir: str,
    status_callback: Callable[[str], None],
    lazy_loading: bool = True
) -> bool:
    """Generate HTML gallery from processed image data.

    Args:
        gallery_data: List of slate dictionaries with image data
        focal_length_data: List of focal length data dictionaries
        date_data: List of date data dictionaries
        template_path: Path to Jinja2 template file
        output_dir: Directory to write generated HTML
        root_dir: Root directory for image paths
        status_callback: Callback function for status updates
        lazy_loading: Whether to enable lazy loading in gallery

    Returns:
        True if gallery generated successfully, False otherwise
    """
    return _generate_html_gallery(
        gallery_data, focal_length_data, date_data,
        template_path, output_dir, root_dir,
        status_callback, lazy_loading
    )


def get_exif_data(image_path: str) -> dict[str, object]:
    """Extract EXIF data from an image file.

    Args:
        image_path: Path to the image file

    Returns:
        Dictionary containing EXIF data (FocalLength, Orientation, DateTime, etc.)
    """
    return _get_exif_data(image_path)


def get_orientation(image_path: str, exif_data: dict[str, object]) -> str:
    """Determine image orientation from EXIF data or dimensions.

    Args:
        image_path: Path to the image file
        exif_data: EXIF data dictionary from get_exif_data()

    Returns:
        One of: 'portrait', 'landscape', or 'unknown'
    """
    return _get_orientation(image_path, exif_data)


def scan_directories(root_dir: str) -> dict[str, dict[str, list[str]]]:
    """Scan directory tree for image files.

    Args:
        root_dir: Root directory to scan

    Returns:
        Dictionary mapping slate names to image lists
    """
    return _scan_directories(root_dir)


__all__ = [
    "get_exif_data",
    "get_orientation",
    "scan_directories",
    "load_config",
    "save_config",
    "ImprovedCacheManager",
    "generate_html_gallery",
    "ImageData",
    "SlateData",
    "FocalLengthData",
    "DateData",
]
