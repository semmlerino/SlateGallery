"""Gallery generation - extracted identically from original SlateGallery.py"""

import os

from jinja2 import Environment, FileSystemLoader
from utils.logging_config import log_function, logger

# ----------------------------- HTML Gallery Generation -----------------------------

@log_function
def generate_html_gallery(gallery_data, focal_length_data, date_data, template_path, output_dir, root_dir, status_callback):
    try:
        # Process image paths
        for slate in gallery_data:
            for image in slate['images']:
                original_path = image['original_path']
                try:
                    # Verify path is within root directory
                    real_original_path = os.path.realpath(original_path)
                    real_root_dir = os.path.realpath(root_dir)
                    if not real_original_path.startswith(real_root_dir):
                        logger.error(f"Image path {original_path} is outside of root directory {root_dir}")
                        status_callback(f"Skipping image outside of root directory: {original_path}")
                        continue

                    # Use absolute path with forward slashes for web
                    absolute_path = os.path.abspath(original_path)
                    web_path = 'file://' + absolute_path.replace('\\', '/')
                    image['web_path'] = web_path

                except Exception as e:
                    logger.error(f"Error processing image {original_path}: {e}", exc_info=True)
                    status_callback(f"Error processing image {original_path}: {e}")
                    continue

        # Load and render template
        env = Environment(
            loader=FileSystemLoader(os.path.dirname(template_path)),
            autoescape=True
        )
        template = env.get_template(os.path.basename(template_path))

        try:
            output_html = template.render(gallery=gallery_data, focal_lengths=focal_length_data, dates=date_data)
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
            html_file_path = os.path.join(output_dir, 'index.html')
            with open(html_file_path, 'wb') as f:
                f.write(output_html.encode('utf-8'))
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
