"""Image processing functions - extracted identically from original SlateGallery.py"""

import hashlib
import os
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import IFD, TAGS
from utils.logging_config import log_function, logger

# ----------------------------- Helper Functions -----------------------------


@log_function
def get_exif_data(image_path):
    try:
        with Image.open(image_path) as image:
            exif_data = {}

            # Modern approach: getexif() + get_ifd() for EXIF subdirectories
            if hasattr(image, "getexif"):
                exif = image.getexif()
                if exif:
                    # Base EXIF tags
                    for tag, value in exif.items():
                        decoded = TAGS.get(tag, tag)
                        if decoded in (
                            "FocalLength",
                            "Orientation",
                            "DateTime",
                            "DateTimeOriginal",
                            "DateTimeDigitized",
                        ):
                            exif_data[decoded] = value

                    # EXIF IFD (where FocalLength usually resides)
                    try:
                        exif_ifd = exif.get_ifd(IFD.Exif)
                        for tag, value in exif_ifd.items():
                            decoded = TAGS.get(tag, tag)
                            if (
                                decoded
                                in ("FocalLength", "Orientation", "DateTime", "DateTimeOriginal", "DateTimeDigitized")
                                and decoded not in exif_data
                            ):
                                exif_data[decoded] = value
                    except (KeyError, AttributeError):
                        pass

                    if exif_data:
                        return exif_data

            # Fallback to deprecated _getexif() for compatibility
            if hasattr(image, "_getexif"):
                exifinfo = image._getexif()  # type: ignore[attr-defined]
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
def get_image_date(exif_data):
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
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except ValueError as e:
                logger.warning(f"Invalid date format for {tag}: {date_str}, error: {e}")
                continue

    return None


@log_function
def get_orientation(image_path, exif_data):
    if "Orientation" in exif_data:
        orientation = exif_data["Orientation"]
        if orientation in [6, 8]:
            return "portrait"
        else:
            return "landscape"
    else:
        image = None
        try:
            image = Image.open(image_path)
            width, height = image.size
            return "portrait" if height > width else "landscape"
        except Exception as e:
            logger.error(f"Error determining orientation for {image_path}: {e}", exc_info=True)
            return "unknown"
        finally:
            if image and hasattr(image, "fp") and image.fp and hasattr(image.fp, "close"):
                try:
                    image.fp.close()
                except Exception:
                    pass


@log_function
def scan_directories(root_dir):
    # QString is no longer needed in PySide6, using native Python strings
    root_dir = str(root_dir)

    image_extensions = [".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"]
    slates = {}

    if not os.path.exists(root_dir):
        logger.error(f"Slate directory does not exist: {root_dir}")
        return slates

    for dirpath, _dirnames, filenames in os.walk(root_dir, followlinks=False):
        logger.info(f"Scanning directory: {dirpath}")
        images_in_dir = []
        for f in filenames:
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
def generate_thumbnail(image_path, thumb_dir, sizes=None):
    """Generate thumbnails for an image at specified sizes.
    
    Args:
        image_path: Path to the original image
        thumb_dir: Directory to store thumbnails
        sizes: List of tuples (width, height) for thumbnail sizes
               Defaults to [(400, 400), (800, 800)]
    
    Returns:
        Dict with thumbnail paths keyed by size string (e.g., "400x400")
    """
    if sizes is None:
        sizes = [(400, 400), (800, 800)]
    
    thumbnails = {}
    
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
            
            # Preserve EXIF orientation
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
            
            for size in sizes:
                size_str = f"{size[0]}x{size[1]}"
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
                
                # Create high-quality thumbnail
                thumb = img.copy()
                thumb.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save with optimized quality
                thumb.save(thumb_path, 'JPEG', quality=85, optimize=True, progressive=True)
                thumbnails[size_str] = thumb_path
                logger.debug(f"Generated thumbnail: {thumb_path}")
        
        return thumbnails
        
    except Exception as e:
        logger.error(f"Error generating thumbnails for {image_path}: {e}", exc_info=True)
        return {}
