# SlateGallery Design System Reference

Quick reference guide for maintaining and extending the modernized UI.

## Design Tokens

### Spacing Constants
```python
SPACING_XS = 4   # Tight spacing (e.g., icon padding)
SPACING_SM = 8   # Small spacing (e.g., between related items)
SPACING_MD = 16  # Medium spacing (e.g., between sections)
SPACING_LG = 24  # Large spacing (e.g., card padding)
SPACING_XL = 32  # Extra large spacing (e.g., major sections)
```

**Usage Example:**
```python
layout.setSpacing(SPACING_MD)
layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
```

### Color Constants

#### Primary Colors (Main Actions)
```python
COLOR_PRIMARY = "#2196F3"           # Material Blue
COLOR_PRIMARY_HOVER = "#1976D2"     # Darker blue
COLOR_PRIMARY_PRESSED = "#1565C0"   # Even darker
COLOR_PRIMARY_DISABLED = "#BBDEFB"  # Light blue
```

#### Secondary Colors (Less Important Actions)
```python
COLOR_SECONDARY = "#E3F2FD"         # Very light blue
COLOR_SECONDARY_HOVER = "#BBDEFB"   # Light blue
```

#### Tertiary Colors (Minimal Actions)
```python
COLOR_TERTIARY_BG = "transparent"
COLOR_TERTIARY_BORDER = "#2196F3"   # Blue border
COLOR_TERTIARY_HOVER = "#F5F5F5"    # Light gray
```

#### Surface & Background
```python
COLOR_SURFACE = "#FFFFFF"           # White (cards)
COLOR_BACKGROUND = "#F5F5F5"        # Light gray (window)
COLOR_BORDER = "#E0E0E0"           # Medium gray
```

#### Text Colors
```python
COLOR_TEXT_PRIMARY = "#212121"      # Almost black
COLOR_TEXT_SECONDARY = "#757575"    # Medium gray
COLOR_TEXT_DISABLED = "#9E9E9E"    # Light gray
```

#### Semantic Colors
```python
COLOR_SUCCESS = "#4CAF50"          # Green
COLOR_WARNING = "#FF9800"          # Orange
```

## Button Styling Guide

### When to Use Each Button Type

#### Primary Button
**Use for:** The single most important action on the screen
- ✅ Generate Gallery
- ❌ Don't use for multiple actions

**Code:**
```python
btn = QPushButton("Generate Gallery")
btn.setObjectName("primaryButton")
btn.setToolTip("Generate HTML gallery from selected collections")
```

**Visual:** Bold blue background, white text, most prominent

---

#### Secondary Button
**Use for:** Important preparatory actions
- ✅ Scan Directory
- ✅ Import Data
- ✅ Load File

**Code:**
```python
btn = QPushButton("Scan Directory")
btn.setObjectName("secondaryButton")
btn.setToolTip("Scan the selected directory for photo collections")
```

**Visual:** Light blue background, blue text, medium prominence

---

#### Tertiary Button
**Use for:** Utility actions, less critical operations
- ✅ Browse
- ✅ Manage...
- ✅ Select All / Deselect All
- ✅ Refresh
- ✅ Open Gallery

**Code:**
```python
btn = QPushButton("Browse")
btn.setObjectName("tertiaryButton")
btn.setToolTip("Browse for directory")
```

**Visual:** Transparent background, blue border, minimal prominence

## Card Widget Usage

### Basic Card
```python
card = CardWidget("Card Title")
card.content_layout.addWidget(some_widget)
```

### Card Without Title
```python
card = CardWidget()  # No title parameter
card.content_layout.addWidget(some_widget)
```

### Card with Complex Layout
```python
card = CardWidget("Options")

# Add a horizontal layout to the card
h_layout = QHBoxLayout()
h_layout.setSpacing(SPACING_SM)
h_layout.addWidget(label)
h_layout.addWidget(input_field)

card.content_layout.addLayout(h_layout)
```

### Card Properties
- **Automatic shadow:** 12px blur, 2px offset, subtle
- **Padding:** SPACING_LG (24px) on all sides
- **Spacing:** SPACING_MD (16px) between items
- **Border:** 1px solid COLOR_BORDER
- **Background:** COLOR_SURFACE (white)
- **Rounded corners:** 8px radius

## Layout Spacing Guidelines

### Card Spacing
```python
# Between cards in main layout
main_layout.setSpacing(SPACING_MD)  # 16px

# Card internal padding
# (automatic in CardWidget - 24px)

# Between items inside cards
card.content_layout.setSpacing(SPACING_MD)  # 16px
```

### Form Layouts
```python
# Between label and input
layout = QHBoxLayout()
layout.setSpacing(SPACING_SM)  # 8px

# Between form rows
form_layout.setSpacing(SPACING_MD)  # 16px
```

### Button Groups
```python
# Between related buttons
button_layout = QVBoxLayout()
button_layout.setSpacing(SPACING_SM)  # 8px

# Between button group and other content
parent_layout.setSpacing(SPACING_MD)  # 16px
```

## Typography Guidelines

### Labels
```python
# Regular label (automatic styling via QLabel in stylesheet)
label = QLabel("Photo Directory:")

# Instruction label (secondary text)
instruction = QLabel("Select one or more collections (Ctrl+Click for multiple):")
instruction.setObjectName("instructionLabel")

# Card title (automatic via CardWidget)
card = CardWidget("Card Title")
```

### Font Sizes
- **Card Title:** 16px, weight 600
- **Labels:** 13px, weight 500
- **Instruction Labels:** 12px, weight normal
- **Button Text:** 14px, weight 500
- **Progress Bar:** 12px, weight 500

## Common Patterns

### Input with Label
```python
layout = QHBoxLayout()
layout.setSpacing(SPACING_SM)

label = QLabel("Filter:")
layout.addWidget(label)

input_field = QLineEdit()
input_field.setPlaceholderText("Type to filter...")
layout.addWidget(input_field)

card.content_layout.addLayout(layout)
```

### Button Row
```python
button_layout = QHBoxLayout()
button_layout.setSpacing(SPACING_SM)

btn1 = QPushButton("Action 1")
btn1.setObjectName("tertiaryButton")
button_layout.addWidget(btn1)

btn2 = QPushButton("Action 2")
btn2.setObjectName("tertiaryButton")
button_layout.addWidget(btn2)

button_layout.addStretch()  # Push buttons to left

card.content_layout.addLayout(button_layout)
```

### Checkbox with Dependent Controls
```python
layout = QHBoxLayout()
layout.setSpacing(SPACING_SM)

checkbox = QCheckBox("Enable feature")
layout.addWidget(checkbox)

dependent_label = QLabel("Options:")
layout.addWidget(dependent_label)

dependent_combo = QComboBox()
dependent_combo.addItems(["Option 1", "Option 2"])
layout.addWidget(dependent_combo)

# Enable/disable dependent controls based on checkbox
dependent_combo.setEnabled(checkbox.isChecked())
checkbox.stateChanged.connect(
    lambda: dependent_combo.setEnabled(checkbox.isChecked())
)

layout.addStretch()
card.content_layout.addLayout(layout)
```

## Tooltip Best Practices

### Good Tooltips
✅ Explain what will happen
✅ Provide context for warnings
✅ Describe keyboard shortcuts

```python
btn.setToolTip("Scan the selected directory for photo collections")
btn.setToolTip("Warning: This will clear your current selections")
combo.setToolTip("Select or enter the path to your photo directory")
```

### Bad Tooltips
❌ Repeat the button text
❌ State the obvious
❌ Too wordy

```python
# Don't do this:
btn.setToolTip("Click this button to scan")  # Obvious
btn.setToolTip("Scan")  # Repeats button text
```

## Widget State Management

### Enabling/Disabling Buttons
```python
# Disable during operation
self.btn_generate.setEnabled(False)

# Re-enable after completion
self.btn_generate.setEnabled(True)
```

### Progress Bar Updates
```python
# Start operation
self.progress_bar.setValue(0)

# Update during operation
self.progress_bar.setValue(50)

# Complete operation
self.progress_bar.setValue(100)
```

### Status Updates
```python
# Clear, descriptive messages
self.update_status("Scanning directory...")
self.update_status("Found 45 collections")
self.update_status("Gallery generated successfully")
```

## Accessibility Checklist

When adding new UI elements:

- [ ] Button has clear text (not just an icon)
- [ ] Tooltip explains what will happen
- [ ] Keyboard tab order is logical
- [ ] Color contrast meets WCAG AA (4.5:1 for text)
- [ ] Interactive elements are at least 24px tall
- [ ] Focus states are visible
- [ ] Error messages are descriptive

## Modifying the Design System

### Changing Colors
1. Update constants at top of file (lines 51-82)
2. Colors will cascade through entire UI
3. No need to update individual stylesheets

### Changing Spacing
1. Update SPACING_* constants
2. Spacing will update throughout UI
3. Maintain 8px grid system (use multiples of 4 or 8)

### Adding New Button Types
1. Add objectName pattern (e.g., "warningButton")
2. Add stylesheet in setup_style() method
3. Follow existing pattern (normal, hover, pressed, disabled states)

### Creating New Card Types
1. Inherit from CardWidget or create new class
2. Keep consistent shadow and padding
3. Use design tokens for all values

## Testing Checklist

Before committing UI changes:

- [ ] All buttons have objectName set
- [ ] All tooltips are helpful and clear
- [ ] Spacing uses SPACING_* constants (no hardcoded values)
- [ ] Colors use COLOR_* constants (no hardcoded colors)
- [ ] Cards use CardWidget class
- [ ] No inline setStyleSheet() calls
- [ ] ruff check passes
- [ ] basedpyright shows no new errors
- [ ] Visual appearance is consistent
- [ ] All buttons respond to hover/press
- [ ] Tab order is logical

## Quick Reference

| Element | ObjectName | Background | Text Color | Border |
|---------|-----------|------------|------------|--------|
| Primary Button | primaryButton | COLOR_PRIMARY | white | none |
| Secondary Button | secondaryButton | COLOR_SECONDARY | COLOR_PRIMARY | none |
| Tertiary Button | tertiaryButton | transparent | COLOR_PRIMARY | 2px COLOR_PRIMARY |
| Card | card | COLOR_SURFACE | - | 1px COLOR_BORDER |
| Card Title | cardTitle | - | COLOR_PRIMARY | - |
| Instruction Label | instructionLabel | - | COLOR_TEXT_SECONDARY | - |

---

**Last Updated:** 2025-10-18
**Designer:** Claude Code (qt-ui-modernizer agent)
**Maintainer:** See CLAUDE.md for project guidelines
