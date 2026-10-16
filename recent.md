# myWizTree — Session Handoff

## Current App Behavior

- Python 3.12 + PyQt6 app; start with `python main.py`.
- Scans include Markdown files and other regular files.
- **SNAPSHOT** saves the current scan as a compact `.snap` file with the scanned directory's absolute path in its metadata. Legacy `.json` snapshots still load.
- The small arrow beside **COMPARE** opens snapshots matching the current scan path. Comparison runs in a background `QThread`, shows progress, and writes results into the main tree.
- Main-tree comparison columns are `% Change` and `Size Δ`. New/deleted files have green/red names; size changes are color-coded.
- Settings control main-tree column visibility. Name stays left-aligned; other columns are right-aligned, and the Name column uses remaining width.
- Expanding a folder highlights its name pink and dims unrelated branches. Collapsing it moves focus to its parent so peers return to normal brightness. Regular folder names use a warm Explorer-style gold.
- Tree selection has no white focus box and uses a subtle dark highlight.
- Desktop tray notification appears after scan or comparison completion; taskbar attention is used if the tray is unavailable.

## Important Implementation Notes

- `src/scanner.py` defines `FileNode`; comparison values are stored on nodes as display metadata.
- `src/snapshot.py` saves compact snapshots and accepts a progress callback while loading `.snap` entries.
- `src/ui/main_window.py` owns the Snapshot/Compare toolbar actions and the background comparison worker.
- `src/ui/tree_view.py` implements comparison columns, column visibility, focus dimming, folder colors, and selection styling.
- `settings.json` stores persisted tree and top-files column selections.

## Known Pending Work

- The Settings dialog exposes `skip_hidden`, but `scanner.py` still scans hidden files and folders. Implement this setting if requested.
