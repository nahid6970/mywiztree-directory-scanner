# ============================================================
# ui/main_window.py — Main application window
# ============================================================

import os
import sys
import csv
import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTabWidget, QFileDialog,
    QInputDialog, QMessageBox, QStatusBar, QProgressBar,
    QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import QFont

from src.scanner   import ScannerThread, FileNode, format_size, get_top_files
from src.treemap   import TreemapWidget
from src.theme     import (
    CP_BG, CP_PANEL, CP_CYAN, CP_YELLOW, CP_RED, CP_GREEN,
    CP_DIM, CP_TEXT, CP_SUBTEXT, get_global_stylesheet,
)
from src.ui.table_view      import TableView
from src.ui.diff_view       import DiffView
from src.ui.ext_breakdown   import ExtBreakdownPanel
from src.ui.settings_dialog import SettingsDialog


DEFAULT_SETTINGS = {
    "top_n":               100,
    "skip_hidden":         False,
    "treemap_color_mode":  "ext",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("myWizTree  ⚡  CYBERPUNK DISK SCANNER")
        self.resize(1400, 860)

        self._settings   = DEFAULT_SETTINGS.copy()
        self._scanner:   ScannerThread | None = None
        self._root:      FileNode | None      = None
        self._scan_start = 0.0

        self._build_ui()
        self._apply_theme()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 4)
        root_layout.setSpacing(4)

        # ── Top toolbar ──────────────────────────────────────────────────────
        root_layout.addLayout(self._build_toolbar())

        # ── Scan feed strip (live progress) ──────────────────────────────────
        self._feed_label = QLabel("READY — choose a directory to scan")
        self._feed_label.setStyleSheet(f"color: {CP_SUBTEXT}; font-size: 9pt;")
        self._feed_label.setMaximumHeight(18)
        self._feed_label.setMinimumWidth(0)
        self._feed_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        root_layout.addWidget(self._feed_label)

        # ── Progress bar ─────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setMaximumHeight(6)
        root_layout.addWidget(self._progress)

        # ── Main content splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: treemap
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        map_header = QHBoxLayout()
        self._path_label = QLabel("—")
        self._path_label.setStyleSheet(f"color: {CP_CYAN}; font-weight: bold;")
        self._path_label.setMinimumWidth(0)
        self._path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        map_header.addWidget(self._path_label, stretch=1)

        self._nav_up_btn = QPushButton("▲ UP")
        self._nav_up_btn.setFixedWidth(64)
        self._nav_up_btn.clicked.connect(self._treemap_up)
        self._nav_up_btn.setEnabled(False)
        map_header.addWidget(self._nav_up_btn)

        self._color_btn = QPushButton("🎨 EXT")
        self._color_btn.setFixedWidth(72)
        self._color_btn.setToolTip("Toggle between Extension and File Age heatmap coloring")
        self._color_btn.clicked.connect(self._toggle_color_mode)
        map_header.addWidget(self._color_btn)

        left_layout.addLayout(map_header)

        self._treemap = TreemapWidget()
        self._treemap.node_clicked.connect(self._on_treemap_click)
        self._treemap.node_hovered.connect(self._on_node_hover)
        left_layout.addWidget(self._treemap)

        splitter.addWidget(left)

        # Right: tab panel
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._table_view = TableView()
        self._table_view.row_selected.connect(self._on_row_selected)

        self._top_files_view = TableView()

        self._ext_panel = ExtBreakdownPanel()

        self._diff_view = DiffView()

        self._tabs.addTab(self._table_view,    "📋  FILES")
        self._tabs.addTab(self._top_files_view, "🏆  TOP FILES")
        self._tabs.addTab(self._ext_panel,      "📊  EXTENSIONS")
        self._tabs.addTab(self._diff_view,      "🔍  SNAPSHOT DIFF")

        splitter.addWidget(self._tabs)
        splitter.setSizes([600, 780])

        root_layout.addWidget(splitter)

        # ── Status bar ───────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("READY")
        self._status_label.setMinimumWidth(0)
        self._status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._status.addWidget(self._status_label, 1)   # stretch=1, takes all spare space
        self._stats_label = QLabel("")
        self._stats_label.setFixedWidth(220)
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._status.addPermanentWidget(self._stats_label)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        # Path input
        bar.addWidget(QLabel("PATH:"))
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("C:\\  or  D:\\Projects\\...")
        self._path_edit.returnPressed.connect(self._start_scan)
        bar.addWidget(self._path_edit)

        # Browse
        btn_browse = QPushButton("📂  BROWSE")
        btn_browse.clicked.connect(self._browse)
        bar.addWidget(btn_browse)

        # Scan
        self._scan_btn = QPushButton("⚡  SCAN")
        self._scan_btn.setStyleSheet(
            f"QPushButton {{ background-color: #003a00; border: 1px solid {CP_GREEN}; "
            f"color: {CP_GREEN}; font-weight: bold; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: {CP_GREEN}; color: #000; }}"
        )
        self._scan_btn.clicked.connect(self._start_scan)
        bar.addWidget(self._scan_btn)

        # Abort
        self._abort_btn = QPushButton("✖  ABORT")
        self._abort_btn.setEnabled(False)
        self._abort_btn.setStyleSheet(
            f"QPushButton {{ background-color: #3a0000; border: 1px solid {CP_RED}; "
            f"color: {CP_RED}; font-weight: bold; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background-color: {CP_RED}; color: #000; }}"
            f"QPushButton:disabled {{ background-color: #1a0000; border: 1px solid #3a0000; color: #3a0000; }}"
        )
        self._abort_btn.clicked.connect(self._abort_scan)
        bar.addWidget(self._abort_btn)

        bar.addSpacing(10)

        # Export
        btn_export = QPushButton("📤  EXPORT CSV")
        btn_export.clicked.connect(self._export_csv)
        bar.addWidget(btn_export)

        bar.addStretch()

        # Settings / Restart
        btn_settings = QPushButton("⚙  SETTINGS")
        btn_settings.clicked.connect(self._open_settings)
        bar.addWidget(btn_settings)

        btn_restart = QPushButton("↺  RESTART")
        btn_restart.clicked.connect(self._restart)
        bar.addWidget(btn_restart)

        return bar

    def _apply_theme(self):
        self.setStyleSheet(get_global_stylesheet())

    # ── Scan ─────────────────────────────────────────────────────────────────

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Directory to Scan")
        if path:
            self._path_edit.setText(path)

    def _start_scan(self):
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "NO PATH", "Enter a directory path to scan.")
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "INVALID PATH", f"Not a valid directory:\n{path}")
            return

        if self._scanner and self._scanner.isRunning():
            self._scanner.abort()
            self._scanner.wait()

        self._root = None
        self._table_view.clear()
        self._treemap.set_root(FileNode(
            name=os.path.basename(path) or path, path=path,
            size=0, is_dir=True, modified=0,
            file_count=0, children=[], parent=None,
        ))

        self._scan_btn.setEnabled(False)
        self._abort_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._scan_start = time.time()
        self._feed_label.setStyleSheet(f"color: {CP_CYAN}; font-size: 9pt;")
        self._status_label.setText("SCANNING…")

        self._scanner = ScannerThread(path)
        self._scanner.progress.connect(self._on_progress)
        self._scanner.scan_complete.connect(self._on_scan_complete)
        self._scanner.scan_error.connect(self._on_scan_error)
        self._scanner.stats_update.connect(self._on_stats_update)
        self._scanner.start()

    def _abort_scan(self):
        if self._scanner:
            self._scanner.abort()
        self._scan_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_label.setText("ABORTED")

    # ── Scanner signals ───────────────────────────────────────────────────────

    _progress_counter = 0

    def _on_progress(self, path: str):
        self._progress_counter += 1
        if self._progress_counter % 200 == 0:
            self._feed_label.setText(f"  {path}")

    def _on_stats_update(self, files: int, dirs: int):
        self._stats_label.setText(f"Files: {files:,}   Dirs: {dirs:,}")

    def _on_scan_complete(self, root: FileNode):
        self._root = root
        elapsed = time.time() - self._scan_start

        self._scan_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._feed_label.setText(
            f"  Scan complete  │  {root.file_count:,} files  │  "
            f"{format_size(root.size)}  │  {elapsed:.1f}s"
        )
        self._feed_label.setStyleSheet(f"color: {CP_GREEN}; font-size: 9pt;")
        self._status_label.setText("COMPLETE")
        self._set_path_label(root.path)

        # Populate panels
        self._treemap.set_root(root)
        self._treemap.set_color_mode(self._settings["treemap_color_mode"])
        self._table_view.set_root(root)
        self._top_files_view.set_nodes(get_top_files(root, self._settings["top_n"]))
        self._ext_panel.set_root(root)
        self._diff_view.set_current_root(root)
        self._diff_view.refresh_snapshot_list()
        self._nav_up_btn.setEnabled(False)

    def _on_scan_error(self, msg: str):
        self._scan_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_label.setText("ERROR")
        QMessageBox.critical(self, "SCAN ERROR", msg)

    # ── Treemap navigation ───────────────────────────────────────────────────

    def _set_path_label(self, path: str):
        """Set path label with elided text so long paths never expand the window."""
        fm = self._path_label.fontMetrics()
        available = self._path_label.width() or 400
        elided = fm.elidedText(path, Qt.TextElideMode.ElideMiddle, available)
        self._path_label.setText(elided)
        self._path_label.setToolTip(path)  # full path on hover

    def _on_treemap_click(self, node: FileNode):
        self._set_path_label(node.path)
        self._nav_up_btn.setEnabled(bool(self._treemap._nav_stack))

    def _treemap_up(self):
        self._treemap.navigate_up()
        current = self._treemap.current_node()
        if current:
            self._set_path_label(current.path)
        self._nav_up_btn.setEnabled(bool(self._treemap._nav_stack))

    def _toggle_color_mode(self):
        current = self._settings["treemap_color_mode"]
        new_mode = "age" if current == "ext" else "ext"
        self._settings["treemap_color_mode"] = new_mode
        self._treemap.set_color_mode(new_mode)
        self._color_btn.setText("🎨 AGE" if new_mode == "age" else "🎨 EXT")

    def _on_node_hover(self, node: FileNode):
        self._status_label.setText(
            f"{node.path}   │   {format_size(node.size)}   │   {node.file_count} files"
        )

    def _on_row_selected(self, node: FileNode):
        self._set_path_label(node.path)
        self._status_label.setText(
            f"{node.path}   │   {format_size(node.size)}"
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
            if self._root:
                self._treemap.set_color_mode(self._settings["treemap_color_mode"])
                mode = self._settings["treemap_color_mode"]
                self._color_btn.setText("🎨 AGE" if mode == "age" else "🎨 EXT")

    # ── Restart ──────────────────────────────────────────────────────────────

    def _restart(self):
        if self._scanner and self._scanner.isRunning():
            self._scanner.abort()
            self._scanner.wait()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # ── Close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._scanner and self._scanner.isRunning():
            self._scanner.abort()
            self._scanner.wait()
        event.accept()
