# ============================================================
# snapshot.py — Save, load, and diff directory scan snapshots
# ============================================================

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from src.scanner import FileNode, format_size


SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "snapshots")


def ensure_snapshots_dir():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


# ── Serialisation ────────────────────────────────────────────────────────────

def _node_to_dict(node: FileNode) -> dict:
    """Recursively convert a FileNode tree to a plain dict (JSON-serialisable)."""
    return {
        "name":       node.name,
        "path":       node.path,
        "size":       node.size,
        "is_dir":     node.is_dir,
        "modified":   node.modified,
        "file_count": node.file_count,
        "extension":  node.extension,
        "children":   [_node_to_dict(c) for c in node.children],
    }


def _dict_to_node(d: dict, parent: Optional[FileNode] = None) -> FileNode:
    """Recursively rebuild a FileNode tree from a plain dict."""
    node = FileNode(
        name       = d["name"],
        path       = d["path"],
        size       = d["size"],
        is_dir     = d["is_dir"],
        modified   = d["modified"],
        file_count = d["file_count"],
        children   = [],
        parent     = parent,
        extension  = d.get("extension", ""),
    )
    node.children = [_dict_to_node(c, parent=node) for c in d.get("children", [])]
    return node


# ── Save ─────────────────────────────────────────────────────────────────────

def save_snapshot(root: FileNode, name: str) -> str:
    """
    Save a scan snapshot to disk.
    Returns the path of the saved file.
    """
    ensure_snapshots_dir()
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    filename  = f"{safe_name}.json"
    filepath  = os.path.join(SNAPSHOTS_DIR, filename)

    data = {
        "snapshot_name": name,
        "saved_at":      time.time(),
        "root_path":     root.path,
        "tree":          _node_to_dict(root),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return filepath


def load_snapshot(filepath: str) -> tuple[FileNode, dict]:
    """
    Load a snapshot from disk.
    Returns (root_node, metadata_dict).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    root = _dict_to_node(data["tree"])
    meta = {
        "snapshot_name": data.get("snapshot_name", ""),
        "saved_at":      data.get("saved_at", 0.0),
        "root_path":     data.get("root_path", ""),
    }
    return root, meta


def list_snapshots() -> list[dict]:
    """
    Return a list of available snapshots with metadata.
    Each entry: { "filename", "filepath", "snapshot_name", "saved_at", "root_path" }
    """
    ensure_snapshots_dir()
    result = []
    for fname in sorted(os.listdir(SNAPSHOTS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(SNAPSHOTS_DIR, fname)
        try:
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
    """A single change between two snapshots."""
    path:     str
    name:     str
    status:   str        # "new" | "deleted" | "grown" | "shrunk" | "unchanged"
    old_size: int = 0
    new_size: int = 0
    is_dir:   bool = False

    @property
    def delta(self) -> int:
        return self.new_size - self.old_size

    def delta_str(self) -> str:
        d = self.delta
        sign = "+" if d >= 0 else ""
        return f"{sign}{format_size(abs(d))}" if d != 0 else "—"

    def old_size_str(self) -> str:
        return format_size(self.old_size) if self.old_size >= 0 else "—"

    def new_size_str(self) -> str:
        return format_size(self.new_size) if self.new_size >= 0 else "—"


def _flatten_to_dict(node: FileNode, result: dict | None = None) -> dict:
    """Flatten a FileNode tree to { path: FileNode }."""
    if result is None:
        result = {}
    result[node.path] = node
    for child in node.children:
        _flatten_to_dict(child, result)
    return result


def diff_snapshots(old_root: FileNode, new_root: FileNode) -> list[DiffEntry]:
    """
    Compare two FileNode trees and return a list of DiffEntry changes.
    Matches nodes by path (relative path from scan root for portability).
    """
    def normalise_key(base_path: str, full_path: str) -> str:
        """Make paths relative to the root so different scan bases still match."""
        try:
            return os.path.relpath(full_path, base_path)
        except ValueError:
            return full_path

    old_base = old_root.path
    new_base = new_root.path

    old_flat = _flatten_to_dict(old_root)
    new_flat = _flatten_to_dict(new_root)

    # Normalise keys
    old_rel = {normalise_key(old_base, p): nd for p, nd in old_flat.items()}
    new_rel = {normalise_key(new_base, p): nd for p, nd in new_flat.items()}

    all_keys = set(old_rel) | set(new_rel)
    entries: list[DiffEntry] = []

    for key in all_keys:
        in_old = key in old_rel
        in_new = key in new_rel

        if in_old and not in_new:
            nd = old_rel[key]
            entries.append(DiffEntry(
                path=nd.path, name=nd.name,
                status="deleted",
                old_size=nd.size, new_size=0,
                is_dir=nd.is_dir,
            ))
        elif in_new and not in_old:
            nd = new_rel[key]
            entries.append(DiffEntry(
                path=nd.path, name=nd.name,
                status="new",
                old_size=0, new_size=nd.size,
                is_dir=nd.is_dir,
            ))
        else:
            old_nd = old_rel[key]
            new_nd = new_rel[key]
            if new_nd.size > old_nd.size:
                status = "grown"
            elif new_nd.size < old_nd.size:
                status = "shrunk"
            else:
                status = "unchanged"

            if status != "unchanged":
                entries.append(DiffEntry(
                    path=new_nd.path, name=new_nd.name,
                    status=status,
                    old_size=old_nd.size, new_size=new_nd.size,
                    is_dir=new_nd.is_dir,
                ))

    # Sort: deleted first, then new, then grown, shrunk — by abs delta desc
    order = {"deleted": 0, "new": 1, "grown": 2, "shrunk": 3}
    entries.sort(key=lambda e: (order.get(e.status, 9), -abs(e.delta)))
    return entries
