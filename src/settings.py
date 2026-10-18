# ============================================================
# settings.py — Persistent settings (saved to settings.json)
# ============================================================

import os
import json

_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "settings.json")

DEFAULT_SETTINGS = {
    "top_n":          100,
    "skip_hidden":    False,
    "follow_dir_symlinks": False,
    "exclude_patterns": [],
    "dirs_first":     True,
    "show_tooltips":  True,
    "top_files_cols": [0, 1, 2, 4, 5],  # Name, Size, %, Modified, Path
    "tree_cols":      [1, 2, 3, 4, 5, 6],  # Size, Size Bar, Files, Modified, % Change, Size Δ
}


def load_settings() -> dict:
    """Load settings from disk, falling back to defaults for missing keys."""
    settings = DEFAULT_SETTINGS.copy()
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for key, default in DEFAULT_SETTINGS.items():
                if key in saved:
                    settings[key] = saved[key]
    except Exception:
        pass  # corrupted file — just use defaults

    # top_files_cols is stored as list in JSON, convert to set internally
    if isinstance(settings["top_files_cols"], list):
        settings["top_files_cols"] = set(settings["top_files_cols"])
    if isinstance(settings["tree_cols"], list):
        settings["tree_cols"] = set(settings["tree_cols"])

    return settings


def save_settings(settings: dict):
    """Save settings to disk."""
    # Convert set → list for JSON serialisation
    serialisable = {}
    for key, val in settings.items():
        serialisable[key] = list(val) if isinstance(val, set) else val
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(serialisable, f, indent=2)
    except Exception:
        pass
