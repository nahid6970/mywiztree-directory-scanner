# myWizTree — Feature List

A WizTree-inspired directory scanner with a Cyberpunk UI theme.

---

## Core Scanner

- Scan any folder or full drive (C:\\, D:\\, etc.)
- Animated live scan feed showing files discovered in real time
- Sortable file tables and path navigation
- Markdown files are included like other scanned files

## Analysis and Tree

- Top N largest files and extension breakdown
- Search and filter by filename or extension
- Main tree comparison columns show `% Change` and signed `Size Δ`
- New files are green; deleted files are red; size increases and decreases are color-coded
- Expanding a folder highlights its name pink and dims unrelated branches
- Collapsing a folder moves focus to its parent, bringing peer items back to normal brightness
- Settings can hide or show main-tree columns; Name stays left-aligned and other columns are right-aligned

## Snapshots and Comparison

- Save the current scan with the **SNAPSHOT** toolbar button
- Snapshots record the absolute path of the scanned directory
- The small menu beside **COMPARE** lists snapshots for the current scan path
- Comparisons run in a background thread and show progress on large drives
- The main tree shows unchanged, new, deleted, grown, and shrunk entries
- Compact `.snap` snapshots are used; legacy `.json` snapshots remain loadable

## Utilities

- Export the current scan to CSV
- Right-click to copy a path, open it in Explorer, or delete with confirmation
- Desktop notifications appear when scans and comparisons complete
- Settings include scanner and column visibility options
- Restart button reloads the app

## UI / Theme

- Near-black background with cyan, yellow, red, green, gold, and pink accents
- Consolas monospace font, sharp corners, and custom scrollbars
