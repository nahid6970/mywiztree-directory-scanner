# ============================================================
# ui/settings_dialog.py — Settings dialog
# ============================================================

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QPushButton, QLabel, QSpinBox, QCheckBox, QDialogButtonBox,
    QComboBox,
)
from PyQt6.QtCore import Qt

from src.theme import CP_YELLOW, CP_CYAN


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  SETTINGS")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._settings = settings.copy()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Scanner ─────────────────────────────────────────
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

        grp_scan.setLayout(form_scan)

        # ── Treemap ──────────────────────────────────────────
        grp_map = QGroupBox("TREEMAP")
        form_map = QFormLayout()

        self._color_mode = QComboBox()
        self._color_mode.addItems(["Extension (default)", "File Age (heatmap)"])
        mode = self._settings.get("treemap_color_mode", "ext")
        self._color_mode.setCurrentIndex(0 if mode == "ext" else 1)
        form_map.addRow("Color mode:", self._color_mode)

        grp_map.setLayout(form_map)

        # ── Buttons ──────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        layout.addWidget(grp_scan)
        layout.addWidget(grp_map)
        layout.addWidget(buttons)

    def _apply(self):
        self._settings["top_n"]               = self._top_n.value()
        self._settings["skip_hidden"]         = self._skip_hidden.isChecked()
        self._settings["treemap_color_mode"]  = (
            "ext" if self._color_mode.currentIndex() == 0 else "age"
        )
        self.accept()

    def get_settings(self) -> dict:
        return self._settings
