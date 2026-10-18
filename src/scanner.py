# ============================================================
# scanner.py — Multithreaded directory scanner with Qt signals
#
# Strategy:
#   1. Scan the root's immediate children to find top-level subdirs
#   2. Dispatch each subdir to a ThreadPoolExecutor (up to MAX_WORKERS)
#   3. Each worker recursively scans its subtree independently
#   4. Results merged back into root node on the QThread
# ============================================================

import os
import stat
import time
import threading
import fnmatch
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

# Workers = logical CPU count, capped so we don't thrash on HDD
import os as _os
_CPU = _os.cpu_count() or 4
MAX_WORKERS = min(_CPU, 8)


def _is_reparse_entry(entry: os.DirEntry, st=None) -> bool:
    """Identify symbolic links and Windows reparse points without following them."""
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return False
    try:
        st = st or entry.stat(follow_symlinks=False)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(getattr(st, "st_file_attributes", 0) & reparse_flag)
    except OSError:
        return False


def _entry_is_directory(entry: os.DirEntry, is_reparse: bool) -> bool:
    """Get link target type only for display; never recurse into a link."""
    try:
        return entry.is_dir(follow_symlinks=is_reparse)
    except OSError:
        return False


def _is_excluded(path: str, root_path: str, patterns: tuple[str, ...],
                 is_directory: bool = False) -> bool:
    if not patterns:
        return False
    relative = os.path.relpath(path, root_path).replace("\\", "/").casefold()
    name = os.path.basename(path).casefold()
    path_candidates = ["/".join(relative.split("/")[index:])
                       for index in range(len(relative.split("/")))]
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/").casefold()
        if (fnmatch.fnmatchcase(name, normalized_pattern)
                or any(fnmatch.fnmatchcase(candidate, normalized_pattern)
                       for candidate in path_candidates)):
            return True
        # A contents pattern such as "node_modules/*" should prune the
        # node_modules directory itself before scandir enters it.
        if is_directory and any(fnmatch.fnmatchcase(
                candidate + "/__excluded_child__", normalized_pattern)
                for candidate in path_candidates):
            return True
    return False


@dataclass
class FileNode:
    """Represents a file or directory in the scanned tree."""
    name:       str
    path:       str
    size:       int           # bytes (total for dirs, actual for files)
    is_dir:     bool
    modified:   float         # Unix timestamp of last modification
    file_count: int           # files underneath (1 for files)
    children:   list          # list[FileNode]
    parent:     Optional[object] = field(default=None, repr=False, compare=False)
    extension:  str = ""
    previous_size: Optional[int] = None
    change_status: str = ""
    change_pct: Optional[float] = None
    change_delta: Optional[int] = None
    is_link: bool = False

    def size_str(self) -> str:
        return format_size(self.size)

    def pct_of_parent(self) -> float:
        if self.parent and self.parent.size > 0:
            return (self.size / self.parent.size) * 100.0
        return 0.0


def format_size(size_bytes: int) -> str:
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
    root:      "FileNode"
    flat_list: list
    top_files: list
    ext_map:   dict
    elapsed:   float


# ── Shared counter (thread-safe via GIL on int ops) ───────────────────────────

class _Counter:
    __slots__ = ("files", "dirs", "_lock")
    def __init__(self):
        self.files = 0
        self.dirs  = 0
        self._lock = threading.Lock()

    def add_file(self):
        with self._lock:
            self.files += 1
            return self.files

    def add_dir(self):
        with self._lock:
            self.dirs += 1
            return self.dirs


# ── Core recursive scanner (runs on worker threads) ───────────────────────────

def _scan_dir(path: str,
              parent: Optional[FileNode],
              abort_flag: list,          # [False] — set to [True] to abort
              counter: _Counter,
              progress_cb,               # callable(path) — throttled
              dir_entry: Optional[os.DirEntry] = None,
              follow_dir_symlinks: bool = False,
              ancestor_paths: frozenset[str] = frozenset(),
              is_link: bool = False,
              exclude_patterns: tuple[str, ...] = (),
              scan_root_path: str | None = None) -> FileNode:
    """
    Recursively scan a directory.
    Thread-safe: each call owns its own node; counters use a lock.
    """
    if abort_flag[0]:
        raise InterruptedError()

    try:
        modified = (dir_entry.stat(follow_symlinks=False).st_mtime
                    if dir_entry is not None else os.stat(path).st_mtime)
    except OSError:
        modified = 0.0

    node = FileNode(
        name       = os.path.basename(path) or path.rstrip("\\/"),
        path       = path,
        size       = 0,
        is_dir     = True,
        modified   = modified,
        file_count = 0,
        children   = [],
        parent     = parent,
        is_link    = is_link,
    )
    counter.add_dir()

    try:
        entries = list(os.scandir(path))
    except (PermissionError, OSError):
        return node

    for entry in entries:
        if abort_flag[0]:
            raise InterruptedError()
        try:
            st = entry.stat(follow_symlinks=False)
            is_reparse = _is_reparse_entry(entry, st)
            is_directory = _entry_is_directory(entry, is_reparse)
            if _is_excluded(entry.path, scan_root_path or path,
                            exclude_patterns, is_directory):
                continue
            can_follow = is_reparse and is_directory and follow_dir_symlinks
            target_identity = os.path.normcase(os.path.realpath(entry.path)) if is_directory else ""
            if is_directory and (not is_reparse or can_follow) and target_identity not in ancestor_paths:
                child = _scan_dir(entry.path, parent=node,
                                   abort_flag=abort_flag, counter=counter,
                                   progress_cb=progress_cb, dir_entry=entry,
                                   follow_dir_symlinks=follow_dir_symlinks,
                                   ancestor_paths=ancestor_paths | {os.path.normcase(os.path.realpath(path))},
                                   is_link=is_reparse,
                                   exclude_patterns=exclude_patterns,
                                   scan_root_path=scan_root_path or path)
                node.children.append(child)
                node.size       += child.size
                node.file_count += child.file_count
            elif is_directory and can_follow and target_identity in ancestor_paths:
                # Display cyclic links without recursing back into an ancestor.
                node.children.append(FileNode(
                    name=entry.name, path=entry.path, size=0, is_dir=True,
                    modified=st.st_mtime, file_count=0, children=[], parent=node,
                    is_link=True,
                ))
                counter.add_dir()
            else:
                try:
                    size_stat = entry.stat(follow_symlinks=follow_dir_symlinks and is_reparse)
                    fsize = size_stat.st_size
                    fmod  = size_stat.st_mtime
                except OSError:
                    fsize = 0
                    fmod  = 0.0

                ext = os.path.splitext(entry.name)[1].lower()
                file_node = FileNode(
                    name       = entry.name,
                    path       = entry.path,
                    size       = fsize,
                    is_dir     = is_directory,
                    modified   = fmod,
                    file_count = 0 if is_directory else 1,
                    children   = [],
                    parent     = node,
                    extension  = ext,
                    is_link    = is_reparse,
                )
                node.children.append(file_node)
                node.size       += fsize
                node.file_count += file_node.file_count

                if is_directory:
                    counter.add_dir()
                else:
                    fc = counter.add_file()
                    if fc % 500 == 0:
                        progress_cb(entry.path, counter.files, counter.dirs)

        except (PermissionError, OSError):
            continue

    node.children.sort(key=lambda n: n.size, reverse=True)
    return node


# ── QThread wrapper ───────────────────────────────────────────────────────────

class ScannerThread(QThread):
    """
    Signals:
        progress(str)             — throttled live path feed
        stats_update(int, int)    — (total_files, total_dirs)
        scan_complete(ScanResult) — all data pre-computed
        scan_error(str)           — fatal error
    """
    progress      = pyqtSignal(str)
    stats_update  = pyqtSignal(int, int)
    scan_complete = pyqtSignal(object)
    scan_error    = pyqtSignal(str)

    def __init__(self, root_path: str, top_n: int = 100, parent=None,
                 follow_dir_symlinks: bool = False,
                 exclude_patterns: list[str] | None = None):
        super().__init__(parent)
        self.root_path  = root_path
        self.top_n      = top_n
        self.follow_dir_symlinks = follow_dir_symlinks
        self.exclude_patterns = tuple(p.strip() for p in (exclude_patterns or []) if p.strip())
        self._abort     = [False]   # list so worker threads share the reference
        self._counter   = _Counter()

    def abort(self):
        self._abort[0] = True

    def run(self):
        t_start = time.perf_counter()
        try:
            root = self._parallel_scan(self.root_path)
            if self._abort[0]:
                return

            self.progress.emit("  Post-processing…")
            flat    = _build_flat_list(root)
            top     = _get_top_files_from_flat(flat, self.top_n)
            ext     = _get_ext_breakdown_from_flat(flat)
            elapsed = time.perf_counter() - t_start

            self.stats_update.emit(self._counter.files, self._counter.dirs)
            self.scan_complete.emit(ScanResult(
                root=root, flat_list=flat,
                top_files=top, ext_map=ext,
                elapsed=elapsed,
            ))

        except InterruptedError:
            pass
        except Exception as e:
            self.scan_error.emit(f"Scan error: {e}")

    def _progress_cb(self, path: str, files: int, dirs: int):
        """Called from worker threads — emit signals back to UI thread."""
        self.progress.emit(path)
        if files % 2000 == 0:
            self.stats_update.emit(files, dirs)

    def _parallel_scan(self, root_path: str) -> FileNode:
        """
        Scan root's immediate children, then fan out top-level subdirs
        across a thread pool. Files at root level are handled inline.
        """
        abort   = self._abort
        counter = self._counter
        cb      = self._progress_cb

        # Get root mtime
        try:
            root_mtime = os.stat(root_path).st_mtime
        except OSError:
            root_mtime = 0.0

        root_node = FileNode(
            name       = os.path.basename(root_path) or root_path.rstrip("\\/"),
            path       = root_path,
            size       = 0,
            is_dir     = True,
            modified   = root_mtime,
            file_count = 0,
            children   = [],
            parent     = None,
        )
        counter.add_dir()

        # Read root entries
        try:
            root_entries = list(os.scandir(root_path))
        except (PermissionError, OSError):
            return root_node

        # Split into files (handle inline) and subdirs (parallelise)
        root_files = []
        root_dirs  = []
        for entry in root_entries:
            try:
                is_reparse = _is_reparse_entry(entry)
                is_directory = _entry_is_directory(entry, is_reparse)
                if _is_excluded(entry.path, root_path, self.exclude_patterns, is_directory):
                    continue
                if is_directory and (not is_reparse or self.follow_dir_symlinks):
                    root_dirs.append(entry)
                else:
                    root_files.append(entry)
            except OSError:
                continue

        # Handle files directly in root
        for entry in root_files:
            if abort[0]:
                raise InterruptedError()
            try:
                st    = entry.stat(follow_symlinks=False)
                is_reparse = _is_reparse_entry(entry, st)
                size_stat = entry.stat(follow_symlinks=self.follow_dir_symlinks and is_reparse)
                fsize = size_stat.st_size
                fmod  = size_stat.st_mtime
            except OSError:
                st = None
                fsize = 0
                fmod  = 0.0
            ext = os.path.splitext(entry.name)[1].lower()
            is_reparse = _is_reparse_entry(entry, st)
            is_directory_link = is_reparse and _entry_is_directory(entry, True)
            fn  = FileNode(
                name=entry.name, path=entry.path,
                size=fsize, is_dir=is_directory_link, modified=fmod,
                file_count=0 if is_directory_link else 1, children=[], parent=root_node,
                extension=ext, is_link=is_reparse,
            )
            root_node.children.append(fn)
            root_node.size       += fsize
            root_node.file_count += fn.file_count
            if is_directory_link:
                counter.add_dir()
            else:
                counter.add_file()

        # Parallelise subdirectory scanning
        self.progress.emit(f"  Scanning with {MAX_WORKERS} threads…")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(
                    _scan_dir, entry.path, root_node,
                    abort, counter, cb, entry,
                    self.follow_dir_symlinks,
                    frozenset({os.path.normcase(os.path.realpath(root_path))}),
                    _is_reparse_entry(entry),
                    self.exclude_patterns,
                    root_path,
                ): entry
                for entry in root_dirs
            }

            for future in as_completed(futures):
                if abort[0]:
                    # Cancel remaining futures gracefully
                    for f in futures:
                        f.cancel()
                    raise InterruptedError()
                try:
                    child = future.result()
                    root_node.children.append(child)
                    root_node.size       += child.size
                    root_node.file_count += child.file_count
                except InterruptedError:
                    raise
                except Exception:
                    pass  # skip unreadable subtrees

        root_node.children.sort(key=lambda n: n.size, reverse=True)
        return root_node


# ── Post-processing helpers ───────────────────────────────────────────────────

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


# ── Public helpers ────────────────────────────────────────────────────────────

def build_flat_list(node: FileNode, result: list | None = None) -> list:
    return _build_flat_list(node, result)

def get_top_files(root: FileNode, n: int = 100) -> list:
    return _get_top_files_from_flat(_build_flat_list(root), n)

def get_extension_breakdown(root: FileNode) -> dict:
    return _get_ext_breakdown_from_flat(_build_flat_list(root))
