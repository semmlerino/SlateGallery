# SlateGallery - Photo Gallery Generator

A modular Python application for generating HTML photo galleries with EXIF data extraction, intelligent organization, and responsive web templates.

## Features

- **EXIF Data Extraction**: Automatic focal length and orientation detection from JPEG, PNG, and TIFF images
- **Smart Organization**: Organize photos by directory with filtering and selection capabilities  
- **Responsive HTML Gallery**: Generate clean, modern HTML galleries with image metadata
- **Performance Optimized**: Multi-threaded scanning with intelligent caching
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Unicode Support**: Handles international filenames and paths

## Quick Start

### Requirements
- Python 3.9+
- PySide6 (Qt GUI framework)
- Pillow (PIL) for image processing
- Jinja2 for HTML templating

### Installation
```bash
# Clone or download the project
cd SlateGallery

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install PySide6 Pillow Jinja2 piexif typing-extensions
```

### Running the Application
```bash
# Simple execution
python run_slate_gallery.py

# Or directly run the main module
python -m src.main
```

## Project Structure

```
SlateGallery/
├── src/                          # Modular source code
│   ├── core/                     # Core business logic
│   │   ├── image_processor.py    # EXIF extraction & directory scanning
│   │   ├── cache_manager.py      # Performance caching
│   │   ├── config_manager.py     # Settings persistence
│   │   └── gallery_generator.py  # HTML generation with security
│   ├── utils/                    # Utilities
│   │   ├── logging_config.py     # Logging setup
│   │   └── threading.py          # Qt threading classes
│   └── main.py                   # Main application & UI
├── templates/                    # HTML templates
├── tests/                        # Comprehensive test suite
├── archive/                      # Legacy files (gitignored)
├── run_slate_gallery.py         # Entry point script
└── README.md                     # This file
```

## Usage

1. **Launch Application**: Run `python run_slate_gallery.py`
2. **Select Directory**: Choose a folder containing your photos
3. **Scan Photos**: Click "Scan Directories" to analyze your images
4. **Select Slates**: Choose which photo groups to include in your gallery
5. **Generate Gallery**: Click "Generate Gallery" to create your HTML gallery
6. **View Results**: Open the generated `index.html` in your browser

## Architecture Highlights

### Modular Design
- **Clean separation of concerns** with dedicated modules for each responsibility
- **Testable components** with minimal interdependence
- **Scalable structure** supporting future enhancements

### Robust Image Processing
- **Modern PIL compatibility** with fallback support for older versions
- **Multi-format support** (JPEG, PNG, TIFF) with proper EXIF handling
- **Error resilient** processing with graceful failure handling

### Performance Optimized
- **Smart caching system** to avoid repeated image processing
- **Multi-threaded operations** for responsive UI during scanning
- **Efficient memory management** with proper resource cleanup

## Testing

The project includes a comprehensive test suite with 77 tests achieving 100% pass rate:

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src

# Run specific test categories
python -m pytest tests/test_image_processing.py  # Core functionality
python -m pytest tests/test_integration.py       # End-to-end workflows  
python -m pytest tests/test_ui_threading.py      # UI and threading
```

### Test Philosophy
- **Minimal mocking**: Real implementations with isolated test environments
- **Real data**: Actual images with EXIF data for authentic testing
- **Bug detection**: Tests designed to catch real issues, not just code coverage

## Development

### Key Design Principles
- **Real over mocked**: Tests use real images and data when possible
- **Fail fast**: Tests designed to catch real bugs early
- **Clean architecture**: Modular design with clear boundaries
- **Performance conscious**: Efficient algorithms and caching

### Contributing
1. Tests must pass: `python -m pytest tests/`
2. Follow modular structure: Keep concerns separated
3. Maintain real test data: Use actual images for testing
4. Document changes: Update relevant documentation

## Legacy

This project was successfully refactored from a monolithic 1257-line file into a clean modular architecture while maintaining 100% functional compatibility. The original implementation and migration artifacts are preserved in the `archive/` directory.

## License

[Add your license here]

## Support

For issues, feature requests, or questions, please [create an issue](link-to-issues) or contact the maintainer.