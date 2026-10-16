# ============================================================
# scanner.py — Threaded directory scanner with Qt signals
# ============================================================

import os
import time
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class FileNode:
    """Represents a file or directory in the scanned tree."""
    name: str
    path: str
    size: int           # bytes (total for dirs, actual for files)
    is_dir: bool
    modified: float     # Unix timestamp of last modification
    file_count: int     # number of files underneath (1 for files)
    children: list      # list[FileNode]
    parent: Optional[object] = field(default=None, repr=False, compare=False)
    extension: str = ""

    def size_str(self) -> str:
        return format_size(self.size)

    def pct_of_parent(self) -> float:
        if self.parent and self.parent.size > 0:
            return (self.size / self.parent.size) * 100.0
        return 0.0


def format_size(size_bytes: int) -> str:
    """Human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    elif size_bytes < 1024 ** 4:
        return f"{size_bytes / 1024 ** 3:.1f} GB"
    else:
        return f"{size_bytes / 1024 ** 4:.2f} TB"


class ScannerThread(QThread):
    """
    Threaded directory scanner.

    Signals:
        progress(str)           — emitted for each file/dir processed (path string)
        node_ready(FileNode)    — emitted when a top-level child node is complete
        scan_complete(FileNode) — emitted with root node when scan finishes
        scan_error(str)         — emitted if a fatal error occurs
        stats_update(int, int)  — (total_files, total_dirs) periodic stats
    """
    progress      = pyqtSignal(str)
    node_ready    = pyqtSignal(object)
    scan_complete = pyqtSignal(object)
    scan_error    = pyqtSignal(str)
    stats_update  = pyqtSignal(int, int)

    def __init__(self, root_path: str, parent=None):
        super().__init__(parent)
        self.root_path = root_path
        self._abort = False
        self._total_files = 0
        self._total_dirs  = 0

    def abort(self):
        self._abort = True

    def run(self):
        try:
            root_node = self._scan_dir(self.root_path, parent=None, is_root=True)
            if not self._abort:
                self.scan_complete.emit(root_node)
        except PermissionError as e:
            self.scan_error.emit(f"Permission denied: {e}")
        except Exception as e:
            self.scan_error.emit(f"Scan error: {e}")

    def _scan_dir(self, path: str, parent: Optional[FileNode], is_root: bool = False) -> FileNode:
        """Recursively scan a directory, returning a populated FileNode."""
        if self._abort:
            raise InterruptedError("Scan aborted")

        try:
            stat = os.stat(path)
            modified = stat.st_mtime
        except (PermissionError, OSError):
            modified = 0.0

        node = FileNode(
            name=os.path.basename(path) or path,
            path=path,
            size=0,
            is_dir=True,
            modified=modified,
            file_count=0,
            children=[],
            parent=parent,
        )

        self._total_dirs += 1
        self.progress.emit(path)

        try:
            entries = list(os.scandir(path))
        except PermissionError:
            return node

        for entry in entries:
            if self._abort:
                break
            try:
                if entry.is_dir(follow_symlinks=False):
                    child = self._scan_dir(entry.path, parent=node)
                    node.children.append(child)
                    node.size       += child.size
                    node.file_count += child.file_count
                else:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        fsize    = stat.st_size
                        fmod     = stat.st_mtime
                    except (PermissionError, OSError):
                        fsize = 0
                        fmod  = 0.0

                    ext = os.path.splitext(entry.name)[1].lower()
                    file_node = FileNode(
                        name=entry.name,
                        path=entry.path,
                        size=fsize,
                        is_dir=False,
                        modified=fmod,
                        file_count=1,
                        children=[],
                        parent=node,
                        extension=ext,
                    )
                    node.children.append(file_node)
                    node.size       += fsize
                    node.file_count += 1
                    self._total_files += 1
                    self.progress.emit(entry.path)

            except (PermissionError, OSError):
                continue

        # Sort children by size descending for a nice treemap
        node.children.sort(key=lambda n: n.size, reverse=True)

        # Emit top-level children as they complete
        if is_root:
            self.stats_update.emit(self._total_files, self._total_dirs)

        return node


def build_flat_list(node: FileNode, result: list | None = None) -> list:
    """
    Flatten the FileNode tree into a list for the table view.
    Returns list of FileNode (files only, or all, depending on caller).
    """
    if result is None:
        result = []
    result.append(node)
    for child in node.children:
        build_flat_list(child, result)
    return result


def get_top_files(root: FileNode, n: int = 100) -> list:
    """Return the N largest files (non-directories) from the tree."""
    all_nodes = build_flat_list(root)
    files = [nd for nd in all_nodes if not nd.is_dir]
    files.sort(key=lambda nd: nd.size, reverse=True)
    return files[:n]


def get_extension_breakdown(root: FileNode) -> dict:
    """
    Returns dict: { ".ext": {"size": int, "count": int} }
    for all files in the tree.
    """
    breakdown: dict[str, dict] = {}
    all_nodes = build_flat_list(root)
    for nd in all_nodes:
        if nd.is_dir:
            continue
        ext = nd.extension or "(no ext)"
        if ext not in breakdown:
            breakdown[ext] = {"size": 0, "count": 0}
        breakdown[ext]["size"]  += nd.size
        breakdown[ext]["count"] += 1
    return breakdown
