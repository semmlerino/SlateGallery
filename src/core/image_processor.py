"""Image processing functions - extracted identically from original SlateGallery.py"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, cast

from PIL import Image
from PIL.ExifTags import IFD, TAGS

from utils.logging_config import log_function, logger

# Type alias for EXIF data dictionaries from PIL/piexif
# Note: PIL's EXIF data is untyped; we use Any here as a pragmatic solution
ExifData = dict[str, Any]  # type: ignore[type-arg]

# ----------------------------- Helper Functions -----------------------------


@log_function
def get_exif_data(image_path: str) -> ExifData:
    try:
        # Skip macOS resource fork files as a last line of defense
        if os.path.basename(image_path).startswith("._"):
            logger.debug(f"Skipping macOS resource fork file in get_exif_data: {image_path}")
            return {}

        with Image.open(image_path) as image:
            exif_data: ExifData = {}

            # Modern approach: getexif() + get_ifd() for EXIF subdirectories
            if hasattr(image, "getexif"):
                exif = image.getexif()
                if exif:
                    # Base EXIF tags
                    for tag, value in exif.items():  # type: ignore[attr-defined]
                        decoded = TAGS.get(tag, tag)
                        if decoded in (
                            "FocalLength",
                            "Orientation",
                            "DateTime",
                            "DateTimeOriginal",
                            "DateTimeDigitized",
                        ):
                            exif_data[decoded] = value  # type: ignore[assignment]

                    # EXIF IFD (where FocalLength usually resides)
                    try:
                        exif_ifd = exif.get_ifd(IFD.Exif)
                        for tag, value in exif_ifd.items():  # type: ignore[attr-defined]
                            decoded = TAGS.get(tag, tag)
                            if (
                                decoded
                                in ("FocalLength", "Orientation", "DateTime", "DateTimeOriginal", "DateTimeDigitized")
                                and decoded not in exif_data
                            ):
                                exif_data[decoded] = value  # type: ignore[assignment]
                    except (KeyError, AttributeError):
                        pass

                    if exif_data:
                        return exif_data

            # Fallback to deprecated _getexif() for compatibility with older Pillow versions
            if hasattr(image, "_getexif"):
                # PIL's _getexif() is untyped; cast to Any to access it
                image_any = cast(Any, image)
                exifinfo = image_any._getexif()
                if exifinfo:
                    for tag, value in exifinfo.items():
                        decoded = TAGS.get(tag, tag)
                        if decoded in (
                            "FocalLength",
                            "Orientation",
                            "DateTime",
                            "DateTimeOriginal",
                            "DateTimeDigitized",
                        ):
                            exif_data[decoded] = value

            return exif_data
    except Exception as e:
        logger.error(f"Error extracting EXIF data for {image_path}: {e}", exc_info=True)
        return {}


@log_function
def get_image_date(exif_data: ExifData) -> Union[datetime, None]:
    """Extract the best available date from EXIF data.

    Prioritizes DateTimeOriginal, then DateTimeDigitized, then DateTime.
    Returns datetime object or None if no valid date found.
    """
    date_tags = ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]

    for tag in date_tags:
        date_str = exif_data.get(tag)
        if date_str:
            try:
                # EXIF date format is 'YYYY:MM:DD HH:MM:SS'
                return datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")  # type: ignore[arg-type]
            except ValueError as e:
                logger.warning(f"Invalid date format for {tag}: {date_str}, error: {e}")
                continue

    return None


@log_function
def get_orientation(image_path: str, exif_data: ExifData) -> str:
    if "Orientation" in exif_data:
        orientation = exif_data["Orientation"]  # type: ignore[assignment]
        if orientation in [6, 8]:
            return "portrait"
        else:
            return "landscape"
    else:
        try:
            with Image.open(image_path) as image:
                width, height = image.size
                return "portrait" if height > width else "landscape"
        except Exception as e:
            logger.error(f"Error determining orientation for {image_path}: {e}", exc_info=True)
            return "unknown"


@log_function
def scan_directories(root_dir: str, exclude_patterns: str = "") -> dict[str, dict[str, list[str]]]:
    # QString is no longer needed in PySide6, using native Python strings
    root_dir = str(root_dir)

    image_extensions = [".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"]
    slates: dict[str, dict[str, list[str]]] = {}

    if not os.path.exists(root_dir):
        logger.error(f"Slate directory does not exist: {root_dir}")
        return slates

    # Parse exclude patterns (comma or semicolon separated)
    import fnmatch
    patterns = []
    if exclude_patterns:
        # Split by comma or semicolon and strip whitespace
        raw_patterns = [p.strip() for p in exclude_patterns.replace(';', ',').split(',')]
        # Filter out empty patterns
        patterns = [p for p in raw_patterns if p]
        logger.info(f"Applying exclude patterns: {patterns}")

    def should_exclude(path: str) -> bool:
        """Check if path matches any exclude pattern (case-insensitive)"""
        if not patterns:
            return False
        path_lower = path.lower()
        for pattern in patterns:
            # Case-insensitive match
            if fnmatch.fnmatch(path_lower, pattern.lower()):
                logger.debug(f"Excluding {path} (matched pattern: {pattern})")
                return True
        return False

    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=False):
        # Filter out excluded directories (modifying dirnames in-place prevents os.walk from descending)
        # Exclude dot folders (.git, .venv, etc.) and pattern-matched directories
        dirnames[:] = [d for d in dirnames if not (d.startswith('.') or should_exclude(d))]

        logger.info(f"Scanning directory: {dirpath}")
        images_in_dir: list[str] = []
        for f in filenames:
            # Skip macOS resource fork files (._*)
            if f.startswith("._"):
                continue

            # Skip if matches exclude pattern
            if should_exclude(f):
                continue

            if os.path.splitext(f)[1].lower() in image_extensions:
                images_in_dir.append(f)

        if images_in_dir:
            relative_dir = os.path.relpath(dirpath, root_dir)
            if relative_dir == ".":
                relative_dir = "/"
            slates[relative_dir] = {"images": [os.path.join(dirpath, f) for f in images_in_dir]}
            logger.info(f"Found {len(images_in_dir)} images in slate: {relative_dir}")

    return slates


@log_function
def scan_multiple_directories(root_dirs: list[str], exclude_patterns: str = "") -> dict[str, dict[str, list[str]]]:
    """Scan multiple root directories and merge results with prefixed slate names.

    Args:
        root_dirs: List of root directory paths to scan
        exclude_patterns: Comma or semicolon separated patterns to exclude

    Returns:
        Dictionary mapping prefixed slate names to image lists
        Format: {"{root_basename}/{slate_name}": {"images": [...]}}
        Root-level slates are named: "{root_basename}/Root"
    """
    merged_slates: dict[str, dict[str, list[str]]] = {}

    for root_dir in root_dirs:
        if not os.path.exists(root_dir):
            logger.warning(f"Skipping non-existent root directory: {root_dir}")
            continue

        # Get basename for prefixing
        root_basename = os.path.basename(root_dir.rstrip(os.sep))
        if not root_basename:
            # Handle edge case of root filesystem path
            root_basename = root_dir.replace(os.sep, "_").strip("_") or "Root"

        logger.info(f"Scanning root directory: {root_dir} (prefix: {root_basename})")

        # Scan this root directory
        slates = scan_directories(root_dir, exclude_patterns)

        # Prefix slate names and merge
        for slate_name, slate_data in slates.items():
            # Handle root-level slate (named "/")
            if slate_name == "/":
                prefixed_name = f"{root_basename}/Root"
            else:
                # Remove leading slash if present
                clean_slate_name = slate_name.lstrip("/")
                prefixed_name = f"{root_basename}/{clean_slate_name}"

            # Handle potential naming conflicts by appending suffix
            original_prefixed_name = prefixed_name
            counter = 2
            while prefixed_name in merged_slates:
                prefixed_name = f"{original_prefixed_name}_{counter}"
                counter += 1
                logger.warning(f"Slate name conflict: renamed {original_prefixed_name} to {prefixed_name}")

            merged_slates[prefixed_name] = slate_data
            logger.debug(f"Added slate: {prefixed_name} with {len(slate_data['images'])} images")

    logger.info(f"Merged scan complete: {len(merged_slates)} total slates from {len(root_dirs)} root directories")
    return merged_slates


@log_function
def generate_thumbnail(
    image_path: str,
    thumb_dir: str,
    size: Union[int, tuple[int, int], None] = None,
    orientation: Optional[int] = None
) -> dict[str, str]:
    """Generate a thumbnail for an image at specified size.

    Args:
        image_path: Path to the original image
        thumb_dir: Directory to store thumbnails
        size: Single size as an integer (e.g., 600 for 600x600) or tuple (width, height)
        orientation: Optional EXIF orientation value (1-8). If provided, skips EXIF read.

    Returns:
        Dict with thumbnail path keyed by size string (e.g., "600x600")
    """
    # Optimized settings for good balance of speed and quality
    if size is None:
        size = 600

    # Convert single integer to tuple
    if isinstance(size, int):
        sizes: list[tuple[int, int]] = [(size, size)]
    else:
        # At this point size is guaranteed to be a tuple[int, int]
        # (None was handled above, and we only reach here if it's int or tuple)
        sizes = [size]  # type: ignore[list-item]

    thumbnails: dict[str, str] = {}

    try:
        # Create a unique filename based on image path hash
        path_hash = hashlib.md5(image_path.encode()).hexdigest()[:8]
        base_name = Path(image_path).stem

        # Ensure thumbnail directory exists
        Path(thumb_dir).mkdir(parents=True, exist_ok=True)

        # Open image once for all thumbnails
        with Image.open(image_path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                # Paste image with alpha channel as mask
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img

            # Use provided orientation or extract from EXIF
            if orientation is None:
                exif = img.getexif() if hasattr(img, 'getexif') else None
                orientation = exif.get(0x0112) if exif else None

            # Rotate image based on EXIF orientation
            if orientation:
                rotations = {
                    3: 180,
                    6: 270,
                    8: 90
                }
                if orientation in rotations:
                    img = img.rotate(rotations[orientation], expand=True)

            for size_tuple in sizes:
                size_str = f"{size_tuple[0]}x{size_tuple[1]}"
                thumb_filename = f"{base_name}_{path_hash}_{size_str}.jpg"
                thumb_path = os.path.join(thumb_dir, thumb_filename)

                # Check if thumbnail already exists
                if os.path.exists(thumb_path):
                    # Verify it's not corrupted
                    try:
                        with Image.open(thumb_path) as test_img:
                            test_img.verify()
                        thumbnails[size_str] = thumb_path
                        logger.debug(f"Thumbnail already exists: {thumb_path}")
                        continue
                    except Exception:
                        # Corrupted thumbnail, regenerate
                        logger.warning(f"Corrupted thumbnail found, regenerating: {thumb_path}")

                # Create thumbnail with optimized settings for speed and quality
                thumb = img.copy()
                thumb.thumbnail(size_tuple, Image.Resampling.LANCZOS)

                # Save with balanced quality settings
                # 90% quality is a good balance, no optimize for speed
                thumb.save(
                    thumb_path,
                    'JPEG',
                    quality=90,
                    optimize=False,  # Skip for speed
                    subsampling=1    # Balanced quality/speed
                )
                thumbnails[size_str] = thumb_path
                logger.debug(f"Generated thumbnail: {thumb_path}")

        return thumbnails

    except Exception as e:
        logger.error(f"Error generating thumbnails for {image_path}: {e}", exc_info=True)
        return {}
