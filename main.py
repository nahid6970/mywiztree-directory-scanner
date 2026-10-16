# ============================================================
# main.py — Entry point for myWizTree
# ============================================================

import sys
import os

# Ensure the project root is on sys.path so `src.*` imports work
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Ensure snapshots directory exists
_SNAPSHOTS_DIR = os.path.join(_PROJECT_ROOT, "snapshots")
os.makedirs(_SNAPSHOTS_DIR, exist_ok=True)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QFont

from src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("myWizTree")
    app.setApplicationDisplayName("myWizTree ⚡ Cyberpunk Disk Scanner")

    # Set default font
    font = QFont("Consolas", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
