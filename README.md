# myWizTree ⚡ CYBERPUNK DISK SCANNER

A WizTree-inspired directory scanner with a full Cyberpunk aesthetic, snapshot diffing, and interactive treemap visualisation built with PyQt6.

---

## Features

✅ **Core Scanner**
- Scan any folder or full drive (C:\, D:\, etc.)
- Animated live scan feed showing files being discovered in real time
- Sortable table view with columns: Name, Size, % of Parent, File Count, Last Modified
- Path navigation bar

✅ **Visualisation**
- Interactive squarified treemap with proportional rectangle grid
- Cyberpunk heatmap coloring:
  - **Extension mode** (default) — color by file type
  - **Age mode** — color by file age (cyan = old, red/yellow = recently modified)
- Click to zoom into folders, right-click to navigate up

✅ **Analysis**
- Top N largest files view (default: 100, configurable)
- Extension breakdown with total size, count, avg size, and percentage bars
- Search & filter by filename or extension

✅ **Snapshot & Diff**
- Save named snapshots of any scan to JSON
- Load and compare any two snapshots
- Diff view with color-coded results:
  - 🟢 New files/folders
  - 🔴 Deleted files/folders
  - 🟡 Files that grew in size (with delta)
  - 🔵 Files that shrank in size (with delta)
  - Folder-level rollup showing total size changes

✅ **Utilities**
- Export current scan to CSV
- Right-click context menu: copy path, open in Explorer, delete
- Settings dialog for customization
- Hot-reload via ↺ Restart button

---

## Installation

```bash
cd C:\@delta\myWizTree_Directory_Scanner
uv add pyqt6
```

Or if using pip:

```bash
pip install pyqt6
```

---

## Usage

```bash
python main.py
```

**Workflow:**

1. Enter a path (e.g., `C:\Users`, `D:\`) or click **📂 BROWSE**
2. Click **⚡ SCAN** — watch the live feed as files are discovered
3. Explore the **treemap** (click to zoom, right-click to go up)
4. Browse **📋 FILES**, **🏆 TOP FILES**, **📊 EXTENSIONS**
5. To track changes over time:
   - Click **💾 SAVE SNAPSHOT** with a descriptive name
   - Scan again later (or scan a different snapshot)
   - Go to **🔍 SNAPSHOT DIFF** tab → pick OLD and NEW → **⚡ COMPARE**

---

## Project Structure

```
myWizTree_Directory_Scanner/
├── main.py                     # Entry point
├── pyproject.toml              # uv project file
├── FEATURES.md                 # Full feature list
├── README.md
├── .gitignore
├── snapshots/                  # Saved snapshot JSON files
└── src/
    ├── scanner.py              # Threaded directory scanner
    ├── treemap.py              # Custom squarified treemap widget
    ├── snapshot.py             # Save/load/diff logic
    ├── theme.py                # Cyberpunk palette + QSS stylesheet
    └── ui/
        ├── main_window.py      # Main window + layout
        ├── table_view.py       # Sortable file table
        ├── diff_view.py        # Snapshot diff results
        ├── ext_breakdown.py    # Extension breakdown panel
        └── settings_dialog.py  # Settings
```

---

## Theme

Full cyberpunk aesthetic inspired by `THEME_GUIDE.md`:

- Near-black background `#050505`
- Neon accents: cyan `#00F0FF`, yellow `#FCEE0A`, red `#FF003C`, green `#00ff21`
- Monospace font: **Consolas**
- Sharp corners, custom scrollbars, neon borders

---

## Keyboard Shortcuts

- **Enter** in path field → start scan
- **Right-click** in treemap → navigate up
- **Right-click** in table → context menu (copy path, open, delete)

---

## Tips

- **Scan from root drives with caution** — C:\ scans can take minutes depending on size
- **Use snapshots** to track project growth, cleanup results, or archive states before major deletions
- **Filter by extension** in the table (e.g., type `.mp4` to see only video files)
- **Color mode toggle** — use Age mode to spot rarely-accessed files

---

## Requirements

- Python 3.12+
- PyQt6 6.7+

---

## License

MIT
