#!/usr/bin/env python3

"""
Main entry point for SlateGallery - uses new modular structure
while maintaining identical functionality to the original.
"""

# System imports
import os
import sys
import webbrowser

# Add src to path for imports
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

# Qt imports
from core.cache_manager import ImprovedCacheManager
from core.config_manager import load_config, save_config
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
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

# Import from our new modular structure
from utils.logging_config import log_function, logger
from utils.threading import GenerateGalleryThread, ScanThread

# ----------------------------- Custom File Dialog -----------------------------


class CustomFileDialog(QFileDialog):
    def __init__(self, *args):
        QFileDialog.__init__(self, *args)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.FileMode.Directory)

        # Create path input widget (though it appears unused in current implementation)
        self.path_input = QLineEdit()

        self.directoryEntered.connect(self.update_path_input)

        current_path = self.directory().absolutePath()
        self.update_path_input(current_path)

    @log_function
    def navigate_to_path(self):
        path = str(self.path_input.text())
        if os.path.exists(path):
            self.setDirectory(path)
        else:
            QMessageBox.warning(self, "Invalid Path", "The specified path does not exist.")
            logger.warning(f"User attempted to navigate to invalid path: {path}")

    @log_function
    def update_path_input(self, path):
        path = str(path)
        self.path_input.setText(path)
        logger.debug(f"Directory changed to: {path}")


# ----------------------------- Main Application -----------------------------


class GalleryGeneratorApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Slate Photography Gallery Generator")
        self.setGeometry(100, 100, 900, 700)

        # Load configuration with multiple directories
        self.current_root_dir, self.cached_root_dirs = load_config()
        self.output_dir = os.path.expanduser("~")

        self.cache_manager = ImprovedCacheManager(
            base_dir=os.path.expanduser("~/.slate_gallery"), max_workers=4, batch_size=100
        )

        if not self.current_root_dir:
            self.current_root_dir = os.path.expanduser("~")
            self.cached_root_dirs.append(self.current_root_dir)
            save_config(self.current_root_dir, self.cached_root_dirs)
            logger.info(f"Default root directory set to home directory: {self.current_root_dir}")

        self.slates_dict = {}
        self.filtered_slates = {}
        self.unique_focal_lengths = set()

        # Set up debounced filtering timer
        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)  # Only fire once per timeout period
        self.filter_timer.timeout.connect(self.apply_filters_debounced)
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
                self.update_status("Loaded slates from cache.")
                # Note: Progress bar stays at 0 - it only shows progress during active operations
            else:
                self.update_status("No cache found. Please scan directories.")

    def setup_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FAFAFA;
            }
            QPushButton {
                background-color: #90CAF9;
                color: #1A237E;
                border: none;
                padding: 8px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #64B5F6;
            }
            QPushButton:pressed {
                background-color: #42A5F5;
            }
            QPushButton:disabled {
                background-color: #E0E0E0;
                color: #9E9E9E;
            }
            QLabel {
                color: #37474F;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                padding: 6px;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: white;
                color: #424242;
            }
            QListWidget {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
            }
            QListWidget::item:hover {
                background-color: #F5F5F5;
            }
            QProgressBar {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: #FAFAFA;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #90CAF9;
                border-radius: 3px;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #1976D2;
            }
            QCheckBox {
                font-weight: bold;
                color: #37474F;
            }
        """)

    def initUI(self):
        # Central widget with margin
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with margins
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        central_widget.setLayout(main_layout)

        dir_group = QGroupBox("Directory Selection")
        dir_layout = QGridLayout()
        dir_group.setLayout(dir_layout)

        lbl_root = QLabel("Slate Directory:")
        dir_layout.addWidget(lbl_root, 0, 0)

        self.cmb_root = QComboBox()
        self.cmb_root.setEditable(True)  # Allow manual input
        self.cmb_root.addItems(self.cached_root_dirs)
        current_index = self.cmb_root.findText(self.current_root_dir)
        if current_index != -1:
            self.cmb_root.setCurrentIndex(current_index)
        else:
            self.cmb_root.setCurrentIndex(0)
            self.cmb_root.setEditText(self.current_root_dir)
        self.cmb_root.currentIndexChanged.connect(self.on_root_dir_changed)

        self.cmb_root.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.cmb_root.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cmb_root.customContextMenuRequested.connect(self.open_context_menu)

        dir_layout.addWidget(self.cmb_root, 0, 1)

        btn_browse_root = QPushButton("Browse")
        btn_browse_root.clicked.connect(self.on_browse_root)
        dir_layout.addWidget(btn_browse_root, 0, 2)

        dir_layout.setColumnStretch(0, 0)
        dir_layout.setColumnStretch(1, 1)
        dir_layout.setColumnStretch(2, 0)

        main_layout.addWidget(dir_group)

        # Scan button
        btn_scan = QPushButton("Scan Directories and List Slates")
        btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #90CAF9;
                color: #1A237E;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #64B5F6;
            }
        """)
        btn_scan.clicked.connect(self.on_scan)
        main_layout.addWidget(btn_scan)

        # Filter group
        filter_group = QGroupBox("Slate Selection")
        filter_layout = QVBoxLayout()
        filter_group.setLayout(filter_layout)

        # Filter input
        filter_input_layout = QHBoxLayout()
        lbl_filter = QLabel("Filter Slates:")
        filter_input_layout.addWidget(lbl_filter)

        self.txt_filter = QLineEdit()
        self.txt_filter.textChanged.connect(self.on_filter)
        filter_input_layout.addWidget(self.txt_filter)

        filter_layout.addLayout(filter_input_layout)

        # List and buttons layout
        list_buttons_layout = QHBoxLayout()

        # Slates list
        self.list_slates = QListWidget()
        self.list_slates.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        list_buttons_layout.addWidget(self.list_slates)

        # Selection buttons
        selection_buttons_layout = QVBoxLayout()

        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(self.on_select_all)
        selection_buttons_layout.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(self.on_deselect_all)
        selection_buttons_layout.addWidget(btn_deselect_all)

        # Add Refresh button
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.on_refresh)

        # Apply custom stylesheet for the Refresh button
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;  /* Dark Blue background */
                color: white;               /* White text */
                border: none;
                padding: 8px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0D47A1;  /* Darker blue on hover */
            }
            QPushButton:pressed {
                background-color: #0A3888;  /* Even darker on press */
            }
            QPushButton:disabled {
                background-color: #E0E0E0;  /* Gray background when disabled */
                color: #9E9E9E;             /* Gray text when disabled */
            }
        """)

        selection_buttons_layout.addWidget(btn_refresh)

        selection_buttons_layout.addStretch()
        list_buttons_layout.addLayout(selection_buttons_layout)

        filter_layout.addLayout(list_buttons_layout)
        main_layout.addWidget(filter_group)

        btn_generate = QPushButton("Generate Gallery")
        btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #A5D6A7;
                color: #1B5E20;
                font-weight: bold;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #81C784;
            }
            QPushButton:disabled {
                background-color: #E0E0E0;
                color: #9E9E9E;
            }
        """)
        btn_generate.clicked.connect(self.on_generate)
        main_layout.addWidget(btn_generate)

        self.btn_generate = btn_generate

        btn_open_gallery = QPushButton("Open Generated Gallery")
        btn_open_gallery.setStyleSheet("""
            QPushButton {
                background-color: #FFD54F;
                color: #BF360C;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #FFB74D;
            }
            QPushButton:disabled {
                background-color: #E0E0E0;
                color: #9E9E9E;
            }
        """)
        btn_open_gallery.clicked.connect(self.on_open_gallery)
        btn_open_gallery.setEnabled(False)
        main_layout.addWidget(btn_open_gallery)

        self.btn_open_gallery = btn_open_gallery

        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("Idle")
        status_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)

        main_layout.addLayout(status_layout)

    def open_context_menu(self, position):
        menu = QMenu()
        delete_action = QAction("Delete Cached Directory", self)
        delete_action.triggered.connect(self.delete_cached_directory)
        menu.addAction(delete_action)
        if len(self.cached_root_dirs) <= 1:
            delete_action.setEnabled(False)
        menu.exec_(self.cmb_root.mapToGlobal(position))

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
                save_config(self.current_root_dir, self.cached_root_dirs)
                index = self.cmb_root.findText(current_dir)
                if index != -1:
                    self.cmb_root.blockSignals(True)
                    self.cmb_root.removeItem(index)
                    self.cmb_root.blockSignals(False)
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
                    QMessageBox.information(
                        self,
                        "No Directories",
                        "All cached directories have been deleted. Please add a new slate directory.",
                        QMessageBox.StandardButton.Ok,
                    )
                    logger.info("All cached directories deleted. Awaiting new directory selection.")
        else:
            QMessageBox.warning(self, "Deletion Error", "The selected directory is not in the cached list.")
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
            save_config(new_dir, self.cached_root_dirs)
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
                logger.info(f"Loaded slates from cache for directory: {self.current_root_dir}")
            else:
                # Start scan thread
                self.scan_thread = ScanThread(root_path, self.cache_manager)
                self.scan_thread.scan_complete.connect(self.on_scan_complete)
                self.scan_thread.progress.connect(self.on_scan_progress)
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

            self.current_root_dir = root_path
            self.update_cached_dirs(root_path)  # Ensure it's cached
            self.update_status("Refreshing directories...")
            logger.info(f"Refreshing directories: {self.current_root_dir}")
            self.progress_bar.setValue(0)
            self.slates_dict = {}
            self.filtered_slates = {}
            self.unique_focal_lengths = set()
            self.list_slates.clear()

            # Start scan thread to re-scan and update cache
            self.scan_thread = ScanThread(root_path, self.cache_manager)
            self.scan_thread.scan_complete.connect(self.on_scan_complete)
            self.scan_thread.progress.connect(self.on_scan_progress)
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
                generate_thumbnails=True,  # Enable thumbnail generation for performance
            )
            self.gallery_thread.gallery_complete.connect(self.on_gallery_complete)
            self.gallery_thread.progress.connect(self.on_gallery_progress)
            self.gallery_thread.start()
            logger.debug("Gallery generation thread started.")
        except Exception as e:
            self.update_status(f"Error initiating gallery generation: {e}")
            self.btn_generate.setEnabled(True)
            logger.error(f"Error initiating gallery generation: {e}", exc_info=True)

    def on_gallery_complete(self, success, message):
        self.update_status(message)
        self.progress_bar.setValue(100 if success else 0)
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
                webbrowser.open(url, new=2)  # new=2 opens in a new window if possible
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

    def closeEvent(self, event):
        try:
            # Ensure clean shutdown
            self.cache_manager.shutdown()
            logger.info("Cache manager shutdown successfully.")
            # Save configuration
            root_dir = str(self.cmb_root.currentText()).strip()
            save_config(root_dir, self.cached_root_dirs)
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
        app.setStyleSheet("""
            QMessageBox {
                background-color: #FFFFFF;
            }
            QMessageBox QLabel {
                color: #424242;
            }
            QMessageBox QPushButton {
                background-color: #90CAF9;
                color: #1A237E;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #64B5F6;
            }
            QFileDialog {
                background-color: #FFFFFF;
            }
            QFileDialog QTreeView {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QFileDialog QTreeView::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
            }
            QFileDialog QTreeView::item:hover {
                background-color: #F5F5F5;
            }
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
