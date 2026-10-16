# ============================================================
# treemap.py — Custom QPainter squarified treemap widget
# ============================================================

import time
from typing import Optional

from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore    import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui     import QPainter, QColor, QFont, QBrush, QPen, QCursor

from src.scanner import FileNode, format_size
from src.theme   import (CP_BG, CP_PANEL, CP_DIM, CP_TEXT, CP_CYAN,
                          CP_YELLOW, CP_RED, CP_ORANGE,
                          HEAT_COLD, HEAT_COOL, HEAT_WARM, HEAT_HOT)


# Age thresholds in seconds
ONE_DAY   = 86_400
ONE_WEEK  = 604_800
ONE_MONTH = 2_592_000


def _age_color(modified_ts: float) -> QColor:
    """Map file modification time to a heatmap color."""
    age = time.time() - modified_ts
    if age < ONE_DAY:
        return QColor(HEAT_HOT)
    elif age < ONE_WEEK:
        return QColor(HEAT_WARM)
    elif age < ONE_MONTH:
        return QColor(HEAT_COOL)
    else:
        return QColor(HEAT_COLD)


def _ext_color(ext: str) -> QColor:
    """Map file extension to a distinct color bucket."""
    EXT_COLORS = {
        ".mp4": "#8b0000", ".mkv": "#8b0000", ".avi": "#8b0000", ".mov": "#8b0000",
        ".mp3": "#4b0082", ".flac": "#4b0082", ".wav": "#4b0082",
        ".jpg": "#006400", ".jpeg": "#006400", ".png": "#006400", ".gif": "#006400",
        ".zip": "#8b4513", ".rar": "#8b4513", ".7z": "#8b4513", ".tar": "#8b4513",
        ".exe": "#b8860b", ".dll": "#b8860b", ".msi": "#b8860b",
        ".py":  "#00688b", ".js":  "#00688b", ".ts":  "#00688b",
        ".pdf": "#8b0000",
        ".doc": "#00008b", ".docx": "#00008b", ".xlsx": "#00008b",
    }
    color_hex = EXT_COLORS.get(ext.lower(), "#2a2a2a")
    return QColor(color_hex)


class _Block:
    """Stores a rendered rectangle + the node it maps to."""
    __slots__ = ("rect", "node")
    def __init__(self, rect: QRect, node: FileNode):
        self.rect = rect
        self.node = node


class TreemapWidget(QWidget):
    """
    Interactive squarified treemap.

    Signals:
        node_clicked(FileNode)  — user clicked a directory or file
        node_hovered(FileNode)  — user hovered a block
    """
    node_clicked = pyqtSignal(object)
    node_hovered = pyqtSignal(object)

    # Color modes
    MODE_AGE = "age"
    MODE_EXT = "ext"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root:    Optional[FileNode] = None
        self._current: Optional[FileNode] = None  # currently zoomed node
        self._blocks:  list[_Block]       = []
        self._hovered: Optional[_Block]   = None
        self._color_mode: str             = self.MODE_EXT
        self._nav_stack: list[FileNode]   = []

        self.setMouseTracking(True)
        self.setMinimumSize(300, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_root(self, root: FileNode):
        self._root    = root
        self._current = root
        self._nav_stack = []
        self._rebuild()

    def set_color_mode(self, mode: str):
        self._color_mode = mode
        self.update()

    def navigate_up(self):
        if self._nav_stack:
            self._current = self._nav_stack.pop()
            self._rebuild()

    def current_node(self) -> Optional[FileNode]:
        return self._current

    # ── Layout ──────────────────────────────────────────────────────────────

    def _rebuild(self):
        self._blocks = []
        if self._current and self._current.size > 0:
            rect = QRect(0, 0, self.width(), self.height())
            self._squarify(self._current.children, rect, self._current.size)
        self.update()

    def _squarify(self, nodes: list, rect: QRect, total_size: int):
        """Squarified treemap layout algorithm."""
        nodes = [n for n in nodes if n.size > 0]
        if not nodes or rect.width() <= 0 or rect.height() <= 0:
            return

        if len(nodes) == 1:
            self._blocks.append(_Block(rect, nodes[0]))
            return

        # Lay out nodes using the squarify heuristic
        self._squarify_row(nodes, rect, total_size)

    def _squarify_row(self, nodes: list, rect: QRect, total_size: int):
        if not nodes:
            return

        w = rect.width()
        h = rect.height()

        if total_size == 0:
            return

        # Determine split direction (always split along the shorter axis)
        horizontal = w >= h

        # Build rows greedily
        row: list[FileNode] = []
        row_size = 0
        best_ratio = float("inf")

        for i, node in enumerate(nodes):
            test_row = row + [node]
            test_size = row_size + node.size
            ratio = self._worst_ratio(test_row, test_size, rect, total_size, horizontal)

            if ratio <= best_ratio or not row:
                row       = test_row
                row_size  = test_size
                best_ratio = ratio
            else:
                break  # Adding this node makes things worse — cut the row here

        # Layout the row
        row_frac = row_size / total_size if total_size > 0 else 0

        if horizontal:
            row_w = max(1, int(round(w * row_frac)))
            row_rect = QRect(rect.x(), rect.y(), row_w, h)
            rest_rect = QRect(rect.x() + row_w, rect.y(), w - row_w, h)
        else:
            row_h = max(1, int(round(h * row_frac)))
            row_rect = QRect(rect.x(), rect.y(), w, row_h)
            rest_rect = QRect(rect.x(), rect.y() + row_h, w, h - row_h)

        # Subdivide the row
        self._layout_row(row, row_rect, row_size, not horizontal)

        # Recurse for the rest
        rest_nodes = [n for n in nodes if n not in row]
        rest_size  = total_size - row_size
        if rest_nodes and rest_size > 0:
            self._squarify_row(rest_nodes, rest_rect, rest_size)

    def _layout_row(self, row: list, rect: QRect, row_size: int, vertical: bool):
        """Divide a row rect among nodes proportionally."""
        if row_size == 0:
            return
        x, y = rect.x(), rect.y()
        w, h  = rect.width(), rect.height()

        for i, node in enumerate(row):
            frac = node.size / row_size
            if vertical:
                bh = max(1, int(round(h * frac))) if i < len(row) - 1 else (rect.y() + h - y)
                block_rect = QRect(x, y, w, bh)
                y += bh
            else:
                bw = max(1, int(round(w * frac))) if i < len(row) - 1 else (rect.x() + w - x)
                block_rect = QRect(x, y, bw, h)
                x += bw
            self._blocks.append(_Block(block_rect, node))

    @staticmethod
    def _worst_ratio(row: list, row_size: int, rect: QRect,
                     total_size: int, horizontal: bool) -> float:
        if not row or row_size == 0 or total_size == 0:
            return float("inf")
        w, h = rect.width(), rect.height()
        if horizontal:
            length = max(1, w * row_size / total_size)
        else:
            length = max(1, h * row_size / total_size)

        worst = 0.0
        for node in row:
            area  = (node.size / row_size) * length * (h if horizontal else w)
            side  = area / length if length > 0 else 1
            ratio = max(length / side, side / length) if side > 0 else float("inf")
            worst = max(worst, ratio)
        return worst

    # ── Paint ───────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background
        painter.fillRect(self.rect(), QColor(CP_BG))

        if not self._blocks:
            painter.setPen(QColor(CP_DIM))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No data — scan a directory first")
            painter.end()
            return

        font = QFont("Consolas", 8)
        painter.setFont(font)

        for block in self._blocks:
            node = block.node
            rect = block.rect
            if rect.width() < 2 or rect.height() < 2:
                continue

            # Fill color
            if self._color_mode == self.MODE_AGE:
                color = _age_color(node.modified)
            else:
                color = _ext_color(node.extension) if not node.is_dir else QColor("#1a1a1a")

            # Hover highlight
            is_hovered = self._hovered is not None and self._hovered is block
            if is_hovered:
                color = color.lighter(160)

            painter.fillRect(rect, color)

            # Border
            border_color = QColor(CP_CYAN) if is_hovered else QColor(CP_BG)
            pen = QPen(border_color, 1)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Label if big enough
            if rect.width() > 60 and rect.height() > 20:
                text_color = QColor(CP_TEXT) if not is_hovered else QColor(CP_BG)
                painter.setPen(text_color)
                label_rect = rect.adjusted(3, 2, -3, -2)
                name = node.name
                if rect.height() > 36:
                    painter.drawText(label_rect,
                                     Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                                     name)
                    painter.setPen(QColor(CP_YELLOW) if not is_hovered else QColor(CP_BG))
                    painter.drawText(label_rect,
                                     Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                                     node.size_str())
                else:
                    painter.drawText(label_rect,
                                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                     f"{name}  {node.size_str()}")

        painter.end()

    # ── Mouse ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        self._rebuild()

    def _block_at(self, pos: QPoint) -> Optional[_Block]:
        for block in reversed(self._blocks):
            if block.rect.contains(pos):
                return block
        return None

    def mouseMoveEvent(self, event):
        block = self._block_at(event.pos())
        if block != self._hovered:
            self._hovered = block
            self.update()
        if block:
            self.node_hovered.emit(block.node)
            tip = (f"{block.node.path}\n"
                   f"Size: {block.node.size_str()}\n"
                   f"Files: {block.node.file_count}")
            QToolTip.showText(QCursor.pos(), tip, self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            block = self._block_at(event.pos())
            if block:
                self.node_clicked.emit(block.node)
                if block.node.is_dir and block.node.children:
                    self._nav_stack.append(self._current)
                    self._current = block.node
                    self._rebuild()
        elif event.button() == Qt.MouseButton.RightButton:
            self.navigate_up()

    def leaveEvent(self, event):
        self._hovered = None
        self.update()
