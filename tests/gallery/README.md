# SlateGallery JavaScript Test Suite

Comprehensive test suite for the SlateGallery HTML template with **102 tests** covering all critical functionality.

## Quick Start

### Running Tests Locally

**Option 1: Open in Browser (Simplest)**
```bash
# Open the test file directly in your browser
firefox tests/gallery/gallery_tests.html
# or
google-chrome tests/gallery/gallery_tests.html
# or
open tests/gallery/gallery_tests.html  # macOS
```

**Option 2: Local Web Server (Recommended for CI)**
```bash
# Using Python's built-in HTTP server
cd /path/to/SlateGallery
python3 -m http.server 8000

# Open in browser: http://localhost:8000/tests/gallery/gallery_tests.html
```

**Option 3: Headless Browser (CI/CD)**
```bash
# Using Playwright (install first: pip install playwright && playwright install)
playwright test tests/gallery/gallery_tests.html

# Using Puppeteer
npx puppeteer tests/gallery/gallery_tests.html
```

## Test Structure

### Test Categories (102 Total Tests)

#### 1. **Modal Functionality** (15 tests)
- ✅ Modal opening and closing
- ✅ Image display and metadata
- ✅ Keyboard navigation (arrows, ESC)
- ✅ Click outside to close
- ✅ Focus management
- ✅ Body scroll prevention

**Priority**: 🔴 **Critical** - Just fixed enlarge button delegation

**Key Tests**:
- `should open modal when enlarge button is clicked` - Validates the recent event delegation fix
- `should navigate to next image with arrow key` - Tests keyboard UX
- `should close modal when ESC key is pressed` - Essential accessibility

#### 2. **Event Delegation** (8 tests)
- ✅ Checkbox change handling
- ✅ Image click toggling
- ✅ Enlarge button clicks
- ✅ No individual listeners (memory optimization)
- ✅ Dynamic element support
- ✅ Performance with rapid changes

**Priority**: 🔴 **Critical** - Performance optimization validation

**Key Tests**:
- `should handle checkbox changes through event delegation` - Core performance fix
- `should work with dynamically added images` - Future-proofing
- `should handle rapid checkbox changes without lag` - Scale validation

#### 3. **Selection Persistence** (9 tests)
- ✅ localStorage save/restore
- ✅ Gallery identifier isolation
- ✅ Multiple selection handling
- ✅ Quota exceeded handling
- ✅ Missing localStorage graceful degradation
- ✅ Debounced writes

**Priority**: 🟠 **High** - Data integrity and UX

**Key Tests**:
- `should restore selections on page load` - Critical for UX
- `should use gallery identifier to prevent cross-gallery pollution` - Data integrity
- `should handle localStorage quota exceeded gracefully` - Error resilience

#### 4. **Selection Visibility** (8 tests)
- ✅ Checkmark badge display
- ✅ Blue border styling
- ✅ Background tint
- ✅ Shadow effects
- ✅ Hover state enhancements
- ✅ Filter persistence

**Priority**: 🟡 **Medium** - Visual feedback

**Key Tests**:
- `should show checkmark badge on selected items` - Primary visual indicator
- `should maintain visibility during filter changes` - State consistency

#### 5. **Status Bar** (7 tests)
- ✅ Initial count display
- ✅ Filter updates
- ✅ Selection count tracking
- ✅ Real-time updates
- ✅ Edge cases (0 visible, all selected)

**Priority**: 🟡 **Medium** - User feedback

**Key Tests**:
- `should display correct initial count` - Baseline functionality
- `should update in real-time with selections` - Dynamic updates

#### 6. **Export Button** (10 tests)
- ✅ FAB positioning (bottom-right)
- ✅ Selection badge display/hide
- ✅ Dynamic badge count
- ✅ Clipboard API integration
- ✅ Focal length inclusion
- ✅ Error handling
- ✅ Fallback for old browsers

**Priority**: 🟠 **High** - Core workflow

**Key Tests**:
- `should copy data to clipboard on click` - Essential functionality
- `should include focal lengths in export data` - Data completeness
- `should handle clipboard API failure gracefully` - Error resilience

#### 7. **Performance** (7 tests)
- ✅ 100 image handling
- ✅ 500 image handling (scale test)
- ✅ Event delegation efficiency
- ✅ Visible image caching
- ✅ Debouncing (filters, resize)
- ✅ Memory leak prevention

**Priority**: 🟠 **High** - Scale validation

**Key Tests**:
- `should handle 500 images without lag` - Real-world scale test
- `should use event delegation to minimize listeners` - Memory optimization
- `should not leak memory with IntersectionObserver` - Long-term stability

#### 8. **Integration Scenarios** (12 tests)
- ✅ Full workflow: select → export → verify
- ✅ Filter → select → status updates
- ✅ Persistence across refresh
- ✅ Modal + filter interaction
- ✅ Modal ↔ gallery sync
- ✅ Bulk operations
- ✅ Edge cases

**Priority**: 🟠 **High** - Real-world validation

**Key Tests**:
- `should complete full workflow: select → export → verify data` - End-to-end
- `should persist selections across page refresh simulation` - Critical UX
- `should handle edge case: export with no selection` - Error prevention

## Test Results Interpretation

### Expected Results

✅ **All tests should pass** on first run with the current template implementation.

### Common Test Patterns

The tests use several key patterns:

1. **Mock DOM Creation**
   ```javascript
   containers = TestHelpers.createMockGallery(10);
   ```

2. **Event Simulation**
   ```javascript
   TestHelpers.simulateClick(element);
   TestHelpers.simulateKeyPress('Escape');
   ```

3. **Async Handling**
   ```javascript
   await TestHelpers.wait(100);
   ```

4. **Stub/Mock APIs**
   ```javascript
   mockStorage = TestHelpers.mockLocalStorage();
   mockClipboard = TestHelpers.mockClipboard();
   ```

## Test Helpers Reference

### TestHelpers API

#### DOM Creation
```javascript
// Create single image container
const container = TestHelpers.createMockImageContainer({
    orientation: 'landscape',
    focalLength: '50',
    dateTaken: '2024-01-15',
    filename: 'test.jpg',
    fullPath: '/path/to/test.jpg',
    isVisible: true
});

// Create multiple containers
const containers = TestHelpers.createMockGallery(10);

// Create UI elements
const modal = TestHelpers.createModalElements();
const statusBar = TestHelpers.createStatusBar();
const exportButton = TestHelpers.createExportButton();
const notificationBar = TestHelpers.createNotificationBar();
```

#### Event Simulation
```javascript
// Click simulation
TestHelpers.simulateClick(element);

// Keyboard simulation
TestHelpers.simulateKeyPress('Escape');
TestHelpers.simulateKeyPress('ArrowRight');

// Checkbox change
TestHelpers.simulateCheckboxChange(checkbox, true);
```

#### Mocking
```javascript
// Mock localStorage
const mockStorage = TestHelpers.mockLocalStorage();
mockStorage.getItem('key');
mockStorage.setItem('key', 'value');

// Mock clipboard
const mockClipboard = TestHelpers.mockClipboard();
await mockClipboard.writeText('data');
```

#### Utilities
```javascript
// Wait for async operations
await TestHelpers.wait(100);

// Cleanup between tests
TestHelpers.cleanup();
```

## Extending the Test Suite

### Adding New Tests

1. **Choose the right test suite**:
   ```javascript
   describe('Gallery Modal Functionality', function() {
       describe('New Feature', function() {
           it('should do something specific', function() {
               // Test code
           });
       });
   });
   ```

2. **Use beforeEach/afterEach for setup**:
   ```javascript
   beforeEach(function() {
       fixtures = document.getElementById('test-fixtures');
       TestHelpers.cleanup();
       // Setup test state
   });

   afterEach(function() {
       TestHelpers.cleanup();
   });
   ```

3. **Follow AAA pattern**:
   ```javascript
   it('should update status bar on selection', function() {
       // Arrange
       const container = TestHelpers.createMockImageContainer();
       fixtures.appendChild(container);

       // Act
       const checkbox = container.querySelector('.select-checkbox');
       TestHelpers.simulateCheckboxChange(checkbox, true);

       // Assert
       expect(checkbox.checked).to.be.true;
   });
   ```

### Testing Real Gallery Template

To test against the actual rendered gallery template:

1. **Generate a test gallery**:
   ```bash
   python run_slate_gallery.py --output-dir test_output
   ```

2. **Inject test script into generated HTML**:
   ```javascript
   // Add to gallery HTML before </body>
   <script src="../../tests/gallery/test_runner.js"></script>
   ```

3. **Run integration tests**:
   ```bash
   # Open generated gallery with tests
   firefox test_output/gallery.html
   ```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Gallery JavaScript Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install playwright
          playwright install chromium

      - name: Run tests
        run: |
          python3 -m http.server 8000 &
          SERVER_PID=$!
          sleep 2
          npx playwright test --headed tests/gallery/gallery_tests.html
          kill $SERVER_PID
```

### Local Headless Testing

```bash
# Install playwright
pip install playwright
playwright install chromium

# Run headless
playwright test tests/gallery/gallery_tests.html
```

## Test Coverage Summary

| Category | Tests | Priority | Status |
|----------|-------|----------|--------|
| Modal Functionality | 15 | 🔴 Critical | ✅ |
| Event Delegation | 8 | 🔴 Critical | ✅ |
| Selection Persistence | 9 | 🟠 High | ✅ |
| Selection Visibility | 8 | 🟡 Medium | ✅ |
| Status Bar | 7 | 🟡 Medium | ✅ |
| Export Button | 10 | 🟠 High | ✅ |
| Performance | 7 | 🟠 High | ✅ |
| Integration | 12 | 🟠 High | ✅ |
| **Total** | **102** | - | **✅** |

## Recent Fixes Validated

### ✅ Modal Enlarge Button Fix (2024-10-18)
- **Issue**: `event.currentTarget` causing null errors
- **Fix**: Changed to `event.target.closest('.enlarge-button')`
- **Tests**: `Modal Functionality` suite validates the fix
- **Coverage**: 15 tests for modal behavior

### ✅ Event Delegation Performance (2024-10-17)
- **Issue**: 500+ individual event listeners causing memory bloat
- **Fix**: Centralized event delegation on document
- **Tests**: `Event Delegation` suite validates optimization
- **Coverage**: 8 tests for delegation patterns

### ✅ Selection Persistence (2024-10-17)
- **Feature**: localStorage-based selection saving/restoring
- **Tests**: `Selection Persistence` suite
- **Coverage**: 9 tests including error handling

## Troubleshooting

### Tests Not Loading
- **Check browser console** for CDN loading errors
- **Verify internet connection** (tests use CDN for Mocha/Chai)
- **Try local web server** instead of file:// protocol

### Tests Failing
- **Check browser compatibility** (modern browser required)
- **Verify template changes** haven't broken contracts
- **Review test output** for specific failure details

### Performance Tests Timing Out
- **Close other tabs** to reduce CPU load
- **Increase timeout** in mocha.setup(): `timeout: 10000`
- **Run tests individually** to isolate issues

## Next Steps

1. ✅ **Run tests locally** to validate current implementation
2. ⬜ **Integrate with CI/CD** for automated testing
3. ⬜ **Add visual regression tests** with Percy/Chromatic
4. ⬜ **Expand performance benchmarks** for larger galleries
5. ⬜ **Add accessibility tests** (aria, keyboard navigation)

## Resources

- **Mocha Documentation**: https://mochajs.org/
- **Chai Assertions**: https://www.chaijs.com/
- **Sinon Mocks**: https://sinonjs.org/
- **Testing Best Practices**: ../TESTING_BEST_PRACTICES.md

## Support

For questions or issues with the test suite:
1. Check test output in browser console
2. Review test helper implementations
3. Consult Mocha/Chai documentation
4. Create issue with failing test details

---

**Last Updated**: 2025-10-18
**Template Version**: gallery_template.html (latest)
**Test Framework**: Mocha 10.2.0 + Chai 4.3.10 + Sinon 17.0.1
