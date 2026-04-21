from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.app_listing import list_app_summaries
from utils.appinfo import find_steam_appinfo_path


class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SteamMetadataTool")
        self.resize(720, 560)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["App ID", "Name"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(self._table, 1)
        self.setCentralWidget(root)

        if initial_path:
            self._load_apps(initial_path)

    def _load_apps(self, path: str) -> None:
        path_obj = Path(path).expanduser()
        if not path_obj.exists():
            QMessageBox.warning(
                self,
                "SteamMetadataTool",
                f"File does not exist:\n{path_obj}",
            )
            return

        try:
            summaries = list_app_summaries(path_obj)
        except Exception as exc:
            QMessageBox.critical(self, "SteamMetadataTool", str(exc))
            return

        self._table.setRowCount(len(summaries))
        for row, summary in enumerate(summaries):
            appid_item = QTableWidgetItem(str(summary.appid))
            appid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            name_item = QTableWidgetItem(summary.name)
            self._table.setItem(row, 0, appid_item)
            self._table.setItem(row, 1, name_item)


def main() -> int:
    parser = argparse.ArgumentParser(prog="steam_appinfo_gui")
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to appinfo.vdf (defaults to auto-detected Steam install)",
    )
    args = parser.parse_args()

    initial_path = args.path
    if not initial_path:
        detected_path = find_steam_appinfo_path()
        if detected_path:
            initial_path = str(detected_path)

    app = QApplication([])
    window = MainWindow(initial_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
