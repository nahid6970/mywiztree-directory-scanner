# ============================================================
# ui/settings_dialog.py — Settings dialog
# ============================================================

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QGroupBox,
    QSpinBox, QCheckBox, QDialogButtonBox,
)

# Column indices — must match table_view.py
COL_NAME, COL_SIZE, COL_PCT, COL_COUNT, COL_MOD, COL_PATH = range(6)

# Default visible columns for top files tab (no Files column)
DEFAULT_TOP_FILES_COLS = {COL_NAME, COL_SIZE, COL_PCT, COL_MOD, COL_PATH}


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

        self._dirs_first = QCheckBox("Folders before files")
        self._dirs_first.setChecked(self._settings.get("dirs_first", True))
        form_scan.addRow("", self._dirs_first)

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
        self._settings["dirs_first"]  = self._dirs_first.isChecked()

        cols = {COL_NAME}  # Name always visible
        if self._col_size.isChecked():  cols.add(COL_SIZE)
        if self._col_pct.isChecked():   cols.add(COL_PCT)
        if self._col_count.isChecked(): cols.add(COL_COUNT)
        if self._col_mod.isChecked():   cols.add(COL_MOD)
        if self._col_path.isChecked():  cols.add(COL_PATH)
        self._settings["top_files_cols"] = cols

        self.accept()

    def get_settings(self) -> dict:
        return self._settings
