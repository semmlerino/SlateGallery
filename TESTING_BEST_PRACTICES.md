# Testing Best Practices for SlateGallery

*Based on pytest, pytest-qt, and industry best practices research (October 2025)*

## Table of Contents

1. [Strategic Testing Principles](#strategic-testing-principles)
2. [Error Path Testing](#error-path-testing)
3. [Coverage Strategy](#coverage-strategy)
4. [Threading & Async Testing](#threading--async-testing)
5. [Test Organization](#test-organization)
6. [Pytest Best Practices](#pytest-best-practices)
7. [Quick Wins for Coverage](#quick-wins-for-coverage)

## Strategic Testing Principles

### The Five Exit Doors

Every backend flow should test these five observable outcomes:

1. **Response** - Correct return values, schemas, and status
2. **State Changes** - Data modifications (database, cache, files)
3. **External Calls** - HTTP requests, file I/O, service calls
4. **Message Queues** - Async message handling and acknowledgment
5. **Observability** - Logging, metrics, error handling

```python
# Example: Test all five exit doors for image processing
def test_process_image_complete_flow(tmp_path):
    """Test all observable outcomes of image processing"""

    # Arrange
    image_path = tmp_path / "test.jpg"
    create_test_image(image_path)
    processor = ImageProcessor()

    # Act
    result = processor.process(str(image_path))

    # Assert - Door 1: Response
    assert result['status'] == 'success'
    assert result['focal_length'] == 50.0

    # Assert - Door 2: State Changes
    cache_file = tmp_path / ".slate_gallery" / "metadata.json"
    assert cache_file.exists()

    # Assert - Door 3: External Calls (file I/O)
    assert image_path.read_bytes()  # File was read

    # Assert - Door 5: Observability
    assert 'Processed image' in caplog.text
```

### Write Tests During Coding

**When to write tests:**
- ✅ **During development** - Provides immediate safety net
- ✅ **After design clarity** - When you understand what you're building
- ❌ **Too early (strict TDD)** - Leads to excessive refactoring
- ❌ **After everything is done** - Loses anti-regression value

**Sweet spot**: Write tests when requirements are clear but before moving to next feature.

### Focus on Observable Outcomes, Not Implementation

```python
# ❌ BAD - Tests internal implementation
def test_internal_state():
    processor = ImageProcessor()
    processor._extract_exif(image)
    assert processor._exif_cache == expected  # Fragile!

# ✅ GOOD - Tests observable behavior
def test_extract_focal_length():
    processor = ImageProcessor()
    metadata = processor.extract_metadata(image_path)
    assert metadata['focal_length'] == 50.0  # Public interface
```

## Error Path Testing

### Comprehensive Error Coverage

**Critical principle**: Test both happy paths AND error paths. Error paths often have more bugs.

```python
# Happy path + error paths for image processing
class TestImageProcessing:
    def test_valid_jpeg_image(self):
        """Happy path: Process valid JPEG"""
        result = process_image('valid.jpg')
        assert result['status'] == 'success'

    def test_nonexistent_file(self):
        """Error: File doesn't exist"""
        with pytest.raises(FileNotFoundError):
            process_image('/nonexistent.jpg')

    def test_corrupted_image(self):
        """Error: PIL can't read image"""
        result = process_image('corrupted.jpg')
        assert result['status'] == 'error'
        assert 'Cannot identify image' in result['message']

    def test_permission_denied(self):
        """Error: No read permissions"""
        # Create file with no read permissions
        result = process_image('nopermission.jpg')
        assert result['status'] == 'error'

    def test_missing_exif_data(self):
        """Edge case: Valid image but no EXIF"""
        result = process_image('no_exif.jpg')
        assert result['focal_length'] is None
        assert result['status'] == 'success'
```

### Error Path Categories

Test these error scenarios systematically:

| Category | Examples | SlateGallery Context |
|----------|----------|---------------------|
| **Input validation** | None, empty, wrong type | Empty directory, invalid path |
| **Resource availability** | File missing, disk full | Image file deleted during scan |
| **Permissions** | Access denied | Read-only directories |
| **External failures** | Network timeout, service down | PIL fails to load image |
| **Data corruption** | Malformed data | Corrupted EXIF metadata |
| **Concurrent access** | Race conditions | Multiple threads reading cache |
| **Resource exhaustion** | Memory limit, thread pool full | Too many parallel workers |

### Testing Exception Handling

```python
# Test that exceptions are caught and handled
def test_exception_handling_with_context_manager():
    """Verify exceptions are caught and logged properly"""

    processor = ImageProcessor()

    # Mock to raise exception
    with patch('PIL.Image.open', side_effect=IOError("Disk read error")):
        result = processor.process_safe('test.jpg')

    # Assert exception was handled
    assert result['status'] == 'error'
    assert 'Disk read error' in result['message']

def test_exception_not_raised_to_caller():
    """Ensure internal exceptions don't crash the application"""

    processor = ImageProcessor()

    # Should not raise, even with invalid input
    try:
        result = processor.process_safe(None)
        assert result['status'] == 'error'
    except Exception as e:
        pytest.fail(f"Exception should have been caught: {e}")
```

## Coverage Strategy

### Current SlateGallery Coverage Analysis

**Excellent (94-98% coverage)**:
- ✅ `image_processor.py` - Core business logic
- ✅ `config_manager.py` - Configuration
- ✅ `gallery_generator.py` - HTML generation
- ✅ `cache_manager.py` - Caching

**Needs Improvement**:
- ⚠️ `threading.py` (44%) - **Error paths untested**
- ⚠️ `main.py` (0%) - **UI requires display server**

### Realistic Coverage Goals

| Timeframe | Target | Focus Areas |
|-----------|--------|-------------|
| **Immediate (1 week)** | 50% → 60% | Threading error tests |
| **Short-term (1 month)** | 60% → 70% | Cache stress, gallery edge cases |
| **Long-term (3 months)** | 70% → 75% | UI testing with Xvfb (optional) |

### Prioritization Framework

**Quick Win Formula**: `(Coverage Gain × Criticality) / Effort`

```python
# Priority 1: Threading errors (High impact, low effort)
# - Current: 44% coverage
# - Target: 60% coverage (+15%)
# - Criticality: HIGH (error handling gaps)
# - Effort: 2-4 hours
# - ROI: ⭐⭐⭐⭐⭐

# Priority 2: Cache stress tests (Medium impact, low effort)
# - Current: 94% coverage
# - Target: 97% coverage (+3%)
# - Criticality: MEDIUM
# - Effort: 1-2 hours
# - ROI: ⭐⭐⭐

# Priority 3: UI testing (Low ROI)
# - Current: 0% coverage
# - Target: 30% coverage (+30%)
# - Criticality: LOW (UI logic minimal)
# - Effort: 12+ weeks
# - ROI: ⭐
```

## Threading & Async Testing

### pytest-qt Best Practices for Threads

```python
# Pattern 1: Wait for signal with timeout
def test_thread_completion(qtbot):
    """Test thread completes successfully"""
    thread = ScanThread('/test/path', cache_manager)

    # Wait for completion signal
    with qtbot.waitSignal(thread.scan_complete, timeout=5000) as blocker:
        thread.start()

    # Verify signal was emitted
    assert blocker.signal_triggered
    assert blocker.args[0] == expected_result

# Pattern 2: Wait for condition
def test_thread_processing(qtbot):
    """Test thread processes all items"""
    thread = ScanThread('/test/path', cache_manager)
    thread.start()

    # Wait until processing complete
    qtbot.waitUntil(lambda: not thread.isRunning(), timeout=5000)

    assert thread.items_processed == expected_count

# Pattern 3: Capture exceptions in Qt virtual methods
def test_thread_exception_handling(qtbot):
    """Test exception in thread.run() is captured"""
    thread = ScanThread('/invalid/path', None)

    with qtbot.captureExceptions() as exceptions:
        thread.start()
        qtbot.waitUntil(lambda: not thread.isRunning(), timeout=2000)

    assert len(exceptions) > 0
    assert isinstance(exceptions[0], ValueError)
```

### Threading Error Scenarios

```python
class TestScanThreadErrors:
    """Comprehensive error testing for ScanThread"""

    @pytest.fixture
    def cleanup_thread(self):
        """Fixture to ensure thread cleanup"""
        threads = []
        yield threads
        # Cleanup all threads
        for thread in threads:
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)

    def test_nonexistent_directory(self, qtbot, cleanup_thread):
        """Test handling of non-existent directory"""
        thread = ScanThread('/nonexistent', cache_manager)
        cleanup_thread.append(thread)

        with qtbot.waitSignal(thread.scan_complete, timeout=2000):
            thread.start()

        # Should complete with error status
        assert thread.error_occurred

    def test_permission_denied(self, qtbot, cleanup_thread, tmp_path):
        """Test handling of permission denied"""
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir(mode=0o000)

        thread = ScanThread(str(restricted_dir), cache_manager)
        cleanup_thread.append(thread)

        with qtbot.waitSignal(thread.scan_complete, timeout=2000):
            thread.start()

        assert thread.error_occurred

    def test_thread_interruption(self, qtbot, cleanup_thread):
        """Test clean shutdown on interruption"""
        thread = ScanThread('/large/directory', cache_manager)
        cleanup_thread.append(thread)

        thread.start()

        # Request interruption immediately
        thread.requestInterruption()

        qtbot.waitUntil(lambda: not thread.isRunning(), timeout=2000)

        assert thread.isInterruptionRequested()
        assert not thread.isRunning()
```

### ThreadPoolExecutor Testing

```python
def test_thread_pool_exception_handling():
    """Test exception handling in thread pool"""

    def failing_task(path):
        raise ValueError(f"Cannot process {path}")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(failing_task, f"path{i}") for i in range(5)]

        errors = []
        for future in futures:
            try:
                future.result()
            except ValueError as e:
                errors.append(str(e))

        assert len(errors) == 5
        assert all("Cannot process" in error for error in errors)

def test_thread_pool_shutdown():
    """Test thread pool shuts down cleanly"""

    executor = ThreadPoolExecutor(max_workers=2)

    # Submit some tasks
    futures = [executor.submit(time.sleep, 0.1) for _ in range(5)]

    # Shutdown and wait
    executor.shutdown(wait=True)

    # All futures should be done
    assert all(f.done() for f in futures)
```

## Test Organization

### Structure by API/Component

```python
# Organize tests to mirror code structure
"""
tests/
├── test_image_processor.py       # Tests for src/core/image_processor.py
│   ├── TestEXIFExtraction
│   ├── TestImageScanning
│   └── TestErrorHandling
├── test_cache_manager.py          # Tests for src/core/cache_manager.py
├── test_threading.py              # Tests for src/utils/threading.py
│   ├── TestScanThread
│   ├── TestGenerateGalleryThread
│   └── TestThreadErrors
└── test_integration_realistic.py  # End-to-end tests
"""
```

### Naming Conventions

```python
# Test function naming pattern: test_<scenario>_<expected_outcome>
def test_valid_image_returns_metadata():
    """Test that valid image returns complete metadata"""
    pass

def test_missing_file_raises_error():
    """Test that missing file raises FileNotFoundError"""
    pass

def test_corrupted_exif_returns_none():
    """Test that corrupted EXIF data returns None gracefully"""
    pass
```

### Use Descriptive Test Classes

```python
class TestImageProcessorHappyPaths:
    """Test successful image processing scenarios"""

    def test_jpeg_with_exif(self):
        pass

    def test_png_without_exif(self):
        pass

class TestImageProcessorErrorHandling:
    """Test error scenarios in image processing"""

    def test_nonexistent_file(self):
        pass

    def test_corrupted_image(self):
        pass

    def test_permission_denied(self):
        pass
```

## Pytest Best Practices

### Effective Fixture Usage

```python
# Pattern: Fixture hierarchy for complex setup
@pytest.fixture
def temp_image_dir(tmp_path):
    """Create directory with test images"""
    image_dir = tmp_path / "images"
    image_dir.mkdir()

    # Create test images
    for i in range(5):
        create_test_image(image_dir / f"test{i}.jpg")

    return image_dir

@pytest.fixture
def cache_manager(temp_image_dir):
    """Create cache manager for test directory"""
    manager = CacheManager(str(temp_image_dir))
    yield manager
    # Cleanup
    manager.clear()

@pytest.fixture
def image_processor(cache_manager):
    """Create image processor with cache"""
    return ImageProcessor(cache_manager)
```

### Parameterized Testing for Error Cases

```python
@pytest.mark.parametrize("invalid_path,expected_error", [
    ("/nonexistent/path", FileNotFoundError),
    ("", ValueError),
    (None, TypeError),
    ("/proc/1/mem", PermissionError),  # Common unreadable path
])
def test_invalid_paths_raise_errors(invalid_path, expected_error):
    """Test various invalid path scenarios"""
    processor = ImageProcessor()

    with pytest.raises(expected_error):
        processor.process(invalid_path)
```

### Monkeypatching for External Dependencies

```python
def test_pil_failure_handled(monkeypatch):
    """Test that PIL failures are handled gracefully"""

    def mock_open(*args, **kwargs):
        raise IOError("Cannot identify image file")

    monkeypatch.setattr('PIL.Image.open', mock_open)

    processor = ImageProcessor()
    result = processor.process_safe('test.jpg')

    assert result['status'] == 'error'
    assert 'Cannot identify' in result['message']
```

### Capturing Logs for Observability Testing

```python
def test_error_logging(caplog):
    """Test that errors are logged properly"""

    processor = ImageProcessor()

    with caplog.at_level(logging.ERROR):
        processor.process('/nonexistent.jpg')

    # Verify error was logged
    assert 'Failed to process image' in caplog.text
    assert '/nonexistent.jpg' in caplog.text
```

### Test Timeouts for Hanging Operations

```python
@pytest.mark.timeout(5)  # Requires pytest-timeout
def test_thread_doesnt_hang():
    """Test that thread completes within reasonable time"""
    thread = ScanThread('/test/path', cache_manager)
    thread.start()
    thread.wait(5000)

    assert not thread.isRunning()
```

## Quick Wins for Coverage

### Priority 1: Threading Error Tests (2-4 hours → +15% coverage)

**File**: `tests/test_threading_errors.py`

```python
# Create comprehensive error tests for threading.py
- test_scan_thread_nonexistent_directory
- test_scan_thread_permission_denied
- test_scan_thread_corrupted_cache
- test_scan_thread_interruption
- test_scan_thread_exception_in_callback
- test_gallery_thread_template_missing
- test_gallery_thread_disk_full
- test_gallery_thread_permission_denied
```

### Priority 2: Cache Stress Tests (1-2 hours → +3% coverage)

**File**: `tests/test_cache_stress.py`

```python
# Add edge cases and stress tests
- test_concurrent_cache_access
- test_cache_with_1000_images
- test_cache_corruption_recovery
- test_cache_disk_space_handling
```

### Priority 3: Gallery Edge Cases (1-2 hours → +4% coverage)

**File**: Enhance `tests/test_gallery_generator.py`

```python
# Add error scenario tests
- test_empty_image_list
- test_missing_template_file
- test_invalid_metadata_format
- test_template_rendering_error
```

### Priority 4: Logging Edge Cases (1-2 hours → +5% coverage)

**File**: `tests/test_logging_config.py`

```python
# Test logging setup and error cases
- test_log_directory_creation_failure
- test_log_rotation
- test_logging_with_unicode_characters
```

## Summary Checklist

Testing best practices checklist for SlateGallery:

- [ ] Test the 5 exit doors (response, state, external calls, queues, observability)
- [ ] Write tests during development, not after
- [ ] Focus on observable outcomes, not implementation
- [ ] Test both happy paths AND error paths
- [ ] Use pytest-qt's `qtbot` for thread testing
- [ ] Clean up threads properly in fixtures
- [ ] Parameterize tests for multiple error scenarios
- [ ] Use monkeypatch for external dependencies
- [ ] Capture logs to test observability
- [ ] Prioritize high-impact, low-effort coverage wins
- [ ] Aim for 60-70% coverage (realistic, maintainable)
- [ ] Skip UI testing unless critical (high effort, low ROI)

## Next Steps

1. **Immediate (This week)**:
   - Create `tests/test_threading_errors.py` with 8-10 error scenario tests
   - Run tests and verify coverage improvement
   - Target: 45% → 60% coverage

2. **Short-term (This month)**:
   - Add cache stress tests
   - Add gallery edge case tests
   - Target: 60% → 70% coverage

3. **Optional (Long-term)**:
   - Set up Xvfb for UI testing in CI/CD
   - Add basic UI tests for critical paths
   - Target: 70% → 75% coverage

---

*Document created: October 2025*
*Based on pytest-dev/pytest, pytest-dev/pytest-qt, and nodejs-testing-best-practices research*
