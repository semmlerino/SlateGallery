# SlateGallery JavaScript Tests - Index

Quick navigation for the gallery template test suite.

## 🚀 Quick Actions

### Run Tests Now
```bash
# Fastest way - open in browser
firefox tests/gallery/gallery_tests.html
```

### Read Documentation
- **Just want to run tests?** → [TEST_GUIDE.md](TEST_GUIDE.md) (2 min read)
- **Want full details?** → [README.md](README.md) (10 min read)
- **Want executive summary?** → [SUMMARY.md](SUMMARY.md) (5 min read)

## 📁 Files in This Directory

### Test Files
- **`gallery_tests.html`** (56 KB)
  - Main test suite with 75 tests
  - Open directly in browser
  - Self-contained, no dependencies

- **`run_tests.sh`** (executable)
  - Shell script to run tests
  - Options: browser, server, headless
  - Usage: `./run_tests.sh browser`

### Documentation
- **`TEST_GUIDE.md`** (8 KB) ⭐ **Start here!**
  - Quick reference guide
  - How to run tests
  - How to debug failures
  - 5-minute read

- **`README.md`** (12 KB)
  - Comprehensive documentation
  - Test suite architecture
  - Helper functions reference
  - CI/CD integration guide
  - 10-minute read

- **`SUMMARY.md`** (10 KB)
  - Executive summary
  - Test coverage breakdown
  - Recent fixes validated
  - Metrics and statistics
  - 5-minute read

- **`INDEX.md`** (this file)
  - Navigation hub
  - Quick links
  - File descriptions

## 🎯 What Gets Tested (75 Tests)

### Critical Features (23 tests)
1. **Modal Functionality** (15 tests) - Open, navigate, close
2. **Event Delegation** (8 tests) - Performance optimization

### High Priority (27 tests)
3. **Selection Persistence** (9 tests) - localStorage save/restore
4. **Export Button** (10 tests) - Clipboard API, data format
5. **Performance** (7 tests) - 500 image scale testing
6. **Integration** (12 tests) - End-to-end workflows

### Medium Priority (15 tests)
7. **Selection Visibility** (8 tests) - Checkmarks, borders, shadows
8. **Status Bar** (7 tests) - Real-time count display

## 🔍 Find What You Need

### I want to...

**Run the tests**
→ Open `gallery_tests.html` in browser
→ Or run `./run_tests.sh browser`

**Understand the tests**
→ Read [TEST_GUIDE.md](TEST_GUIDE.md) first
→ Then [README.md](README.md) for details

**Debug a failing test**
→ Open `gallery_tests.html` in browser
→ Check browser console (F12)
→ Read test name and error message
→ Find test code in `gallery_tests.html`

**Add new tests**
→ Read [README.md § Extending the Test Suite](README.md#extending-the-test-suite)
→ Copy existing test pattern
→ Use TestHelpers utilities

**Integrate with CI/CD**
→ Read [README.md § CI/CD Integration](README.md#cicd-integration)
→ Use `./run_tests.sh headless`

**See recent changes**
→ Read [SUMMARY.md § Recent Fixes](SUMMARY.md#recent-fixes-validated)

**Understand architecture**
→ Read [SUMMARY.md § Architecture Decisions](SUMMARY.md#architecture-decisions)

**Get metrics/stats**
→ Read [SUMMARY.md § Key Metrics](SUMMARY.md#key-metrics)

**Troubleshoot issues**
→ Read [TEST_GUIDE.md § Debugging](TEST_GUIDE.md#-debugging-failed-tests)
→ Or [README.md § Troubleshooting](README.md#troubleshooting)

## 📊 Test Coverage Summary

| Category | Tests | Priority | What It Tests |
|----------|-------|----------|---------------|
| Modal | 15 | 🔴 Critical | Open, navigate, close, keyboard |
| Events | 8 | 🔴 Critical | Delegation, performance |
| Persistence | 9 | 🟠 High | Save, restore, errors |
| Export | 10 | 🟠 High | Clipboard, data format |
| Performance | 7 | 🟠 High | 500 images, memory |
| Integration | 12 | 🟠 High | End-to-end flows |
| Visibility | 8 | 🟡 Medium | Visual feedback |
| Status Bar | 7 | 🟡 Medium | Count display |
| **Total** | **75** | - | **All features** |

## 🛠️ Tech Stack

- **Test Framework**: Mocha 10.2.0 (BDD style)
- **Assertions**: Chai 4.3.10 (expect syntax)
- **Mocking**: Sinon 17.0.1 (stubs, spies, mocks)
- **Delivery**: HTML file (CDN-based, zero install)
- **Execution**: Browser (any modern browser)

## 📚 Related Documentation

### In This Directory
- [TEST_GUIDE.md](TEST_GUIDE.md) - Quick reference
- [README.md](README.md) - Full documentation
- [SUMMARY.md](SUMMARY.md) - Executive summary

### In Parent `tests/` Directory
- [../TESTING_BEST_PRACTICES.md](../TESTING_BEST_PRACTICES.md) - Python testing guide
- [../QT_TESTING_BEST_PRACTICES.md](../QT_TESTING_BEST_PRACTICES.md) - Qt testing patterns
- [../README_TESTING.md](../README_TESTING.md) - Quick start for Python tests

### Project Documentation
- [../../CLAUDE.md](../../CLAUDE.md) - Project context for AI assistants
- [../../README.md](../../README.md) - Main project README

## 🎓 Learning Path

### Beginner
1. Read [TEST_GUIDE.md](TEST_GUIDE.md) (5 min)
2. Run `./run_tests.sh browser` (1 min)
3. Watch tests run in browser
4. Read test names to understand what's tested

### Intermediate
1. Open `gallery_tests.html` in editor
2. Find a test, read its code
3. Run that single test with `.only`
4. Modify test, see it fail
5. Fix test, see it pass

### Advanced
1. Read [README.md](README.md) fully
2. Study TestHelpers implementation
3. Add a new test category
4. Integrate with CI/CD
5. Add custom test helpers

## 💡 Pro Tips

1. **Always run tests in browser first**
   - Visual feedback is better
   - Console shows detailed errors
   - Can debug with DevTools

2. **Read test names as documentation**
   - They describe exact behavior
   - Use them to understand features

3. **Use `.only` to focus**
   - Change `it('test', ...)` to `it.only('test', ...)`
   - Only that test will run
   - Great for debugging

4. **Check browser console**
   - F12 opens DevTools
   - Console shows errors
   - Network tab shows CDN loading

5. **Mock everything external**
   - Tests should be self-contained
   - Don't depend on real browser APIs
   - Use TestHelpers.mock* functions

## 🆘 Quick Help

### Problem: Tests won't load
**Solution**: Check internet (CDN required), try different browser

### Problem: Tests fail
**Solution**: Read error message, check browser console, try `.only`

### Problem: Tests timeout
**Solution**: Close other programs, increase timeout in mocha.setup()

### Problem: Don't understand a test
**Solution**: Read test code, it's self-documenting with descriptive names

### Problem: Want to add a test
**Solution**: Copy existing test pattern, modify for your case

## 🔗 Quick Links

- 🧪 [Run Tests](gallery_tests.html)
- 📖 [Quick Guide](TEST_GUIDE.md)
- 📚 [Full Docs](README.md)
- 📊 [Summary](SUMMARY.md)
- 🎨 [Gallery Template](../../templates/gallery_template.html)
- 🐛 [Main Tests](../)

---

**Last Updated**: 2025-10-18
**Total Tests**: 75
**Estimated Read Time**: 2 minutes
**Estimated Run Time**: 1-2 seconds
