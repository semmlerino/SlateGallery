"""Centralized type definitions for SlateGallery.

This module contains all TypedDict definitions to avoid circular imports
between threading.py and gallery_generator.py. All modules should import
types from here rather than defining local aliases.

Data Flow Stages:
    Stage 1 (scan_directories): ScanResults
        {"slate_name": {"images": ["/path/img1.jpg", ...]}}

    Stage 2 (after EXIF processing): ProcessedResults
        {"slate_name": {"images": [CachedImageInfo{path, mtime, exif}, ...]}}

    Stage 3 (for gallery generation): list[SlateData]
        [{"slate": str, "images": [ImageData{...}]}, ...]
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from typing_extensions import TypedDict


# =============================================================================
# EXIF Data Types
# =============================================================================


class ExifData(TypedDict, total=False):
    """EXIF data extracted from images.

    All fields are optional since any image may lack specific EXIF tags.
    FocalLength can be either a pre-computed float or a (numerator, denominator) tuple.
    """

    FocalLength: Union[float, tuple[int, int]]
    Orientation: int
    DateTime: str
    DateTimeOriginal: str
    DateTimeDigitized: str


# =============================================================================
# Cache Data Types (Stage 2 - used by cache_manager.py and threading.py)
# =============================================================================


class CachedImageInfo(TypedDict):
    """Image info as stored in the cache after EXIF processing.

    Represents Stage 2 data - after scan but before gallery generation.
    """

    path: str
    mtime: float
    exif: ExifData


class ScanSlateData(TypedDict):
    """Slate data from initial directory scan (Stage 1).

    This represents raw scan results before EXIF processing.
    images contains simple file paths as strings.
    """

    images: list[str]


class ProcessedSlateData(TypedDict):
    """Slate data after EXIF processing (Stage 2).

    This represents cached data with EXIF metadata attached.
    images contains CachedImageInfo dictionaries.
    """

    images: list[CachedImageInfo]


class CacheMetadata(TypedDict, total=False):
    """Metadata stored in cache files.

    Single-directory caches use version, dir_mtime, file_count.
    Composite caches additionally use root_dirs.
    """

    version: int
    dir_mtime: float
    file_count: int
    scan_time: float
    root_dirs: list[str]  # Only present in composite cache


# =============================================================================
# Gallery Data Types (Stage 3 - used by gallery_generator.py and threading.py)
# =============================================================================


class _ImageDataRequired(TypedDict):
    """Required fields for gallery image data."""

    original_path: str


class _ImageDataOptional(TypedDict, total=False):
    """Optional fields for gallery image data."""

    thumbnail: str
    thumbnail_600: str
    thumbnail_1200: str
    thumbnails: dict[str, str]
    focal_length: Optional[float]
    orientation: str  # "portrait", "landscape", or "unknown"
    filename: str
    date_taken: Optional[str]
    web_path: str  # Added during gallery generation


class ImageData(_ImageDataRequired, _ImageDataOptional):
    """Type definition for image data in gallery output.

    Required fields: original_path
    Optional fields: thumbnail, thumbnails, focal_length, orientation,
                     filename, date_taken, web_path
    """

    pass


class SlateData(TypedDict):
    """Type definition for slate data in gallery output (Stage 3)."""

    slate: str
    images: list[ImageData]


# =============================================================================
# Filter Data Types (passed to HTML template)
# =============================================================================


class FocalLengthData(TypedDict):
    """Type definition for focal length filter data.

    value is Union[float, Literal["unknown"]] to support the "Unknown" filter
    option for images without focal length EXIF data.
    """

    value: Union[float, Literal["unknown"]]
    count: int


class DateData(TypedDict):
    """Type definition for date filter data.

    value is YYYY-MM-DD format or "unknown" for images without EXIF dates.
    display_date is DD/MM/YY format or "Unknown Date" for display.
    """

    value: str  # YYYY-MM-DD format or "unknown"
    count: int
    display_date: str  # DD/MM/YY format or "Unknown Date"


# =============================================================================
# Type Aliases for Common Patterns
# =============================================================================

# Stage 1: Raw scan results (slate_name -> ScanSlateData)
ScanResults = dict[str, ScanSlateData]

# Stage 2: After EXIF processing (slate_name -> ProcessedSlateData)
ProcessedResults = dict[str, ProcessedSlateData]
