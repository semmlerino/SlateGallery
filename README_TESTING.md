# SlateGallery Testing Guide

## Running Tests

SlateGallery includes a comprehensive test suite with 110 tests covering all major functionality.

### Quick Start

```bash
# Run all tests
./run_tests.sh

# Run specific test file
./run_tests.sh tests/test_image_processor.py

# Run with coverage
./run_tests.sh --cov=src

# Run non-Qt tests only (if having display issues)
python -m pytest tests/ -k "not Thread"
```

### Test Categories

- **Unit Tests**: Core functionality (image processing, config, cache)
- **Integration Tests**: End-to-end workflows
- **Qt Thread Tests**: GUI threading and signals

## Headless/CI Environment Setup

The test suite uses Qt components that require a display. For headless environments (CI/CD, SSH sessions):

### Option 1: Xvfb (Recommended)

```bash
# Install Xvfb
sudo apt-get install xvfb

# Tests will automatically use Xvfb when no display is detected
./run_tests.sh
```

### Option 2: Run Without Qt Tests

```bash
# Skip Qt-specific tests
python -m pytest tests/ -k "not Thread"
```

### Option 3: Docker with Xvfb

```dockerfile
FROM python:3.12
RUN apt-get update && apt-get install -y xvfb
# ... rest of Dockerfile
CMD xvfb-run -a pytest tests/
```

## Test Coverage

Current test coverage:
- ✅ 110 total tests
- ✅ Image processing with EXIF data
- ✅ Configuration management
- ✅ Cache management
- ✅ HTML gallery generation
- ✅ Threading and parallel processing
- ✅ Date filtering and sorting
- ✅ Thumbnail generation
- ✅ macOS resource fork file filtering

## Known Issues

1. **Qt tests in pure headless mode**: Without Xvfb, Qt tests may crash during cleanup. This is a Qt limitation, not a code bug.

2. **WSL2 Warning**: You may see Wayland warnings in WSL2. These can be safely ignored:
   ```
   Failed to create wl_display (No such file or directory)
   qt.qpa.plugin: Could not load the Qt platform plugin "wayland"
   ```

## Writing New Tests

Tests use pytest and follow these patterns:

```python
# Unit test example
def test_feature():
    result = my_function(input_data)
    assert result == expected_output

# Qt thread test example
def test_qt_thread(qtbot):
    thread = MyQThread()
    with qtbot.waitSignal(thread.finished):
        thread.start()
    assert thread.result == expected
```

## Continuous Integration

For GitHub Actions or other CI:

```yaml
- name: Install dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y xvfb
    pip install -r requirements.txt

- name: Run tests
  run: xvfb-run -a pytest tests/ -v
```