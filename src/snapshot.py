# ============================================================
# snapshot.py — Compact snapshots: one line per entry (size\tpath)
#
# File format:
#   Line 1: JSON header  {"n": name, "t": timestamp, "r": root_path}
#   Line 2+: <size>\t<path>   (dirs end with \, files don't)
#
# ~10-20x smaller than the old nested-JSON format.
# Old .json snapshots are still loadable via legacy fallback.
# ============================================================

import os
import json
import time
from dataclasses import dataclass
from typing import Optional

from src.scanner import FileNode, format_size, build_flat_list


SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "snapshots")


def ensure_snapshots_dir():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


# ── Save ─────────────────────────────────────────────────────────────────────

def save_snapshot(root: FileNode, name: str) -> str:
    """
    Save a compact snapshot.
    Format: header JSON on line 1, then one tab-separated (size, path) per line.
    Returns the saved filepath.
    """
    ensure_snapshots_dir()
    safe  = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    fpath = os.path.join(SNAPSHOTS_DIR, f"{safe}.snap")

    header = json.dumps({
        "n": name,
        "t": time.time(),
        "r": os.path.abspath(os.path.normpath(root.path)),
    }, separators=(",", ":"))

    # Removed entries are display-only rows injected into the tree for the
    # comparison. They must not become part of the next saved baseline.
    flat = [node for node in build_flat_list(root)
            if getattr(node, "change_status", "") != "DELETED"]

    with open(fpath, "w", encoding="utf-8", buffering=1 << 20) as f:
        f.write(header + "\n")
        for node in flat:
            # Append backslash to path to mark directories
            path = node.path + "\\" if node.is_dir and not node.path.endswith("\\") else node.path
            f.write(f"{node.size}\t{path}\n")

    return fpath


# ── Load ─────────────────────────────────────────────────────────────────────

def load_snapshot(filepath: str, progress_callback=None) -> tuple["SnapData", dict]:
    """
    Load a snapshot from disk.
    Returns (SnapData, meta_dict).
    Supports both new .snap format and legacy .json format.
    """
    if filepath.endswith(".json"):
        return _load_legacy_json(filepath)

    entries: dict[str, int] = {}   # path → size
    meta = {}

    with open(filepath, "r", encoding="utf-8", buffering=1 << 20) as f:
        header_line = f.readline()
        try:
            h    = json.loads(header_line)
            meta = {
                "snapshot_name": h.get("n", ""),
                "saved_at":      h.get("t", 0.0),
                "root_path":     h.get("r", ""),
            }
        except Exception:
            meta = {"snapshot_name": "", "saved_at": 0.0, "root_path": ""}

        for line_number, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            tab = line.index("\t")
            size = int(line[:tab])
            path = line[tab + 1:]
            entries[path] = size
            if progress_callback and line_number % 50000 == 0:
                progress_callback(line_number)

    return SnapData(entries=entries, root_path=meta.get("root_path", "")), meta


def _load_legacy_json(filepath: str) -> tuple["SnapData", dict]:
    """Fallback loader for old nested-JSON snapshots."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = {
        "snapshot_name": data.get("snapshot_name", ""),
        "saved_at":      data.get("saved_at", 0.0),
        "root_path":     data.get("root_path", ""),
    }

    # Flatten the old tree into path→size dict
    entries: dict[str, int] = {}

    def _walk(node_dict):
        path = node_dict["path"]
        if node_dict.get("is_dir"):
            path = path + "\\" if not path.endswith("\\") else path
        entries[path] = node_dict["size"]
        for child in node_dict.get("children", []):
            _walk(child)

    _walk(data["tree"])
    return SnapData(entries=entries, root_path=meta["root_path"]), meta


@dataclass
class SnapData:
    """Lightweight snapshot: just a flat path→size mapping."""
    entries:   dict   # { path_str: size_int }  (dirs have trailing \)
    root_path: str


# ── List ─────────────────────────────────────────────────────────────────────

def list_snapshots() -> list[dict]:
    """Return available snapshots (both .snap and legacy .json)."""
    ensure_snapshots_dir()
    result = []
    for fname in sorted(os.listdir(SNAPSHOTS_DIR)):
        if not (fname.endswith(".snap") or fname.endswith(".json")):
            continue
        fpath = os.path.join(SNAPSHOTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                first = f.readline()
            if fname.endswith(".snap"):
                h = json.loads(first)
                result.append({
                    "filename":      fname,
                    "filepath":      fpath,
                    "snapshot_name": h.get("n", fname),
                    "saved_at":      h.get("t", 0.0),
                    "root_path":     h.get("r", ""),
                })
            else:
                # Legacy JSON — read just top-level keys
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result.append({
                    "filename":      fname,
                    "filepath":      fpath,
                    "snapshot_name": data.get("snapshot_name", fname),
                    "saved_at":      data.get("saved_at", 0.0),
                    "root_path":     data.get("root_path", ""),
                })
        except Exception:
            continue
    return result


# ── Diff ─────────────────────────────────────────────────────────────────────

@dataclass
class DiffEntry:
    path:     str
    name:     str
    status:   str     # "new" | "deleted" | "grown" | "shrunk"
    old_size: int = 0
    new_size: int = 0
    is_dir:   bool = False

    @property
    def delta(self) -> int:
        return self.new_size - self.old_size

    def delta_str(self) -> str:
        d    = self.delta
        sign = "+" if d >= 0 else ""
        return f"{sign}{format_size(abs(d))}" if d != 0 else "—"

    def old_size_str(self) -> str:
        return format_size(self.old_size) if self.old_size >= 0 else "—"

    def new_size_str(self) -> str:
        return format_size(self.new_size) if self.new_size >= 0 else "—"


def diff_snapshots(old: SnapData, new: SnapData) -> list[DiffEntry]:
    """
    Diff two SnapData objects.
    Normalises paths relative to their roots so scans of the same
    directory from different machines/times still match.
    """
    def rel(base: str, path: str) -> str:
        try:
            return os.path.relpath(path.rstrip("\\"), base)
        except ValueError:
            return path

    old_rel = {rel(old.root_path, p): (p, s) for p, s in old.entries.items()}
    new_rel = {rel(new.root_path, p): (p, s) for p, s in new.entries.items()}

    all_keys = set(old_rel) | set(new_rel)
    entries: list[DiffEntry] = []

    for key in all_keys:
        in_old = key in old_rel
        in_new = key in new_rel
        is_dir = key in old_rel and old_rel[key][0].endswith("\\") or \
                 key in new_rel and new_rel[key][0].endswith("\\")

        if in_old and not in_new:
            path, size = old_rel[key]
            entries.append(DiffEntry(
                path=path, name=os.path.basename(path.rstrip("\\")),
                status="deleted", old_size=size, new_size=0, is_dir=is_dir,
            ))
        elif in_new and not in_old:
            path, size = new_rel[key]
            entries.append(DiffEntry(
                path=path, name=os.path.basename(path.rstrip("\\")),
                status="new", old_size=0, new_size=size, is_dir=is_dir,
            ))
        else:
            _, old_size = old_rel[key]
            path, new_size = new_rel[key]
            if new_size > old_size:
                status = "grown"
            elif new_size < old_size:
                status = "shrunk"
            else:
                continue  # unchanged — skip

            entries.append(DiffEntry(
                path=path, name=os.path.basename(path.rstrip("\\")),
                status=status, old_size=old_size, new_size=new_size, is_dir=is_dir,
            ))

    order = {"deleted": 0, "new": 1, "grown": 2, "shrunk": 3}
    entries.sort(key=lambda e: (order.get(e.status, 9), -abs(e.delta)))
    return entries
