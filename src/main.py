#!/usr/bin/env python3

"""
Main entry point for SlateGallery - uses new modular structure
while maintaining identical functionality to the original.
"""

# System imports
import os
import sys
import webbrowser
from typing import Optional, cast

from typing_extensions import override

# Add src to path for imports
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

# Qt imports
from PySide6 import QtWidgets
from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAbstractTextDocumentLayout, QColor, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from core.cache_manager import ImprovedCacheManager
from core.config_manager import GalleryConfig, load_config, save_config

# Import from our new modular structure
from utils.logging_config import log_function, logger
from utils.threading import GenerateGalleryThread, ScanThread


class HtmlItemDelegate(QStyledItemDelegate):
    """Custom delegate to render HTML/rich text in list items.

    Note: Type ignores are needed due to incomplete PySide6 type stubs for QStyleOptionViewItem.
    """

    @override
    def paint(  # pyright: ignore[reportUnknownMemberType]
        self,
        painter: object,
        option: QStyleOptionViewItem,
        index: object,
    ) -> None:
        from typing import Any

        from PySide6.QtCore import QModelIndex
        from PySide6.QtGui import QPainter

        if not isinstance(painter, QPainter) or not isinstance(index, QModelIndex):
            return

        # Initialize style option - use Any to work around incomplete PySide6 stubs
        # for QStyleOptionViewItem properties (widget, text, rect are not typed)
        opt: Any = QStyleOptionViewItem(option)  # pyright: ignore[reportExplicitAny]
        self.initStyleOption(opt, index)

        # Get the style
        style: Optional[QStyle] = opt.widget.style() if opt.widget else QApplication.style()

        # Create text document for HTML rendering
        doc = QTextDocument()
        doc.setHtml(opt.text)
        doc.setTextWidth(opt.rect.width())

        # Clear text so it won't be drawn by default
        opt.text = ""

        # Draw the item background and selection
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        # Calculate text rect
        text_rect: QRect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget
        ) if style else opt.rect

        # Draw the HTML content
        painter.save()
        painter.translate(text_rect.topLeft())
        painter.setClipRect(QRect(0, 0, text_rect.width(), text_rect.height()))
        ctx = QAbstractTextDocumentLayout.PaintContext()
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    @override
    def sizeHint(self, option: QStyleOptionViewItem, index: object) -> QSize:  # pyright: ignore[reportUnknownMemberType]
        from typing import Any

        from PySide6.QtCore import QModelIndex

        if not isinstance(index, QModelIndex):
            return QSize()

        # Use Any to work around incomplete PySide6 stubs for QStyleOptionViewItem
        opt: Any = QStyleOptionViewItem(option)  # pyright: ignore[reportExplicitAny]
        self.initStyleOption(opt, index)

        doc = QTextDocument()
        doc.setHtml(opt.text)
        doc.setTextWidth(opt.rect.width() if opt.rect.width() > 0 else 200)

        # Add vertical padding for better spacing
        height = int(doc.size().height()) + 12
        return QSize(int(doc.idealWidth()), height)


# ----------------------------- Design Tokens -----------------------------

# Spacing (reduced for tighter layout)
SPACING_XS = 2
SPACING_SM = 4
SPACING_MD = 8
SPACING_LG = 12
SPACING_XL = 16

# Color Palette (softer, closer to original)
COLOR_PRIMARY = "#A5D6A7"           # Light green - primary actions (Generate)
COLOR_PRIMARY_HOVER = "#81C784"
COLOR_PRIMARY_PRESSED = "#66BB6A"
COLOR_PRIMARY_TEXT = "#1B5E20"

COLOR_SECONDARY = "#90CAF9"         # Light blue - secondary actions (Scan)
COLOR_SECONDARY_HOVER = "#64B5F6"
COLOR_SECONDARY_TEXT = "#1A237E"

COLOR_TERTIARY_BG = "transparent"   # Tertiary buttons
COLOR_TERTIARY_BORDER = "#BDBDBD"
COLOR_TERTIARY_HOVER = "#F5F5F5"
COLOR_TERTIARY_TEXT = "#424242"

COLOR_SURFACE = "#FFFFFF"           # Card backgrounds
COLOR_BACKGROUND = "#FAFAFA"        # Main background (lighter)
COLOR_BORDER = "#E0E0E0"

COLOR_TEXT_PRIMARY = "#37474F"
COLOR_TEXT_SECONDARY = "#78909C"
COLOR_TEXT_DISABLED = "#9E9E9E"

COLOR_SUCCESS = "#A5D6A7"           # Light green
COLOR_WARNING = "#FFB74D"           # Light orange

COLOR_ACCENT = "#FFD54F"            # Yellow - accent actions (Open Gallery)
COLOR_ACCENT_HOVER = "#FFB74D"
COLOR_ACCENT_TEXT = "#BF360C"

# ----------------------------- Custom File Dialog -----------------------------


class CustomFileDialog(QFileDialog):
    def __init__(self, *args: object, **kwargs: object) -> None:
        multi_select = kwargs.pop('multi_select', False)
        QFileDialog.__init__(self, *args)  # type: ignore[arg-type]
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.FileMode.Directory)

        # Enable multi-selection if requested
        if multi_select:
            # Find the list/tree view and enable multi-selection
            for view in self.findChildren(QtWidgets.QAbstractItemView):
                view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        # Create path input widget (though it appears unused in current implementation)
        self.path_input = QLineEdit()

        _ = self.directoryEntered.connect(self.update_path_input)

        current_path = self.directory().absolutePath()
        self.update_path_input(current_path)

    @log_function
    def navigate_to_path(self):
        path = str(self.path_input.text())
        if os.path.exists(path):
            self.setDirectory(path)
        else:
            _ = QMessageBox.warning(self, "Invalid Path", "The specified path does not exist.")
            logger.warning(f"User attempted to navigate to invalid path: {path}")

    @log_function
    def update_path_input(self, path: object) -> None:
        path_str = str(path)
        self.path_input.setText(path_str)
        logger.debug(f"Directory changed to: {path_str}")


# ----------------------------- Card Widget -----------------------------


class CardWidget(QWidget):
    """Modern card widget with optional title and shadow effect."""

    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        # Optional title
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            layout.addWidget(title_label)

        # Content layout (exposed for adding widgets)
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)

        # Add very subtle shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 10))  # Very light shadow
        self.setGraphicsEffect(shadow)


# ----------------------------- Main Application -----------------------------


class GalleryGeneratorApp(QMainWindow):
    # UI widget type annotations (initialized in initUI via _create_* methods)
    selected_dirs_display: QtWidgets.QPlainTextEdit  # pyright: ignore[reportUninitializedInstanceVariable]
    btn_scan: QPushButton  # pyright: ignore[reportUninitializedInstanceVariable]
    lbl_filter_count: QLabel  # pyright: ignore[reportUninitializedInstanceVariable]
    txt_filter: QLineEdit  # pyright: ignore[reportUninitializedInstanceVariable]
    txt_exclude: QLineEdit  # pyright: ignore[reportUninitializedInstanceVariable]
    list_slates: QListWidget  # pyright: ignore[reportUninitializedInstanceVariable]
    btn_refresh: QPushButton  # pyright: ignore[reportUninitializedInstanceVariable]
    chk_generate_thumbnails: QCheckBox  # pyright: ignore[reportUninitializedInstanceVariable]
    combo_thumbnail_size: QComboBox  # pyright: ignore[reportUninitializedInstanceVariable]
    chk_lazy_loading: QCheckBox  # pyright: ignore[reportUninitializedInstanceVariable]
    btn_generate: QPushButton  # pyright: ignore[reportUninitializedInstanceVariable]
    btn_open_gallery: QPushButton  # pyright: ignore[reportUninitializedInstanceVariable]
    lbl_status: QLabel  # pyright: ignore[reportUninitializedInstanceVariable]
    progress_bar: QProgressBar  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Slate Photography Gallery Generator")
        self.setGeometry(100, 100, 900, 700)

        # Load configuration with multiple directories
        self.config: GalleryConfig = load_config()
        # Aliases for backward compatibility
        self.current_root_dir = self.config.current_slate_dir
        self.cached_root_dirs = self.config.slate_dirs
        self.selected_slate_dirs = self.config.selected_slate_dirs
        self.generate_thumbnails_pref = self.config.generate_thumbnails
        self.thumbnail_size = self.config.thumbnail_size
        self.lazy_loading_pref = self.config.lazy_loading
        self.exclude_patterns_pref = self.config.exclude_patterns
        self.output_dir = os.path.expanduser("~")

        self.cache_manager = ImprovedCacheManager(
            base_dir=os.path.expanduser("~/.slate_gallery"), max_workers=4, batch_size=100
        )

        if not self.current_root_dir:
            self.current_root_dir = os.path.expanduser("~")
            self.cached_root_dirs.append(self.current_root_dir)
            self._sync_config_and_save()
            logger.info(f"Default root directory set to home directory: {self.current_root_dir}")

        self.slates_dict: dict[str, object] = {}
        self.filtered_slates: dict[str, object] = {}
        self.unique_focal_lengths: set[object] = set()

        # Thread attributes - initialized dynamically when needed
        self.scan_thread: Optional[ScanThread] = None
        self.gallery_thread: Optional[GenerateGalleryThread] = None

        # Set up debounced filtering timer
        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)  # Only fire once per timeout period
        _ = self.filter_timer.timeout.connect(self.apply_filters_debounced)
        self.filter_delay = 300  # 300ms delay after user stops typing

        # Set up the UI
        self.setup_style()
        self.initUI()

        # Restore selected directories display from config
        self.update_selected_dirs_display()

        # Load cached slates if available
        if self.current_root_dir:
            cached_slates = self.cache_manager.load_cache(self.current_root_dir)
            if cached_slates:
                self.slates_dict = cached_slates
                self.apply_filters()
                # Check if cache is still valid
                if self.cache_manager.validate_cache(self.current_root_dir):
                    self.update_status(f"Loaded {len(cached_slates)} collections from cache (ready to generate)")
                else:
                    self.update_status(f"Loaded {len(cached_slates)} collections (cache may be outdated - click Scan to refresh)")
                self.progress_bar.setValue(100)
            else:
                self.update_status("No cache found. Please scan directory.")

    def _sync_config_and_save(self) -> None:
        """Sync alias attributes back to config dataclass and save."""
        self.config.current_slate_dir = self.current_root_dir
        self.config.slate_dirs = self.cached_root_dirs
        self.config.selected_slate_dirs = self.selected_slate_dirs
        self.config.generate_thumbnails = self.generate_thumbnails_pref
        self.config.thumbnail_size = self.thumbnail_size
        self.config.lazy_loading = self.lazy_loading_pref
        self.config.exclude_patterns = self.exclude_patterns_pref
        save_config(self.config)

    def setup_style(self) -> None:
        self.setStyleSheet(f"""
            /* Main Window */
            QMainWindow {{
                background-color: {COLOR_BACKGROUND};
            }}

            /* Card Widgets */
            #card {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
            }}

            #cardTitle {{
                color: {COLOR_TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                margin-bottom: {SPACING_SM}px;
            }}

            /* Button System - Primary (Main Actions) */
            #primaryButton {{
                background-color: {COLOR_PRIMARY};
                color: {COLOR_PRIMARY_TEXT};
                border: none;
                border-radius: 6px;
                padding: {SPACING_MD}px {SPACING_LG}px;
                font-size: 14px;
                font-weight: bold;
                min-width: 120px;
            }}

            #primaryButton:hover {{
                background-color: {COLOR_PRIMARY_HOVER};
            }}

            #primaryButton:pressed {{
                background-color: {COLOR_PRIMARY_PRESSED};
            }}

            #primaryButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_DISABLED};
            }}

            /* Button System - Secondary (Less Important Actions) */
            #secondaryButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_SECONDARY_TEXT};
                border: none;
                border-radius: 6px;
                padding: {SPACING_SM}px {SPACING_MD}px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }}

            #secondaryButton:hover {{
                background-color: {COLOR_SECONDARY_HOVER};
            }}

            #secondaryButton:pressed {{
                background-color: #90CAF9;
            }}

            #secondaryButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_DISABLED};
            }}

            /* Button System - Tertiary (Minimal Actions) */
            #tertiaryButton {{
                background-color: {COLOR_TERTIARY_BG};
                color: {COLOR_TERTIARY_TEXT};
                border: 1px solid {COLOR_TERTIARY_BORDER};
                border-radius: 4px;
                padding: {SPACING_SM}px {SPACING_MD}px;
                font-size: 13px;
                font-weight: normal;
                min-width: 80px;
            }}

            #tertiaryButton:hover {{
                background-color: {COLOR_TERTIARY_HOVER};
            }}

            #tertiaryButton:pressed {{
                background-color: {COLOR_SECONDARY};
            }}

            #tertiaryButton:disabled {{
                border-color: {COLOR_BORDER};
                color: {COLOR_TEXT_DISABLED};
            }}

            /* Button System - Accent (Eye-catching actions like Open Gallery) */
            #accentButton {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_ACCENT_TEXT};
                border: none;
                border-radius: 6px;
                padding: {SPACING_MD}px {SPACING_LG}px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }}

            #accentButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}

            #accentButton:pressed {{
                background-color: #FFA726;
            }}

            #accentButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_DISABLED};
            }}

            /* Labels */
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
            }}

            #instructionLabel {{
                color: {COLOR_TEXT_SECONDARY};
                font-size: 12px;
                font-weight: normal;
                margin-bottom: {SPACING_SM}px;
            }}

            /* Input Fields */
            QLineEdit, QComboBox {{
                padding: {SPACING_SM}px {SPACING_MD}px;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                background-color: {COLOR_SURFACE};
                color: {COLOR_TEXT_PRIMARY};
                font-size: 13px;
            }}

            QLineEdit:focus, QComboBox:focus {{
                border-color: {COLOR_PRIMARY};
                outline: none;
            }}

            QLineEdit:disabled, QComboBox:disabled {{
                background-color: {COLOR_BACKGROUND};
                color: {COLOR_TEXT_DISABLED};
            }}

            /* List Widget */
            QListWidget {{
                border: 2px solid {COLOR_BORDER};
                border-radius: 6px;
                background-color: {COLOR_SURFACE};
                padding: {SPACING_SM}px;
                font-size: 13px;
            }}

            QListWidget::item {{
                padding: {SPACING_SM}px;
                border-radius: 4px;
                margin: 2px 0;
            }}

            QListWidget::item:selected {{
                background-color: #E3F2FD;
                color: #1565C0;
                border-left: 3px solid #1976D2;
            }}

            QListWidget::item:selected:hover {{
                background-color: #BBDEFB;
                color: #0D47A1;
            }}

            QListWidget::item:hover {{
                background-color: #F5F5F5;
            }}

            /* Progress Bar */
            QProgressBar {{
                border: 2px solid {COLOR_BORDER};
                border-radius: 6px;
                background-color: {COLOR_BACKGROUND};
                text-align: center;
                height: 24px;
                font-size: 12px;
                font-weight: 500;
            }}

            QProgressBar::chunk {{
                background-color: {COLOR_PRIMARY};
                border-radius: 4px;
            }}

            /* Checkboxes */
            QCheckBox {{
                font-size: 13px;
                font-weight: 500;
                color: {COLOR_TEXT_PRIMARY};
                spacing: {SPACING_SM}px;
            }}

            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {COLOR_BORDER};
                border-radius: 4px;
            }}

            QCheckBox::indicator:checked {{
                background-color: {COLOR_PRIMARY};
                border-color: {COLOR_PRIMARY};
            }}
        """)

    def _create_directory_card(self) -> CardWidget:
        """Create the directory selection card with browse and scan buttons."""
        dir_card = CardWidget()  # No title - self-evident
        dir_layout = QGridLayout()
        dir_layout.setSpacing(SPACING_SM)

        lbl_root = QLabel("Photo Directories:")
        lbl_root.setToolTip("Select one or more directories to scan")
        dir_layout.addWidget(lbl_root, 0, 0, Qt.AlignmentFlag.AlignTop)

        # Create text display for selected directories
        self.selected_dirs_display = QtWidgets.QPlainTextEdit()
        self.selected_dirs_display.setReadOnly(True)
        self.selected_dirs_display.setMaximumHeight(100)
        self.selected_dirs_display.setPlaceholderText("No directories selected - click Browse to select")
        self.selected_dirs_display.setToolTip("Selected directories for scanning")
        dir_layout.addWidget(self.selected_dirs_display, 0, 1, 2, 1)  # Span 2 rows

        # Browse button
        btn_browse_root = QPushButton("Browse...")
        btn_browse_root.setObjectName("tertiaryButton")
        btn_browse_root.setToolTip("Select one or more directories to scan (multi-select enabled)")
        _ = btn_browse_root.clicked.connect(self.on_browse_root)
        dir_layout.addWidget(btn_browse_root, 0, 2, 2, 1)  # Span 2 rows, align top

        dir_layout.setColumnStretch(0, 0)
        dir_layout.setColumnStretch(1, 1)
        dir_layout.setColumnStretch(2, 0)

        # Add Scan button in third row of directory card
        self.btn_scan = QPushButton("Scan Selected Directories")
        self.btn_scan.setObjectName("secondaryButton")  # Visible but not primary
        self.btn_scan.setToolTip("Scan all checked directories for photo collections")
        _ = self.btn_scan.clicked.connect(self.on_scan)
        dir_layout.addWidget(self.btn_scan, 2, 1, 1, 2)  # Row 2, span across columns 1-2

        dir_card.content_layout.addLayout(dir_layout)
        return dir_card

    def _create_slates_card(self) -> CardWidget:
        """Create the slates selection card with filters and list."""
        selection_card = CardWidget()  # No card title

        # Centered "Slates" title (compact with subtle background)
        title_container = QHBoxLayout()
        title_container.addStretch()

        slates_title = QLabel("Slates")
        slates_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #37474F; background-color: #F0F7FF; border-radius: 4px; padding: 8px 32px;")
        title_container.addWidget(slates_title)

        title_container.addStretch()
        selection_card.content_layout.addLayout(title_container)

        # Filter count label (showing X of Y slates)
        self.lbl_filter_count = QLabel("")
        self.lbl_filter_count.setStyleSheet("font-size: 12px; color: #666666; padding: 4px 0px;")
        self.lbl_filter_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        selection_card.content_layout.addWidget(self.lbl_filter_count)

        # Filter input
        filter_input_layout = QHBoxLayout()
        filter_input_layout.setSpacing(SPACING_SM)
        lbl_filter = QLabel("Filter:")
        filter_input_layout.addWidget(lbl_filter)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Type to filter collections...")
        _ = self.txt_filter.textChanged.connect(self.on_filter)
        filter_input_layout.addWidget(self.txt_filter)

        selection_card.content_layout.addLayout(filter_input_layout)

        # Exclusion filter input
        exclude_input_layout = QHBoxLayout()
        exclude_input_layout.setSpacing(SPACING_SM)
        lbl_exclude = QLabel("Exclude:")
        exclude_input_layout.addWidget(lbl_exclude)

        self.txt_exclude = QLineEdit()
        self.txt_exclude.setPlaceholderText("Exclude (e.g., hdri, test)...")
        self.txt_exclude.setText(self.exclude_patterns_pref)  # Load saved preference
        _ = self.txt_exclude.textChanged.connect(self.on_filter)
        exclude_input_layout.addWidget(self.txt_exclude)

        selection_card.content_layout.addLayout(exclude_input_layout)

        # List and buttons layout
        list_buttons_layout = QHBoxLayout()
        list_buttons_layout.setSpacing(SPACING_MD)

        # Collections list with standard Qt multi-selection
        self.list_slates = QListWidget()
        self.list_slates.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_slates.setItemDelegate(HtmlItemDelegate(self.list_slates))
        self.list_slates.setMinimumHeight(200)
        self.list_slates.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        list_buttons_layout.addWidget(self.list_slates)

        # Selection buttons
        selection_buttons_layout = QVBoxLayout()
        selection_buttons_layout.setSpacing(SPACING_SM)

        btn_select_all = QPushButton("Select All")
        btn_select_all.setObjectName("tertiaryButton")
        _ = btn_select_all.clicked.connect(self.on_select_all)
        selection_buttons_layout.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.setObjectName("tertiaryButton")
        _ = btn_deselect_all.clicked.connect(self.on_deselect_all)
        selection_buttons_layout.addWidget(btn_deselect_all)

        # Add Refresh button
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("tertiaryButton")
        self.btn_refresh.setToolTip("Warning: This will re-scan the directory and clear current selections")
        _ = self.btn_refresh.clicked.connect(self.on_refresh)
        selection_buttons_layout.addWidget(self.btn_refresh)

        selection_buttons_layout.addStretch()
        list_buttons_layout.addLayout(selection_buttons_layout)

        selection_card.content_layout.addLayout(list_buttons_layout)
        return selection_card

    def _create_options_card(self) -> CardWidget:
        """Create the gallery options card with thumbnail and lazy loading settings."""
        options_card = CardWidget("Gallery Options")

        # Thumbnail generation option with size selector
        thumbnail_layout = QHBoxLayout()
        thumbnail_layout.setSpacing(SPACING_SM)

        self.chk_generate_thumbnails = QCheckBox("Generate thumbnails for faster loading")
        self.chk_generate_thumbnails.setChecked(self.generate_thumbnails_pref)
        self.chk_generate_thumbnails.setToolTip(
            "When enabled, creates optimized thumbnails for faster gallery loading.\n" +
            "Uses parallel processing for 5-10x faster generation.\n" +
            "When disabled, uses original full-resolution images (slower but no processing needed)."
        )
        _ = self.chk_generate_thumbnails.stateChanged.connect(self.on_thumbnail_pref_changed)

        # Add thumbnail size dropdown
        thumbnail_size_label = QLabel("Size:")
        self.combo_thumbnail_size = QComboBox()
        self.combo_thumbnail_size.addItems(["600x600", "800x800", "1200x1200"])
        self.combo_thumbnail_size.setToolTip(
            "Select the thumbnail resolution:\n" +
            "• 600x600: Smallest files, fastest loading (recommended for web)\n" +
            "• 800x800: Balanced quality and file size\n" +
            "• 1200x1200: Higher quality, larger files (recommended for high-DPI displays)"
        )
        # Set the current selection based on config
        current_size_text = f"{self.thumbnail_size}x{self.thumbnail_size}"
        index = self.combo_thumbnail_size.findText(current_size_text)
        if index >= 0:
            self.combo_thumbnail_size.setCurrentIndex(index)
        _ = self.combo_thumbnail_size.currentTextChanged.connect(self.on_thumbnail_size_changed)
        # Enable/disable based on checkbox state
        self.combo_thumbnail_size.setEnabled(self.chk_generate_thumbnails.isChecked())

        thumbnail_layout.addWidget(self.chk_generate_thumbnails)
        thumbnail_layout.addWidget(thumbnail_size_label)
        thumbnail_layout.addWidget(self.combo_thumbnail_size)
        thumbnail_layout.addStretch()

        options_card.content_layout.addLayout(thumbnail_layout)

        # Lazy loading option
        self.chk_lazy_loading = QCheckBox("Enable lazy loading (recommended for large galleries)")
        self.chk_lazy_loading.setChecked(self.lazy_loading_pref)
        self.chk_lazy_loading.setToolTip(
            "When enabled, images load progressively as you scroll (better performance).\n" +
            "When disabled, all images load immediately (may be slow for large galleries).\n" +
            "Recommended: ON for galleries with 50+ images, OFF for small galleries."
        )
        _ = self.chk_lazy_loading.stateChanged.connect(self.on_lazy_loading_pref_changed)
        options_card.content_layout.addWidget(self.chk_lazy_loading)

        return options_card

    def _create_action_buttons(self, layout: QVBoxLayout) -> None:
        """Create and add the generate and open gallery buttons to layout."""
        self.btn_generate = QPushButton("Generate Gallery")
        self.btn_generate.setObjectName("primaryButton")
        self.btn_generate.setToolTip("Generate HTML gallery from selected collections")
        _ = self.btn_generate.clicked.connect(self.on_generate)
        layout.addWidget(self.btn_generate)

        self.btn_open_gallery = QPushButton("Open Gallery")
        self.btn_open_gallery.setObjectName("accentButton")
        _ = self.btn_open_gallery.clicked.connect(self.on_open_gallery)
        self.btn_open_gallery.setEnabled(False)
        layout.addWidget(self.btn_open_gallery)

    def _create_status_bar(self, layout: QVBoxLayout) -> None:
        """Create and add the status bar with progress indicator to layout."""
        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("Select a photo directory and click 'Scan Directory' to begin")
        status_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # Hidden by default
        status_layout.addWidget(self.progress_bar)

        layout.addLayout(status_layout)

    def initUI(self) -> None:
        """Initialize the main UI layout with all cards and controls."""
        # Central widget with margin
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with margins
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        main_layout.setSpacing(SPACING_SM)  # Tighter spacing between cards
        central_widget.setLayout(main_layout)

        # Add cards
        main_layout.addWidget(self._create_directory_card())
        main_layout.addWidget(self._create_slates_card())
        main_layout.addWidget(self._create_options_card())

        # Add action buttons and status bar
        self._create_action_buttons(main_layout)
        self._create_status_bar(main_layout)


    @log_function
    def update_cached_dirs(self, new_dir: str) -> None:
        if new_dir and new_dir not in self.cached_root_dirs:
            self.cached_root_dirs.append(new_dir)
            self.current_root_dir = new_dir
            self._sync_config_and_save()
            logger.info(f"Added new directory to cached slate directories: {new_dir}")

    @log_function
    def on_browse_root(self) -> None:
        """Browse for directories with multi-select support."""
        try:
            # Use current directory or first cached as starting point
            start_dir = self.current_root_dir if self.current_root_dir else (self.cached_root_dirs[0] if self.cached_root_dirs else os.path.expanduser("~"))

            dialog = CustomFileDialog(self, "Select Photo Directories (Ctrl/Cmd+Click for multiple)", start_dir, multi_select=True)

            if dialog.exec() == QFileDialog.DialogCode.Accepted:
                selected = dialog.selectedFiles()
                if selected:
                    # Replace selection with newly selected directories
                    self.selected_slate_dirs = [str(d) for d in selected]

                    # Update current_root_dir to first selected for compatibility
                    self.current_root_dir = self.selected_slate_dirs[0]

                    # Update cached directories (add any new ones)
                    for dir_path in self.selected_slate_dirs:
                        if dir_path not in self.cached_root_dirs:
                            self.cached_root_dirs.append(dir_path)

                    # Update display
                    self.update_selected_dirs_display()

                    # Update preferences from UI and save configuration
                    self.generate_thumbnails_pref = self.chk_generate_thumbnails.isChecked()
                    self.lazy_loading_pref = self.chk_lazy_loading.isChecked()
                    self._sync_config_and_save()

                    logger.info(f"Selected {len(self.selected_slate_dirs)} directories: {self.selected_slate_dirs}")
                    self.update_status(f"Selected {len(self.selected_slate_dirs)} director{'y' if len(self.selected_slate_dirs) == 1 else 'ies'}")

        except Exception as e:
            self.update_status(f"Error in directory selection: {e}")
            logger.error(f"Error in directory selection: {e}", exc_info=True)

    @log_function
    def update_selected_dirs_display(self) -> None:
        """Update the text display to show currently selected directories."""
        if self.selected_slate_dirs:
            # Show one path per line
            display_text = "\n".join(self.selected_slate_dirs)
            self.selected_dirs_display.setPlainText(display_text)
        else:
            # Clear display if nothing selected
            self.selected_dirs_display.clear()

    def on_scan(self) -> None:
        """Scan selected directories for photo collections."""
        try:
            # Guard against multiple concurrent scans
            if self.scan_thread is not None and self.scan_thread.isRunning():
                logger.warning("Scan already in progress, ignoring request")
                return

            # Get list of checked folders
            if not self.selected_slate_dirs:
                self.update_status("Please check at least one directory to scan.")
                logger.warning("Scan initiated without selecting any directories.")
                _ = QMessageBox.information(
                    self,
                    "No Directories Selected",
                    "Please check one or more directories from the list before scanning.",
                    QMessageBox.StandardButton.Ok
                )
                return

            # Validate that all selected directories exist
            invalid_dirs = [d for d in self.selected_slate_dirs if not os.path.isdir(d)]
            if invalid_dirs:
                self.update_status(f"Some selected directories do not exist: {', '.join(invalid_dirs)}")
                logger.error(f"Invalid directories selected: {invalid_dirs}")
                return

            # Update current_root_dir to first selected directory for compatibility
            self.current_root_dir = self.selected_slate_dirs[0]

            self.update_status(f"Scanning {len(self.selected_slate_dirs)} director{'y' if len(self.selected_slate_dirs) == 1 else 'ies'}...")
            logger.info(f"Scanning {len(self.selected_slate_dirs)} directories: {self.selected_slate_dirs}")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.slates_dict = {}
            self.filtered_slates = {}
            self.unique_focal_lengths = set()
            self.list_slates.clear()

            # Check cache (single directory or composite for multiple)
            cached_slates = None
            cache_valid = False

            if len(self.selected_slate_dirs) == 1:
                cached_slates = self.cache_manager.load_cache(self.selected_slate_dirs[0])
                cache_valid = self.cache_manager.validate_cache(self.selected_slate_dirs[0]) if cached_slates else False
            else:
                cached_slates = self.cache_manager.load_composite_cache(self.selected_slate_dirs)
                cache_valid = self.cache_manager.validate_composite_cache(self.selected_slate_dirs) if cached_slates else False

            if cached_slates:
                if cache_valid:
                    # Cache is valid - use it directly
                    self.slates_dict = cached_slates
                    self.apply_filters()
                    self.update_status("Loaded slates from cache.")
                    self.progress_bar.setValue(100)  # type: ignore[union-attr]
                    QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))  # type: ignore[union-attr]
                    logger.info(f"Loaded slates from cache for {len(self.selected_slate_dirs)} directory(ies)")
                    return
                else:
                    # Cache exists but is outdated - ask user before using stale data
                    reply = QMessageBox.question(
                        self,
                        "Cache Outdated",
                        "The cached data may be outdated. Use cached data anyway?\n\n"
                        "Click 'Yes' to use cache (faster)\n"
                        "Click 'No' to re-scan directories (accurate)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No  # Default to re-scan for safety
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.slates_dict = cached_slates
                        self.apply_filters()
                        self.update_status("Using outdated cache (re-scan recommended)")
                        self.progress_bar.setValue(100)  # type: ignore[union-attr]
                        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))  # type: ignore[union-attr]
                        logger.info(f"User chose to use outdated cache for {len(self.selected_slate_dirs)} directory(ies)")
                        return
                    # User chose No - fall through to perform fresh scan
                    logger.info("User chose to re-scan instead of using outdated cache")

            # Disable scan/refresh buttons during scan
            self.btn_scan.setEnabled(False)
            self.btn_refresh.setEnabled(False)

            # Start scan thread with selected directories
            self.scan_thread = ScanThread(self.selected_slate_dirs, self.cache_manager, self.exclude_patterns_pref)  # pyright: ignore[reportArgumentType]
            # Use QueuedConnection for thread-to-main-thread signals to prevent race conditions
            _ = self.scan_thread.scan_complete.connect(self.on_scan_complete, Qt.ConnectionType.QueuedConnection)
            _ = self.scan_thread.progress.connect(self.on_scan_progress, Qt.ConnectionType.QueuedConnection)
            self.scan_thread.start()
            logger.debug(f"Scan thread started for {len(self.selected_slate_dirs)} directories")
        except Exception as e:
            self.update_status(f"Error initiating scan: {e}")
            logger.error(f"Error initiating scan: {e}", exc_info=True)

    def on_scan_complete(self, slates_dict: object, message: object) -> None:
        self.slates_dict = slates_dict  # type: ignore[assignment]
        self.apply_filters()
        self.update_status(str(message))
        self.progress_bar.setValue(100)
        # Hide progress bar after 2 seconds
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
        # Re-enable scan/refresh buttons
        self.btn_scan.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        logger.info(f"Scan complete: {message}")

    def on_scan_progress(self, progress: object) -> None:
        progress_int = int(progress)  # type: ignore[arg-type]
        self.progress_bar.setValue(progress_int)
        logger.debug(f"Scan progress: {progress_int}%")

    def on_filter(self) -> None:
        """Handle filter text changes with debouncing to improve UI responsiveness."""
        try:
            # Stop any pending filter operation
            self.filter_timer.stop()

            # Start new timer - will trigger apply_filters_debounced after delay
            self.filter_timer.start(self.filter_delay)

            logger.debug(f"Filter timer started (delay: {self.filter_delay}ms)")
        except Exception as e:
            self.update_status(f"Error during filter setup: {e}")
            logger.error(f"Error during filter setup: {e}", exc_info=True)

    def apply_filters_debounced(self) -> None:
        """Apply filters with performance monitoring and enhanced error handling."""
        import time

        start_time = time.perf_counter()

        try:
            filter_text = str(self.txt_filter.text()).strip().lower()
            slate_count = len(self.slates_dict)

            logger.debug(f"Applying filter '{filter_text}' to {slate_count} slates")

            # Apply the actual filtering
            self.apply_filters()

            # Performance metrics
            end_time = time.perf_counter()
            filter_time = (end_time - start_time) * 1000  # Convert to milliseconds
            filtered_count = len(self.filtered_slates)

            logger.debug(f"Filter applied in {filter_time:.1f}ms: {filtered_count}/{slate_count} slates shown")

            # Provide user feedback for slow operations
            if filter_time > 100:  # If filtering takes more than 100ms
                self.update_status(f"Filtered {filtered_count} of {slate_count} slates ({filter_time:.0f}ms)")
            elif filtered_count == 0 and filter_text:
                self.update_status(f"No slates match '{filter_text}'")
            elif filter_text:
                self.update_status(f"Showing {filtered_count} slates matching '{filter_text}'")
            else:
                self.update_status(f"Showing all {slate_count} slates")

        except Exception as e:
            error_msg = f"Error during filtering: {e}"
            self.update_status(error_msg)
            logger.error(error_msg, exc_info=True)

    @log_function
    def apply_filters(self) -> None:
        filter_text = str(self.txt_filter.text()).strip().lower()
        exclude_pattern = str(self.txt_exclude.text()).strip()

        # Save exclude pattern preference if it changed
        if exclude_pattern != self.exclude_patterns_pref:
            self.exclude_patterns_pref = exclude_pattern
            self._sync_config_and_save()

        # Start with all slates
        filtered = self.slates_dict.copy()

        # Apply inclusion filter if text is present
        if filter_text:
            filtered = {
                slate: data
                for slate, data in filtered.items()
                if filter_text in slate.lower()
            }

        # Apply exclusion filter if pattern is present
        if exclude_pattern:
            # Split by comma to support multiple patterns
            exclude_patterns = [p.strip().lower() for p in exclude_pattern.split(',') if p.strip()]
            filtered = {
                slate: data
                for slate, data in filtered.items()
                if not any(pattern in slate.lower() for pattern in exclude_patterns)
            }

        self.filtered_slates = filtered
        self.populate_slates_list()
        logger.info(f"Filtered slates - filter: '{filter_text}', exclude: '{exclude_pattern}', result: {len(filtered)} slates")

    @log_function
    def populate_slates_list(self) -> None:
        # Save currently selected slate names before clearing (using stored data, not display text)
        selected_names: set[str] = {
            str(item.data(Qt.ItemDataRole.UserRole))  # pyright: ignore[reportAny]
            for item in self.list_slates.selectedItems()
        }

        self.list_slates.clear()
        for slate in sorted(self.filtered_slates.keys()):
            # Get image count from slate data
            slate_data = self.filtered_slates[slate]
            image_count = 0
            if isinstance(slate_data, dict):
                slate_dict = cast(dict[str, object], slate_data)
                images = slate_dict.get("images", [])
                if isinstance(images, list):
                    image_count = len(cast(list[object], images))

            # Create item with HTML: bold name, regular count
            item = QListWidgetItem(f"<b>{slate}</b> ({image_count})")
            # Store original slate name for lookups
            item.setData(Qt.ItemDataRole.UserRole, slate)
            self.list_slates.addItem(item)

            # Restore selection if this slate was previously selected
            if slate in selected_names:
                item.setSelected(True)

        # Update filter count label
        filtered_count = len(self.filtered_slates)
        total_count = len(self.slates_dict)
        if filtered_count == total_count:
            self.lbl_filter_count.setText(f"Showing all {total_count} slates")
        else:
            filtered_out = total_count - filtered_count
            self.lbl_filter_count.setText(f"Showing {filtered_count} of {total_count} slates ({filtered_out} filtered out)")

        logger.debug(f"Populated slates list with {self.list_slates.count()} slates.")

    def on_select_all(self) -> None:
        try:
            for index in range(self.list_slates.count()):
                item = self.list_slates.item(index)
                item.setSelected(True)
            logger.info("All slates selected.")
        except Exception as e:
            self.update_status(f"Error selecting all slates: {e}")
            logger.error(f"Error selecting all slates: {e}", exc_info=True)

    def on_deselect_all(self) -> None:
        try:
            self.list_slates.clearSelection()
            logger.info("All slates deselected.")
        except Exception as e:
            self.update_status(f"Error deselecting all slates: {e}")
            logger.error(f"Error deselecting all slates: {e}", exc_info=True)

    def on_refresh(self) -> None:
        """Re-scan selected directories, clearing cache."""
        try:
            # Guard against multiple concurrent scans
            if self.scan_thread is not None and self.scan_thread.isRunning():
                logger.warning("Scan already in progress, ignoring refresh request")
                return

            if not self.selected_slate_dirs:
                self.update_status("Please check at least one directory to refresh.")
                logger.warning("Refresh initiated without selecting any directories.")
                return

            # Validate directories exist
            invalid_dirs = [d for d in self.selected_slate_dirs if not os.path.isdir(d)]
            if invalid_dirs:
                self.update_status(f"Some selected directories do not exist: {', '.join(invalid_dirs)}")
                logger.error(f"Invalid directories selected: {invalid_dirs}")
                return

            # Confirm before refreshing
            reply = QMessageBox.question(
                self,
                "Confirm Refresh",
                f"This will re-scan {len(self.selected_slate_dirs)} director{'y' if len(self.selected_slate_dirs) == 1 else 'ies'} and clear the cache.\n\n" +
                "Are you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                logger.info("Refresh cancelled by user")
                return

            self.current_root_dir = self.selected_slate_dirs[0]  # Update to first selected
            self.update_status(f"Refreshing {len(self.selected_slate_dirs)} director{'y' if len(self.selected_slate_dirs) == 1 else 'ies'}...")
            logger.info(f"Refreshing directories: {self.selected_slate_dirs}")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.slates_dict = {}
            self.filtered_slates = {}
            self.unique_focal_lengths = set()
            self.list_slates.clear()

            # Disable scan/refresh buttons during scan
            self.btn_scan.setEnabled(False)
            self.btn_refresh.setEnabled(False)

            # Start scan thread to re-scan and update cache
            self.scan_thread = ScanThread(self.selected_slate_dirs, self.cache_manager, self.exclude_patterns_pref)  # pyright: ignore[reportArgumentType]
            # Use QueuedConnection for thread-to-main-thread signals to prevent race conditions
            _ = self.scan_thread.scan_complete.connect(self.on_scan_complete, Qt.ConnectionType.QueuedConnection)
            _ = self.scan_thread.progress.connect(self.on_scan_progress, Qt.ConnectionType.QueuedConnection)
            self.scan_thread.start()
            logger.debug(f"Refresh scan thread started for {len(self.selected_slate_dirs)} directories")
        except Exception as e:
            self.update_status(f"Error initiating refresh: {e}")
            logger.error(f"Error initiating refresh: {e}", exc_info=True)

    def on_generate(self) -> None:
        try:
            # Guard against multiple concurrent gallery generations
            if self.gallery_thread is not None and self.gallery_thread.isRunning():
                logger.warning("Gallery generation already in progress, ignoring request")
                return

            selected_items = self.list_slates.selectedItems()
            if not selected_items:
                self.update_status("Please select at least one slate.")
                logger.warning("Generate gallery initiated without selecting any slates.")
                return

            selected_slates = [
                str(item.data(Qt.ItemDataRole.UserRole))  # pyright: ignore[reportAny]
                for item in selected_items
            ]
            output = self.output_dir

            if not output:
                output = os.path.expanduser("~")
                self.output_dir = output
                self.update_status("Output directory set to home directory.")
                logger.info(f"Output directory set to home directory: {self.output_dir}")

            if not os.path.exists(output):
                try:
                    os.makedirs(output)
                    logger.info(f"Created output directory: {output}")
                except Exception as e:
                    self.update_status(f"Error creating output directory: {e}")
                    logger.error(f"Error creating output directory: {e}", exc_info=True)
                    return

            self.btn_generate.setEnabled(False)
            self.btn_open_gallery.setEnabled(False)
            self.update_status("Generating gallery...")
            logger.info(f"Generating gallery at: {output}")
            self.progress_bar.setVisible(True)  # Show progress bar
            self.progress_bar.setValue(0)

            # Path to the HTML template
            template_file = "gallery_template.html"
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", template_file
            )
            if not os.path.exists(template_path):
                self.update_status(f"HTML template not found: {template_path}")
                logger.error(f"HTML template not found: {template_path}")
                self.btn_generate.setEnabled(True)
                return

            # Start the GenerateGalleryThread
            self.gallery_thread = GenerateGalleryThread(
                selected_slates=selected_slates,
                slates_dict=self.slates_dict,
                cache_manager=self.cache_manager,  # pyright: ignore[reportArgumentType]
                output_dir=output,
                allowed_root_dirs=self.selected_slate_dirs if self.selected_slate_dirs else [self.current_root_dir],
                template_path=template_path,
                generate_thumbnails=self.chk_generate_thumbnails.isChecked(),
                thumbnail_size=self.thumbnail_size,
                lazy_loading=self.chk_lazy_loading.isChecked()
            )
            # Use QueuedConnection for thread-to-main-thread signals to prevent race conditions
            _ = self.gallery_thread.gallery_complete.connect(self.on_gallery_complete, Qt.ConnectionType.QueuedConnection)
            _ = self.gallery_thread.progress.connect(self.on_gallery_progress, Qt.ConnectionType.QueuedConnection)
            self.gallery_thread.start()
            logger.debug("Gallery generation thread started.")
        except Exception as e:
            self.update_status(f"Error initiating gallery generation: {e}")
            self.btn_generate.setEnabled(True)
            logger.error(f"Error initiating gallery generation: {e}", exc_info=True)

    def on_gallery_complete(self, success: object, message: object) -> None:
        self.update_status(str(message))
        self.progress_bar.setValue(100 if success else 0)  # type: ignore[arg-type]
        # Hide progress bar after 2 seconds
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
        self.btn_generate.setEnabled(True)
        if success:
            self.btn_open_gallery.setEnabled(True)
        else:
            self.btn_open_gallery.setEnabled(False)
        logger.info(f"Gallery generation result: {message}")

    def on_gallery_progress(self, progress: object) -> None:
        progress_int = int(progress)  # type: ignore[arg-type]
        self.progress_bar.setValue(progress_int)
        logger.debug(f"Gallery generation progress: {progress_int}%")

    def on_open_gallery(self) -> None:
        try:
            html_file_path = os.path.join(self.output_dir, "index.html")
            if os.path.exists(html_file_path):
                # Use webbrowser module to open the file in the default browser
                url = "file://" + os.path.abspath(html_file_path)
                _ = webbrowser.open(url, new=2)  # new=2 opens in a new window if possible
                logger.info(f"Opened gallery at: {html_file_path}")
                self.update_status("Opening gallery in new browser window...")
            else:
                self.update_status("Generated gallery not found.")
                logger.warning(f"Generated gallery not found at: {html_file_path}")
                if self.btn_open_gallery:
                    self.btn_open_gallery.setEnabled(False)
        except Exception as e:
            self.update_status(f"Error opening gallery: {e}")
            logger.error(f"Error opening gallery: {e}", exc_info=True)

    @log_function
    def update_status(self, message: str) -> None:
        self.lbl_status.setText(message)
        logger.info(f"Status updated: {message}")

    def on_thumbnail_pref_changed(self) -> None:
        """Save thumbnail preference when checkbox state changes."""
        self.generate_thumbnails_pref = self.chk_generate_thumbnails.isChecked()
        # Enable/disable size dropdown based on checkbox state
        self.combo_thumbnail_size.setEnabled(self.generate_thumbnails_pref)
        self._sync_config_and_save()

    def on_thumbnail_size_changed(self, text: object) -> None:
        """Save thumbnail size preference when dropdown changes."""
        text_str = str(text)
        if text_str:
            # Extract the size number from the text (e.g., "600x600" -> 600)
            if 'x' in text_str:
                size_str = text_str.split('x')[0].strip()
                try:
                    self.thumbnail_size = int(size_str)
                    self._sync_config_and_save()
                    logger.info(f"Thumbnail size changed to: {self.thumbnail_size}")
                except ValueError:
                    logger.error(f"Invalid thumbnail size format: {text_str}")
            else:
                logger.error(f"Invalid thumbnail size format (missing 'x'): {text_str}")

    def on_lazy_loading_pref_changed(self) -> None:
        """Save lazy loading preference when checkbox state changes."""
        self.lazy_loading_pref = self.chk_lazy_loading.isChecked()
        self._sync_config_and_save()
        logger.info(f"Lazy loading preference changed to: {self.lazy_loading_pref}")

    @override
    def closeEvent(self, event: object) -> None:
        try:
            # Signal both threads to stop (non-blocking, triggers parallel shutdown)
            if self.scan_thread and self.scan_thread.isRunning():
                logger.info("Signaling scan thread to stop...")
                self.scan_thread.signal_stop()

            if self.gallery_thread and self.gallery_thread.isRunning():
                logger.info("Signaling gallery thread to stop...")
                self.gallery_thread.signal_stop()

            # Wait for both threads (they're now stopping in parallel)
            if self.scan_thread and not self.scan_thread.wait(5000):
                logger.warning("Scan thread did not stop within timeout")

            if self.gallery_thread and not self.gallery_thread.wait(5000):
                logger.warning("Gallery thread did not stop within timeout")

            # Stop filter timer
            self.filter_timer.stop()

            # Ensure clean shutdown
            self.cache_manager.shutdown()
            logger.info("Cache manager shutdown successfully.")

            # Save configuration
            self._sync_config_and_save()

            event.accept()  # type: ignore[union-attr]
            logger.info("Application closed.")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}", exc_info=True)
            event.accept()  # type: ignore[union-attr]


# ----------------------------- Main Execution -----------------------------


def main() -> None:
    try:
        app = QApplication(sys.argv)

        # Set application-wide stylesheet for dialogs
        app.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLOR_SURFACE};
            }}
            QMessageBox QLabel {{
                color: {COLOR_TEXT_PRIMARY};
            }}
            QMessageBox QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_PRIMARY};
                border: none;
                padding: {SPACING_SM}px {SPACING_MD}px;
                border-radius: 6px;
                min-width: 80px;
                font-weight: 500;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {COLOR_SECONDARY_HOVER};
            }}
            QFileDialog {{
                background-color: {COLOR_SURFACE};
            }}
            QFileDialog QTreeView {{
                background-color: {COLOR_SURFACE};
                border: 2px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
            QFileDialog QTreeView::item:selected {{
                background-color: {COLOR_SECONDARY};
                color: {COLOR_PRIMARY};
            }}
            QFileDialog QTreeView::item:hover {{
                background-color: {COLOR_BACKGROUND};
            }}
        """)

        window = GalleryGeneratorApp()
        window.show()
        logger.info("Application started successfully.")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Critical error in main execution: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
