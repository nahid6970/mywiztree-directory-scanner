# ============================================================
# ui/settings_dialog.py — Settings dialog
# ============================================================

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QGroupBox,
    QSpinBox, QCheckBox, QDialogButtonBox, QPlainTextEdit,
)

# Column indices — must match table_view.py
COL_NAME, COL_SIZE, COL_PCT, COL_COUNT, COL_MOD, COL_PATH = range(6)

# Default visible columns for top files tab (no Files column)
DEFAULT_TOP_FILES_COLS = {COL_NAME, COL_SIZE, COL_PCT, COL_MOD, COL_PATH}

# Main tree columns — Name is always visible.
TREE_COL_SIZE, TREE_COL_BAR, TREE_COL_FILES, TREE_COL_MOD, TREE_COL_CHANGE, TREE_COL_DELTA = range(1, 7)
DEFAULT_TREE_COLS = {TREE_COL_SIZE, TREE_COL_BAR, TREE_COL_FILES, TREE_COL_MOD, TREE_COL_CHANGE, TREE_COL_DELTA}


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  SETTINGS")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._settings = settings.copy()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Scanner group ────────────────────────────────────────────────────
        grp_scan = QGroupBox("SCANNER")
        form_scan = QFormLayout()

        self._top_n = QSpinBox()
        self._top_n.setRange(10, 1000)
        self._top_n.setValue(self._settings.get("top_n", 100))
        self._top_n.setSuffix("  files")
        form_scan.addRow("Top N largest files:", self._top_n)

        self._skip_hidden = QCheckBox("Skip hidden files & folders")
        self._skip_hidden.setChecked(self._settings.get("skip_hidden", False))
        form_scan.addRow("", self._skip_hidden)

        self._follow_dir_symlinks = QCheckBox("Follow symlinks (show target size and browse linked folders)")
        self._follow_dir_symlinks.setChecked(self._settings.get("follow_dir_symlinks", False))
        form_scan.addRow("", self._follow_dir_symlinks)

        self._exclude_patterns = QPlainTextEdit()
        self._exclude_patterns.setPlaceholderText("One glob per line: node_modules, *.tmp, build/cache/*")
        self._exclude_patterns.setPlainText("\n".join(self._settings.get("exclude_patterns", [])))
        self._exclude_patterns.setMaximumHeight(78)
        form_scan.addRow("Exclude patterns:", self._exclude_patterns)

        self._dirs_first = QCheckBox("Folders before files")
        self._dirs_first.setChecked(self._settings.get("dirs_first", True))
        form_scan.addRow("", self._dirs_first)

        self._show_tooltips = QCheckBox("Show tooltips")
        self._show_tooltips.setChecked(self._settings.get("show_tooltips", True))
        form_scan.addRow("", self._show_tooltips)

        grp_scan.setLayout(form_scan)
        layout.addWidget(grp_scan)

        # ── Top Files columns group ───────────────────────────────────────────
        grp_cols = QGroupBox("TOP FILES — VISIBLE COLUMNS")
        form_cols = QFormLayout()

        visible = self._settings.get("top_files_cols", DEFAULT_TOP_FILES_COLS)

        self._col_size  = QCheckBox("Size")
        self._col_size.setChecked(COL_SIZE in visible)
        form_cols.addRow("", self._col_size)

        self._col_pct   = QCheckBox("% of Parent")
        self._col_pct.setChecked(COL_PCT in visible)
        form_cols.addRow("", self._col_pct)

        self._col_count = QCheckBox("Files count")
        self._col_count.setChecked(COL_COUNT in visible)
        form_cols.addRow("", self._col_count)

        self._col_mod   = QCheckBox("Modified")
        self._col_mod.setChecked(COL_MOD in visible)
        form_cols.addRow("", self._col_mod)

        self._col_path  = QCheckBox("Full Path")
        self._col_path.setChecked(COL_PATH in visible)
        form_cols.addRow("", self._col_path)

        grp_cols.setLayout(form_cols)
        layout.addWidget(grp_cols)

        # ── Main Tree columns group ──────────────────────────────────────────
        grp_tree = QGroupBox("MAIN TREE — VISIBLE COLUMNS")
        form_tree = QFormLayout()
        tree_visible = self._settings.get("tree_cols", DEFAULT_TREE_COLS)
        self._tree_col_size = QCheckBox("Size")
        self._tree_col_size.setChecked(TREE_COL_SIZE in tree_visible)
        form_tree.addRow("", self._tree_col_size)
        self._tree_col_bar = QCheckBox("Size Bar")
        self._tree_col_bar.setChecked(TREE_COL_BAR in tree_visible)
        form_tree.addRow("", self._tree_col_bar)
        self._tree_col_files = QCheckBox("Files")
        self._tree_col_files.setChecked(TREE_COL_FILES in tree_visible)
        form_tree.addRow("", self._tree_col_files)
        self._tree_col_mod = QCheckBox("Modified")
        self._tree_col_mod.setChecked(TREE_COL_MOD in tree_visible)
        form_tree.addRow("", self._tree_col_mod)
        self._tree_col_change = QCheckBox("% Change")
        self._tree_col_change.setChecked(TREE_COL_CHANGE in tree_visible)
        form_tree.addRow("", self._tree_col_change)
        self._tree_col_delta = QCheckBox("Size Change")
        self._tree_col_delta.setChecked(TREE_COL_DELTA in tree_visible)
        form_tree.addRow("", self._tree_col_delta)
        grp_tree.setLayout(form_tree)
        layout.addWidget(grp_tree)

        # ── Buttons ──────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply(self):
        self._settings["top_n"]       = self._top_n.value()
        self._settings["skip_hidden"] = self._skip_hidden.isChecked()
        self._settings["follow_dir_symlinks"] = self._follow_dir_symlinks.isChecked()
        self._settings["exclude_patterns"] = [
            line.strip() for line in self._exclude_patterns.toPlainText().splitlines()
            if line.strip()
        ]
        self._settings["dirs_first"]  = self._dirs_first.isChecked()
        self._settings["show_tooltips"] = self._show_tooltips.isChecked()

        cols = {COL_NAME}  # Name always visible
        if self._col_size.isChecked():  cols.add(COL_SIZE)
        if self._col_pct.isChecked():   cols.add(COL_PCT)
        if self._col_count.isChecked(): cols.add(COL_COUNT)
        if self._col_mod.isChecked():   cols.add(COL_MOD)
        if self._col_path.isChecked():  cols.add(COL_PATH)
        self._settings["top_files_cols"] = cols

        tree_cols = set()
        if self._tree_col_size.isChecked(): tree_cols.add(TREE_COL_SIZE)
        if self._tree_col_bar.isChecked(): tree_cols.add(TREE_COL_BAR)
        if self._tree_col_files.isChecked(): tree_cols.add(TREE_COL_FILES)
        if self._tree_col_mod.isChecked(): tree_cols.add(TREE_COL_MOD)
        if self._tree_col_change.isChecked(): tree_cols.add(TREE_COL_CHANGE)
        if self._tree_col_delta.isChecked(): tree_cols.add(TREE_COL_DELTA)
        self._settings["tree_cols"] = tree_cols

        self.accept()

    def get_settings(self) -> dict:
        return self._settings
