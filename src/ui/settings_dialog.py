# ============================================================
# ui/settings_dialog.py — Settings dialog
# ============================================================

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QGroupBox,
    QPushButton, QSpinBox, QCheckBox, QDialogButtonBox,
)

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

        grp = QGroupBox("SCANNER")
        form = QFormLayout()

        self._top_n = QSpinBox()
        self._top_n.setRange(10, 1000)
        self._top_n.setValue(self._settings.get("top_n", 100))
        self._top_n.setSuffix("  files")
        form.addRow("Top N largest files:", self._top_n)

        self._skip_hidden = QCheckBox("Skip hidden files & folders")
        self._skip_hidden.setChecked(self._settings.get("skip_hidden", False))
        form.addRow("", self._skip_hidden)

        self._dirs_first = QCheckBox("Folders before files")
        self._dirs_first.setChecked(self._settings.get("dirs_first", True))
        form.addRow("", self._dirs_first)

        grp.setLayout(form)
        layout.addWidget(grp)

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
        self.accept()

    def get_settings(self) -> dict:
        return self._settings
