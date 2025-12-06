"""Core components for SlateGallery."""

from collections.abc import Callable
from typing import Union

from .cache_manager import ImprovedCacheManager
from .config_manager import GalleryConfig
from .config_manager import load_config as _load_config
from .config_manager import save_config as _save_config
from .gallery_generator import DateData, FocalLengthData, ImageData, SlateData
from .gallery_generator import generate_html_gallery as _generate_html_gallery
from .image_processor import get_exif_data as _get_exif_data
from .image_processor import get_orientation as _get_orientation
from .image_processor import scan_directories as _scan_directories


# Re-export with proper type annotations
def load_config() -> tuple[str, list[str], list[str], bool, int, bool, str]:
    """Load configuration from ~/.slate_gallery/config.ini.

    Returns:
        Tuple of (current_slate_dir, slate_dirs, selected_slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading, exclude_patterns)
    """
    cfg = _load_config()
    return (
        cfg.current_slate_dir,
        cfg.slate_dirs,
        cfg.selected_slate_dirs,
        cfg.generate_thumbnails,
        cfg.thumbnail_size,
        cfg.lazy_loading,
        cfg.exclude_patterns,
    )


def save_config(
    current_slate_dir: str,
    slate_dirs: list[str],
    selected_slate_dirs: list[str],
    generate_thumbnails: bool = False,
    thumbnail_size: int = 600,
    lazy_loading: bool = True,
    exclude_patterns: str = ""
) -> None:
    """Save configuration to ~/.slate_gallery/config.ini.

    Args:
        current_slate_dir: Current slate directory path
        slate_dirs: List of slate directory paths
        selected_slate_dirs: List of directories selected for scanning
        generate_thumbnails: Whether to generate thumbnails
        thumbnail_size: Thumbnail size (600, 800, or 1200)
        lazy_loading: Whether to enable lazy loading in gallery
        exclude_patterns: Patterns to exclude from slate list (comma-separated wildcards)
    """
    cfg = GalleryConfig(
        current_slate_dir=current_slate_dir,
        slate_dirs=slate_dirs,
        selected_slate_dirs=selected_slate_dirs,
        generate_thumbnails=generate_thumbnails,
        thumbnail_size=thumbnail_size,
        lazy_loading=lazy_loading,
        exclude_patterns=exclude_patterns,
    )
    _save_config(cfg)


def generate_html_gallery(
    gallery_data: list[SlateData],
    focal_length_data: list[FocalLengthData],
    date_data: list[DateData],
    template_path: str,
    output_dir: str,
    allowed_root_dirs: Union[str, list[str]],
    status_callback: Callable[[str], None],
    lazy_loading: bool = True
) -> tuple[bool, int]:
    """Generate HTML gallery from processed image data.

    Args:
        gallery_data: List of slate dictionaries with image data
        focal_length_data: List of focal length data dictionaries
        date_data: List of date data dictionaries
        template_path: Path to Jinja2 template file
        output_dir: Directory to write generated HTML
        allowed_root_dirs: Single root directory or list of allowed root directories for security validation
        status_callback: Callback function for status updates
        lazy_loading: Whether to enable lazy loading in gallery

    Returns:
        Tuple of (success: bool, skipped_count: int)
    """
    return _generate_html_gallery(
        gallery_data, focal_length_data, date_data,
        template_path, output_dir, allowed_root_dirs,
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
