# ============================================================
# scanner.py — Threaded directory scanner with Qt signals
# ============================================================

import os
import time
import threading
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


@dataclass
class ScanResult:
    """All data the UI needs, pre-computed on the worker thread."""
    root:        "FileNode"
    flat_list:   list          # all FileNode objects flattened
    top_files:   list          # top N largest files
    ext_map:     dict          # extension breakdown
    elapsed:     float


class ScannerThread(QThread):
    """
    Threaded directory scanner.

    Signals:
        progress(str)             — throttled live path feed (every 500 files)
        stats_update(int, int)    — (total_files, total_dirs) every 2000 files
        scan_complete(ScanResult) — all data pre-computed, ready to hand to UI
        scan_error(str)           — fatal error message
    """
    progress      = pyqtSignal(str)
    stats_update  = pyqtSignal(int, int)
    scan_complete = pyqtSignal(object)   # ScanResult
    scan_error    = pyqtSignal(str)

    PROGRESS_INTERVAL = 500
    STATS_INTERVAL    = 2000

    def __init__(self, root_path: str, top_n: int = 100, parent=None):
        super().__init__(parent)
        self.root_path   = root_path
        self.top_n       = top_n
        self._abort      = False
        self._file_count = 0
        self._dir_count  = 0
        self._t_start    = 0.0

    def abort(self):
        self._abort = True

    def run(self):
        self._t_start = time.perf_counter()
        try:
            root = self._scan_dir(self.root_path, parent=None)
            if self._abort:
                return

            # ── Post-processing on worker thread so UI never blocks ──────────
            self.progress.emit("  Post-processing…")

            flat   = _build_flat_list(root)
            top    = _get_top_files_from_flat(flat, self.top_n)
            ext    = _get_ext_breakdown_from_flat(flat)

            elapsed = time.perf_counter() - self._t_start

            self.stats_update.emit(self._file_count, self._dir_count)
            self.scan_complete.emit(ScanResult(
                root=root, flat_list=flat,
                top_files=top, ext_map=ext,
                elapsed=elapsed,
            ))

        except InterruptedError:
            pass
        except Exception as e:
            self.scan_error.emit(f"Scan error: {e}")

    # ── Core recursive scanner ────────────────────────────────────────────────

    def _scan_dir(self, path: str, parent: Optional[FileNode],
                  dir_entry: Optional[os.DirEntry] = None) -> FileNode:
        if self._abort:
            raise InterruptedError()

        # Reuse DirEntry cached stat when available — avoids extra syscall
        try:
            modified = (dir_entry.stat(follow_symlinks=False).st_mtime
                        if dir_entry is not None else os.stat(path).st_mtime)
        except OSError:
            modified = 0.0

        node = FileNode(
            name       = os.path.basename(path) or path,
            path       = path,
            size       = 0,
            is_dir     = True,
            modified   = modified,
            file_count = 0,
            children   = [],
            parent     = parent,
        )
        self._dir_count += 1

        try:
            entries = list(os.scandir(path))
        except (PermissionError, OSError):
            return node

        for entry in entries:
            if self._abort:
                raise InterruptedError()
            try:
                if entry.is_dir(follow_symlinks=False):
                    child = self._scan_dir(entry.path, parent=node, dir_entry=entry)
                    node.children.append(child)
                    node.size       += child.size
                    node.file_count += child.file_count
                else:
                    try:
                        st    = entry.stat(follow_symlinks=False)
                        fsize = st.st_size
                        fmod  = st.st_mtime
                    except OSError:
                        fsize = 0
                        fmod  = 0.0

                    ext = os.path.splitext(entry.name)[1].lower()
                    file_node = FileNode(
                        name       = entry.name,
                        path       = entry.path,
                        size       = fsize,
                        is_dir     = False,
                        modified   = fmod,
                        file_count = 1,
                        children   = [],
                        parent     = node,
                        extension  = ext,
                    )
                    node.children.append(file_node)
                    node.size       += fsize
                    node.file_count += 1
                    self._file_count += 1

                    fc = self._file_count
                    if fc % self.PROGRESS_INTERVAL == 0:
                        self.progress.emit(entry.path)
                    if fc % self.STATS_INTERVAL == 0:
                        self.stats_update.emit(fc, self._dir_count)

            except (PermissionError, OSError):
                continue

        # Sort for treemap layout only — O(n log n) per dir, deferred to worker
        node.children.sort(key=lambda n: n.size, reverse=True)
        return node


# ── Post-processing helpers (run on worker thread) ────────────────────────────

def _build_flat_list(node: FileNode, result: list | None = None) -> list:
    if result is None:
        result = []
    result.append(node)
    for child in node.children:
        _build_flat_list(child, result)
    return result


def _get_top_files_from_flat(flat: list, n: int) -> list:
    files = [nd for nd in flat if not nd.is_dir]
    files.sort(key=lambda nd: nd.size, reverse=True)
    return files[:n]


def _get_ext_breakdown_from_flat(flat: list) -> dict:
    breakdown: dict[str, dict] = {}
    for nd in flat:
        if nd.is_dir:
            continue
        ext = nd.extension or "(no ext)"
        if ext not in breakdown:
            breakdown[ext] = {"size": 0, "count": 0}
        breakdown[ext]["size"]  += nd.size
        breakdown[ext]["count"] += 1
    return breakdown


# ── Public helpers (used by other modules) ────────────────────────────────────

def build_flat_list(node: FileNode, result: list | None = None) -> list:
    """Public wrapper — builds a flat list of all FileNodes."""
    return _build_flat_list(node, result)


def get_top_files(root: FileNode, n: int = 100) -> list:
    flat = _build_flat_list(root)
    return _get_top_files_from_flat(flat, n)


def get_extension_breakdown(root: FileNode) -> dict:
    flat = _build_flat_list(root)
    return _get_ext_breakdown_from_flat(flat)
