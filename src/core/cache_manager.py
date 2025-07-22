"""Cache manager - extracted identically from original SlateGallery.py"""

import hashlib
import json
import os
import threading

from utils.logging_config import log_function, logger

# ----------------------------- ImprovedCacheManager Class -----------------------------

class ImprovedCacheManager:
    def __init__(self, base_dir='.', max_workers=4, batch_size=100):
        self.base_dir = base_dir
        self.cache_dir = os.path.join(base_dir, 'cache')
        self.thumb_dir = os.path.join(base_dir, 'thumbnails')
        self.metadata_file = os.path.join(self.cache_dir, 'metadata.json')

        self.max_workers = max_workers
        self.batch_size = batch_size
        self._cache_lock = threading.Lock()
        self._metadata = {}
        self._processing = set()

        self.ensure_directories()
        logger.debug(f"ImprovedCacheManager initialized with base_dir: {self.base_dir}")

    @log_function
    def ensure_directories(self):
        for directory in [self.cache_dir]:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    logger.info(f"Created directory: {directory}")
                except Exception as e:
                    logger.error(f"Error creating directory {directory}: {e}", exc_info=True)

    @log_function
    def get_cache_file(self, root_dir):
        # Create a unique name for the root_dir, e.g., hash
        dir_hash = hashlib.md5(root_dir.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f'{dir_hash}.json')

    @log_function
    def load_cache(self, root_dir):
        cache_file = self.get_cache_file(root_dir)
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    slates = json.load(f)
                logger.info(f"Loaded slates from cache for directory: {root_dir}")
                return slates
            except Exception as e:
                logger.error(f"Error loading cache for {root_dir}: {e}", exc_info=True)
                return None
        else:
            logger.info(f"No cache found for directory: {root_dir}")
            return None

    @log_function
    def save_cache(self, root_dir, slates):
        cache_file = self.get_cache_file(root_dir)
        try:
            with open(cache_file, 'w') as f:
                json.dump(slates, f)
            logger.info(f"Saved cache for directory: {root_dir}")
        except Exception as e:
            logger.error(f"Error saving cache for {root_dir}: {e}", exc_info=True)

    @log_function
    def process_images_batch(self, image_paths, callback=None):
        logger.info(f"Processing batch of {len(image_paths)} images for scanning.")

        return [{'path': path} for path in image_paths]

    @log_function
    def shutdown(self):
        try:
            logger.info("ImprovedCacheManager shutdown completed.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
