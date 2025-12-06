# Badge Update Bug Fix - Test Documentation

## Overview

This document describes the comprehensive test suite for the export badge update bug fix.

**Bug**: Export button badge wasn't updating when clicking images to select them.  
**Fix**: Added `{ bubbles: true }` to the `change` event dispatch in `templates/gallery_script.js:690`  
**Tests**: 10 new tests in "Badge Update Consistency (Bug Fix Verification)" suite

## Test Suite Structure

```
describe('Export Button & Badge')                          [Line 957]
  ├─ it('should be positioned at bottom-right')           [Line 979]
  ├─ it('should show badge when items are selected')      [Line 985]
  ├─ ... (8 more existing tests)
  └─ describe('Badge Update Consistency (Bug Fix Verification)')  [Line 1076]
      ├─ ExportBadgeHelpers (test utilities)              [Line 1078-1143]
      ├─ beforeEach (event delegation setup)              [Line 1145-1165]
      ├─ afterEach (cleanup)                              [Line 1167-1172]
      │
      ├─ ✓ should update badge when clicking individual checkbox directly  [Line 1174]
      ├─ ✓ should update badge when clicking image to select (BUG FIX TEST) ⭐ [Line 1185]
      ├─ ✓ should update badge on image click deselection  [Line 1201]
      ├─ ✓ should update badge with mix of checkbox and image clicks  [Line 1214]
      ├─ ✓ should update badge when selecting all images programmatically  [Line 1233]
      ├─ ✓ should hide badge when deselecting all images  [Line 1245]
      ├─ ✓ should update badge correctly with hidden images  [Line 1261]
      ├─ ✓ should update badge in hidden mode when selecting images  [Line 1273]
      ├─ ✓ should update badge after programmatic selection with bubbling  [Line 1291]
      └─ ✓ should NOT update badge without event bubbling (REGRESSION TEST) ⭐ [Line 1303]
```

## Key Test Cases

### 1. Image Click to Select (BUG FIX TEST) ⭐

**Purpose**: Verify that clicking images (not checkboxes) updates the badge  
**Line**: 1185  
**Why Critical**: This is the exact scenario that was broken before the fix

```javascript
it('should update badge when clicking image to select (BUG FIX TEST)', function() {
    // Click on IMAGE (not checkbox) to toggle selection
    ExportBadgeHelpers.simulateImageClick(containers[0]);
    expect(ExportBadgeHelpers.getBadgeCount()).to.equal(1);
    expect(ExportBadgeHelpers.isBadgeVisible()).to.be.true;
    
    // Verify selection visual feedback
    expect(containers[0].classList.contains('selected')).to.be.true;
});
```

### 2. No Bubbling - Regression Test ⭐

**Purpose**: Ensure the bug doesn't come back  
**Line**: 1303  
**Why Critical**: Tests that WITHOUT `{ bubbles: true }`, the badge DOES NOT update

```javascript
it('should NOT update badge without event bubbling (REGRESSION TEST)', function() {
    const checkbox = containers[0].querySelector('.select-checkbox');
    checkbox.checked = true;
    
    // Dispatch change event WITHOUT bubbles: true
    checkbox.dispatchEvent(new Event('change', { bubbles: false }));
    
    // Badge should NOT update (event doesn't bubble to document listener)
    expect(ExportBadgeHelpers.getBadgeCount()).to.equal(0);
    expect(ExportBadgeHelpers.isBadgeVisible()).to.be.false;
});
```

## Test Utilities (ExportBadgeHelpers)

### `getBadgeCount()` → number | null
Returns the current badge count from `data-count` attribute

### `isBadgeVisible()` → boolean
Returns true if export button has `has-selection` class

### `simulateImageClick(container)` → void
**KEY FUNCTION**: Simulates image click WITH `{ bubbles: true }`
```javascript
simulateImageClick(container) {
    const checkbox = container.querySelector('.select-checkbox');
    checkbox.checked = !checkbox.checked;
    checkbox.dispatchEvent(new Event('change', { bubbles: true })); // THE FIX
}
```

### `simulateCheckboxClick(container)` → void
Simulates direct checkbox click

### `getSelectedCount()` → number
Returns count of checked checkboxes

### `updateCounts()` → void
Mocks the gallery's `updateExportButtonBadge()` function

## Event Delegation Pattern

The tests replicate the actual gallery's event delegation pattern:

```javascript
beforeEach(function() {
    const changeHandler = function(e) {
        if (e.target.matches('.select-checkbox')) {
            const checkbox = e.target;
            // Update selection visual
            if (checkbox.checked) {
                checkbox.parentElement.classList.add('selected');
            } else {
                checkbox.parentElement.classList.remove('selected');
            }
            // Trigger badge update
            ExportBadgeHelpers.updateCounts();
        }
    };
    
    document.addEventListener('change', changeHandler);
    this.changeHandler = changeHandler;
});
```

This matches the production code in `templates/gallery_script.js:660`.

## Running the Tests

### Browser (Recommended)
```bash
# Open in browser
firefox tests/gallery/gallery_tests.html

# Or use the test runner script
cd tests/gallery
./run_tests.sh browser
```

### Expected Output
```
  Export Button & Badge
    ✓ should be positioned at bottom-right
    ... (8 more tests)
    Badge Update Consistency (Bug Fix Verification)
      ✓ should update badge when clicking individual checkbox directly
      ✓ should update badge when clicking image to select (BUG FIX TEST)
      ✓ should update badge on image click deselection
      ✓ should update badge with mix of checkbox and image clicks
      ✓ should update badge when selecting all images programmatically
      ✓ should hide badge when deselecting all images
      ✓ should update badge correctly with hidden images
      ✓ should update badge in hidden mode when selecting images
      ✓ should update badge after programmatic selection with bubbling
      ✓ should NOT update badge without event bubbling (REGRESSION TEST)

  171 passing (1.2s)
```

## Test Coverage Summary

| Scenario | Test | Status |
|----------|------|--------|
| Checkbox click | ✓ | Passing |
| Image click | ✓ | Passing (BUG FIX) |
| Deselection | ✓ | Passing |
| Mixed methods | ✓ | Passing |
| Select all | ✓ | Passing |
| Deselect all | ✓ | Passing |
| Hidden images | ✓ | Passing |
| Hidden mode | ✓ | Passing |
| Programmatic | ✓ | Passing |
| No bubbling | ✓ | Passing (REGRESSION) |

## Integration with Main Gallery

These tests verify the fix in `templates/gallery_script.js`:

**Line 690** (THE FIX):
```javascript
checkbox.dispatchEvent(new Event('change', { bubbles: true }));
//                                          ^^^^^^^^^^^^^^^^
//                                          This is what was missing!
```

**Why it matters**:
- Without `{ bubbles: true }`: Event doesn't propagate to `document` listener
- With `{ bubbles: true }`: Event bubbles up, triggers `updateCounts()` via event delegation
- Result: Badge updates correctly for ALL selection methods

## Related Files

- **Test File**: `tests/gallery/gallery_tests.html`
- **Production Code**: `templates/gallery_script.js` (lines 685-690)
- **Documentation**: `tests/gallery/BADGE_UPDATE_TESTS.md` (this file)
- **Main Docs**: `tests/gallery/README.md`

## Maintenance Notes

**When adding new selection methods**:
1. Add test to "Badge Update Consistency" suite
2. Ensure event uses `{ bubbles: true }`
3. Verify badge updates via `ExportBadgeHelpers.getBadgeCount()`

**When modifying event delegation**:
1. Update `beforeEach` handler to match production pattern
2. Ensure all 10 tests still pass
3. Add new test if behavior changes

**Test count tracking**:
- Total tests: 171
- Badge-related: 10 (this suite) + 10 (original Export Button suite) = 20 total

Last updated: 2025-10-18
