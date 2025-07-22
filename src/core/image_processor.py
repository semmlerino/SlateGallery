"""Image processing functions - extracted identically from original SlateGallery.py"""

import os

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
            if hasattr(image, 'getexif'):
                exif = image.getexif()
                if exif:
                    # Base EXIF tags
                    for tag, value in exif.items():
                        decoded = TAGS.get(tag, tag)
                        if decoded in ('FocalLength', 'Orientation'):
                            exif_data[decoded] = value

                    # EXIF IFD (where FocalLength usually resides)
                    try:
                        exif_ifd = exif.get_ifd(IFD.Exif)
                        for tag, value in exif_ifd.items():
                            decoded = TAGS.get(tag, tag)
                            if decoded in ('FocalLength', 'Orientation') and decoded not in exif_data:
                                exif_data[decoded] = value
                    except (KeyError, AttributeError):
                        pass

                    if exif_data:
                        return exif_data

            # Fallback to deprecated _getexif() for compatibility
            if hasattr(image, '_getexif'):
                exifinfo = image._getexif()  # type: ignore[attr-defined]
                if exifinfo:
                    for tag, value in exifinfo.items():
                        decoded = TAGS.get(tag, tag)
                        if decoded in ('FocalLength', 'Orientation'):
                            exif_data[decoded] = value

            return exif_data
    except Exception as e:
        logger.error(f"Error extracting EXIF data for {image_path}: {e}", exc_info=True)
        return {}

@log_function
def get_orientation(image_path, exif_data):
    if 'Orientation' in exif_data:
        orientation = exif_data['Orientation']
        if orientation in [6, 8]:
            return 'portrait'
        else:
            return 'landscape'
    else:
        image = None
        try:
            image = Image.open(image_path)
            width, height = image.size
            return 'portrait' if height > width else 'landscape'
        except Exception as e:
            logger.error(f"Error determining orientation for {image_path}: {e}", exc_info=True)
            return 'unknown'
        finally:
            if image and hasattr(image, 'fp') and image.fp and hasattr(image.fp, 'close'):
                try:
                    image.fp.close()
                except Exception:
                    pass

@log_function
def scan_directories(root_dir):
    # QString is no longer needed in PySide6, using native Python strings
    root_dir = str(root_dir)

    image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif']
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
            if relative_dir == '.':
                relative_dir = '/'
            slates[relative_dir] = {
                'images': [os.path.join(dirpath, f) for f in images_in_dir]
            }
            logger.info(f"Found {len(images_in_dir)} images in slate: {relative_dir}")

    return slates
