# Quick Test Guide for SlateGallery

A concise reference for running and understanding the JavaScript test suite.

## 🚀 Quick Start (30 seconds)

```bash
# Open test file in browser
firefox tests/gallery/gallery_tests.html
```

That's it! Tests will run automatically and show results in your browser.

## 📊 What Gets Tested

### Critical Features ✅
- **Modal functionality** - Opens/closes, navigation, keyboard controls
- **Event delegation** - Performance optimization with 500+ images
- **Selection persistence** - localStorage save/restore across sessions

### High Priority ⚠️
- **Export button** - Clipboard API, focal length data format
- **Status bar** - Real-time count updates
- **Performance** - 500 image scale testing

### Medium Priority 📋
- **Visual feedback** - Checkmarks, borders, shadows
- **Integration** - End-to-end workflows

## 🎯 Test Results

### Success Indicators
- ✅ **Green checkmarks** - Test passed
- 🟢 **102 passing** - All tests successful
- ⏱️ **<5s total time** - Performance is good

### Failure Indicators
- ❌ **Red X marks** - Test failed
- 📝 **Error message** - Details what broke
- 🔍 **Stack trace** - Where the failure occurred

## 🔧 Common Test Scenarios

### Testing Modal Opening
```javascript
// What the test does:
1. Click enlarge button
2. Verify modal has 'show' class
3. Check image src is correct
4. Verify metadata displayed
```

### Testing Selection Persistence
```javascript
// What the test does:
1. Select 3 images
2. Save to localStorage
3. Clear DOM
4. Restore from localStorage
5. Verify 3 images still selected
```

### Testing Performance
```javascript
// What the test does:
1. Create 500 mock images
2. Measure time to render
3. Verify < 1 second
4. Check memory usage stable
```

## 🐛 Debugging Failed Tests

### Test Fails: "Modal not opening"
**Likely cause**: Event delegation not working
**Check**:
- `document.addEventListener('click', ...)` present?
- `event.target.closest('.enlarge-button')` correct?

### Test Fails: "Selection not persisting"
**Likely cause**: localStorage disabled or quota exceeded
**Check**:
- Browser allows localStorage?
- `getGalleryIdentifier()` returning unique value?

### Test Fails: "Performance timeout"
**Likely cause**: Computer too slow or tests hanging
**Fix**:
```javascript
// Increase timeout in gallery_tests.html
mocha.setup({
    ui: 'bdd',
    timeout: 10000  // Changed from 5000
});
```

## 📝 Test File Structure

```
tests/gallery/
├── gallery_tests.html    # Main test suite (open this)
├── README.md             # Comprehensive documentation
└── TEST_GUIDE.md         # This quick reference
```

## 🎨 Visual Test Runner

When you open `gallery_tests.html`, you'll see:

```
SlateGallery JavaScript Tests
─────────────────────────────

✓ Gallery Modal Functionality (15)
  ✓ Modal Opening (5)
    ✓ should open modal when enlarge button is clicked
    ✓ should display correct image in modal
    ✓ should show image metadata in modal caption
    ...
  ✓ Modal Navigation (5)
  ✓ Modal Closing (5)

✓ Event Delegation System (8)
✓ Selection Persistence (localStorage) (9)
✓ Selection Visibility & Visual Feedback (8)
✓ Status Bar Display (7)
✓ Export Button & Badge (10)
✓ Performance Optimization (7)
✓ Integration & End-to-End Scenarios (12)

102 passing (1.2s)
```

## 🔍 Test Helper Cheatsheet

### Create Mock Gallery
```javascript
const containers = TestHelpers.createMockGallery(10);
// Creates 10 mock image containers
```

### Simulate User Actions
```javascript
TestHelpers.simulateClick(button);
TestHelpers.simulateKeyPress('Escape');
TestHelpers.simulateCheckboxChange(checkbox, true);
```

### Mock Browser APIs
```javascript
const mockStorage = TestHelpers.mockLocalStorage();
const mockClipboard = TestHelpers.mockClipboard();
```

## ⚡ Advanced Usage

### Run Specific Test Suite
1. Open `gallery_tests.html`
2. Open browser DevTools (F12)
3. In console:
```javascript
// Run only modal tests
mocha.grep('Modal Functionality').run();
```

### Run Single Test
```javascript
// Run specific test
mocha.grep('should open modal when enlarge button is clicked').run();
```

### Debug Specific Test
1. Find test in `gallery_tests.html`
2. Change `it(` to `it.only(`
3. Refresh browser
4. Only that test will run

## 📊 Coverage Map

| Feature | Test Count | What's Tested |
|---------|------------|---------------|
| Modal | 15 | Open, close, navigate, keyboard |
| Events | 8 | Delegation, performance |
| Persistence | 9 | Save, restore, errors |
| Visibility | 8 | Visual feedback |
| Status Bar | 7 | Count updates |
| Export | 10 | Clipboard, data format |
| Performance | 7 | 500 images, memory |
| Integration | 12 | End-to-end flows |

## 🎓 Understanding Test Output

### What Each Section Tests

**Gallery Modal Functionality**
- Can you click enlarge and see the image bigger?
- Do arrow keys switch images?
- Does ESC close the modal?

**Event Delegation System**
- Are we using one listener instead of 500?
- Does performance improve with many images?

**Selection Persistence**
- Do selections survive page refresh?
- Is data saved correctly to localStorage?

**Selection Visibility**
- Do selected items show checkmarks?
- Are borders and shadows applied?

**Status Bar Display**
- Does it show "X of Y images | Z selected"?
- Does it update in real-time?

**Export Button & Badge**
- Does badge show selection count?
- Does export copy data to clipboard?

**Performance Optimization**
- Can we handle 500 images smoothly?
- Are there memory leaks?

**Integration Scenarios**
- Do complete workflows work end-to-end?
- Are edge cases handled?

## 🚨 Red Flags

If you see these, investigate immediately:

❌ **"ReferenceError: X is not defined"**
- Template JavaScript may have changed
- Variable name mismatch

❌ **"Timeout of 5000ms exceeded"**
- Test is hanging
- Check for infinite loops
- Increase timeout if computer is slow

❌ **"Cannot read property of null"**
- DOM element not found
- Check element creation in test

❌ **"QuotaExceededError"**
- localStorage is full
- Clear browser storage

## 💡 Pro Tips

1. **Run tests in multiple browsers**
   - Firefox, Chrome, Safari behave differently
   - localStorage implementation varies

2. **Use browser DevTools**
   - Console shows detailed errors
   - Network tab shows CDN loading
   - Elements tab shows DOM state

3. **Read the test names**
   - They describe exactly what's being tested
   - Use them as documentation

4. **Check test fixtures**
   - Tests use `#test-fixtures` div (hidden)
   - Inspect to see mock DOM

5. **Mock everything external**
   - localStorage, clipboard, IntersectionObserver
   - Tests should be self-contained

## 🎯 Next Steps After Tests Pass

1. ✅ Tests pass locally
2. ⬜ Set up CI/CD integration
3. ⬜ Add to pull request checklist
4. ⬜ Document any new features with tests
5. ⬜ Review coverage gaps

## 📚 Full Documentation

For comprehensive documentation, see:
- **README.md** - Full test suite documentation
- **TESTING_BEST_PRACTICES.md** - Python testing guide (in parent `tests/` dir)
- **QT_TESTING_BEST_PRACTICES.md** - Qt testing patterns

## 🆘 Getting Help

**Test fails and you don't know why?**
1. Read the error message carefully
2. Find the test in `gallery_tests.html`
3. Read the test code - it's self-documenting
4. Check browser console for details
5. Try running just that one test with `.only`

**Test suite won't load?**
1. Check internet connection (needs CDN access)
2. Try different browser
3. Check browser console for errors
4. Use local web server instead of file://

**Performance tests are slow?**
1. Close other tabs/programs
2. Increase timeout in mocha.setup()
3. Run fewer images in performance tests
4. Skip performance tests if needed

---

**Quick Links**
- 📖 [Full README](README.md)
- 🧪 [Run Tests](gallery_tests.html)
- 🎨 [Gallery Template](../../templates/gallery_template.html)

**Last Updated**: 2025-10-18
