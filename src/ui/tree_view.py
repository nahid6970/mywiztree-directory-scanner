# ============================================================
# ui/tree_view.py — Collapsible tree view with inline size bars
# ============================================================

import os
import subprocess
import shutil
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QLineEdit,
    QLabel, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QSizePolicy, QApplication,
)
from PyQt6.QtCore import (
    Qt, QAbstractItemModel, QModelIndex, QSortFilterProxyModel,
    pyqtSignal, QRect,
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QBrush, QPen,
)

from src.scanner import FileNode, format_size
from src.theme   import (
    CP_PANEL, CP_BG, CP_TEXT, CP_CYAN, CP_YELLOW,
    CP_RED, CP_GREEN, CP_DIM, CP_SUBTEXT,
)

# Column indices
COL_NAME  = 0
COL_SIZE  = 1
COL_BAR   = 2   # visual size bar
COL_FILES = 3
COL_MOD   = 4

COLUMNS   = ["Name", "Size", "Size Bar", "Files", "Modified"]


# ── Item model ────────────────────────────────────────────────────────────────

class FileTreeModel(QAbstractItemModel):
    """
    Maps a FileNode tree directly to QTreeView.
    Lazy — children are only accessed when a node is expanded.
    """

    def __init__(self, root: FileNode | None = None, parent=None):
        super().__init__(parent)
        self._root: FileNode | None = root

    def set_root(self, root: FileNode):
        self.beginResetModel()
        self._root = root
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._root = None
        self.endResetModel()

    # ── Required overrides ───────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not self._root:
            return 0
        node = self._node_from_index(parent)
        return len(node.children) if node else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(COLUMNS)

    def index(self, row: int, col: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self._root or not self.hasIndex(row, col, parent):
            return QModelIndex()
        parent_node = self._node_from_index(parent)
        if parent_node and 0 <= row < len(parent_node.children):
            return self.createIndex(row, col, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: FileNode = index.internalPointer()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        # Find parent's row in grandparent's children
        grandparent = parent_node.parent
        if grandparent is None:
            grandparent = self._root
        try:
            row = grandparent.children.index(parent_node)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, parent_node)

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        node = self._node_from_index(parent)
        if node is None:
            return False
        return node.is_dir and len(node.children) > 0

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node: FileNode = index.internalPointer()
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_NAME:
                return node.name
            if col == COL_SIZE:
                return format_size(node.size)
            if col == COL_BAR:
                return None   # drawn by delegate
            if col == COL_FILES:
                return str(node.file_count)
            if col == COL_MOD:
                if node.modified:
                    return time.strftime("%Y-%m-%d %H:%M", time.localtime(node.modified))
                return "—"

        elif role == Qt.ItemDataRole.DecorationRole:
            if col == COL_NAME:
                # simple text icon via font — no external icons needed
                return None

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == COL_NAME:
                return QColor(CP_CYAN) if node.is_dir else QColor(CP_TEXT)
            if col == COL_SIZE:
                return QColor(CP_YELLOW)
            if col == COL_FILES:
                return QColor(CP_SUBTEXT)
            if col == COL_MOD:
                return QColor(CP_SUBTEXT)

        elif role == Qt.ItemDataRole.FontRole:
            f = QFont("Consolas", 9)
            if node.is_dir:
                f.setBold(True)
            return f

        elif role == Qt.ItemDataRole.UserRole:
            # Raw value for sorting
            if col == COL_SIZE:  return node.size
            if col == COL_FILES: return node.file_count
            if col == COL_MOD:   return node.modified
            # Bar column: pct of parent (0.0–1.0)
            if col == COL_BAR:
                if node.parent and node.parent.size > 0:
                    return node.size / node.parent.size
                return 1.0
            return None

        elif role == Qt.ItemDataRole.ToolTipRole:
            return node.path

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _node_from_index(self, index: QModelIndex) -> FileNode | None:
        if not index.isValid():
            return self._root
        return index.internalPointer()

    def get_node(self, index: QModelIndex) -> FileNode | None:
        return self._node_from_index(index)


# ── Size bar delegate ─────────────────────────────────────────────────────────

class SizeBarDelegate(QAbstractItemModel.__class__):
    pass  # placeholder — defined below properly


from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

class SizeBarDelegate(QStyledItemDelegate):
    """
    Renders a horizontal bar in COL_BAR proportional to the node's
    share of its parent's total size.
    """
    BAR_COLOR    = QColor("#005a5a")
    BAR_BORDER   = QColor(CP_CYAN)
    TEXT_COLOR   = QColor(CP_CYAN)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex):
        painter.save()

        rect = option.rect

        # Background
        if option.state & option.state.State_Selected:
            painter.fillRect(rect, QColor("#003a3a"))
        else:
            painter.fillRect(rect, QColor(CP_PANEL if rect.top() % 2 == 0 else "#161616"))

        pct: float = index.data(Qt.ItemDataRole.UserRole) or 0.0
        pct = max(0.0, min(1.0, pct))

        if pct > 0:
            # Bar
            padding    = 3
            bar_rect   = QRect(
                rect.x() + padding,
                rect.y() + padding,
                max(2, int((rect.width() - padding * 2) * pct)),
                rect.height() - padding * 2,
            )
            painter.fillRect(bar_rect, self.BAR_COLOR)
            painter.setPen(QPen(self.BAR_BORDER, 1))
            painter.drawRect(bar_rect)

        # Percentage text
        painter.setPen(self.TEXT_COLOR)
        painter.setFont(QFont("Consolas", 8))
        pct_text = f"{pct * 100:.1f}%"
        painter.drawText(
            rect.adjusted(4, 0, -4, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            pct_text,
        )

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return sh


# ── Numeric-aware sort proxy ──────────────────────────────────────────────────

class TreeSortProxy(QSortFilterProxyModel):
    """Sort proxy that uses UserRole (raw int) for numeric columns."""
    NUMERIC_COLS = (COL_SIZE, COL_BAR, COL_FILES, COL_MOD)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dirs_first = True

    def set_dirs_first(self, enabled: bool):
        self._dirs_first = enabled
        self.invalidate()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        # Dirs-first: always keep dirs above files regardless of column or direction.
        # Qt reverses lessThan results for descending order, so we must flip with it.
        if self._dirs_first:
            l_node = self.sourceModel().get_node(left)
            r_node = self.sourceModel().get_node(right)
            if l_node and r_node and l_node.is_dir != r_node.is_dir:
                asc = (self.sortOrder() == Qt.SortOrder.AscendingOrder)
                # ascending:  dir < file → dir appears first ✓
                # descending: dir > file → Qt reverses, dir still appears first ✓
                return l_node.is_dir if asc else not l_node.is_dir

        col = left.column()
        if col in self.NUMERIC_COLS:
            lv = self.sourceModel().data(left,  Qt.ItemDataRole.UserRole) or 0
            rv = self.sourceModel().data(right, Qt.ItemDataRole.UserRole) or 0
            try:
                return float(lv) < float(rv)
            except (TypeError, ValueError):
                pass
        lv = self.sourceModel().data(left,  Qt.ItemDataRole.DisplayRole) or ""
        rv = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return str(lv).lower() < str(rv).lower()


# ── Tree view widget ──────────────────────────────────────────────────────────

class TreeFileView(QWidget):
    """
    Collapsible tree view of the scanned directory.
    - Folders expand to show subdirectories and files
    - Size column shows human-readable size
    - Size Bar column shows proportional bar + % of parent
    - Right-click: copy path, open in Explorer, delete

    Signals:
        node_selected(FileNode)
    """
    node_selected = pyqtSignal(object)

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
        layout.addLayout(bar)

        # Model + proxy
        self._model = FileTreeModel()
        self._proxy = TreeSortProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(COL_NAME)
        self._proxy.setRecursiveFilteringEnabled(True)

        # Tree view
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setUniformRowHeights(True)
        self._tree.setAnimated(False)          # smoother on large trees
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(COL_SIZE, Qt.SortOrder.DescendingOrder)
        self._tree.setIndentation(16)

        # Column widths
        hdr = self._tree.header()
        hdr.setSectionResizeMode(COL_NAME,  QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_SIZE,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_BAR,   QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_FILES, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_MOD,   QHeaderView.ResizeMode.Fixed)
        self._tree.setColumnWidth(COL_SIZE,  90)
        self._tree.setColumnWidth(COL_BAR,   180)
        self._tree.setColumnWidth(COL_FILES, 70)
        self._tree.setColumnWidth(COL_MOD,   140)

        # Size bar delegate on COL_BAR
        self._bar_delegate = SizeBarDelegate(self._tree)
        self._tree.setItemDelegateForColumn(COL_BAR, self._bar_delegate)

        # Row height — QTreeView has no verticalHeader, use stylesheet
        self._tree.setStyleSheet("QTreeView::item { height: 22px; }")

        self._tree.clicked.connect(self._on_click)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)

        layout.addWidget(self._tree)

    # ── Public ───────────────────────────────────────────────────────────────

    def set_root(self, root: FileNode):
        self._root = root
        self._model.set_root(root)

    def clear(self):
        self._model.clear()

    def set_dirs_first(self, enabled: bool):
        self._proxy.set_dirs_first(enabled)

    # ── Internals ────────────────────────────────────────────────────────────

    def _apply_filter(self, text: str):
        self._proxy.setFilterFixedString(text)

    def _on_click(self, proxy_index: QModelIndex):
        src_index = self._proxy.mapToSource(proxy_index)
        node = self._model.get_node(src_index)
        if node:
            self.node_selected.emit(node)

    def _get_node_at(self, pos) -> FileNode | None:
        proxy_index = self._tree.indexAt(pos)
        if not proxy_index.isValid():
            return None
        src_index = self._proxy.mapToSource(proxy_index)
        return self._model.get_node(src_index)

    def _context_menu(self, pos):
        node = self._get_node_at(pos)
        if not node:
            return

        menu = QMenu(self)
        act_copy = menu.addAction("📋  Copy Path")
        act_open = menu.addAction("📂  Open in Explorer")
        menu.addSeparator()
        act_del  = menu.addAction("🗑️  Delete…")

        action = menu.exec(self._tree.viewport().mapToGlobal(pos))

        if action == act_copy:
            QApplication.clipboard().setText(node.path)
        elif action == act_open:
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
            try:
                if node.is_dir:
                    shutil.rmtree(node.path)
                else:
                    os.remove(node.path)
            except Exception as e:
                QMessageBox.critical(self, "DELETE FAILED", str(e))
