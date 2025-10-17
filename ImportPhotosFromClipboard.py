# 3DE4.script.name: Import Reference Frames From Clipboard
# 3DE4.script.version: v3.0
# 3DE4.script.gui: Main Window::Matchmove::Gabriel::RefPhotos
# 3DE4.script.comment: Creates reference frame cameras from clipboard data

import datetime
import os
import re

import tde4


def log_message(message, error=None):
    """Log message to both console and file"""
    try:
        log_dir = "/nethome/gabriel-h/log"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "import_ref_frames.log")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        if error:
            full_msg += f" Error: {str(error)}"

        print(full_msg)

        with open(log_file, "a") as f:
            f.write(full_msg + "\n")

    except Exception as e:
        print(f"Failed to write to log file: {e}")
        if error:
            print(f"{message} Error: {str(error)}")
        else:
            print(message)


def extract_slate_from_path(path):
    """Extract slate identifier from path (e.g., J256G, J256H)"""
    # Look for pattern like J256G, J256H etc in the path
    # Using a simpler regex pattern
    pattern = r'J[0-9]+[A-Z]'
    matches = re.findall(pattern, path)
    if matches:
        # Return the last match (most specific slate in the path)
        return matches[-1]
    return None


def infer_slate_from_filename(filename, last_slate=None):
    """Try to infer slate from filename patterns or use intelligent guessing"""
    # If we have a previous slate and the filename is similar, increment the letter
    if last_slate and re.match(r'J[0-9]+[A-Z]', last_slate):
        # For now, we'll need more context to determine the correct slate
        # This is a placeholder for more sophisticated logic
        return last_slate

    return None


def parse_clipboard_data(text):
    """Parse clipboard data with improved path resolution logic"""
    result = []
    lines = text.splitlines()
    log_message(f"Processing {len(lines)} lines from clipboard")

    root_path = None  # Root directory up to and including 'slates'
    current_slate = None  # Current slate directory (e.g., J256G)

    # First pass: identify the base structure from any full paths
    for line in lines:
        line = line.strip()
        if line.startswith('/'):
            parts = line.rsplit('-', 1)
            if len(parts) == 2:
                full_path = parts[0].strip()
                if '/slates/' in full_path:
                    # Extract the base path up to slates
                    path_parts = full_path.split('/')
                    slates_idx = path_parts.index('slates')
                    root_path = '/'.join(path_parts[:slates_idx + 1])
                    log_message(f"Identified root path: {root_path}")

                    # Extract slate from this path
                    slate = extract_slate_from_path(full_path)
                    if slate:
                        current_slate = slate
                        log_message(f"Initial slate context: {current_slate}")
                    break

    # Second pass: process all entries
    processed_slates = set()
    slate_sequence = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            log_message(f"Line {i}: Skipping empty line")
            continue

        try:
            # Split on the last '-' to separate path from focal length
            parts = line.rsplit('-', 1)

            if len(parts) != 2:
                log_message(f"Line {i}: Invalid format - no '-' separator found in '{line}'")
                continue

            path_part, focal_part = parts
            path_part = path_part.strip()
            focal_part = focal_part.strip()

            # Parse focal length first
            try:
                focal_value = float(focal_part)
            except ValueError:
                log_message(f"Line {i}: Invalid focal length '{focal_part}' - skipping")
                continue

            # Determine full path based on path type
            if path_part.startswith('/'):
                # Full absolute path
                full_path = os.path.normpath(path_part)

                # Update root path and slate context
                if '/slates/' in full_path:
                    path_parts = full_path.split('/')
                    slates_idx = path_parts.index('slates')
                    root_path = '/'.join(path_parts[:slates_idx + 1])

                    # Extract and update slate
                    slate = extract_slate_from_path(full_path)
                    if slate and slate != current_slate:
                        current_slate = slate
                        if slate not in processed_slates:
                            processed_slates.add(slate)
                            slate_sequence.append(slate)
                        log_message(f"Line {i}: Updated slate context to '{current_slate}' from full path")

                log_message(f"Line {i}: Full path resolved: '{full_path}'")

            elif '/' in path_part and root_path:
                # Relative path with directory
                # First check if it starts with a slate identifier
                first_part = path_part.split('/')[0]
                if re.match(r'^J[0-9]+[A-Z]', first_part):
                    # This is a slate-prefixed path (e.g., J256H/set_ref/IMG_1094.JPG)
                    current_slate = first_part
                    log_message(f"Line {i}: Found slate '{current_slate}' at start of relative path")
                    full_path = os.path.normpath(os.path.join(root_path, path_part))
                    log_message(f"Line {i}: Slate-prefixed path resolved to: '{full_path}'")
                else:
                    # Other relative paths
                    full_path = os.path.normpath(os.path.join(root_path, path_part))
                    log_message(f"Line {i}: Relative path '{path_part}' resolved to: '{full_path}'")

            elif root_path and current_slate:
                # Filename only - use current slate context
                # Place in the set_ref subdirectory of the current slate
                full_path = os.path.normpath(os.path.join(root_path, current_slate, 'set_ref', path_part))
                log_message(f"Line {i}: Filename only '{path_part}' resolved to: '{full_path}' (slate: '{current_slate}')")

            elif root_path:
                # Filename only but no slate context
                full_path = os.path.normpath(os.path.join(root_path, path_part))
                log_message(f"Line {i}: Filename only '{path_part}' resolved to: '{full_path}' (no slate context)")

            else:
                # Cannot determine full path
                log_message(f"Line {i}: Cannot determine full path for '{path_part}' - no root path established")
                continue

            entry = (full_path, focal_value)
            result.append(entry)
            log_message(f"Line {i}: Successfully added '{os.path.basename(full_path)}' with focal {focal_value}mm")

        except Exception as e:
            log_message(f"Error processing line {i}: '{line}'", e)
            continue

    # Log summary of slates encountered
    if slate_sequence:
        log_message(f"Slates encountered in order: {', '.join(slate_sequence)}")

    log_message(f"Successfully parsed {len(result)} valid entries from clipboard data")

    # Log final results for verification
    log_message("=== Final parsed results ===")
    for i, (path, focal) in enumerate(result, 1):
        log_message(f"  {i}. {path} - {focal}mm")
    log_message("=== End of parsed results ===")

    return result


def extract_focal_from_name(lens_name):
    """Extract focal length from lens name"""
    try:
        # More robust focal length extraction
        # Look for patterns like: 24mm, 24-70mm, 24 mm, etc.

        # Pattern 1: number followed by mm (with or without space)
        match = re.search(r'(\d+(?:\.\d+)?)\s*mm', lens_name.lower())
        if match:
            focal = float(match.group(1))
            log_message(f"Extracted focal {focal} from lens name: '{lens_name}'")
            return focal

        # Pattern 2: number-number mm (zoom lens, take first value)
        match = re.search(r'(\d+(?:\.\d+)?)-\d+\s*mm', lens_name.lower())
        if match:
            focal = float(match.group(1))
            log_message(f"Extracted focal {focal} from lens name: '{lens_name}'")
            return focal

    except Exception as e:
        log_message(f"Error extracting focal length from lens name: '{lens_name}'", e)

    log_message(f"Could not extract focal length from lens name: '{lens_name}'")
    return None


def find_matching_lens_by_name(target_focal):
    """Find lens that matches the target focal length"""
    try:
        target_focal_str = str(int(target_focal) if target_focal.is_integer() else target_focal)
        log_message(f"Searching for lens with focal length: {target_focal_str}mm")

        lens_list = tde4.getLensList(0)
        matching_lenses = []

        for lens in lens_list:
            try:
                lens_name = tde4.getLensName(lens)
                extracted_focal = extract_focal_from_name(lens_name)

                if extracted_focal is not None:
                    extracted_focal_str = str(int(extracted_focal) if extracted_focal.is_integer() else extracted_focal)

                    if extracted_focal_str == target_focal_str:
                        matching_lenses.append((lens, lens_name))
                        log_message(f"Found matching lens: '{lens_name}' for focal {target_focal}mm")

            except Exception as e:
                log_message(f"Error processing lens: {lens_name}", e)
                continue

        if matching_lenses:
            if len(matching_lenses) > 1:
                log_message(f"Multiple matching lenses found for {target_focal}mm:")
                for _, name in matching_lenses:
                    log_message(f"  - '{name}'")
                log_message("Using first match")

            return matching_lenses[0][0]
        else:
            log_message(f"No matching lens found for focal length {target_focal}mm")
            return None

    except Exception as e:
        log_message(f"Error searching for lens with focal {target_focal}mm", e)
        return None


def create_confirmation_gui(image_data):
    """Create GUI for user to review and select images to import"""
    log_message("Creating confirmation GUI")
    req = tde4.createCustomRequester()

    # Title label
    label_text = f"Reference Frames To Import ({len(image_data)} total)"
    tde4.addLabelWidget(req, "list_label", label_text, "ALIGN_LABEL_LEFT")
    tde4.setWidgetOffsets(req, "list_label", 20, 20, 5, 0)

    # File list widget with paths shown
    tde4.addListWidget(req, "file_list", "", 1, 300)  # Multi-selection, 300px height
    tde4.setWidgetOffsets(req, "file_list", 20, 20, 5, 0)
    log_message(f"Adding {len(image_data)} items to list widget")

    # Group by slate for better visibility
    slate_groups = {}
    for path, focal in image_data:
        slate = extract_slate_from_path(path)
        if not slate:
            slate = "Unknown"
        if slate not in slate_groups:
            slate_groups[slate] = []
        slate_groups[slate].append((path, focal))

    # Populate list with image data grouped by slate
    item_index = 0
    for slate in sorted(slate_groups.keys()):
        # Add slate header
        if len(slate_groups) > 1:
            idx = tde4.insertListWidgetItem(req, "file_list", f"--- Slate: {slate} ---", 0, "LIST_ITEM_ATOM", -1)
            tde4.setListWidgetItemSelectionFlag(req, "file_list", idx, 0)  # Not selectable
            item_index += 1

        for path, focal in slate_groups[slate]:
            try:
                matching_lens = find_matching_lens_by_name(focal)
                filename = os.path.basename(path)

                # Show more path context for clarity
                path_parts = path.split('/')
                if len(path_parts) > 3:
                    context_path = '/'.join(path_parts[-3:])  # Show last 3 parts of path
                else:
                    context_path = path

                if matching_lens:
                    lens_name = tde4.getLensName(matching_lens)
                    text = f"{context_path} - {focal}mm (Lens: {lens_name})"
                else:
                    text = f"{context_path} - {focal}mm (No matching lens)"

                idx = tde4.insertListWidgetItem(req, "file_list", text, item_index, "LIST_ITEM_ATOM", -1)
                tde4.setListWidgetItemSelectionFlag(req, "file_list", idx, 1)  # Select by default
                item_index += 1

            except Exception as e:
                log_message(f"Error adding item to list: {filename}", e)
                continue

    log_message("Confirmation GUI created successfully")
    return req, image_data


def create_ref_cameras(req, image_data, match_focal=True):
    """Create reference frame cameras for selected images"""
    created_cameras = []
    try:
        selected_indices = tde4.getListWidgetSelectedItems(req, "file_list")
        log_message(f"Selected indices: {selected_indices}")
    except Exception as e:
        log_message("Error retrieving selected items from list", e)
        return []

    # Create a mapping from list widget index to data index
    widget_to_data_map = {}
    widget_idx = 0

    # Group by slate for consistency with GUI creation
    slate_groups = {}
    for idx, (path, focal) in enumerate(image_data):
        slate = extract_slate_from_path(path)
        if not slate:
            slate = "Unknown"
        if slate not in slate_groups:
            slate_groups[slate] = []
        slate_groups[slate].append((idx, path, focal))

    # Build the mapping
    for slate in sorted(slate_groups.keys()):
        # Skip slate header index if multiple slates
        if len(slate_groups) > 1:
            widget_idx += 1

        for data_idx, _path, _focal in slate_groups[slate]:
            widget_to_data_map[widget_idx] = data_idx
            widget_idx += 1

    log_message(f"Widget to data mapping: {widget_to_data_map}")

    # Process selected items
    for widget_idx in selected_indices:
        if widget_idx not in widget_to_data_map:
            continue

        data_idx = widget_to_data_map[widget_idx]
        path, focal = image_data[data_idx]

        try:
            # Create reference frame camera
            cam = tde4.createCamera("REF_FRAME")
            if not cam:
                log_message(f"Failed to create camera for '{path}'")
                continue

            filename = os.path.basename(path)
            tde4.setCameraName(cam, filename)
            tde4.setCameraPath(cam, path)
            log_message(f"Created camera: '{filename}' with path: '{path}'")

            # Attach lens if requested
            if match_focal:
                lens = find_matching_lens_by_name(focal)
                if lens:
                    tde4.setCameraLens(cam, lens)
                    lens_name = tde4.getLensName(lens)
                    log_message(f"Attached lens '{lens_name}' to camera '{filename}'")
                else:
                    log_message(f"No matching lens found for {focal}mm - camera '{filename}' created without lens")

            created_cameras.append(cam)
        except Exception as e:
            log_message(f"Error creating camera for '{path}'", e)
            continue

    log_message(f"Successfully created {len(created_cameras)} reference frame cameras")
    return created_cameras


def main():
    """Main script execution"""
    try:
        log_message("=== Import Reference Frames Script Started ===")

        # Get clipboard data
        clipboard = tde4.getClipboardString()
        if not clipboard:
            log_message("ERROR: No data found in clipboard")
            tde4.postQuestionRequester("Error", "No data found in clipboard.", "OK")
            return
        log_message("Clipboard data retrieved successfully")

        # Parse clipboard data
        image_data = parse_clipboard_data(clipboard)
        if not image_data:
            log_message("ERROR: No valid image data found in clipboard")
            tde4.postQuestionRequester("Error", "No valid image data found in clipboard.", "OK")
            return

        log_message(f"Found {len(image_data)} valid image entries")

        # Create confirmation GUI
        req, paths_list = create_confirmation_gui(image_data)

        # Add a note about path resolution
        tde4.addLabelWidget(req, "note_label",
                            "Note: Review paths carefully. Relative paths are resolved based on detected slate context.",
                            "ALIGN_LABEL_LEFT")
        tde4.setWidgetOffsets(req, "note_label", 20, 20, 5, 10)

        # Show dialog and get user choice
        result = tde4.postCustomRequester(
            req,
            "Import Reference Frames",
            700, 450,
            "Import with Lens",
            "Import without Lens",
            "Cancel"
        )

        if result == 0:  # Import with lens
            log_message("User selected: Import with lens attachment")
            created_cameras = create_ref_cameras(req, paths_list, match_focal=True)
            if created_cameras:
                log_message(f"SUCCESS: Imported {len(created_cameras)} reference frames with lens attachment")
                tde4.postQuestionRequester("Success",
                                           f"Successfully imported {len(created_cameras)} reference frame(s) with lens attachment.",
                                           "OK")
            else:
                log_message("ERROR: No cameras were created")
                tde4.postQuestionRequester("Error", "No cameras were created.", "OK")

        elif result == 1:  # Import without lens
            log_message("User selected: Import without lens attachment")
            created_cameras = create_ref_cameras(req, paths_list, match_focal=False)
            if created_cameras:
                log_message(f"SUCCESS: Imported {len(created_cameras)} reference frames without lens attachment")
                tde4.postQuestionRequester("Success",
                                           f"Successfully imported {len(created_cameras)} reference frame(s) without lens attachment.",
                                           "OK")
            else:
                log_message("ERROR: No cameras were created")
                tde4.postQuestionRequester("Error", "No cameras were created.", "OK")

        else:  # Cancel
            log_message("User cancelled import operation")

        log_message("=== Import Reference Frames Script Completed ===")

    except Exception as e:
        log_message("CRITICAL ERROR in script execution", e)
        tde4.postQuestionRequester("Critical Error",
                                   f"A critical error occurred: {str(e)}", "OK")


# Execute main function
if __name__ == "__main__":
    main()
