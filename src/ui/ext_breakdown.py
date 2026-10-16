# ============================================================
# ui/ext_breakdown.py — Extension breakdown panel
# ============================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PyQt6.QtGui  import QColor, QFont, QPainter, QBrush
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from src.scanner import FileNode, format_size, get_extension_breakdown
from src.theme   import CP_CYAN, CP_YELLOW, CP_SUBTEXT, CP_DIM, CP_PANEL


COLUMNS = ["Extension", "Total Size", "File Count", "Avg Size", "% of Total"]
C_EXT, C_SIZE, C_COUNT, C_AVG, C_PCT = range(5)


class BarDelegate(QStyledItemDelegate):
    """Renders a cyan progress bar behind the % column."""
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        if index.column() != C_PCT:
            super().paint(painter, option, index)
            return

        pct_text = index.data(Qt.ItemDataRole.DisplayRole) or "0%"
        try:
            pct = float(pct_text.rstrip("%"))
        except ValueError:
            pct = 0.0

        rect = option.rect

        # Background
        painter.fillRect(rect, QColor(CP_PANEL))

        # Bar
        bar_width = max(0, int(rect.width() * pct / 100))
        if bar_width > 0:
            bar_rect = rect.adjusted(0, 2, -(rect.width() - bar_width), -2)
            painter.fillRect(bar_rect, QColor("#00303a"))

        # Text
        painter.setPen(QColor(CP_CYAN))
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(rect.adjusted(4, 0, -4, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                         pct_text)


class ExtModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._rows: list[tuple] = []   # (ext, size, count, avg, pct)
        self._total_size = 0

    def set_data(self, breakdown: dict):
        self.beginResetModel()
        total = sum(v["size"] for v in breakdown.values())
        self._total_size = total
        rows = []
        for ext, info in breakdown.items():
            avg = info["size"] // max(info["count"], 1)
            pct = (info["size"] / total * 100) if total > 0 else 0.0
            rows.append((ext, info["size"], info["count"], avg, pct))
        rows.sort(key=lambda r: r[1], reverse=True)
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        ext, size, count, avg, pct = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == C_EXT:   return ext
            if col == C_SIZE:  return format_size(size)
            if col == C_COUNT: return str(count)
            if col == C_AVG:   return format_size(avg)
            if col == C_PCT:   return f"{pct:.1f}%"

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == C_SIZE:  return QColor(CP_CYAN)
            if col == C_COUNT: return QColor(CP_YELLOW)
            if col == C_AVG:   return QColor(CP_SUBTEXT)

        elif role == Qt.ItemDataRole.UserRole:
            if col == C_SIZE:  return size
            if col == C_COUNT: return count
            if col == C_AVG:   return avg
            if col == C_PCT:   return pct
            return None

        elif role == Qt.ItemDataRole.FontRole:
            return QFont("Consolas", 9)

        return None


class ExtSortProxy(QSortFilterProxyModel):
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        col = left.column()
        if col in (C_SIZE, C_COUNT, C_AVG, C_PCT):
            lv = self.sourceModel().data(left,  Qt.ItemDataRole.UserRole) or 0
            rv = self.sourceModel().data(right, Qt.ItemDataRole.UserRole) or 0
            return lv < rv
        lv = self.sourceModel().data(left,  Qt.ItemDataRole.DisplayRole) or ""
        rv = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return str(lv) < str(rv)


class ExtBreakdownPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("EXTENSION BREAKDOWN"))
        self._total_label = QLabel("")
        self._total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        hdr.addWidget(self._total_label)
        layout.addLayout(hdr)

        self._model = ExtModel()
        self._proxy = ExtSortProxy()
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(C_EXT, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(C_SIZE,  110)
        self._table.setColumnWidth(C_COUNT, 80)
        self._table.setColumnWidth(C_AVG,   100)
        self._table.setColumnWidth(C_PCT,   120)
        self._table.sortByColumn(C_SIZE, Qt.SortOrder.DescendingOrder)
        self._table.setItemDelegateForColumn(C_PCT, BarDelegate(self._table))

        layout.addWidget(self._table)

    def set_root(self, root: FileNode):
        breakdown = get_extension_breakdown(root)
        self._model.set_data(breakdown)
        total = sum(v["size"] for v in breakdown.values())
        self._total_label.setText(
            f"{len(breakdown)} types  │  {format_size(total)} total"
        )
