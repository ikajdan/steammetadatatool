from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.core.appinfo import AppInfoFile, find_steam_appinfo_path
from steammetadatatool.core.keyvalues1 import kv_deep_get


def _common_value(data: dict[str, Any], key: str) -> Any:
    return kv_deep_get(data, "common", key) or kv_deep_get(
        data, "appinfo", "common", key
    )


def _extended_value(data: dict[str, Any], key: str) -> Any:
    return kv_deep_get(data, "extended", key) or kv_deep_get(
        data, "appinfo", "extended", key
    )


def _format_aliases(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "-"
    raw = str(value).strip()
    return raw or "-"


def _format_release_date(value: Any) -> str:
    if value is None:
        return "-"

    unix_value: int | None = None
    if isinstance(value, int):
        unix_value = value
    elif isinstance(value, str) and value.isdigit():
        unix_value = int(value)

    if unix_value is None:
        text = str(value).strip()
        return text or "-"

    if unix_value <= 0:
        return "-"

    try:
        return datetime.fromtimestamp(unix_value, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return str(unix_value)


class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SteamMetadataTool")
        self.resize(1200, 560)
        self.setMinimumSize(980, 520)

        self._details_by_appid: dict[int, dict[str, str]] = {}
        self._detail_labels: dict[str, QLabel] = {}

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["App ID", "Name"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumWidth(380)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        details_widget = QWidget()
        details_widget.setMinimumWidth(500)
        details_outer_layout = QVBoxLayout(details_widget)
        details_outer_layout.setContentsMargins(18, 18, 18, 18)
        details_outer_layout.setSpacing(10)
        details_outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        details_heading = QLabel("Details")
        details_heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        details_outer_layout.addWidget(details_heading)

        heading_separator = QFrame()
        heading_separator.setFrameShape(QFrame.Shape.HLine)
        heading_separator.setFrameShadow(QFrame.Shadow.Sunken)
        details_outer_layout.addWidget(heading_separator)

        details_form_container = QWidget()
        details_outer_layout.addWidget(details_form_container)

        details_layout = QFormLayout(details_form_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setHorizontalSpacing(20)
        details_layout.setVerticalSpacing(10)
        details_layout.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        details_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        details_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        fields = (
            ("appid", "App ID"),
            ("name", "Name"),
            ("_separator_1", ""),
            ("sort_as", "Sort As"),
            ("aliases", "Aliases"),
            ("_separator_2", ""),
            ("developer", "Developer"),
            ("publisher", "Publisher"),
            ("_separator_3", ""),
            ("original_release_date", "Original Release Date"),
            ("steam_release_date", "Steam Release Date"),
        )
        for key, title in fields:
            if key.startswith("_separator_"):
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                details_layout.addRow(separator)
                continue

            title_label = QLabel(f"{title}:")
            title_label.setMinimumWidth(175)
            title_label.setStyleSheet("font-weight: 600;")

            value_label = QLabel("-")
            value_label.setMinimumWidth(280)
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            details_layout.addRow(title_label, value_label)
            self._detail_labels[key] = value_label

        details_outer_layout.addStretch(1)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)
        layout.addWidget(self._table, 3)
        layout.addWidget(details_widget, 2)
        layout.setAlignment(details_widget, Qt.AlignmentFlag.AlignTop)
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
            rows: list[tuple[int, str]] = []
            details_by_appid: dict[int, dict[str, str]] = {}

            with AppInfoFile.open(path_obj) as appinfo:
                for app in appinfo.iter_apps():
                    name = app.name or ""
                    rows.append((app.appid, name))

                    details_by_appid[app.appid] = {
                        "appid": str(app.appid),
                        "name": name or "-",
                        "sort_as": str(_common_value(app.data, "sortas") or "-"),
                        "aliases": _format_aliases(_common_value(app.data, "aliases")),
                        "developer": str(_extended_value(app.data, "developer") or "-"),
                        "publisher": str(_extended_value(app.data, "publisher") or "-"),
                        "original_release_date": _format_release_date(
                            _common_value(app.data, "original_release_date")
                        ),
                        "steam_release_date": _format_release_date(
                            _common_value(app.data, "steam_release_date")
                        ),
                    }
        except Exception as exc:
            QMessageBox.critical(self, "SteamMetadataTool", str(exc))
            return

        self._details_by_appid = details_by_appid

        self._table.setRowCount(len(rows))
        for row, (appid, name) in enumerate(rows):
            appid_item = QTableWidgetItem(str(appid))
            appid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            name_item = QTableWidgetItem(name)
            self._table.setItem(row, 0, appid_item)
            self._table.setItem(row, 1, name_item)

        self._set_details(None)
        if rows:
            self._table.selectRow(0)

    def _set_details(self, details: dict[str, str] | None) -> None:
        for key, label in self._detail_labels.items():
            label.setText((details or {}).get(key, "-"))

    def _on_selection_changed(self) -> None:
        selected = self._table.selectedItems()
        if not selected:
            self._set_details(None)
            return

        row = selected[0].row()
        appid_item = self._table.item(row, 0)
        if appid_item is None:
            self._set_details(None)
            return

        try:
            appid = int(appid_item.text())
        except ValueError:
            self._set_details(None)
            return

        self._set_details(self._details_by_appid.get(appid))


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
