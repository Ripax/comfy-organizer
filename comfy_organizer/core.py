"""Core UI and startup for ComfyUI Model Organizer."""

import os
import shutil
import sys
import configparser
from datetime import datetime

from PySide6.QtCore import QDir, Qt, Signal, QSize, QSortFilterProxyModel
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTreeView,
    QListView,
    QFileSystemModel,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QTextEdit,
)

from .icons import FileIconProvider, app_icon
from .qss import load_stylesheet
from .splash import OrganizerSplashScreen
from .utils import (
    DEFAULT_FILTER_EXTENSIONS,
    MODEL_EXTENSIONS as MODEL_FILE_EXTENSIONS,
    folder_size,
    format_size,
    load_panel_filter,
    load_panel_paths,
    read_safetensors_details,
)


# ============================================================================
# FILE SYSTEM MODEL WITH FOLDER SIZES
# ============================================================================

class FolderSizeFileSystemModel(QFileSystemModel):

    MODEL_EXTENSIONS = MODEL_FILE_EXTENSIONS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder_size_cache = {}
        self.icon_provider = FileIconProvider()

    @staticmethod
    def format_size(size):
        return format_size(size)

    def folder_size(self, folder_path):
        folder_path = os.path.abspath(folder_path)

        if folder_path in self._folder_size_cache:
            return self._folder_size_cache[folder_path]

        size = folder_size(folder_path)
        self._folder_size_cache[folder_path] = size
        return size

    def clear_folder_size_cache(self):
        self._folder_size_cache.clear()
        self.icon_provider.clear_preview_cache()

    @staticmethod
    def size_color(size):
        if size >= 50 * 1024 ** 3:
            return QColor("#ff6b6b")
        if size >= 10 * 1024 ** 3:
            return QColor("#ffa94d")
        if size >= 1 * 1024 ** 3:
            return QColor("#ffd43b")
        return QColor("#69db7c")

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and index.column() == 0:
            folder_path = self.filePath(index)

            if self.isDir(index):
                size = self.folder_size(folder_path)

                if role == Qt.DisplayRole:
                    name = super().data(index, role)
                    return f"{name}\n{self.format_size(size)}"

                if role == Qt.ToolTipRole:
                    name = super().data(index, Qt.DisplayRole)
                    return f"{name}\nFolder size: {self.format_size(size)} ({size:,} bytes)"

                if role == Qt.ForegroundRole:
                    return QBrush(self.size_color(size))
            elif role == Qt.DecorationRole:
                icon = self.icon_provider.icon_for_file(folder_path)
                if icon is not None:
                    return icon

        return super().data(index, role)


class LeftPanelFilterModel(QSortFilterProxyModel):

    def __init__(
        self,
        filter_extensions=DEFAULT_FILTER_EXTENSIONS,
        only_show=True,
        parent=None
    ):
        super().__init__(parent)
        self.filter_extensions = frozenset(filter_extensions)
        self.only_show = only_show

    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        if source_model is None:
            return False

        source_index = source_model.index(
            source_row,
            0,
            source_parent
        )

        if source_model.isDir(source_index):
            return True

        extension = os.path.splitext(
            source_model.fileName(source_index)
        )[1].lower()
        is_filtered = extension in self.filter_extensions
        return is_filtered if self.only_show else not is_filtered

    def filePath(self, index):
        if not index.isValid():
            return ""
        return self.sourceModel().filePath(
            self.mapToSource(index)
        )

    def isDir(self, index):
        if not index.isValid():
            return False
        return self.sourceModel().isDir(
            self.mapToSource(index)
        )

    def rootPath(self):
        return self.sourceModel().rootPath()


# ============================================================================
# LEFT TREE VIEW
# ============================================================================

class StagedTreeView(QTreeView):
    """Filesystem tree with staged drag/drop operations."""

    move_queued = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)

        self.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        index = self.indexAt(event.position().toPoint())
        model = self.model()

        if index.isValid():
            destination = model.filePath(index)

            if not model.isDir(index):
                destination = os.path.dirname(destination)
        else:
            root_index = self.rootIndex()
            destination = (
                model.filePath(root_index)
                if root_index.isValid()
                else model.rootPath()
            )

        self.queue_urls(
            event.mimeData().urls(),
            destination
        )

        event.acceptProposedAction()

    def queue_urls(self, urls, destination):
        for url in urls:
            source = url.toLocalFile()

            if not source or not os.path.exists(source):
                continue

            if not self.is_valid_destination(
                source,
                destination
            ):
                continue

            self.move_queued.emit(
                source,
                destination
            )

    @staticmethod
    def is_valid_destination(source, destination):
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)

        if source == destination:
            return False

        try:
            common = os.path.commonpath(
                [source, destination]
            )

            if common == source:
                return False

        except ValueError:
            return False

        return True


# ============================================================================
# RIGHT GRID VIEW
# ============================================================================

class StagedGridView(QListView):
    """Filesystem icon/grid view with staged drag/drop operations."""

    move_queued = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        self.setDragDropMode(
            QAbstractItemView.DragDrop
        )

        self.setDefaultDropAction(
            Qt.CopyAction
        )

        self.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

        # ------------------------------------------------------------
        # Grid configuration
        # ------------------------------------------------------------

        self.setViewMode(
            QListView.IconMode
        )

        self.setFlow(
            QListView.LeftToRight
        )

        self.setWrapping(True)

        self.setResizeMode(
            QListView.Adjust
        )

        self.setMovement(
            QListView.Static
        )

        self.setSpacing(8)

        self.setIconSize(
            QSize(64, 64)
        )

        self.setGridSize(
            QSize(130, 110)
        )

        self.setWordWrap(True)

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        model = self.model()

        index = self.indexAt(
            event.position().toPoint()
        )

        if index.isValid():

            destination = model.filePath(index)

            if not model.isDir(index):
                destination = os.path.dirname(
                    destination
                )

        else:

            root_index = self.rootIndex()

            if root_index.isValid():
                destination = model.filePath(
                    root_index
                )
            else:
                destination = model.rootPath()

        self.queue_urls(
            event.mimeData().urls(),
            destination
        )

        event.acceptProposedAction()

    def queue_urls(self, urls, destination):

        for url in urls:

            source = url.toLocalFile()

            if not source:
                continue

            if not os.path.exists(source):
                continue

            if not self.is_valid_destination(
                source,
                destination
            ):
                continue

            self.move_queued.emit(
                source,
                destination
            )

    @staticmethod
    def is_valid_destination(source, destination):

        source = os.path.abspath(source)
        destination = os.path.abspath(destination)

        if source == destination:
            return False

        try:

            common = os.path.commonpath(
                [source, destination]
            )

            if common == source:
                return False

        except ValueError:
            return False

        return True


# ============================================================================
# MAIN WINDOW
# ============================================================================

class ComfyUIModelOrganizer(QMainWindow):

    def __init__(
        self,
        left_root_path,
        right_root_path=None,
        filter_extensions=None,
        only_show=True,
        startup_progress=None
    ):
        super().__init__()

        self.left_root_path = os.path.abspath(
            left_root_path
        )
        self.right_root_path = os.path.abspath(
            right_root_path
            if right_root_path is not None
            else left_root_path
        )
        self.filter_extensions = frozenset(
            DEFAULT_FILTER_EXTENSIONS
            if filter_extensions is None
            else filter_extensions
        )
        self.only_show = only_show
        self.startup_progress = startup_progress
        self._expanded_folder_count = 0

        self.setWindowIcon(app_icon())

        self.setWindowTitle(
            "ComfyUI Model Organizer"
        )

        self.resize(
            1400,
            900
        )
        self.setMinimumSize(
            980,
            650
        )

        self._report_startup_progress(38, "Preparing filesystem model...")
        self.setup_model()
        self._report_startup_progress(52, "Building folder panels...")
        self.setup_ui()
        self._report_startup_progress(92, "Applying the interface theme...")
        self.apply_dark_theme()

    def _report_startup_progress(self, value, message):
        if self.startup_progress is not None:
            self.startup_progress(value, message)

    # ========================================================================
    # FILE SYSTEM MODEL
    # ========================================================================

    def setup_model(self):

        self.model = FolderSizeFileSystemModel()

        self.model.setReadOnly(True)

        self.model.setFilter(
            QDir.NoDotAndDotDot
            | QDir.AllDirs
            | QDir.Files
        )

        self.model.setRootPath(
            self.left_root_path
        )

        self.left_filter_model = LeftPanelFilterModel(
            self.filter_extensions,
            self.only_show,
            self
        )
        self.left_filter_model.setSourceModel(self.model)

    # ========================================================================
    # UI
    # ========================================================================

    def setup_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        main_layout = QVBoxLayout(
            central
        )

        main_layout.setContentsMargins(
            10,
            10,
            10,
            10
        )

        main_layout.setSpacing(10)

        header = QWidget()
        header.setObjectName("appHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 4)
        header_layout.setSpacing(2)

        title = QLabel("ComfyUI Model Organizer")
        title.setObjectName("appTitle")
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Browse model folders, inspect files, and stage safe moves."
        )
        subtitle.setObjectName("appSubtitle")
        header_layout.addWidget(subtitle)
        main_layout.addWidget(header)

        # --------------------------------------------------------------------
        # Main vertical splitter
        # --------------------------------------------------------------------

        splitter = QSplitter(
            Qt.Vertical
        )

        main_layout.addWidget(
            splitter
        )

        # --------------------------------------------------------------------
        # Top area
        # --------------------------------------------------------------------

        top_container = QWidget()

        top_layout = QHBoxLayout(
            top_container
        )

        top_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        top_layout.setSpacing(6)

        # Left
        self.left_tree = self.create_tree_view()

        # Right
        self.right_grid = self.create_grid_view()

        left_panel = QWidget()
        left_panel.setObjectName("browserPanel")
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(6)

        folder_heading = QLabel("SOURCE FOLDERS")
        folder_heading.setObjectName("paneTitle")
        left_panel_layout.addWidget(folder_heading)
        left_panel_layout.addWidget(self.left_tree, 1)

        right_panel = QWidget()
        right_panel.setObjectName("browserPanel")
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(6)

        content_header = QHBoxLayout()
        content_heading = QLabel("DESTINATION / CONTENTS")
        content_heading.setObjectName("paneTitle")
        content_header.addWidget(content_heading)
        content_header.addStretch()
        right_panel_layout.addLayout(content_header)
        right_panel_layout.addWidget(self.right_grid, 1)

        top_layout.addWidget(left_panel, 1)
        top_layout.addWidget(right_panel, 2)

        splitter.addWidget(
            top_container
        )

        # --------------------------------------------------------------------
        # Bottom queue
        # --------------------------------------------------------------------

        bottom_container = QWidget()

        bottom_layout = QVBoxLayout(
            bottom_container
        )

        bottom_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        bottom_layout.setSpacing(8)

        queue_header = QHBoxLayout()

        queue_title = QLabel("STAGED MOVES")

        queue_title.setObjectName(
            "queueTitle"
        )

        queue_header.addWidget(queue_title)
        queue_header.addStretch()

        self.queue_count_label = QLabel("0 staged")
        self.queue_count_label.setObjectName("queueCount")
        queue_header.addWidget(self.queue_count_label)
        bottom_layout.addLayout(queue_header)

        # --------------------------------------------------------------------
        # Queue table
        # --------------------------------------------------------------------

        self.queue_table = QTableWidget(
            0,
            2
        )

        self.queue_table.setHorizontalHeaderLabels(
            [
                "Source File",
                "Destination Folder"
            ]
        )

        self.queue_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.Stretch
        )

        self.queue_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.Stretch
        )

        self.queue_table.verticalHeader().setVisible(
            False
        )

        self.queue_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.queue_table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.queue_table.setAlternatingRowColors(
            True
        )

        bottom_layout.addWidget(
            self.queue_table
        )

        # --------------------------------------------------------------------
        # Buttons
        # --------------------------------------------------------------------

        button_layout = QHBoxLayout()

        self.btn_refresh = QPushButton(
            "Refresh View"
        )

        self.btn_refresh.setObjectName(
            "refreshBtn"
        )

        self.btn_refresh.clicked.connect(
            self.refresh_views
        )

        self.btn_parent = QPushButton(
            "Parent Folder"
        )

        self.btn_parent.setObjectName(
            "parentBtn"
        )

        self.btn_parent.setEnabled(
            False
        )

        self.btn_parent.clicked.connect(
            self.open_parent_folder
        )

        self.btn_clear = QPushButton(
            "Clear Queue"
        )

        self.btn_clear.setObjectName(
            "clearBtn"
        )

        self.btn_clear.clicked.connect(
            self.clear_queue
        )

        self.btn_commit = QPushButton(
            "Commit Moves"
        )

        self.btn_commit.setObjectName(
            "commitBtn"
        )

        self.btn_commit.clicked.connect(
            self.commit_moves
        )

        button_layout.addWidget(
            self.btn_refresh
        )

        button_layout.addWidget(
            self.btn_parent
        )

        button_layout.addStretch()

        button_layout.addWidget(
            self.btn_clear
        )

        button_layout.addWidget(
            self.btn_commit
        )

        bottom_layout.addLayout(
            button_layout
        )

        splitter.addWidget(
            bottom_container
        )

        # --------------------------------------------------------------------
        # Splitter ratio
        # --------------------------------------------------------------------

        splitter.setSizes(
            [
                600,
                250
            ]
        )

        self.statusBar().showMessage(
            "Double-click folders to browse. Drag files to stage moves; commit when ready."
        )
        self.update_queue_count()

    # ========================================================================
    # LEFT TREE
    # ========================================================================

    def create_tree_view(self):

        tree = StagedTreeView()

        tree.setModel(self.left_filter_model)

        root_index = self.left_filter_model.mapFromSource(
            self.model.index(self.left_root_path)
        )

        tree.setRootIndex(
            root_index
        )

        tree.setSortingEnabled(
            True
        )

        tree.setColumnWidth(
            0,
            300
        )

        # Only show the Name column
        tree.setColumnHidden(1, True)
        tree.setColumnHidden(2, True)
        tree.setColumnHidden(3, True)

        tree.move_queued.connect(
            self.add_to_queue
        )

        tree.clicked.connect(
            self.show_model_details
        )

        # Expand the complete folder hierarchy
        self.expand_tree_hierarchy(
            tree,
            root_index
        )

        return tree

    def expand_tree_hierarchy(self, tree, parent_index):
        """
        Recursively expand every folder in the left tree.
        """

        if not parent_index.isValid():
            return

        self._expanded_folder_count += 1
        if self._expanded_folder_count % 20 == 0:
            progress = min(
                88,
                55 + self._expanded_folder_count // 10
            )
            self._report_startup_progress(
                progress,
                f"Indexing folders... {self._expanded_folder_count}"
            )

        tree.expand(
            parent_index
        )

        model = tree.model()

        row_count = model.rowCount(
            parent_index
        )

        for row in range(row_count):

            child_index = model.index(
                row,
                0,
                parent_index
            )

            if not child_index.isValid():
                continue

            if model.isDir(child_index):
                self.expand_tree_hierarchy(
                    tree,
                    child_index
                )


    # ========================================================================
    # RIGHT GRID
    # ========================================================================

    def create_grid_view(self):

        grid = StagedGridView()

        grid.setModel(
            self.model
        )

        grid.setRootIndex(
            self.model.index(
                self.right_root_path
            )
        )

        grid.move_queued.connect(
            self.add_to_queue
        )

        grid.doubleClicked.connect(
            self.open_folder_from_grid
        )

        grid.clicked.connect(
            self.show_model_details
        )

        return grid

    def open_folder_from_grid(self, index):

        if not index.isValid():
            return

        if self.model.isDir(index):
            self.open_folder(
                self.model.filePath(index)
            )

    def open_folder(self, folder_path):

        folder_path = os.path.abspath(folder_path)

        if not os.path.isdir(folder_path):
            return

        folder_index = self.model.index(folder_path)

        if not folder_index.isValid():
            return

        self.right_grid.setRootIndex(folder_index)
        self.statusBar().showMessage(
            f"Browsing: {folder_path}",
            5000
        )

        if hasattr(
            self,
            "btn_parent"
        ):
            self.btn_parent.setEnabled(
                folder_path != self.right_root_path
            )

    def show_model_details(self, index):

        if index.model() is self.left_filter_model:
            index = self.left_filter_model.mapToSource(index)

        if not index.isValid() or self.model.isDir(index):
            return

        file_path = self.model.filePath(index)
        extension = os.path.splitext(file_path)[1].lower()
        if extension not in FolderSizeFileSystemModel.MODEL_EXTENSIONS:
            return

        lines = [
            f"Name: {os.path.basename(file_path)}",
            f"Format: {extension.lstrip('.').upper()}",
            f"Location: {file_path}",
        ]

        try:
            file_stat = os.stat(file_path)
            lines.extend(
                [
                    f"Size: {FolderSizeFileSystemModel.format_size(file_stat.st_size)}",
                    f"Size in bytes: {file_stat.st_size:,}",
                    f"Created: {datetime.fromtimestamp(file_stat.st_ctime).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
                    f"Modified: {datetime.fromtimestamp(file_stat.st_mtime).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
                ]
            )
        except OSError as exc:
            lines.append(f"File details could not be read: {exc}")

        if extension == ".safetensors":
            lines.extend(
                read_safetensors_details(file_path)
            )
        else:
            lines.extend(
                [
                    "",
                    "Embedded contents were not inspected. Some model formats "
                    "use executable serialization and are not safe to load "
                    "just to display details."
                ]
            )

        if not hasattr(self, "_model_details_dialog"):
            self._model_details_dialog = QDialog(self)
            self._model_details_dialog.resize(620, 520)
            self._model_details_text = QTextEdit(
                self._model_details_dialog
            )
            self._model_details_text.setReadOnly(True)

            dialog_layout = QVBoxLayout(
                self._model_details_dialog
            )
            dialog_layout.addWidget(
                self._model_details_text
            )

            buttons = QDialogButtonBox(
                QDialogButtonBox.Close,
                parent=self._model_details_dialog
            )
            buttons.rejected.connect(
                self._model_details_dialog.hide
            )
            dialog_layout.addWidget(buttons)

        self._model_details_dialog.setWindowTitle(
            f"Model Details - {os.path.basename(file_path)}"
        )
        self._model_details_text.setPlainText(
            "\n".join(lines)
        )
        self.statusBar().showMessage(
            f"Selected model: {os.path.basename(file_path)}",
            5000
        )
        self._model_details_dialog.show()
        self._model_details_dialog.raise_()
        self._model_details_dialog.activateWindow()

    # ========================================================================
    # ADD TO QUEUE
    # ========================================================================

    def add_to_queue(
        self,
        source,
        destination
    ):

        source = os.path.abspath(
            source
        )

        destination = os.path.abspath(
            destination
        )

        # ------------------------------------------------------------
        # Prevent duplicate source
        # ------------------------------------------------------------

        for row in range(
            self.queue_table.rowCount()
        ):

            item = self.queue_table.item(
                row,
                0
            )

            if item is None:
                continue

            if os.path.abspath(
                item.text()
            ) == source:

                return

        # ------------------------------------------------------------
        # Add queue row
        # ------------------------------------------------------------

        row = self.queue_table.rowCount()

        self.queue_table.insertRow(
            row
        )

        self.queue_table.setItem(
            row,
            0,
            QTableWidgetItem(
                source
            )
        )

        self.queue_table.setItem(
            row,
            1,
            QTableWidgetItem(
                destination
            )
        )

        self.queue_table.scrollToBottom()
        self.update_queue_count()

    # ========================================================================
    # CLEAR QUEUE
    # ========================================================================

    def clear_queue(self):

        self.queue_table.setRowCount(
            0
        )
        self.update_queue_count()

    def update_queue_count(self):

        if not hasattr(self, "queue_table"):
            return

        count = self.queue_table.rowCount()
        self.queue_count_label.setText(
            f"{count} staged"
            if count != 1
            else "1 staged"
        )
        self.btn_commit.setEnabled(count > 0)
        self.btn_clear.setEnabled(count > 0)

    # ========================================================================
    # REFRESH
    # ========================================================================

    def refresh_views(self):

        self.model.clear_folder_size_cache()
        self.model.setRootPath("")

        self.model.setRootPath(
            self.left_root_path
        )

        left_root_index = self.left_filter_model.mapFromSource(
            self.model.index(self.left_root_path)
        )
        right_root_index = self.model.index(
            self.right_root_path
        )

        self.left_tree.setRootIndex(
            left_root_index
        )

        self.right_grid.setRootIndex(
            right_root_index
        )

        if hasattr(
            self,
            "btn_parent"
        ):
            self.btn_parent.setEnabled(
                False
            )

        # Always reopen the complete hierarchy
        self.expand_tree_hierarchy(
            self.left_tree,
            left_root_index
        )

        self.left_tree.viewport().update()
        self.right_grid.viewport().update()
        self.statusBar().showMessage(
            "Model folders refreshed.",
            3000
        )

    def open_parent_folder(self):

        root_index = self.right_grid.rootIndex()

        if not root_index.isValid():
            return

        folder_path = self.model.filePath(
            root_index
        )

        parent_path = os.path.dirname(
            os.path.abspath(folder_path)
        )

        if (
            os.path.commonpath(
                [
                    os.path.abspath(parent_path),
                    self.right_root_path
                ]
            ) != self.right_root_path
        ):
            return

        self.open_folder(parent_path)

    # ========================================================================
    # COMMIT MOVES
    # ========================================================================

    def commit_moves(self):

        count = self.queue_table.rowCount()

        if count == 0:

            QMessageBox.information(
                self,
                "Nothing to Commit",
                "There are no pending operations."
            )

            return

        success_count = 0
        error_count = 0

        errors = []

        # ------------------------------------------------------------
        # Process queue
        # ------------------------------------------------------------

        for row in range(count):

            source_item = self.queue_table.item(
                row,
                0
            )

            destination_item = self.queue_table.item(
                row,
                1
            )

            if not source_item or not destination_item:
                continue

            source = source_item.text()
            destination_folder = destination_item.text()

            filename = os.path.basename(
                source
            )

            final_destination = os.path.join(
                destination_folder,
                filename
            )

            try:

                # ----------------------------------------------------
                # Check source
                # ----------------------------------------------------

                if not os.path.exists(source):

                    error_count += 1

                    errors.append(
                        f"Source missing:\n{source}"
                    )

                    continue

                # ----------------------------------------------------
                # Check destination
                # ----------------------------------------------------

                if not os.path.isdir(
                    destination_folder
                ):

                    error_count += 1

                    errors.append(
                        f"Destination missing:\n"
                        f"{destination_folder}"
                    )

                    continue

                # ----------------------------------------------------
                # Same location
                # ----------------------------------------------------

                if os.path.abspath(source) == os.path.abspath(
                    final_destination
                ):

                    error_count += 1

                    errors.append(
                        f"Already in destination:\n"
                        f"{source}"
                    )

                    continue

                # ----------------------------------------------------
                # Existing destination
                # ----------------------------------------------------

                if os.path.exists(
                    final_destination
                ):

                    error_count += 1

                    errors.append(
                        f"Already exists:\n"
                        f"{final_destination}"
                    )

                    continue

                # ----------------------------------------------------
                # Move
                # ----------------------------------------------------

                shutil.move(
                    source,
                    destination_folder
                )

                success_count += 1

            except Exception as exc:

                error_count += 1

                errors.append(
                    f"Failed:\n"
                    f"{filename}\n"
                    f"{exc}"
                )

        # ------------------------------------------------------------
        # Refresh
        # ------------------------------------------------------------

        self.clear_queue()
        self.refresh_views()

        # ------------------------------------------------------------
        # Result
        # ------------------------------------------------------------

        if error_count == 0:

            QMessageBox.information(
                self,
                "Commit Complete",
                (
                    f"Successfully moved "
                    f"{success_count} item(s)."
                )
            )

            return

        message = (
            f"Successfully moved "
            f"{success_count} item(s).\n\n"
            f"Failed or skipped "
            f"{error_count} item(s)."
        )

        if errors:

            message += (
                "\n\nDetails:\n\n"
                + "\n\n".join(
                    errors[:10]
                )
            )

            if len(errors) > 10:

                message += (
                    f"\n\n... and "
                    f"{len(errors) - 10} more."
                )

        QMessageBox.warning(
            self,
            "Commit Finished",
            message
        )

    # ========================================================================
    # DARK THEME
    # ========================================================================

    def apply_dark_theme(self):

        self.setStyleSheet(load_stylesheet())


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():

    if sys.platform == "win32":
        import ctypes

        set_app_user_model_id = (
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        )
        set_app_user_model_id.argtypes = [ctypes.c_wchar_p]
        set_app_user_model_id.restype = ctypes.c_long
        result = set_app_user_model_id(
            "ComfyUI.ModelOrganizer"
        )
        if result != 0:
            raise OSError(
                f"Could not set Windows app identity (HRESULT {result:#x})"
            )

    app = QApplication(
        sys.argv
    )

    app.setWindowIcon(app_icon())

    app.setApplicationName(
        "ComfyUI Model Organizer"
    )

    app.setApplicationDisplayName(
        "ComfyUI Model Organizer"
    )

    app.setStyle(
        "Fusion"
    )

    splash = OrganizerSplashScreen()
    splash.show()
    splash.update_progress(12, "Loading configuration...")

    # ------------------------------------------------------------------------
    # ComfyUI models directory
    # ------------------------------------------------------------------------

    try:
        left_path, right_path = load_panel_paths()
        filter_extensions, only_show = load_panel_filter()
    except (OSError, configparser.Error) as exc:
        splash.close()
        QMessageBox.critical(
            None,
            "Configuration Error",
            f"Could not read the .config file:\n{exc}"
        )
        return 1
    except ValueError as exc:
        splash.close()
        QMessageBox.critical(
            None,
            "Configuration Error",
            f"Invalid file filter in .config:\n{exc}"
        )
        return 1

    splash.update_progress(28, "Checking configured folders...")

    for panel_name, panel_path in (
        ("Left panel", left_path),
        ("Right panel", right_path),
    ):
        if not os.path.isdir(panel_path):
            splash.close()
            QMessageBox.critical(
                None,
                "Folder Not Found",
                f"The {panel_name.lower()} folder does not exist:\n{panel_path}\n\n"
                "Update the paths in the .config file."
            )
            return 1

    # ------------------------------------------------------------------------
    # Start application
    # ------------------------------------------------------------------------

    window = ComfyUIModelOrganizer(
        left_path,
        right_path,
        filter_extensions,
        only_show,
        splash.update_progress
    )

    window.show()
    splash.update_progress(100, "Ready")
    splash.finish(window)

    return app.exec()

