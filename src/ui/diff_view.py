# ============================================================
# ui/diff_view.py — Snapshot diff results panel
# ============================================================

import os
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableView, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QLineEdit,
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PyQt6.QtGui  import QColor, QFont

from src.snapshot import (
    DiffEntry, diff_snapshots, load_snapshot, list_snapshots,
    save_snapshot,
)
from src.scanner  import FileNode, format_size
from src.theme    import (
    CP_BG, CP_PANEL, CP_TEXT, CP_CYAN, CP_YELLOW,
    CP_RED, CP_GREEN, CP_DIM, CP_SUBTEXT,
    DIFF_NEW, DIFF_DELETED, DIFF_GROWN, DIFF_SHRUNK, DIFF_UNCHANGED,
)


STATUS_ICONS = {
    "new":       "🟢 NEW",
    "deleted":   "🔴 DEL",
    "grown":     "🟡 ▲",
    "shrunk":    "🔵 ▼",
    "unchanged": "   —",
}

DIFF_COLORS = {
    "new":     QColor(DIFF_NEW),
    "deleted": QColor(DIFF_DELETED),
    "grown":   QColor(DIFF_GROWN),
    "shrunk":  QColor(DIFF_SHRUNK),
}

COLUMNS = ["Status", "Name", "Old Size", "New Size", "Delta", "Path"]
C_STATUS, C_NAME, C_OLD, C_NEW, C_DELTA, C_PATH = range(6)


class DiffTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._entries: list[DiffEntry] = []

    def set_entries(self, entries: list[DiffEntry]):
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        col   = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == C_STATUS: return STATUS_ICONS.get(entry.status, entry.status)
            if col == C_NAME:   return ("📁 " if entry.is_dir else "   ") + entry.name
            if col == C_OLD:    return entry.old_size_str()
            if col == C_NEW:    return entry.new_size_str()
            if col == C_DELTA:  return entry.delta_str()
            if col == C_PATH:   return entry.path

        elif role == Qt.ItemDataRole.ForegroundRole:
            color = DIFF_COLORS.get(entry.status)
            if color:
                return color
            return QColor(CP_SUBTEXT)

        elif role == Qt.ItemDataRole.FontRole:
            f = QFont("Consolas", 9)
            if entry.status in ("new", "deleted"):
                f.setBold(True)
            return f

        elif role == Qt.ItemDataRole.UserRole:
            # For sorting
            if col == C_OLD:   return entry.old_size
            if col == C_NEW:   return entry.new_size
            if col == C_DELTA: return entry.delta
            return None

        return None

    def get_entry(self, row: int) -> DiffEntry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None


class DiffSortProxy(QSortFilterProxyModel):
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        col = left.column()
        if col in (C_OLD, C_NEW, C_DELTA):
            lv = self.sourceModel().data(left,  Qt.ItemDataRole.UserRole) or 0
            rv = self.sourceModel().data(right, Qt.ItemDataRole.UserRole) or 0
            return lv < rv
        lv = self.sourceModel().data(left,  Qt.ItemDataRole.DisplayRole) or ""
        rv = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return str(lv) < str(rv)


class DiffView(QWidget):
    """
    Snapshot diff panel.
    Lets the user:
      - Save the current scan as a named snapshot
      - Pick two snapshots and compare them
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_root: FileNode | None = None
        self._build_ui()

    # ── Public ───────────────────────────────────────────────────────────────

    def set_current_root(self, root: FileNode):
        """Called by main window whenever a new scan completes."""
        self._current_root = root
        self._save_btn.setEnabled(root is not None)

    def refresh_snapshot_list(self):
        self._populate_combos()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Save strip ───────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("SNAPSHOT NAME:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g.  D_drive_before_cleanup")
        save_row.addWidget(self._name_edit)
        self._save_btn = QPushButton("💾  SAVE SNAPSHOT")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_snapshot)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        # ── Compare strip ────────────────────────────────────────────────────
        cmp_row = QHBoxLayout()
        cmp_row.addWidget(QLabel("OLD:"))
        self._combo_old = QComboBox()
        self._combo_old.setMinimumWidth(220)
        cmp_row.addWidget(self._combo_old)
        cmp_row.addWidget(QLabel("NEW:"))
        self._combo_new = QComboBox()
        self._combo_new.setMinimumWidth(220)
        cmp_row.addWidget(self._combo_new)
        self._cmp_btn = QPushButton("⚡  COMPARE")
        self._cmp_btn.clicked.connect(self._run_diff)
        cmp_row.addWidget(self._cmp_btn)
        cmp_row.addStretch()
        layout.addLayout(cmp_row)

        # ── Summary bar ──────────────────────────────────────────────────────
        self._summary = QLabel("No diff loaded.")
        self._summary.setStyleSheet(f"color: {CP_SUBTEXT};")
        layout.addWidget(self._summary)

        # ── Filter ───────────────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("FILTER:"))
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("search by filename…")
        self._filter.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter)
        layout.addLayout(filter_row)

        # ── Table ────────────────────────────────────────────────────────────
        self._model = DiffTableModel()
        self._proxy = DiffSortProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(C_NAME, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(C_PATH, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(C_STATUS, 80)
        self._table.setColumnWidth(C_OLD,    90)
        self._table.setColumnWidth(C_NEW,    90)
        self._table.setColumnWidth(C_DELTA,  90)

        layout.addWidget(self._table)

        self._populate_combos()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _save_snapshot(self):
        if not self._current_root:
            return
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "NAME REQUIRED", "Enter a snapshot name first.")
            return
        try:
            path = save_snapshot(self._current_root, name)
            QMessageBox.information(self, "SAVED", f"Snapshot saved:\n{path}")
            self._name_edit.clear()
            self._populate_combos()
        except Exception as e:
            QMessageBox.critical(self, "SAVE ERROR", str(e))

    def _populate_combos(self):
        snaps = list_snapshots()
        for combo in (self._combo_old, self._combo_new):
            combo.clear()
            combo.addItem("— select snapshot —", userData=None)
            for s in snaps:
                ts  = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["saved_at"]))
                label = f"{s['snapshot_name']}  [{ts}]"
                combo.addItem(label, userData=s["filepath"])

        if len(snaps) >= 2:
            self._combo_old.setCurrentIndex(1)
            self._combo_new.setCurrentIndex(2)

    def _run_diff(self):
        old_path = self._combo_old.currentData()
        new_path = self._combo_new.currentData()

        if not old_path or not new_path:
            QMessageBox.warning(self, "SELECT SNAPSHOTS",
                                "Please select both OLD and NEW snapshots.")
            return
        if old_path == new_path:
            QMessageBox.warning(self, "SAME SNAPSHOT",
                                "OLD and NEW are the same snapshot — nothing to diff.")
            return

        try:
            old_root, old_meta = load_snapshot(old_path)
            new_root, new_meta = load_snapshot(new_path)
        except Exception as e:
            QMessageBox.critical(self, "LOAD ERROR", str(e))
            return

        entries = diff_snapshots(old_root, new_root)
        self._model.set_entries(entries)

        counts = {"new": 0, "deleted": 0, "grown": 0, "shrunk": 0}
        for e in entries:
            if e.status in counts:
                counts[e.status] += 1

        self._summary.setText(
            f"🟢 {counts['new']} new   "
            f"🔴 {counts['deleted']} deleted   "
            f"🟡 {counts['grown']} grown   "
            f"🔵 {counts['shrunk']} shrunk   "
            f"│  {len(entries)} total changes"
        )
        self._summary.setStyleSheet(f"color: {CP_CYAN}; font-weight: bold;")

    def _apply_filter(self, text: str):
        self._proxy.setFilterFixedString(text)
