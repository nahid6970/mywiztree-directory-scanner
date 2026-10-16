# recent.md — Session Handoff

## 1. Project DNA (Permanent)
Python 3.12 + PyQt6 desktop app, modular `src/` design (`scanner`, `snapshot`, `theme`, `treemap`, `ui/*`). WizTree-inspired cyberpunk disk scanner: threaded recursive scan, collapsible tree/table views, custom QPainter treemap, and JSON snapshot diffing. Entry point `main.py`.

## 2. Latest Implementation (this session)
- `src/snapshot.py` — migrated snapshots to compact flat `.snap` format (line 1 JSON header, then `<size>\t<path>`), ~10–20x smaller; legacy `.json` still loads.
- `src/ui/diff_view.py` — auto-numbered default snapshot names (`snapshot_N`); pre-fill + refresh combos.
- `src/settings.py` + `settings.json` — persistent settings (load/save, set↔list JSON conversion); `main_window.py` applies them on start/close.
- `src/ui/tree_view.py` — file tree + `TreeSortProxy` numeric sort and dirs-first logic.
- `.gitignore` — ignore whole `snapshots/` dir.

## 3. Critical Context
- **Snapshot dirs** end with a trailing `\`; diff matches via `os.path.relpath` against each file's `root_path`, so re-scans of the same folder still compare.
- **dirs-first sort**: Qt inverts `lessThan` for descending, so `TreeSortProxy` flips the dir check using `sortOrder()`.
- **Scanner**: one `ThreadPoolExecutor` worker per top-level subdir, `MAX_WORKERS = min(cpu, 8)`; progress throttled every 500 files, stats every 2000. Root node has `parent=None`.
- **Top-files table** loads lazily in 2000-row chunks via `QTimer` for responsiveness.
- No external deps beyond PyQt6 — treemap/bars are hand-drawn.

## 4. Pending Task
Honor the `skip_hidden` setting: `scanner.py` still scans hidden files/folders even though the Settings dialog exposes the toggle.
