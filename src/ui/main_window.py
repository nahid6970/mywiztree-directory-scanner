# ============================================================
# ui/main_window.py — Main application window
# ============================================================

import os
import sys
import csv
import time
import string

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTabWidget, QFileDialog,
    QMessageBox, QStatusBar, QProgressBar, QSizePolicy,
    QListWidget, QListWidgetItem, QFrame, QToolButton, QMenu, QSystemTrayIcon, QStyle,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal
from PyQt6.QtGui  import QFont, QColor

from src.scanner   import ScannerThread, ScanResult, FileNode, format_size
from src.theme     import (
    CP_BG, CP_PANEL, CP_CYAN, CP_YELLOW, CP_RED, CP_GREEN,
    CP_DIM, CP_TEXT, CP_SUBTEXT, get_global_stylesheet,
)
from src.ui.tree_view       import TreeFileView
from src.ui.table_view      import TableView
from src.ui.ext_breakdown   import ExtBreakdownPanel
from src.ui.settings_dialog import SettingsDialog
from src.settings           import load_settings, save_settings, DEFAULT_SETTINGS
from src.snapshot           import list_snapshots, load_snapshot, save_snapshot


def _get_drives() -> list[str]:
    """Return available Windows drive letters."""
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PyQt6.QtCore    import QSize

class _DriveItemDelegate(QStyledItemDelegate):
    """Renders each drive row: [CYAN drive]  [DIM label]"""
    def paint(self, painter, option, index):
        from PyQt6.QtGui import QPainter
        painter.save()

        is_hover = bool(option.state & option.state.State_MouseOver) or \
                   bool(option.state & option.state.State_Selected)

        bg = QColor("#002a2a") if is_hover else QColor(CP_PANEL)
        painter.fillRect(option.rect, bg)

        text: str = index.data(Qt.ItemDataRole.DisplayRole) or ""
        parts = text.strip().split("   ", 1)
        drive = parts[0] if parts else ""
        label = parts[1] if len(parts) > 1 else ""

        font_drive = QFont("Consolas", 10, QFont.Weight.Bold)
        font_label = QFont("Consolas", 9)

        x = option.rect.x() + 14
        y = option.rect.y()
        h = option.rect.height()

        painter.setFont(font_drive)
        painter.setPen(QColor(CP_CYAN))
        painter.drawText(x, y, 60, h, Qt.AlignmentFlag.AlignVCenter, drive)

        painter.setFont(font_label)
        painter.setPen(QColor(CP_SUBTEXT) if not is_hover else QColor(CP_TEXT))
        painter.drawText(x + 70, y, option.rect.width() - x - 70, h,
                         Qt.AlignmentFlag.AlignVCenter, label)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 32)


class DriveDropdown(QFrame):
    """
    Floating popup that lists available drives.
    Appears below the path field on click.
    """
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {CP_PANEL};
                border: 1px solid {CP_CYAN};
                border-top: 2px solid {CP_CYAN};
            }}
            QListWidget {{
                background-color: transparent;
                color: {CP_TEXT};
                border: none;
                font-family: 'Consolas';
                font-size: 10pt;
                outline: none;
                padding: 2px 0px;
            }}
            QListWidget::item {{
                height: 32px;
                padding-left: 12px;
                border: none;
            }}
            QListWidget::item:hover {{
                background-color: #002a2a;
                color: {CP_CYAN};
            }}
            QListWidget::item:selected {{
                background-color: #002a2a;
                color: {CP_CYAN};
            }}
            QScrollBar:vertical {{ width: 0px; }}
            QScrollBar:horizontal {{ height: 0px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QListWidget()
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._list)

        self._callback = None
        self._list.itemClicked.connect(self._on_item_click)
        self._list.setItemDelegate(_DriveItemDelegate(self._list))

    def show_below(self, widget: QWidget, callback):
        self._callback = callback
        self._list.clear()

        drives = _get_drives()
        for drive in drives:
            try:
                import ctypes
                buf = ctypes.create_unicode_buffer(261)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    drive, buf, 261, None, None, None, None, 0
                )
                label = buf.value or "Local Disk"
            except Exception:
                label = "Drive"

            # Format: "C:\  —  Local Disk"
            item = QListWidgetItem(f"  {drive}   {label}")
            item.setData(Qt.ItemDataRole.UserRole, drive)
            # Drive letter in cyan, label dimmer — set via font on the letter part
            self._list.addItem(item)

        row_h   = 32
        padding = 4
        total_h = len(drives) * row_h + padding * 2
        self._list.setFixedHeight(total_h)
        self.setFixedWidth(widget.width())
        self.setFixedHeight(total_h)

        global_pos = widget.mapToGlobal(QPoint(0, widget.height() - 1))
        self.move(global_pos)
        self.show()
        self.raise_()

    def _on_item_click(self, item: QListWidgetItem):
        drive = item.data(Qt.ItemDataRole.UserRole)
        if self._callback and drive:
            self._callback(drive)
        self.hide()


CHUNK_SIZE = 2000   # rows loaded per QTimer tick for top-files table


class SnapshotCompareThread(QThread):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, window, root: FileNode, nodes: list, filepath: str):
        super().__init__(window)
        self._window = window
        self._root = root
        self._nodes = nodes
        self._filepath = filepath

    def run(self):
        try:
            label = self._window._apply_last_snapshot_comparison(
                self._root, self._nodes, self._filepath,
                progress_callback=lambda value, maximum, message:
                    self.progress.emit(value, maximum, message),
            )
            self.completed.emit(label)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("myWizTree  ⚡  CYBERPUNK DISK SCANNER")
        self.resize(1400, 860)

        self._settings  = load_settings()
        self._scanner:  ScannerThread | None = None
        self._root:     FileNode | None      = None
        self._flat_nodes: list = []
        self._compare_thread: SnapshotCompareThread | None = None

        # Drive dropdown popup
        self._drive_dropdown = DriveDropdown(self)

        # Lazy loading state for top-files table
        self._pending_top:    list = []
        self._pending_offset: int  = 0
        self._load_timer = QTimer(self)
        self._load_timer.setInterval(0)
        self._load_timer.timeout.connect(self._load_top_chunk)

        self._build_ui()
        self._apply_theme()
        self._setup_notifications()
        # Apply default sort/column preferences
        self._tree_view.set_dirs_first(self._settings["dirs_first"])
        self._tree_view.set_visible_columns(self._settings["tree_cols"])
        self._top_files_view.set_visible_columns(self._settings["top_files_cols"])

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 4)
        root_layout.setSpacing(4)

        root_layout.addLayout(self._build_toolbar())

        # Scan feed
        self._feed_label = QLabel("READY — choose a directory to scan")
        self._feed_label.setStyleSheet(f"color: {CP_SUBTEXT}; font-size: 9pt;")
        self._feed_label.setMaximumHeight(18)
        self._feed_label.setMinimumWidth(0)
        self._feed_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        root_layout.addWidget(self._feed_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(6)
        root_layout.addWidget(self._progress)

        # ── Splitter: tree (left) | tabs (right) ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: tree view (main directory listing)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        # Path breadcrumb bar
        path_bar = QHBoxLayout()
        self._path_label = QLabel("")
        self._path_label.setStyleSheet(f"color: {CP_CYAN}; font-weight: bold;")
        self._path_label.setMinimumWidth(0)
        self._path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(self._path_label, stretch=1)
        left_layout.addLayout(path_bar)

        self._tree_view = TreeFileView()
        self._tree_view.node_selected.connect(self._on_node_selected)
        left_layout.addWidget(self._tree_view)

        splitter.addWidget(left)

        # Right: tabs
        self._tabs = QTabWidget()

        self._top_files_view = TableView()
        self._ext_panel      = ExtBreakdownPanel()

        self._tabs.addTab(self._top_files_view, "🏆  TOP FILES")
        self._tabs.addTab(self._ext_panel,       "📊  EXTENSIONS")

        splitter.addWidget(self._tabs)
        splitter.setSizes([860, 520])   # tree gets more space
        root_layout.addWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("READY")
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._status.addWidget(self._status_label, 1)
        self._stats_label = QLabel("")
        self._stats_label.setFixedWidth(260)
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._status.addPermanentWidget(self._stats_label)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(4)
        bar.setContentsMargins(0, 0, 0, 0)

        # Shared button style helper
        def _btn(text, color, bg, hover_bg="#1a1a1a", fixed_w=None) -> QPushButton:
            b = QPushButton(text)
            b.setFixedHeight(30)
            if fixed_w:
                b.setFixedWidth(fixed_w)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {bg};"
                f"  border: 1px solid {color};"
                f"  color: {color};"
                f"  font-family: 'Consolas';"
                f"  font-weight: bold;"
                f"  font-size: 9pt;"
                f"  padding: 0px 14px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {color};"
                f"  color: #000000;"
                f"}}"
                f"QPushButton:pressed {{"
                f"  background-color: {color};"
                f"  color: #000000;"
                f"}}"
                f"QPushButton:disabled {{"
                f"  background-color: #0d0d0d;"
                f"  border: 1px solid #2a2a2a;"
                f"  color: #2a2a2a;"
                f"}}"
            )
            return b

        # PATH label
        lbl = QLabel("PATH")
        lbl.setStyleSheet(f"color: {CP_SUBTEXT}; font-weight: bold; font-size: 9pt; padding: 0 4px;")
        lbl.setFixedHeight(30)
        bar.addWidget(lbl)

        # Path input — shows drive dropdown on click
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("C:\\  or  D:\\Projects\\...")
        self._path_edit.setFixedHeight(30)
        self._path_edit.returnPressed.connect(self._start_scan)
        self._path_edit.mousePressEvent = self._path_edit_clicked
        bar.addWidget(self._path_edit)

        bar.addSpacing(4)

        btn_browse = _btn("BROWSE", CP_SUBTEXT, "#1a1a1a", fixed_w=90)
        btn_browse.clicked.connect(self._browse)
        bar.addWidget(btn_browse)

        self._scan_btn = _btn("SCAN", CP_GREEN, "#001a00", fixed_w=90)
        self._scan_btn.clicked.connect(self._start_scan)
        bar.addWidget(self._scan_btn)

        self._abort_btn = _btn("ABORT", CP_RED, "#1a0000", fixed_w=90)
        self._abort_btn.setEnabled(False)
        self._abort_btn.clicked.connect(self._abort_scan)
        bar.addWidget(self._abort_btn)

        bar.addSpacing(8)

        btn_export = _btn("EXPORT CSV", CP_CYAN, "#001a1a", fixed_w=110)
        btn_export.clicked.connect(self._export_csv)
        bar.addWidget(btn_export)

        self._snapshot_btn = _btn("SNAPSHOT", CP_CYAN, "#001a1a", fixed_w=100)
        self._snapshot_btn.setEnabled(False)
        self._snapshot_btn.clicked.connect(self._save_current_snapshot)
        bar.addWidget(self._snapshot_btn)

        self._compare_btn = _btn("COMPARE", CP_YELLOW, "#1a1a00", fixed_w=100)
        self._compare_btn.setEnabled(False)
        self._compare_btn.clicked.connect(self._compare_selected_snapshot)
        bar.addWidget(self._compare_btn)

        self._snapshot_menu_btn = QToolButton()
        self._snapshot_menu_btn.setText("▾")
        self._snapshot_menu_btn.setToolTip("Choose a saved snapshot to compare with this scan")
        self._snapshot_menu_btn.setFixedSize(28, 30)
        self._snapshot_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._snapshot_menu_btn.setStyleSheet(f"QToolButton {{ background: #1a1a00; color: {CP_YELLOW}; border: 1px solid {CP_YELLOW}; font: bold 12pt Consolas; }} QToolButton::menu-indicator {{ image: none; }} QToolButton:hover {{ background: {CP_YELLOW}; color: #000; }}")
        self._snapshot_menu = QMenu(self._snapshot_menu_btn)
        self._snapshot_menu_btn.setMenu(self._snapshot_menu)
        self._snapshot_menu_btn.setEnabled(False)
        self._selected_snapshot_path = None
        bar.addWidget(self._snapshot_menu_btn)

        bar.addStretch()

        btn_settings = _btn("SETTINGS", CP_SUBTEXT, "#1a1a1a", fixed_w=100)
        btn_settings.clicked.connect(self._open_settings)
        bar.addWidget(btn_settings)

        btn_restart = _btn("RESTART", CP_YELLOW, "#1a1a00", fixed_w=90)
        btn_restart.clicked.connect(self._restart)
        bar.addWidget(btn_restart)

        return bar

    def _apply_theme(self):
        self.setStyleSheet(get_global_stylesheet())

    def _setup_notifications(self):
        self._tray_icon = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self)
        tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        tray.setToolTip("myWizTree — disk scanner")
        tray.show()
        self._tray_icon = tray

    def _notify_scan_complete(self, result: ScanResult):
        title = "myWizTree scan complete"
        message = f"{result.root.path}\n{result.root.file_count:,} files · {format_size(result.root.size)}"
        if self._tray_icon:
            self._tray_icon.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, 6000
            )
        else:
            QApplication.alert(self, 5000)

    # ── Scan ─────────────────────────────────────────────────────────────────

    def _path_edit_clicked(self, event):
        """Show drive dropdown when user clicks the path field."""
        QLineEdit.mousePressEvent(self._path_edit, event)
        # Only show if field is empty or contains just a drive letter
        text = self._path_edit.text().strip()
        if len(text) <= 3:
            self._drive_dropdown.show_below(self._path_edit, self._select_drive)

    def _select_drive(self, drive: str):
        """Called when user picks a drive from the dropdown."""
        self._path_edit.setText(drive)
        self._path_edit.setFocus()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Directory to Scan")
        if path:
            self._path_edit.setText(path)

    def _start_scan(self):
        if self._compare_thread and self._compare_thread.isRunning():
            return
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "NO PATH", "Enter a directory path to scan.")
            return
        # Normalise separators and strip trailing slash (except bare drive e.g. C:\)
        path = os.path.normpath(path)
        self._path_edit.setText(path)
        if not os.path.isdir(path):
            QMessageBox.warning(self, "INVALID PATH", f"Not a valid directory:\n{path}")
            return

        self._load_timer.stop()
        if self._scanner and self._scanner.isRunning():
            self._scanner.abort()
            self._scanner.wait()

        self._root = None
        self._flat_nodes = []
        self._compare_btn.setEnabled(False)
        self._snapshot_btn.setEnabled(False)
        self._snapshot_menu_btn.setEnabled(False)
        self._tree_view.clear()
        self._top_files_view.clear()

        self._scan_btn.setEnabled(False)
        self._abort_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._feed_label.setStyleSheet(f"color: {CP_CYAN}; font-size: 9pt;")
        self._feed_label.setText("  Scanning…")
        self._status_label.setText("SCANNING…")

        self._scanner = ScannerThread(path, top_n=self._settings["top_n"])
        self._scanner.progress.connect(self._on_progress,       Qt.ConnectionType.QueuedConnection)
        self._scanner.scan_complete.connect(self._on_scan_complete, Qt.ConnectionType.QueuedConnection)
        self._scanner.scan_error.connect(self._on_scan_error,   Qt.ConnectionType.QueuedConnection)
        self._scanner.stats_update.connect(self._on_stats_update, Qt.ConnectionType.QueuedConnection)
        self._scanner.start()

    def _abort_scan(self):
        self._load_timer.stop()
        if self._scanner:
            self._scanner.abort()
        self._scan_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_label.setText("ABORTED")

    # ── Scanner signals ───────────────────────────────────────────────────────

    def _on_progress(self, path: str):
        self._feed_label.setText(f"  {path}")

    def _on_stats_update(self, files: int, dirs: int):
        self._stats_label.setText(f"Files: {files:,}   Dirs: {dirs:,}")

    def _on_scan_complete(self, result: ScanResult):
        self._root = result.root
        self._flat_nodes = result.flat_list

        self._scan_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._progress.setVisible(False)

        self._feed_label.setText(
            f"  Scan complete  │  {result.root.file_count:,} files  │  "
            f"{format_size(result.root.size)}  │  {result.elapsed:.1f}s"
        )
        self._feed_label.setStyleSheet(f"color: {CP_GREEN}; font-size: 9pt;")
        self._notify_scan_complete(result)

        dirs_count = sum(1 for n in result.flat_list if n.is_dir)
        self._stats_label.setText(
            f"Files: {result.root.file_count:,}   Dirs: {dirs_count:,}"
        )
        self._status_label.setText("COMPLETE")
        self._set_path_label(result.root.path)

        # Tree view — fast (just stores root reference, expands lazily)
        self._tree_view.set_root(result.root)
        self._compare_btn.setEnabled(True)

        # Extension breakdown — pre-computed
        self._ext_panel.set_data(result.ext_map, result.root.size)

        # Snapshot controls
        self._snapshot_btn.setEnabled(True)
        self._populate_snapshot_menu()

        # Top files — load lazily in chunks
        self._pending_top    = result.top_files
        self._pending_offset = 0
        self._top_files_view.clear()
        self._load_top_chunk()
        if self._pending_offset < len(self._pending_top):
            self._load_timer.start()

    def _compare_selected_snapshot(self):
        if not self._root:
            return
        if self._compare_thread and self._compare_thread.isRunning():
            return
        filepath = self._selected_snapshot_path
        if not filepath:
            self._feed_label.setText("  No saved snapshot selected for this directory")
            self._feed_label.setStyleSheet(f"color: {CP_YELLOW}; font-size: 9pt;")
            return
        self._tree_view.clear()
        self._compare_btn.setEnabled(False)
        self._snapshot_btn.setEnabled(False)
        self._snapshot_menu_btn.setEnabled(False)
        self._scan_btn.setEnabled(False)
        self._progress.setRange(0, 0)
        self._progress.setVisible(True)
        self._feed_label.setText("  Preparing snapshot comparison…")
        self._feed_label.setStyleSheet(f"color: {CP_YELLOW}; font-size: 9pt;")

        self._compare_thread = SnapshotCompareThread(
            self, self._root, self._flat_nodes, filepath
        )
        self._compare_thread.progress.connect(self._on_compare_progress)
        self._compare_thread.completed.connect(self._on_compare_complete)
        self._compare_thread.failed.connect(self._on_compare_failed)
        self._compare_thread.finished.connect(self._on_compare_thread_finished)
        self._compare_thread.start()

    def _on_compare_progress(self, value: int, maximum: int, message: str):
        if maximum > 0:
            self._progress.setRange(0, 100)
            self._progress.setValue(min(100, int(value * 100 / maximum)))
        else:
            self._progress.setRange(0, 0)
        self._feed_label.setText(f"  {message}")

    def _on_compare_complete(self, label: str):
        self._tree_view.set_root(self._root)
        self._progress.setVisible(False)
        self._compare_btn.setEnabled(True)
        self._snapshot_btn.setEnabled(True)
        self._snapshot_menu_btn.setEnabled(bool(self._selected_snapshot_path))
        self._scan_btn.setEnabled(True)
        self._feed_label.setText(f"  Snapshot comparison  │  {label}")
        self._feed_label.setStyleSheet(f"color: {CP_YELLOW}; font-size: 9pt;")

    def _on_compare_failed(self, error: str):
        self._tree_view.set_root(self._root)
        self._progress.setVisible(False)
        self._compare_btn.setEnabled(True)
        self._snapshot_btn.setEnabled(True)
        self._snapshot_menu_btn.setEnabled(bool(self._selected_snapshot_path))
        self._scan_btn.setEnabled(True)
        self._feed_label.setText(f"  Snapshot comparison failed: {error}")
        self._feed_label.setStyleSheet(f"color: {CP_RED}; font-size: 9pt;")

    def _on_compare_thread_finished(self):
        self._compare_thread = None

    def _populate_snapshot_menu(self):
        self._snapshot_menu.clear()
        self._selected_snapshot_path = None
        if not self._root:
            self._snapshot_menu.addAction("No scan loaded").setEnabled(False)
            self._snapshot_menu_btn.setEnabled(False)
            return
        root_key = os.path.normcase(os.path.abspath(os.path.normpath(self._root.path)))
        snapshots = [s for s in list_snapshots()
                     if os.path.normcase(os.path.abspath(os.path.normpath(s.get("root_path", "")))) == root_key]
        snapshots.sort(key=lambda s: s.get("saved_at", 0), reverse=True)
        for i, snap in enumerate(snapshots):
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(snap.get("saved_at", 0)))
            path = snap["filepath"]
            action = self._snapshot_menu.addAction(f"{snap['snapshot_name']}  ·  {stamp}")
            action.setCheckable(True)
            action.setChecked(i == 0)
            action.triggered.connect(lambda checked=False, selected=path: self._select_snapshot_for_compare(selected))
        if snapshots:
            self._selected_snapshot_path = snapshots[0]["filepath"]
            self._snapshot_menu_btn.setEnabled(True)
            self._snapshot_menu_btn.setToolTip(f"Compare to {snapshots[0]['snapshot_name']} — click to choose another")
        else:
            self._snapshot_menu.addAction("No saved snapshots for this directory").setEnabled(False)
            self._snapshot_menu_btn.setEnabled(False)
            self._snapshot_menu_btn.setToolTip("No saved snapshots for this directory")

    def _select_snapshot_for_compare(self, filepath: str):
        self._selected_snapshot_path = filepath
        action = self.sender()
        if action:
            for menu_action in self._snapshot_menu.actions():
                menu_action.setChecked(menu_action is action)
            self._snapshot_menu_btn.setToolTip(f"Compare to {action.text()} — click to choose another")

    def _save_current_snapshot(self):
        if not self._root:
            return
        existing = {s.get("snapshot_name", "") for s in list_snapshots()}
        number = 1
        while f"snapshot_{number}" in existing:
            number += 1
        name = f"snapshot_{number}"
        try:
            save_snapshot(self._root, name)
            self._populate_snapshot_menu()
            # A snapshot of the current scan is now the selected baseline.
            self._feed_label.setText(f"  Saved snapshot: {name}")
            self._feed_label.setStyleSheet(f"color: {CP_GREEN}; font-size: 9pt;")
        except Exception as e:
            QMessageBox.critical(self, "SNAPSHOT ERROR", str(e))

    def _apply_last_snapshot_comparison(self, root: FileNode, nodes: list, filepath: str,
                                        progress_callback=None) -> str:
        """Annotate scanned nodes against the selected snapshot for this root."""
        selected = next((s for s in list_snapshots() if s["filepath"] == filepath), None)
        if selected is None:
            for node in nodes:
                node.previous_size = None
                node.change_status = ""
                node.change_pct = None
                node.change_delta = None
            return "selected snapshot is unavailable"

        try:
            previous, meta = load_snapshot(
                filepath,
                progress_callback=lambda count: progress_callback(0, 0, f"Loading snapshot… {count:,} entries")
                if progress_callback else None,
            )
        except Exception:
            for node in nodes:
                node.previous_size = None
                node.change_status = ""
                node.change_pct = None
                node.change_delta = None
            return "snapshot comparison unavailable"

        def key(path: str) -> str:
            return os.path.normcase(os.path.normpath(path.rstrip("\\/")))

        old_sizes = {}
        old_total = len(previous.entries)
        for index, (path, size) in enumerate(previous.entries.items(), 1):
            old_sizes[key(path)] = size
            if progress_callback and index % 50000 == 0:
                progress_callback(index, old_total, f"Indexing snapshot… {index:,}/{old_total:,}")

        # Discard display-only deleted rows from an earlier comparison.
        for index, node in enumerate(nodes, 1):
            if node.is_dir:
                node.children[:] = [child for child in node.children
                                    if child.change_status != "DELETED"]
            if progress_callback and index % 50000 == 0:
                progress_callback(index, len(nodes), f"Preparing tree… {index:,}/{len(nodes):,}")

        current_paths = set()
        by_path = {}
        for index, node in enumerate(nodes, 1):
            node_key = key(node.path)
            current_paths.add(node_key)
            by_path[node_key] = node
            if progress_callback and index % 50000 == 0:
                progress_callback(index, len(nodes), f"Indexing current scan… {index:,}/{len(nodes):,}")

        for index, node in enumerate(nodes, 1):
            old = old_sizes.get(key(node.path))
            node.previous_size = old
            node.change_delta = node.size if old is None else node.size - old
            if old is None:
                node.change_status = "NEW"
                node.change_pct = None
            elif node.size == old:
                node.change_status = "UNCHANGED"
                node.change_pct = 0.0
            else:
                node.change_status = "GROWN" if node.size > old else "SHRUNK"
                node.change_pct = ((node.size - old) / old * 100.0) if old else None
            if progress_callback and index % 50000 == 0:
                progress_callback(index, len(nodes), f"Comparing entries… {index:,}/{len(nodes):,}")

        # Add removed paths to their surviving parent. A removed directory
        # represents its removed subtree, so descendants are not duplicated.
        if progress_callback:
            progress_callback(0, 0, "Finding removed entries…")
        removed = sorted(
            ((path, size) for path, size in previous.entries.items()
             if key(path) not in current_paths),
            key=lambda item: (item[0].count("\\") + item[0].count("/"), item[0]),
        )
        removed_dirs: set[str] = set()
        for index, (old_path, old_size) in enumerate(removed, 1):
            normalized = key(old_path)
            if any(normalized.startswith(parent + os.sep) for parent in removed_dirs):
                continue
            is_dir = old_path.endswith(("\\", "/"))
            plain_path = old_path.rstrip("\\/")
            parent_key = key(os.path.dirname(plain_path))
            parent = by_path.get(parent_key, root)
            ghost = FileNode(
                name=os.path.basename(plain_path), path=plain_path, size=old_size,
                is_dir=is_dir, modified=0.0, file_count=0 if is_dir else 1,
                children=[], parent=parent,
                extension=os.path.splitext(plain_path)[1].lower(),
                previous_size=old_size, change_status="DELETED", change_pct=None,
                change_delta=-old_size,
            )
            parent.children.append(ghost)
            if is_dir:
                removed_dirs.add(normalized)
            if progress_callback and index % 50000 == 0:
                progress_callback(index, len(removed), f"Adding removed entries… {index:,}/{len(removed):,}")
        for node in nodes:
            if node.is_dir:
                node.children.sort(key=lambda child: child.size, reverse=True)

        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(meta.get("saved_at", 0)))
        return f"compared with {selected['snapshot_name']} ({stamp})"

    def _load_top_chunk(self):
        chunk = self._pending_top[self._pending_offset:self._pending_offset + CHUNK_SIZE]
        if not chunk:
            self._load_timer.stop()
            return
        self._pending_offset += CHUNK_SIZE
        self._top_files_view.append_nodes(chunk)
        if self._pending_offset >= len(self._pending_top):
            self._load_timer.stop()

    def _on_scan_error(self, msg: str):
        self._load_timer.stop()
        self._scan_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_label.setText("ERROR")
        QMessageBox.critical(self, "SCAN ERROR", msg)

    # ── Node selection ────────────────────────────────────────────────────────

    def _set_path_label(self, path: str):
        fm        = self._path_label.fontMetrics()
        available = self._path_label.width() or 600
        elided    = fm.elidedText(path, Qt.TextElideMode.ElideMiddle, available)
        self._path_label.setText(elided)
        self._path_label.setToolTip(path)

    def _on_node_selected(self, node: FileNode):
        self._set_path_label(node.path)
        self._status_label.setText(
            f"{node.path}   │   {format_size(node.size)}   │   {node.file_count} files"
        )

    # ── Export ───────────────────────────────────────────────────────────────

    def _export_csv(self):
        if not self._root:
            QMessageBox.warning(self, "NO DATA", "Scan a directory first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "scan_results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        from src.scanner import build_flat_list
        nodes = build_flat_list(self._root)
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Path", "Size (bytes)", "Size", "Is Dir",
                                  "Files", "Modified", "Extension"])
                for nd in nodes:
                    writer.writerow([
                        nd.name, nd.path, nd.size, format_size(nd.size),
                        nd.is_dir, nd.file_count,
                        time.strftime("%Y-%m-%d %H:%M", time.localtime(nd.modified))
                        if nd.modified else "",
                        nd.extension,
                    ])
            QMessageBox.information(self, "EXPORTED", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "EXPORT ERROR", str(e))

    # ── Settings ─────────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings = dlg.get_settings()
            save_settings(self._settings)
            self._tree_view.set_dirs_first(self._settings["dirs_first"])
            self._tree_view.set_visible_columns(self._settings["tree_cols"])
            self._top_files_view.set_visible_columns(self._settings["top_files_cols"])

    # ── Restart / Close ──────────────────────────────────────────────────────

    def _restart(self):
        self._load_timer.stop()
        if self._scanner and self._scanner.isRunning():
            self._scanner.abort()
            self._scanner.wait()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def closeEvent(self, event):
        self._load_timer.stop()
        if self._scanner and self._scanner.isRunning():
            self._scanner.abort()
            self._scanner.wait()
        event.accept()
