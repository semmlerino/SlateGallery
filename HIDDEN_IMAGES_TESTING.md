# Hidden Images Feature - Testing Checklist

## Prerequisites
- Generate a gallery with at least 10 images using SlateGallery
- Open the generated HTML file in a modern browser (Chrome, Firefox, or Safari)

## Manual Testing Checklist

### ✅ Basic Functionality

#### 1. Hide Image from Modal
- [ ] Open any image in modal view (click enlarge button)
- [ ] Verify hide button appears at top center with red background
- [ ] Click hide button
- [ ] Verify notification shows "Hidden: [filename]"
- [ ] Verify modal navigates to next/previous image
- [ ] Close modal (Escape key)
- [ ] Verify hidden image no longer appears in gallery
- [ ] Verify hidden count badge appears on "Show Hidden Images" button (top-right)

#### 2. Keyboard Shortcut ('H' Key)
- [ ] Open any image in modal view
- [ ] Press 'h' or 'H' key
- [ ] Verify image is hidden (notification shows, navigates to next)
- [ ] Verify behavior identical to clicking hide button

#### 3. View Hidden Images Mode
- [ ] Hide 2-3 images using steps above
- [ ] Click "Show Hidden Images" button (top-right)
- [ ] Verify status bar turns red with "HIDDEN IMAGES MODE" text
- [ ] Verify ONLY hidden images are shown in gallery
- [ ] Verify button text changes to "Back to Gallery"
- [ ] Verify "Unhide All" button appears next to toggle button

#### 4. Unhide Individual Image
- [ ] While in hidden mode, open an image in modal
- [ ] Verify hide button is green with text "Unhide Image"
- [ ] Click unhide button (or press 'H' key)
- [ ] Verify notification shows "Restored: [filename]"
- [ ] Verify image disappears from hidden gallery
- [ ] Close modal and return to normal gallery
- [ ] Verify restored image now appears in normal gallery

#### 5. Unhide All Images
- [ ] Hide 3-4 images
- [ ] Enter hidden mode ("Show Hidden Images" button)
- [ ] Click "Unhide All" button
- [ ] Verify confirmation dialog appears asking "Are you sure you want to unhide all X images?"
- [ ] Click OK
- [ ] Verify notification shows "All images restored (X images)"
- [ ] Verify gallery returns to normal mode
- [ ] Verify all previously hidden images now appear

### ✅ Persistence

#### 6. localStorage Persistence
- [ ] Hide 2-3 images
- [ ] Note which images are hidden (write down filenames)
- [ ] Refresh the page (F5 or Ctrl+R)
- [ ] Verify hidden images are still not visible in gallery
- [ ] Verify hidden count badge still shows correct count
- [ ] Enter hidden mode and verify correct images are hidden

#### 7. Cross-Session Persistence
- [ ] Hide 1-2 images
- [ ] Close the browser tab
- [ ] Reopen the same gallery HTML file
- [ ] Verify hidden images persist across browser sessions

### ✅ Edge Cases

#### 8. Hide Last Visible Image
- [ ] Filter gallery to show only 1 image (use filters)
- [ ] Open that image in modal
- [ ] Hide the image
- [ ] Verify modal closes automatically
- [ ] Verify notification shows "All images hidden. Returning to gallery."
- [ ] Verify gallery shows empty state (no images match filters)

#### 9. Unhide Last Hidden Image
- [ ] Hide 2-3 images, enter hidden mode
- [ ] Unhide all except one image (unhide individually, not "Unhide All")
- [ ] Unhide the last hidden image
- [ ] Verify notification shows "All images restored. Returning to gallery."
- [ ] Verify gallery automatically exits hidden mode
- [ ] Verify all images now visible in normal gallery

#### 10. Selection Clearing
- [ ] Select 3-4 images (check their checkboxes)
- [ ] Note selection count in status bar
- [ ] Hide ONE of the selected images
- [ ] Verify ONLY that image's selection is cleared
- [ ] Verify other selected images remain selected
- [ ] Verify selection count decreases by 1

#### 11. Modal Navigation After Hide
- [ ] Open image in modal (e.g., image #5 out of 10)
- [ ] Hide the current image
- [ ] Verify modal shows next image (#6) OR previous image (#4) if at end
- [ ] Verify navigation arrows still work
- [ ] Hide 2-3 more images while in modal
- [ ] Verify navigation skips hidden images correctly

#### 12. Hidden Images with Filters
- [ ] Hide 2-3 images with specific focal length (e.g., 50mm)
- [ ] Apply focal length filter to show only that focal length
- [ ] Verify hidden images do NOT appear even though they match filter
- [ ] Enter hidden mode
- [ ] Verify hidden images appear (even with filter active)
- [ ] Verify filter still applies to hidden images (orientation, date, etc.)

### ✅ Accessibility

#### 13. ARIA Labels
- [ ] Right-click "Show Hidden Images" button → Inspect element
- [ ] Verify `aria-pressed="false"` attribute present
- [ ] Enter hidden mode
- [ ] Verify `aria-pressed="true"` changes
- [ ] Open modal, inspect hide button
- [ ] Verify `aria-label` is descriptive ("Hide this image from gallery")

#### 14. Screen Reader Announcements
- [ ] Enable screen reader (NVDA on Windows, VoiceOver on Mac)
- [ ] Hide an image
- [ ] Verify announcement: "Image hidden: [filename]"
- [ ] Enter hidden mode
- [ ] Verify announcement: "Hidden images mode activated. Showing X hidden images."
- [ ] Unhide all images
- [ ] Verify announcement: "All X images restored to gallery"

#### 15. Keyboard Navigation
- [ ] Tab through page, verify "Show Hidden Images" button is focusable
- [ ] Tab to modal, open image, verify hide button is focusable
- [ ] Use only keyboard to hide image (Tab + Enter or 'H' key)
- [ ] Verify full workflow works without mouse

### ✅ Integration

#### 16. Export Button in Hidden Mode
- [ ] Hide 2-3 images
- [ ] Select some remaining images
- [ ] Click export button
- [ ] Verify export works correctly (clipboard has selected images)
- [ ] Enter hidden mode
- [ ] Verify export button is STILL VISIBLE (not hidden)
- [ ] Select some hidden images
- [ ] Export and verify it works in hidden mode too

#### 17. Status Bar Updates
- [ ] Note status bar text: "Showing X of Y images | Z selected"
- [ ] Hide 2 images
- [ ] Verify status bar updates: "Showing X-2 of Y images | Z selected"
- [ ] Enter hidden mode
- [ ] Verify status bar shows: "Showing 2 of Y images | Z selected | HIDDEN IMAGES MODE"
- [ ] Verify status bar background is red in hidden mode

#### 18. Filter Interaction
- [ ] Hide images from multiple slates/dates/focal lengths
- [ ] Apply various filters (orientation, focal length, date)
- [ ] Verify hidden images never appear regardless of filters
- [ ] Enter hidden mode
- [ ] Verify filters still work (can filter hidden images by orientation/focal/date)

### ✅ Performance

#### 19. Large Gallery Performance
- [ ] Generate gallery with 100+ images
- [ ] Hide 10-20 images
- [ ] Verify hiding is instant (no lag)
- [ ] Refresh page
- [ ] Verify page loads quickly (no localStorage read lag)
- [ ] Toggle hidden mode on/off rapidly
- [ ] Verify no performance degradation

#### 20. localStorage Errors
- [ ] Open browser console (F12)
- [ ] Manually fill localStorage until full (use large data)
- [ ] Try to hide an image
- [ ] Verify console shows error but app doesn't crash
- [ ] Verify notification shows (even if save failed)

### ✅ Browser Compatibility

#### 21. Cross-Browser Testing
- [ ] Test in Chrome (latest)
- [ ] Test in Firefox (latest)
- [ ] Test in Safari (latest)
- [ ] Test in Edge (latest)
- [ ] Verify all features work identically in each browser

## Automated Testing (Optional)

For developers who want to add automated tests, here are key test scenarios:

### Unit Tests (JavaScript)
```javascript
describe('Hidden Images System', () => {
  it('should hide image and add to hiddenImages object', () => {
    hideImage('/path/to/image.jpg');
    expect(isImageHidden('/path/to/image.jpg')).toBe(true);
  });

  it('should unhide image and remove from hiddenImages object', () => {
    hideImage('/path/to/image.jpg');
    unhideImage('/path/to/image.jpg');
    expect(isImageHidden('/path/to/image.jpg')).toBe(false);
  });

  it('should persist to localStorage', (done) => {
    hideImage('/path/to/image.jpg');
    setTimeout(() => {
      const stored = localStorage.getItem('gallery_selections_test_hidden');
      expect(JSON.parse(stored)['/path/to/image.jpg']).toBe(true);
      done();
    }, 400); // Wait for debounce
  });
});
```

### Integration Tests
```javascript
describe('Hidden Images Integration', () => {
  it('should filter hidden images in normal mode', () => {
    hideImage('/path/to/image.jpg');
    filterImages();
    const container = document.querySelector('[data-full-image="/path/to/image.jpg"]');
    expect(container.style.display).toBe('none');
  });

  it('should show only hidden images in hidden mode', () => {
    hideImage('/path/to/image.jpg');
    toggleHiddenMode();
    filterImages();
    const container = document.querySelector('[data-full-image="/path/to/image.jpg"]');
    expect(container.style.display).toBe('flex');
  });
});
```

## Success Criteria

✅ All 21 test scenarios pass
✅ No JavaScript errors in console
✅ No layout issues or CSS conflicts
✅ Screen reader announces all actions
✅ Keyboard navigation works completely
✅ Performance is smooth (no lag)
✅ Works in all major browsers

## Known Limitations

1. **localStorage quota**: Hiding 1000s of images may hit localStorage limits (5-10MB)
   - Workaround: Clear hidden images periodically
2. **Cross-device sync**: Hidden state doesn't sync across devices
   - Limitation: localStorage is device-specific
3. **Confirmation on close**: No warning if user closes tab with hidden images
   - Acceptable: Data is persisted, can be restored

## Reporting Issues

If you find any issues during testing:
1. Note the browser and version
2. Describe the exact steps to reproduce
3. Include console errors (F12 → Console tab)
4. Note expected vs actual behavior
5. Create an issue in the project repository
