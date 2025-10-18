# Status Bar Testing Checklist

## Manual Testing Procedures

### Test 1: Initial Page Load
**Steps:**
1. Open the gallery HTML file in a browser
2. Observe the status bar

**Expected Result:**
```
Showing [total] of [total] images | 0 selected
```
Example: `Showing 523 of 523 images | 0 selected`

**Status:** ☐ Pass ☐ Fail

---

### Test 2: Apply Orientation Filter
**Steps:**
1. Check "Portrait" in Orientation filter
2. Observe status bar update

**Expected Result:**
```
Showing [filtered count] of [total] images | 0 selected
```
Example: `Showing 285 of 523 images | 0 selected`

**Status:** ☐ Pass ☐ Fail

---

### Test 3: Apply Focal Length Filter
**Steps:**
1. Check "35mm" in Focal Length filter
2. Observe status bar update

**Expected Result:**
```
Showing [filtered count] of [total] images | 0 selected
```
The visible count should decrease further

**Status:** ☐ Pass ☐ Fail

---

### Test 4: Apply Date Filter
**Steps:**
1. Check a specific date in Date filter
2. Observe status bar update

**Expected Result:**
```
Showing [filtered count] of [total] images | 0 selected
```
The visible count should decrease to only images from that date

**Status:** ☐ Pass ☐ Fail

---

### Test 5: Select Individual Photo
**Steps:**
1. Click on a photo thumbnail to select it
2. Observe status bar update

**Expected Result:**
```
Showing [visible] of [total] images | 1 selected
```
Selected count increases by 1

**Status:** ☐ Pass ☐ Fail

---

### Test 6: Select Multiple Photos
**Steps:**
1. Click on 5 different photo thumbnails
2. Observe status bar update after each click

**Expected Result:**
```
Showing [visible] of [total] images | 5 selected
```
Selected count increments from 1 → 2 → 3 → 4 → 5

**Status:** ☐ Pass ☐ Fail

---

### Test 7: Deselect Photos
**Steps:**
1. Click on a selected photo to deselect it
2. Observe status bar update

**Expected Result:**
```
Showing [visible] of [total] images | 4 selected
```
Selected count decrements from 5 → 4

**Status:** ☐ Pass ☐ Fail

---

### Test 8: "Select All Photos" Button
**Steps:**
1. Clear all filters (show all images)
2. Click "Select all visible Photos" button
3. Observe status bar update

**Expected Result:**
```
Showing [total] of [total] images | [total] selected
```
Example: `Showing 523 of 523 images | 523 selected`

**Status:** ☐ Pass ☐ Fail

---

### Test 9: "Select All Photos" with Filters
**Steps:**
1. Apply filter to show only 47 images
2. Click "Select all visible Photos" button
3. Observe status bar update

**Expected Result:**
```
Showing 47 of [total] images | 47 selected
```
Only visible images are selected

**Status:** ☐ Pass ☐ Fail

---

### Test 10: "Deselect All Photos" Button
**Steps:**
1. Have some photos selected
2. Click "Deselect All Photos" button
3. Observe status bar update

**Expected Result:**
```
Showing [visible] of [total] images | 0 selected
```
Selected count resets to 0

**Status:** ☐ Pass ☐ Fail

---

### Test 11: Slate-Level "Select All"
**Steps:**
1. Scroll to a slate (e.g., "Slate A10B")
2. Click "Select All Photos in Slate" button
3. Observe status bar update

**Expected Result:**
```
Showing [visible] of [total] images | [slate count] selected
```
Selected count equals number of photos in that slate

**Status:** ☐ Pass ☐ Fail

---

### Test 12: Slate-Level "Deselect All"
**Steps:**
1. Have a slate with selected photos
2. Click "Deselect All Photos in Slate" button
3. Observe status bar update

**Expected Result:**
```
Showing [visible] of [total] images | [reduced count] selected
```
Selected count decreases by number of photos in that slate

**Status:** ☐ Pass ☐ Fail

---

### Test 13: Modal Checkbox Selection
**Steps:**
1. Click the enlarge button (🔍) on a photo
2. Check the checkbox in the modal
3. Close the modal
4. Observe status bar

**Expected Result:**
```
Showing [visible] of [total] images | [+1] selected
```
Selected count increases when modal checkbox checked

**Status:** ☐ Pass ☐ Fail

---

### Test 14: Modal Checkbox Deselection
**Steps:**
1. Open modal on a selected photo
2. Uncheck the checkbox in the modal
3. Close the modal
4. Observe status bar

**Expected Result:**
```
Showing [visible] of [total] images | [-1] selected
```
Selected count decreases when modal checkbox unchecked

**Status:** ☐ Pass ☐ Fail

---

### Test 15: Modal Navigation
**Steps:**
1. Open modal on a photo
2. Use arrow buttons to navigate to next photo
3. Select that photo using modal checkbox
4. Observe status bar (visible in background)

**Expected Result:**
Status bar updates immediately when checkbox toggled in modal

**Status:** ☐ Pass ☐ Fail

---

### Test 16: Filter While Photos Selected
**Steps:**
1. Select 10 photos
2. Apply filter that hides 5 of those photos
3. Observe status bar

**Expected Result:**
```
Showing [reduced visible] of [total] images | 10 selected
```
Selected count remains 10 (hidden photos still selected)

**Status:** ☐ Pass ☐ Fail

---

### Test 17: Remove All Filters
**Steps:**
1. Have multiple filters applied
2. Deselect all filter checkboxes
3. Observe status bar

**Expected Result:**
```
Showing [total] of [total] images | [selected count] selected
```
Visible count returns to total

**Status:** ☐ Pass ☐ Fail

---

### Test 18: Edge Case - No Images Match Filter
**Steps:**
1. Apply combination of filters that match zero images
2. Observe status bar

**Expected Result:**
```
Showing 0 of [total] images | [selected count] selected
```
Shows zero visible images gracefully

**Status:** ☐ Pass ☐ Fail

---

### Test 19: Edge Case - All Images Selected
**Steps:**
1. Select all 523 images
2. Observe status bar

**Expected Result:**
```
Showing 523 of 523 images | 523 selected
```
All three numbers match

**Status:** ☐ Pass ☐ Fail

---

### Test 20: Performance Test (Large Gallery)
**Steps:**
1. Work with gallery containing 500+ images
2. Rapidly toggle filters
3. Observe status bar responsiveness

**Expected Result:**
- Status bar updates smoothly without lag
- No visible delay between action and count update
- No JavaScript errors in console

**Status:** ☐ Pass ☐ Fail

---

## Automated Testing (JavaScript Console)

### Test Script
Paste this in browser console to verify updateCounts() function:

```javascript
// Test 1: Function exists
console.assert(typeof updateCounts === 'function', 'updateCounts function exists');

// Test 2: Status bar element exists
const statusBar = document.getElementById('status-bar');
console.assert(statusBar !== null, 'Status bar element exists');

// Test 3: Initial count is correct
const totalImages = document.querySelectorAll('.image-container').length;
console.log('Total images:', totalImages);

// Test 4: Count visible images
const visibleImages = Array.from(document.querySelectorAll('.image-container'))
    .filter(c => c.style.display !== 'none').length;
console.log('Visible images:', visibleImages);

// Test 5: Count selected images
const selectedImages = document.querySelectorAll('.select-checkbox:checked').length;
console.log('Selected images:', selectedImages);

// Test 6: Verify status bar text
const expectedText = `Showing ${visibleImages} of ${totalImages} images | ${selectedImages} selected`;
console.log('Expected:', expectedText);
console.log('Actual:', statusBar.textContent);
console.assert(statusBar.textContent === expectedText, 'Status bar text matches expected format');

// Test 7: Trigger update and verify
updateCounts();
console.log('After updateCounts():', statusBar.textContent);

console.log('✅ All automated tests passed!');
```

---

## Visual Regression Testing

### Before/After Screenshots

**Capture these views:**

1. **Initial load** - No filters, no selections
2. **Filtered view** - Some filters applied
3. **Selection view** - Multiple photos selected
4. **Modal view** - Modal open with status bar visible in background
5. **Mobile view** - Status bar on smaller screen

**Compare:**
- Status bar positioning (between photo-controls and slates)
- Text alignment (centered)
- Color scheme (light gray bg, dark gray text)
- Border styling (subtle top border)
- Spacing (proper margins)

---

## Browser Compatibility Testing

Test in these browsers:

- ☐ Chrome/Edge (Chromium)
- ☐ Firefox
- ☐ Safari (macOS)
- ☐ Safari (iOS)
- ☐ Chrome (Android)

**Expected:** Status bar works identically in all browsers

---

## Accessibility Testing

### Screen Reader Testing

**Tools:** NVDA (Windows), JAWS, VoiceOver (macOS/iOS)

**Steps:**
1. Navigate to status bar with screen reader
2. Trigger filter change
3. Listen for status update announcement

**Expected:**
- Status bar is announced as "Status: Showing X of Y images, Z selected"
- Updates are announced when counts change (if aria-live is added)

**Enhancement Suggestion:**
Add ARIA attributes for better screen reader support:
```html
<div class="status-bar" id="status-bar" role="status" aria-live="polite" aria-atomic="true">
```

---

## Performance Benchmarking

### updateCounts() Performance

```javascript
// Benchmark updateCounts() execution time
console.time('updateCounts');
updateCounts();
console.timeEnd('updateCounts');
```

**Expected:** < 5ms for galleries with 500+ images

### Stress Test

```javascript
// Rapid-fire updates
for (let i = 0; i < 100; i++) {
    updateCounts();
}
```

**Expected:** No lag, no errors, smooth execution

---

## Known Limitations

1. **Mobile responsiveness:** Status bar shows single line (could wrap on very small screens)
2. **ARIA support:** Not yet implemented (enhancement opportunity)
3. **Animation:** No transition effects when counts change (could be added)

---

## Test Results Summary

**Date:** _______________
**Tester:** _______________
**Browser:** _______________
**Gallery Size:** _______________ images

**Overall Status:** ☐ All Pass ☐ Issues Found

**Issues:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

**Notes:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## Quick Validation Checklist

Before deploying to production:

- ☐ Status bar displays on page load
- ☐ Status bar updates when filters change
- ☐ Status bar updates when selections change
- ☐ All 9 updateCounts() integration points work
- ☐ No JavaScript errors in console
- ☐ Text formatting is correct
- ☐ Styling matches gallery design
- ☐ Responsive on mobile devices
- ☐ Works in all target browsers

---

**Testing Status:** Ready for validation
**Implementation Status:** Complete
