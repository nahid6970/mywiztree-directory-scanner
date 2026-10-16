# ============================================================
# ui/table_view.py — Sortable file/folder table
# ============================================================

import os
import subprocess
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QLineEdit,
    QLabel, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QPushButton,
)
from PyQt6.QtCore    import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, pyqtSignal
from PyQt6.QtGui     import QColor, QFont

from src.scanner import FileNode, format_size, build_flat_list, get_top_files
from src.theme   import (CP_PANEL, CP_TEXT, CP_CYAN, CP_YELLOW,
                          CP_RED, CP_GREEN, CP_DIM, CP_SUBTEXT)


COLUMNS = ["Name", "Size", "% of Parent", "Files", "Modified", "Path"]
COL_NAME, COL_SIZE, COL_PCT, COL_COUNT, COL_MOD, COL_PATH = range(6)


class FileTableModel(QAbstractTableModel):
    def __init__(self, nodes: list[FileNode] | None = None):
        super().__init__()
        self._nodes: list[FileNode] = nodes or []

    def set_nodes(self, nodes: list[FileNode]):
        self.beginResetModel()
        self._nodes = nodes
        self.endResetModel()

    def append_nodes(self, nodes: list[FileNode]):
        """Incrementally add rows without full reset — keeps UI responsive."""
        if not nodes:
            return
        first = len(self._nodes)
        last  = first + len(nodes) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._nodes.extend(nodes)
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return len(self._nodes)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = self._nodes[index.row()]
        col  = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_NAME:
                prefix = "📁 " if node.is_dir else "   "
                return prefix + node.name
            elif col == COL_SIZE:
                return format_size(node.size)
            elif col == COL_PCT:
                return f"{node.pct_of_parent():.1f}%"
            elif col == COL_COUNT:
                return str(node.file_count)
            elif col == COL_MOD:
                if node.modified:
                    return time.strftime("%Y-%m-%d %H:%M", time.localtime(node.modified))
                return "—"
            elif col == COL_PATH:
                return node.path

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == COL_SIZE:
                return QColor(CP_CYAN)
            elif col == COL_PCT:
                return QColor(CP_YELLOW)
            elif col == COL_MOD:
                return QColor(CP_SUBTEXT)
            elif col == COL_PATH:
                return QColor(CP_SUBTEXT)

        elif role == Qt.ItemDataRole.UserRole:
            # Return the raw FileNode for sorting
            if col == COL_SIZE:   return node.size
            if col == COL_PCT:    return node.pct_of_parent()
            if col == COL_COUNT:  return node.file_count
            if col == COL_MOD:    return node.modified
            return None

        elif role == Qt.ItemDataRole.FontRole:
            f = QFont("Consolas", 9)
            if node.is_dir:
                f.setBold(True)
            return f

        return None

    def get_node(self, row: int) -> FileNode | None:
        if 0 <= row < len(self._nodes):
            return self._nodes[row]
        return None


class NodeSortProxy(QSortFilterProxyModel):
    """Sort proxy that uses UserRole (raw numeric) for numeric columns."""
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        col = left.column()
        if col in (COL_SIZE, COL_PCT, COL_COUNT, COL_MOD):
            lv = self.sourceModel().data(left,  Qt.ItemDataRole.UserRole) or 0
            rv = self.sourceModel().data(right, Qt.ItemDataRole.UserRole) or 0
            return lv < rv
        lv = self.sourceModel().data(left,  Qt.ItemDataRole.DisplayRole) or ""
        rv = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return str(lv) < str(rv)


class TableView(QWidget):
    """
    Sortable, filterable file/folder table.
    Signals:
        row_selected(FileNode) — emitted when user clicks a row
    """
    row_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: FileNode | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Filter bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("FILTER:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("filename or extension…")
        self._filter_edit.textChanged.connect(self._apply_filter)
        bar.addWidget(self._filter_edit)

        self._count_label = QLabel("0 items")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bar.addWidget(self._count_label)

        layout.addLayout(bar)

        # Table
        self._model = FileTableModel()
        self._proxy = NodeSortProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # Search all columns

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(COL_SIZE,  90)
        self._table.setColumnWidth(COL_PCT,   80)
        self._table.setColumnWidth(COL_COUNT, 70)
        self._table.setColumnWidth(COL_MOD,   140)
        self._table.sortByColumn(COL_SIZE, Qt.SortOrder.DescendingOrder)
        self._table.clicked.connect(self._on_click)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)

        layout.addWidget(self._table)

    # ── Public ───────────────────────────────────────────────────────────────

    def set_root(self, root: FileNode):
        self._root = root
        nodes = build_flat_list(root)
        self._model.set_nodes(nodes)
        self._update_count()

    def set_nodes(self, nodes: list[FileNode]):
        self._model.set_nodes(nodes)
        self._update_count()

    def append_nodes(self, nodes: list[FileNode]):
        """Append additional nodes — used for lazy chunked loading."""
        self._model.append_nodes(nodes)
        self._update_count()

    def clear(self):
        self._model.set_nodes([])
        self._update_count()

    # ── Internals ────────────────────────────────────────────────────────────

    def _apply_filter(self, text: str):
        self._proxy.setFilterFixedString(text)
        self._update_count()

    def _update_count(self):
        self._count_label.setText(f"{self._proxy.rowCount()} items")

    def _on_click(self, index: QModelIndex):
        src_index = self._proxy.mapToSource(index)
        node = self._model.get_node(src_index.row())
        if node:
            self.row_selected.emit(node)

    def _context_menu(self, pos):
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        src_index = self._proxy.mapToSource(index)
        node = self._model.get_node(src_index.row())
        if not node:
            return

        menu = QMenu(self)
        act_copy  = menu.addAction("📋  Copy Path")
        act_open  = menu.addAction("📂  Open in Explorer")
        menu.addSeparator()
        act_del   = menu.addAction("🗑️  Delete…")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if action == act_copy:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(node.path)

        elif action == act_open:
            target = node.path if node.is_dir else os.path.dirname(node.path)
            subprocess.Popen(f'explorer /select,"{node.path}"')

        elif action == act_del:
            self._confirm_delete(node)

    def _confirm_delete(self, node: FileNode):
        msg = QMessageBox(self)
        msg.setWindowTitle("CONFIRM DELETE")
        msg.setText(f"Delete  {node.name}?\n\n{node.path}\n\nSize: {node.size_str()}")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            import shutil
            try:
                if node.is_dir:
                    shutil.rmtree(node.path)
                else:
                    os.remove(node.path)
            except Exception as e:
                QMessageBox.critical(self, "DELETE FAILED", str(e))
