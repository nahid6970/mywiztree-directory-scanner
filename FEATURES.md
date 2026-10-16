# myWizTree — Feature List

A WizTree-inspired directory scanner with a Cyberpunk UI theme and snapshot diffing.

---

## Core Scanner

- Scan any folder or full drive (C:\, D:\, etc.)
- Animated live scan progress feed (cyberpunk style, shows files being discovered in real time)
- Sortable table view with columns: Name, Size, % of Parent, File Count, Last Modified
- Path navigation bar — click segments to navigate up/into folders

---

## Visualization

- **Treemap view** — proportional rectangle grid showing size at a glance
- **Cyberpunk heatmap coloring** — blocks colored by file age:
  - Cyan = old/untouched files
  - Red/Yellow = recently modified files

---

## Analysis

- **Top N Largest Files** — dedicated list of the biggest files across the scanned directory
- **Extension Breakdown** — shows how much total space each file type uses (`.mp4`, `.exe`, `.zip`, etc.)
- **Search & Filter** — filter the tree/table by filename or extension in real time

---

## Snapshot & Diff

- **Save Snapshot** — save a named snapshot of any scan to a JSON file
- **Load & Compare** — select any two snapshots to compare
- **Diff View** — color-coded results showing exactly what changed:
  - 🟢 Green — new files/folders that didn't exist in the old snapshot
  - 🔴 Red — deleted files/folders
  - 🟡 Yellow — files/folders that changed in size, with delta shown (e.g. `+2.3 MB`, `-400 KB`)
  - Folder-level rollup — shows total size change per folder even when individual files differ

---

## Utilities

- **Export to CSV** — export current scan results
- **Right-click context menu** — copy path, open in Explorer
- **Delete with confirmation** — select files and delete with a warning dialog
- **↺ Restart button** — hot-reload the app to apply code changes
- **⚙ Settings** — extensible settings dialog for user customizations

---

## UI / Theme

- Full Cyberpunk aesthetic per `THEME_GUIDE.md`
- Font: Consolas (monospace)
- Color palette: near-black background, cyan/yellow/red neon accents
- Sharp corners, neon borders, custom scrollbars
