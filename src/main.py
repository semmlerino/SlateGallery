#!/usr/bin/env python3

"""
Main entry point for SlateGallery - uses new modular structure
while maintaining identical functionality to the original.
"""

# System imports
import os
import sys
import webbrowser
from typing import Optional

from typing_extensions import override

# Add src to path for imports
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

# Qt imports
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
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
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.cache_manager import ImprovedCacheManager
from core.config_manager import load_config, save_config

# Import from our new modular structure
from utils.logging_config import log_function, logger
from utils.threading import GenerateGalleryThread, ScanThread

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

# ----------------------------- Custom File Dialog -----------------------------


class CustomFileDialog(QFileDialog):
    def __init__(self, *args):
        QFileDialog.__init__(self, *args)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.FileMode.Directory)

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
    def update_path_input(self, path):
        path = str(path)
        self.path_input.setText(path)
        logger.debug(f"Directory changed to: {path}")


# ----------------------------- Card Widget -----------------------------


class CardWidget(QWidget):
    """Modern card widget with optional title and shadow effect."""

    def __init__(self, title="", parent=None):
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Slate Photography Gallery Generator")
        self.setGeometry(100, 100, 900, 700)

        # Load configuration with multiple directories
        self.current_root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref = load_config()
        self.output_dir = os.path.expanduser("~")

        self.cache_manager = ImprovedCacheManager(
            base_dir=os.path.expanduser("~/.slate_gallery"), max_workers=4, batch_size=100
        )

        if not self.current_root_dir:
            self.current_root_dir = os.path.expanduser("~")
            self.cached_root_dirs.append(self.current_root_dir)
            save_config(self.current_root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)
            logger.info(f"Default root directory set to home directory: {self.current_root_dir}")

        self.slates_dict = {}
        self.filtered_slates = {}
        self.unique_focal_lengths = set()

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

        # Load cached slates if available
        if self.current_root_dir:
            cached_slates = self.cache_manager.load_cache(self.current_root_dir)
            if cached_slates:
                self.slates_dict = cached_slates
                self.apply_filters()
                self.update_status(f"Loaded {len(cached_slates)} collections from cache (ready to generate)")
                self.progress_bar.setValue(100)
            else:
                self.update_status("No cache found. Please scan directory.")

    def setup_style(self):
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
                background-color: {COLOR_SECONDARY};
                color: {COLOR_PRIMARY};
            }}

            QListWidget::item:hover {{
                background-color: {COLOR_BACKGROUND};
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

    def initUI(self):
        # Central widget with margin
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with margins
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        main_layout.setSpacing(SPACING_SM)  # Tighter spacing between cards
        central_widget.setLayout(main_layout)

        # Directory Selection Card
        dir_card = CardWidget("Directory Selection")
        dir_layout = QGridLayout()
        dir_layout.setSpacing(SPACING_SM)

        lbl_root = QLabel("Photo Directory:")
        dir_layout.addWidget(lbl_root, 0, 0)

        self.cmb_root = QComboBox()
        self.cmb_root.setEditable(True)  # Allow manual input
        self.cmb_root.setToolTip("Select or enter the path to your photo directory")
        self.cmb_root.addItems(self.cached_root_dirs)
        current_index = self.cmb_root.findText(self.current_root_dir)
        if current_index != -1:
            self.cmb_root.setCurrentIndex(current_index)
        else:
            self.cmb_root.setCurrentIndex(0)
            self.cmb_root.setEditText(self.current_root_dir)
        _ = self.cmb_root.currentIndexChanged.connect(self.on_root_dir_changed)

        self.cmb_root.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.cmb_root.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _ = self.cmb_root.customContextMenuRequested.connect(self.open_context_menu)

        dir_layout.addWidget(self.cmb_root, 0, 1)

        btn_browse_root = QPushButton("Browse")
        btn_browse_root.setObjectName("tertiaryButton")
        _ = btn_browse_root.clicked.connect(self.on_browse_root)
        dir_layout.addWidget(btn_browse_root, 0, 2)

        btn_manage = QPushButton("Manage...")
        btn_manage.setObjectName("tertiaryButton")
        btn_manage.setToolTip("Manage saved directories")
        _ = btn_manage.clicked.connect(self.open_manage_directories_dialog)
        dir_layout.addWidget(btn_manage, 0, 3)

        dir_layout.setColumnStretch(0, 0)
        dir_layout.setColumnStretch(1, 1)
        dir_layout.setColumnStretch(2, 0)
        dir_layout.setColumnStretch(3, 0)

        # Add Scan button in second row of directory card
        btn_scan = QPushButton("Scan Directory")
        btn_scan.setObjectName("secondaryButton")  # Visible but not primary
        btn_scan.setToolTip("Scan the selected directory for photo collections")
        _ = btn_scan.clicked.connect(self.on_scan)
        dir_layout.addWidget(btn_scan, 1, 1, 1, 3)  # Row 1, span across columns 1-3

        dir_card.content_layout.addLayout(dir_layout)
        main_layout.addWidget(dir_card)

        # Photo Collection Selection Card
        selection_card = CardWidget("Photo Collection Selection")

        # Instruction label
        instruction_label = QLabel("Select one or more collections (Ctrl+Click for multiple):")
        instruction_label.setObjectName("instructionLabel")
        selection_card.content_layout.addWidget(instruction_label)

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

        # List and buttons layout
        list_buttons_layout = QHBoxLayout()
        list_buttons_layout.setSpacing(SPACING_MD)

        # Collections list
        self.list_slates = QListWidget()
        self.list_slates.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
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
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("tertiaryButton")
        btn_refresh.setToolTip("Warning: This will re-scan the directory and clear current selections")
        _ = btn_refresh.clicked.connect(self.on_refresh)
        selection_buttons_layout.addWidget(btn_refresh)

        selection_buttons_layout.addStretch()
        list_buttons_layout.addLayout(selection_buttons_layout)

        selection_card.content_layout.addLayout(list_buttons_layout)
        main_layout.addWidget(selection_card)

        # Gallery Options Card
        options_card = CardWidget("Gallery Options")

        # Thumbnail generation option with size selector
        thumbnail_layout = QHBoxLayout()
        thumbnail_layout.setSpacing(SPACING_SM)

        self.chk_generate_thumbnails = QCheckBox("Generate thumbnails for faster loading")
        self.chk_generate_thumbnails.setChecked(self.generate_thumbnails_pref)
        self.chk_generate_thumbnails.setToolTip(
            "When enabled, creates optimized thumbnails for faster gallery loading.\n"
            "Uses parallel processing for 5-10x faster generation.\n"
            "When disabled, uses original full-resolution images (slower but no processing needed)."
        )
        _ = self.chk_generate_thumbnails.stateChanged.connect(self.on_thumbnail_pref_changed)

        # Add thumbnail size dropdown
        thumbnail_size_label = QLabel("Size:")
        self.combo_thumbnail_size = QComboBox()
        self.combo_thumbnail_size.addItems(["600x600", "800x800", "1200x1200"])
        self.combo_thumbnail_size.setToolTip(
            "Select the thumbnail resolution:\n"
            "• 600x600: Smallest files, fastest loading (recommended for web)\n"
            "• 800x800: Balanced quality and file size\n"
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
            "When enabled, images load progressively as you scroll (better performance).\n"
            "When disabled, all images load immediately (may be slow for large galleries).\n"
            "Recommended: ON for galleries with 50+ images, OFF for small galleries."
        )
        _ = self.chk_lazy_loading.stateChanged.connect(self.on_lazy_loading_pref_changed)
        options_card.content_layout.addWidget(self.chk_lazy_loading)

        main_layout.addWidget(options_card)

        btn_generate = QPushButton("Generate Gallery")
        btn_generate.setObjectName("primaryButton")
        btn_generate.setToolTip("Generate HTML gallery from selected collections")
        _ = btn_generate.clicked.connect(self.on_generate)
        main_layout.addWidget(btn_generate)

        self.btn_generate = btn_generate

        btn_open_gallery = QPushButton("Open Gallery")
        btn_open_gallery.setObjectName("tertiaryButton")
        _ = btn_open_gallery.clicked.connect(self.on_open_gallery)
        btn_open_gallery.setEnabled(False)
        main_layout.addWidget(btn_open_gallery)

        self.btn_open_gallery = btn_open_gallery

        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("Select a photo directory and click 'Scan Directory' to begin")
        status_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # Hidden by default
        status_layout.addWidget(self.progress_bar)

        main_layout.addLayout(status_layout)

    def open_context_menu(self, position):
        menu = QMenu()
        delete_action = QAction("Delete Cached Directory", self)
        _ = delete_action.triggered.connect(self.delete_cached_directory)
        _ = menu.addAction(delete_action)
        if len(self.cached_root_dirs) <= 1:
            delete_action.setEnabled(False)
        _ = menu.exec_(self.cmb_root.mapToGlobal(position))

    @log_function
    def delete_cached_directory(self, checked=False):
        current_dir = str(self.cmb_root.currentText()).strip()
        if current_dir in self.cached_root_dirs:
            reply = QMessageBox.question(
                self,
                "Delete Cached Directory",
                f"Are you sure you want to delete the cached directory:\\n\\n{current_dir}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.cached_root_dirs.remove(current_dir)
                save_config(self.current_root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)
                index = self.cmb_root.findText(current_dir)
                if index != -1:
                    _ = self.cmb_root.blockSignals(True)
                    _ = self.cmb_root.removeItem(index)
                    _ = self.cmb_root.blockSignals(False)
                    logger.info(f"Deleted cached directory: {current_dir}")
                else:
                    logger.warning(f"Directory not found in QComboBox: {current_dir}")
                self.slates_dict = {}
                self.filtered_slates = {}
                self.unique_focal_lengths = set()
                self.list_slates.clear()
                self.update_status(f"Deleted cached directory: {current_dir}")

                if self.cached_root_dirs:
                    new_dir = self.cached_root_dirs[0]
                    self.cmb_root.setCurrentIndex(0)
                    self.current_root_dir = new_dir
                    self.on_scan()
                    logger.info(f"Switched to new current directory: {new_dir}")
                else:
                    self.current_root_dir = ""
                    self.update_status("No cached directories available. Please add a new slate directory.")
                    _ = QMessageBox.information(
                        self,
                        "No Directories",
                        "All cached directories have been deleted. Please add a new slate directory.",
                        QMessageBox.StandardButton.Ok,
                    )
                    logger.info("All cached directories deleted. Awaiting new directory selection.")
        else:
            _ = QMessageBox.warning(self, "Deletion Error", "The selected directory is not in the cached list.")
            logger.warning(f"Attempted to delete a non-cached directory: {current_dir}")

    @log_function
    def on_root_dir_changed(self, index):
        selected_dir = str(self.cmb_root.currentText()).strip()
        if selected_dir and selected_dir not in self.cached_root_dirs:
            self.update_cached_dirs(selected_dir)
            logger.info(f"New slate directory added to cache: {selected_dir}")
        self.on_scan()

    @log_function
    def update_cached_dirs(self, new_dir):
        if new_dir and new_dir not in self.cached_root_dirs:
            self.cached_root_dirs.append(new_dir)
            save_config(new_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)
            logger.info(f"Added new directory to cached slate directories: {new_dir}")

    def on_browse_root(self):
        try:
            dialog = CustomFileDialog(self, "Select Slate Directory", self.current_root_dir)
            if dialog.exec() == QFileDialog.DialogCode.Accepted:
                selected = dialog.selectedFiles()
                if selected:
                    new_dir = str(selected[0])
                    self.cmb_root.setEditText(new_dir)  # Update ComboBox
                    self.update_cached_dirs(new_dir)
                    logger.info(f"Slate directory set to: {new_dir}")
        except Exception as e:
            self.update_status(f"Error in slate directory selection: {e}")
            logger.error(f"Error in slate directory selection: {e}", exc_info=True)

    @log_function
    def open_manage_directories_dialog(self):
        """Open a dialog to manage saved directories."""
        if not self.cached_root_dirs:
            QMessageBox.information(
                self,
                "No Directories",
                "No saved directories to manage.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Create dialog
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Manage Directories")
        dialog.setText("Saved Photo Directories:")
        dialog.setInformativeText("\n".join(self.cached_root_dirs))
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Add custom "Remove Current" button if there's more than one directory
        remove_btn = None
        if len(self.cached_root_dirs) > 1:
            remove_btn = dialog.addButton("Remove Current", QMessageBox.ButtonRole.ActionRole)

        _ = dialog.exec()

        # Handle removal if button was clicked
        if remove_btn and dialog.clickedButton() == remove_btn:
            current_dir = str(self.cmb_root.currentText()).strip()
            if current_dir in self.cached_root_dirs:
                reply = QMessageBox.question(
                    self,
                    "Remove Directory",
                    f"Remove this directory from the list?\n\n{current_dir}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.cached_root_dirs.remove(current_dir)
                    save_config(
                        self.current_root_dir,
                        self.cached_root_dirs,
                        self.generate_thumbnails_pref,
                        self.thumbnail_size,
                        self.lazy_loading_pref,
                    )
                    index = self.cmb_root.findText(current_dir)
                    if index != -1:
                        self.cmb_root.removeItem(index)
                    logger.info(f"Removed directory from cache: {current_dir}")
                    self.update_status(f"Removed directory: {current_dir}")

    def on_scan(self):
        try:
            root_path = str(self.cmb_root.currentText()).strip()
            if not root_path:
                self.update_status("Please select a slate directory.")
                logger.warning("Scan initiated without specifying a slate directory.")
                return
            if not os.path.isdir(root_path):
                self.update_status("The specified slate directory does not exist.")
                logger.error(f"The specified slate directory does not exist: {root_path}")
                return

            self.current_root_dir = root_path
            self.update_cached_dirs(root_path)  # Ensure it's cached
            self.update_status("Scanning directories...")
            logger.info(f"Scanning directories: {self.current_root_dir}")
            self.progress_bar.setVisible(True)  # Show progress bar
            self.progress_bar.setValue(0)
            self.slates_dict = {}
            self.filtered_slates = {}
            self.unique_focal_lengths = set()
            self.list_slates.clear()

            # Check if cache exists
            cached_slates = self.cache_manager.load_cache(self.current_root_dir)
            if cached_slates:
                self.slates_dict = cached_slates
                self.apply_filters()
                self.update_status("Loaded slates from cache.")
                self.progress_bar.setValue(100)
                # Hide progress bar after 2 seconds
                QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
                logger.info(f"Loaded slates from cache for directory: {self.current_root_dir}")
            else:
                # Start scan thread
                self.scan_thread = ScanThread(root_path, self.cache_manager)
                _ = self.scan_thread.scan_complete.connect(self.on_scan_complete)
                _ = self.scan_thread.progress.connect(self.on_scan_progress)
                self.scan_thread.start()
                logger.debug("Scan thread started.")
        except Exception as e:
            self.update_status(f"Error initiating scan: {e}")
            logger.error(f"Error initiating scan: {e}", exc_info=True)

    def on_scan_complete(self, slates_dict, message):
        self.slates_dict = slates_dict
        self.apply_filters()
        self.update_status(message)
        self.progress_bar.setValue(100)
        # Hide progress bar after 2 seconds
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
        logger.info(f"Scan complete: {message}")

    def on_scan_progress(self, progress):
        self.progress_bar.setValue(int(progress))
        logger.debug(f"Scan progress: {int(progress)}%")

    def on_filter(self):
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

    def apply_filters_debounced(self):
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
    def apply_filters(self):
        filter_text = str(self.txt_filter.text()).strip().lower()

        # Early exit for empty filter - show all slates
        if not filter_text:
            self.filtered_slates = self.slates_dict.copy()
        else:
            # Optimized filtering with pre-computed lowercase slate names
            self.filtered_slates = {}
            for slate, data in self.slates_dict.items():
                slate_lower = slate.lower()  # Only compute once per slate
                if filter_text in slate_lower:
                    self.filtered_slates[slate] = data

        self.populate_slates_list()
        logger.info(f"Filtered slates based on filter text: '{filter_text}'")

    @log_function
    def populate_slates_list(self):
        self.list_slates.clear()
        for slate in sorted(self.filtered_slates.keys()):
            self.list_slates.addItem(slate)
        logger.debug(f"Populated slates list with {self.list_slates.count()} slates.")

    def on_select_all(self):
        try:
            for index in range(self.list_slates.count()):
                item = self.list_slates.item(index)
                item.setSelected(True)
            logger.info("All slates selected.")
        except Exception as e:
            self.update_status(f"Error selecting all slates: {e}")
            logger.error(f"Error selecting all slates: {e}", exc_info=True)

    def on_deselect_all(self):
        try:
            self.list_slates.clearSelection()
            logger.info("All slates deselected.")
        except Exception as e:
            self.update_status(f"Error deselecting all slates: {e}")
            logger.error(f"Error deselecting all slates: {e}", exc_info=True)

    def on_refresh(self):
        try:
            root_path = str(self.cmb_root.currentText()).strip()
            if not root_path:
                self.update_status("Please select a slate directory.")
                logger.warning("Refresh initiated without specifying a slate directory.")
                return
            if not os.path.isdir(root_path):
                self.update_status("The specified slate directory does not exist.")
                logger.error(f"The specified slate directory does not exist: {root_path}")
                return

            # Confirm before refreshing
            reply = QMessageBox.question(
                self,
                "Confirm Refresh",
                "This will re-scan the directory and clear your current selections.\n\n"
                "Are you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                logger.info("Refresh cancelled by user")
                return

            self.current_root_dir = root_path
            self.update_cached_dirs(root_path)  # Ensure it's cached
            self.update_status("Refreshing directories...")
            logger.info(f"Refreshing directories: {self.current_root_dir}")
            self.progress_bar.setVisible(True)  # Show progress bar
            self.progress_bar.setValue(0)
            self.slates_dict = {}
            self.filtered_slates = {}
            self.unique_focal_lengths = set()
            self.list_slates.clear()

            # Start scan thread to re-scan and update cache
            self.scan_thread = ScanThread(root_path, self.cache_manager)
            _ = self.scan_thread.scan_complete.connect(self.on_scan_complete)
            _ = self.scan_thread.progress.connect(self.on_scan_progress)
            self.scan_thread.start()
            logger.debug("Refresh scan thread started.")
        except Exception as e:
            self.update_status(f"Error initiating refresh: {e}")
            logger.error(f"Error initiating refresh: {e}", exc_info=True)

    def on_generate(self):
        try:
            selected_items = self.list_slates.selectedItems()
            if not selected_items:
                self.update_status("Please select at least one slate.")
                logger.warning("Generate gallery initiated without selecting any slates.")
                return

            selected_slates = [str(item.text()) for item in selected_items]
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
                cache_manager=self.cache_manager,
                output_dir=output,
                root_dir=self.current_root_dir,
                template_path=template_path,
                generate_thumbnails=self.chk_generate_thumbnails.isChecked(),
                thumbnail_size=self.thumbnail_size,
                lazy_loading=self.chk_lazy_loading.isChecked()
            )
            _ = self.gallery_thread.gallery_complete.connect(self.on_gallery_complete)
            _ = self.gallery_thread.progress.connect(self.on_gallery_progress)
            self.gallery_thread.start()
            logger.debug("Gallery generation thread started.")
        except Exception as e:
            self.update_status(f"Error initiating gallery generation: {e}")
            self.btn_generate.setEnabled(True)
            logger.error(f"Error initiating gallery generation: {e}", exc_info=True)

    def on_gallery_complete(self, success, message):
        self.update_status(message)
        self.progress_bar.setValue(100 if success else 0)
        # Hide progress bar after 2 seconds
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
        self.btn_generate.setEnabled(True)
        if success:
            self.btn_open_gallery.setEnabled(True)
        else:
            self.btn_open_gallery.setEnabled(False)
        logger.info(f"Gallery generation result: {message}")

    def on_gallery_progress(self, progress):
        self.progress_bar.setValue(int(progress))
        logger.debug(f"Gallery generation progress: {int(progress)}%")

    def on_open_gallery(self):
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
                self.btn_open_gallery.setEnabled(False)
        except Exception as e:
            self.update_status(f"Error opening gallery: {e}")
            logger.error(f"Error opening gallery: {e}", exc_info=True)

    @log_function
    def update_status(self, message):
        self.lbl_status.setText(f"{message}")
        logger.info(f"Status updated: {message}")

    def on_thumbnail_pref_changed(self):
        """Save thumbnail preference when checkbox state changes."""
        self.generate_thumbnails_pref = self.chk_generate_thumbnails.isChecked()
        # Enable/disable size dropdown based on checkbox state
        self.combo_thumbnail_size.setEnabled(self.generate_thumbnails_pref)
        save_config(self.current_root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)

    def on_thumbnail_size_changed(self, text):
        """Save thumbnail size preference when dropdown changes."""
        if text:
            # Extract the size number from the text (e.g., "600x600" -> 600)
            if 'x' in text:
                size_str = text.split('x')[0].strip()
                try:
                    self.thumbnail_size = int(size_str)
                    save_config(self.current_root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)
                    logger.info(f"Thumbnail size changed to: {self.thumbnail_size}")
                except ValueError:
                    logger.error(f"Invalid thumbnail size format: {text}")
            else:
                logger.error(f"Invalid thumbnail size format (missing 'x'): {text}")

    def on_lazy_loading_pref_changed(self):
        """Save lazy loading preference when checkbox state changes."""
        self.lazy_loading_pref = self.chk_lazy_loading.isChecked()
        save_config(self.current_root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)
        logger.info(f"Lazy loading preference changed to: {self.lazy_loading_pref}")

    @override
    def closeEvent(self, event):
        try:
            # Stop and wait for running threads
            if self.scan_thread and self.scan_thread.isRunning():
                logger.info("Stopping scan thread...")
                self.scan_thread.stop()

            if self.gallery_thread and self.gallery_thread.isRunning():
                logger.info("Stopping gallery generation thread...")
                self.gallery_thread.stop()

            # Stop filter timer
            self.filter_timer.stop()

            # Ensure clean shutdown
            self.cache_manager.shutdown()
            logger.info("Cache manager shutdown successfully.")

            # Save configuration
            root_dir = str(self.cmb_root.currentText()).strip()
            save_config(root_dir, self.cached_root_dirs, self.generate_thumbnails_pref, self.thumbnail_size, self.lazy_loading_pref)

            event.accept()
            logger.info("Application closed.")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}", exc_info=True)
            event.accept()


# ----------------------------- Main Execution -----------------------------


def main():
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
