# ============================================================
# theme.py — Cyberpunk palette constants and global stylesheet
# ============================================================

# CYBERPUNK THEME PALETTE
CP_BG      = "#050505"   # Main Window Background
CP_PANEL   = "#111111"   # Panel/Input Background
CP_YELLOW  = "#FCEE0A"   # Accent: Yellow
CP_CYAN    = "#00F0FF"   # Accent: Cyan
CP_RED     = "#FF003C"   # Accent: Red
CP_GREEN   = "#00ff21"   # Accent: Green
CP_ORANGE  = "#ff934b"   # Accent: Orange
CP_DIM     = "#3a3a3a"   # Dimmed/Borders/Inactive
CP_TEXT    = "#E0E0E0"   # Primary Text
CP_SUBTEXT = "#808080"   # Secondary Text

# Treemap heatmap colors (file age: old → recent)
HEAT_COLD   = "#004d55"  # Very old files (dark cyan)
HEAT_COOL   = "#00F0FF"  # Old files (cyan)
HEAT_WARM   = CP_ORANGE  # Recently modified
HEAT_HOT    = CP_RED     # Very recently modified

# Diff status colors
DIFF_NEW     = CP_GREEN   # New file/folder
DIFF_DELETED = CP_RED     # Deleted file/folder
DIFF_GROWN   = CP_YELLOW  # Increased in size
DIFF_SHRUNK  = CP_CYAN    # Decreased in size
DIFF_UNCHANGED = CP_SUBTEXT


def get_global_stylesheet() -> str:
    return f"""
    QMainWindow, QDialog {{
        background-color: {CP_BG};
    }}
    QWidget {{
        color: {CP_TEXT};
        font-family: 'Consolas';
        font-size: 10pt;
        background-color: {CP_BG};
    }}

    /* ── Inputs ── */
    QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
        background-color: {CP_PANEL};
        color: {CP_CYAN};
        border: 1px solid {CP_DIM};
        padding: 4px;
        selection-background-color: {CP_CYAN};
        selection-color: #000000;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {CP_CYAN};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 0px;
        border: none;
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {CP_PANEL};
        color: {CP_CYAN};
        border: 1px solid {CP_CYAN};
        selection-background-color: {CP_CYAN};
        selection-color: #000000;
    }}

    /* ── Buttons ── */
    QPushButton {{
        background-color: {CP_DIM};
        border: 1px solid {CP_DIM};
        color: white;
        padding: 6px 14px;
        font-weight: bold;
        font-family: 'Consolas';
    }}
    QPushButton:hover {{
        background-color: #1a1a1a;
        border: 1px solid {CP_YELLOW};
        color: {CP_YELLOW};
    }}
    QPushButton:pressed {{
        background-color: {CP_YELLOW};
        color: #000000;
    }}
    QPushButton:disabled {{
        background-color: #1a1a1a;
        border: 1px solid #222222;
        color: {CP_DIM};
    }}

    /* ── Group Boxes ── */
    QGroupBox {{
        border: 1px solid {CP_DIM};
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: {CP_YELLOW};
        background-color: {CP_BG};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
    }}

    /* ── Labels ── */
    QLabel {{
        background-color: transparent;
        color: {CP_TEXT};
    }}

    /* ── Tabs ── */
    QTabWidget::pane {{
        border: 1px solid {CP_DIM};
        background-color: {CP_BG};
    }}
    QTabBar::tab {{
        background-color: {CP_PANEL};
        color: {CP_SUBTEXT};
        border: 1px solid {CP_DIM};
        padding: 6px 16px;
        font-weight: bold;
        font-family: 'Consolas';
    }}
    QTabBar::tab:selected {{
        background-color: {CP_BG};
        color: {CP_CYAN};
        border-bottom: 2px solid {CP_CYAN};
    }}
    QTabBar::tab:hover {{
        color: {CP_YELLOW};
        border-bottom: 1px solid {CP_YELLOW};
    }}

    /* ── Tree / Table Views ── */
    QTreeView, QTableView, QListView {{
        background-color: {CP_PANEL};
        alternate-background-color: #161616;
        color: {CP_TEXT};
        border: 1px solid {CP_DIM};
        gridline-color: {CP_DIM};
        selection-background-color: #003a3a;
        selection-color: {CP_CYAN};
        show-decoration-selected: 1;
    }}
    QTreeView::item:hover, QTableView::item:hover {{
        background-color: #1a1a1a;
    }}
    QHeaderView::section {{
        background-color: #0a0a0a;
        color: {CP_YELLOW};
        border: none;
        border-right: 1px solid {CP_DIM};
        border-bottom: 1px solid {CP_DIM};
        padding: 4px 8px;
        font-weight: bold;
        font-family: 'Consolas';
    }}
    QHeaderView::section:hover {{
        background-color: #1a1a1a;
        color: {CP_CYAN};
    }}

    /* ── Checkboxes ── */
    QCheckBox {{
        spacing: 8px;
        color: {CP_TEXT};
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {CP_DIM};
        background: {CP_PANEL};
    }}
    QCheckBox::indicator:checked {{
        background: {CP_YELLOW};
        border-color: {CP_YELLOW};
    }}

    /* ── Menus ── */
    QMenu {{
        background-color: {CP_PANEL};
        color: {CP_TEXT};
        border: 1px solid {CP_CYAN};
    }}
    QMenu::item:selected {{
        background-color: {CP_CYAN};
        color: {CP_BG};
    }}
    QMenu::separator {{
        height: 1px;
        background: {CP_DIM};
        margin: 2px 0px;
    }}

    /* ── Scrollbars ── */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: {CP_BG};
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {CP_CYAN};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        background: none;
    }}
    QScrollBar:horizontal {{
        background: {CP_BG};
        height: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {CP_CYAN};
        min-width: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        background: none;
    }}

    /* ── Splitter ── */
    QSplitter::handle {{
        background-color: {CP_DIM};
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ── Status Bar ── */
    QStatusBar {{
        background-color: {CP_PANEL};
        color: {CP_SUBTEXT};
        border-top: 1px solid {CP_DIM};
    }}

    /* ── Progress Bar ── */
    QProgressBar {{
        background-color: {CP_PANEL};
        border: 1px solid {CP_DIM};
        color: {CP_BG};
        text-align: center;
        font-weight: bold;
    }}
    QProgressBar::chunk {{
        background-color: {CP_CYAN};
    }}

    /* ── Tooltips ── */
    QToolTip {{
        background-color: {CP_PANEL};
        color: {CP_CYAN};
        border: 1px solid {CP_CYAN};
        padding: 4px;
        font-family: 'Consolas';
    }}
    """
