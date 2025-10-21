# SlateGallery - AI Assistant Context

This document contains important context for AI assistants working on the SlateGallery project.

## Project Overview

SlateGallery is a PyQt6-based photo gallery generator that:
- Scans directories for images (JPEG, PNG, TIFF, BMP, GIF)
- Extracts EXIF metadata (focal length, orientation, date taken)
- Generates HTML galleries with filtering and sorting capabilities
- Supports optional thumbnail generation with parallel processing
- Has a companion 3DE4 script (`ImportPhotosFromClipboard.py`)

## Recent Updates & Important Context

### macOS Resource Fork Files (._ files)
- **Issue**: macOS creates resource fork files starting with `._` that aren't real images
- **Solution**: Added filtering in `src/core/image_processor.py:139` to skip these files
- **Impact**: Prevents PIL.UnidentifiedImageError when processing directories from macOS

### Date Format Change
- **Changed from**: `YYYY-MM` format for date grouping
- **Changed to**: `YYYY-MM-DD` format for more granular date filtering
- **Files affected**: 
  - `src/utils/threading.py` - date_key format
  - `tests/test_threading.py` - test expectations updated

### Thumbnail Generation
- **Feature**: Optional thumbnail generation with configurable quality
- **Config**: Stored in config.ini as `generate_thumbnails` boolean
- **Performance**: Uses parallel processing with configurable worker count

### Hidden Images Feature (NEW - 2025-10-18)
- **Feature**: Hide unwanted images from gallery view with persistent storage
- **Modal Button**: Hide/unhide button in modal view (red for hide, green for unhide)
- **Keyboard Shortcut**: Press 'H' key in modal to hide/unhide current image
- **Hidden Mode**: Toggle to view ONLY hidden images for management
- **Bulk Hide**: Hide multiple selected images at once with floating button and confirmation
- **Unhide All**: Bulk restore with confirmation dialog
- **Persistence**: Uses localStorage with in-memory cache for O(1) performance
- **Accessibility**: Full ARIA support with screen reader announcements
- **Integration**: Works seamlessly with filters, selections, and export
- **Documentation**: See `HIDDEN_IMAGES_FEATURE.md` and `HIDDEN_IMAGES_TESTING.md`

### Shift-Select Range Functionality (NEW - 2025-10-21)
- **Feature**: Select multiple images efficiently by holding Shift and clicking checkboxes
- **Behavior**: Selects all images between first click (anchor) and Shift+click
- **Anchor Point**: Fixed anchor point prevents unexpected range changes
- **Integration**: Works seamlessly with bulk hide, export, and filtering

### Show Selected Images Toggle (NEW - 2025-10-21)
- **Feature**: Filter gallery to show only selected images
- **UI**: Always-blue button for easy distinction from other controls
- **Use Case**: Focus on specific image selections during review workflow

## Code Quality Tools

### Linting Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install linting tools
pip install ruff basedpyright

# Run linters
ruff check src/ --fix  # Auto-fix style issues
basedpyright src/      # Type checking
```

### Important Linting Notes
- **ruff**: Handles code style, formatting, import ordering
- **basedpyright**: Handles type checking
- **Auto-fix caution**: ruff --fix can corrupt malformed files (always backup first)

## Testing

### Test Documentation

**Comprehensive testing guides available**:
- 📘 **TESTING_BEST_PRACTICES.md** - General Python/pytest best practices from industry research
- 📗 **QT_TESTING_BEST_PRACTICES.md** - Qt-specific testing patterns and anti-patterns
- 📕 **THREADING_ERROR_TESTS_GUIDE.md** - Ready-to-implement threading error tests
- 📙 **README_TESTING.md** - Quick start guide for running tests
- 🟦 **JAVASCRIPT_TESTING.md** - JavaScript/HTML template testing guide (NEW!)

### Python Test Suite Overview
- **163 total tests** covering all major functionality and real-world scenarios
- **Test framework**: pytest with pytest-qt for Qt components
- **Current coverage**: 45% overall (625/1,127 lines)
  - ✅ Excellent: image_processor (97%), config_manager (98%), gallery_generator (95%), cache_manager (94%)
  - ⚠️ Needs improvement: threading (44%), main UI (0%)
- **Coverage goals**: 45% → 60% (immediate), 60% → 70% (short-term)
- **Key test files**:
  - `test_integration_realistic.py` - Real-world integration tests without mocking
  - `test_performance_benchmark.py` - Performance benchmarking suite
  - `test_threading_errors.py` - Threading error scenarios (to be implemented, see THREADING_ERROR_TESTS_GUIDE.md)

### JavaScript Test Suite Overview (NEW!)
- **99 total tests** covering gallery template frontend functionality
- **Test framework**: Mocha + Chai + Sinon (HTML-based, CDN delivery)
- **Current coverage**: Modal (100%), Events (100%), Persistence (95%), Empty Slate Hiding (100%)
- **Zero installation required**: Open `tests/gallery/gallery_tests.html` in browser
- **Key features tested**:
  - Modal functionality (open, navigate, close with keyboard)
  - Event delegation (performance optimization)
  - Selection persistence (localStorage save/restore)
  - Export button (clipboard API, focal length data)
  - Empty slate hiding (reduces visual clutter when slates are empty)
  - Performance at scale (500 images validated)
- **Documentation**:
  - `tests/gallery/INDEX.md` - Navigation hub ⭐ Start here
  - `tests/gallery/TEST_GUIDE.md` - Quick reference
  - `tests/gallery/README.md` - Full documentation
  - See **JAVASCRIPT_TESTING.md** for integration guide

### Running Tests

#### Python Tests (Backend)

**Standard Environment (with display)**
```bash
python -m pytest tests/
```

**Headless/CI Environment**
```bash
# Best solution: Use Xvfb
xvfb-run -a python -m pytest tests/

# Or use the provided script
./run_tests.sh

# Alternative: Skip Qt tests if Xvfb unavailable
python -m pytest tests/ -k "not Thread"
```

#### JavaScript Tests (Frontend)

**Quick Start (Simplest)**
```bash
# Open in browser - tests run automatically
firefox tests/gallery/gallery_tests.html
```

**Test Runner Script**
```bash
cd tests/gallery
./run_tests.sh browser    # Open in browser
./run_tests.sh server     # Start web server
./run_tests.sh headless   # CI/CD headless mode
```

**Expected Output**: `99 passing (1.3s)` - All frontend tests pass

### Qt Testing in Headless Environments

**Problem**: Qt tests require a display server to run properly

**Solutions (in order of preference)**:

1. **Xvfb (Recommended)**
   - Provides virtual X11 display
   - Full Qt compatibility
   - No segmentation faults
   - Industry standard for CI/CD
   ```bash
   sudo apt-get install xvfb
   xvfb-run -a pytest tests/
   ```

2. **QT_QPA_PLATFORM=offscreen**
   - Lighter weight but limited functionality
   - May cause segmentation faults during cleanup
   - Not recommended for production CI
   ```bash
   QT_QPA_PLATFORM=offscreen pytest tests/
   ```

3. **Skip Qt Tests**
   - Run only non-Qt tests
   - Safe but incomplete coverage
   ```bash
   pytest tests/ -k "not Thread"
   ```

### Test Configuration
- **conftest.py**: Main test configuration
- **Fixtures**: Temp directories, mock images, sample data
- **Thread cleanup**: Use `cleanup_thread()` helper to prevent Qt thread warnings

## Project Structure

```
SlateGallery/
├── src/
│   ├── core/
│   │   ├── image_processor.py    # EXIF extraction, directory scanning
│   │   ├── gallery_generator.py  # HTML generation
│   │   ├── config_manager.py     # Settings persistence
│   │   └── cache_manager.py      # Metadata caching
│   ├── gui/
│   │   └── main_window.py        # PyQt6 interface
│   └── utils/
│       └── threading.py          # QThread implementations
├── tests/                         # Comprehensive test suite
├── templates/                     # HTML gallery templates
├── ImportPhotosFromClipboard.py  # 3DE4 companion script
└── run_tests.sh                   # Smart test runner script
```

## Common Issues & Solutions

### Issue: Tests crash with "QThread: Destroyed while thread '' is still running"
**Solution**: Ensure proper thread cleanup using the `cleanup_thread()` helper

### Issue: "Failed to create wl_display" warning in WSL2
**Solution**: This Wayland warning can be safely ignored - Qt falls back to X11

### Issue: ImportPhotosFromClipboard.py saved as single line
**Solution**: Complete reformatting required - the file uses 3DE4 special header format

### Issue: Config returns wrong number of values
**Solution**: Config now returns 5 values: (current_dir, slate_dirs, generate_thumbnails, thumbnail_size, lazy_loading)

## Performance Considerations

- **Parallel Processing**: Uses multiprocessing.cpu_count() workers by default
- **Caching**: Metadata cache prevents redundant EXIF extraction
- **Thumbnail Generation**: Optional to avoid unnecessary processing
- **Directory Scanning**: Skips symbolic links to prevent loops

## 3DE4 Integration

The `ImportPhotosFromClipboard.py` script:
- Must maintain specific header format for 3DE4 recognition
- Imports reference frames from clipboard data
- Creates UI widgets for slate selection
- Handles focal length metadata

## Code Style Guidelines

- Follow PEP 8 (enforced by ruff)
- Type hints where beneficial (checked by basedpyright)
- Comprehensive docstrings for public methods
- Logging over print statements
- Error handling with specific exceptions

## Future Improvements

Potential areas for enhancement:
- WebP image format support
- RAW file format support
- Video thumbnail extraction
- Cloud storage integration
- Real-time gallery updates
- Advanced EXIF data display

## Important Commands

```bash
# Install all dependencies
pip install PySide6 Pillow Jinja2 piexif psutil pytest pytest-qt pytest-cov ruff basedpyright

# Run application
python run_slate_gallery.py

# Run linting
ruff check src/ --fix && basedpyright src/

# Run tests with coverage
./run_tests.sh --cov=src

# Generate test coverage report
pytest tests/ --cov=src --cov-report=html
```

## CI/CD Configuration

For GitHub Actions or similar:

```yaml
- name: Setup Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.12'

- name: Install system dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y xvfb

- name: Install Python dependencies
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-qt pytest-cov

- name: Lint code
  run: |
    ruff check src/
    basedpyright src/

- name: Run tests
  run: xvfb-run -a pytest tests/ -v --cov=src
```

## Notes for AI Assistants

1. **Always run linting** after making code changes: `ruff check src/ --fix && basedpyright src/`
2. **Test in headless mode** if no display available: use `xvfb-run` or `./run_tests.sh`
3. **Testing documentation**: Comprehensive guides available in TESTING_BEST_PRACTICES.md and THREADING_ERROR_TESTS_GUIDE.md
4. **Coverage gaps**: Priority #1 is threading error tests (44% → 60% coverage gain, 2-4 hours)
5. **Check for macOS files**: Remember to filter `._*` files when processing images
6. **Thread safety**: Always properly cleanup Qt threads to prevent crashes
7. **Config changes**: Remember config now returns 5 values including thumbnail and lazy loading preferences
8. **Date format**: Use YYYY-MM-DD for date keys, not YYYY-MM
9. **Performance**: Parallel processing is now always enabled for EXIF extraction (fixed bottleneck)
10. **Worker optimization**: Worker count is now 2x CPU cores for I/O operations (up to 16 workers)
11. **Type safety**: Project uses basedpyright in "recommended" mode with 0 errors, 251 warnings (production-ready)

Last updated: 2025-10-21