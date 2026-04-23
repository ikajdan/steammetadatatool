from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _monochrome_icon_pixmap(
    icon: QIcon, size: int, color: QColor, right_padding: int = 0
) -> QPixmap:
    pixmap = icon.pixmap(size, size)
    if pixmap.isNull():
        return pixmap

    monochrome = QPixmap(pixmap.width() + right_padding, pixmap.height())
    monochrome.fill(Qt.GlobalColor.transparent)

    painter = QPainter(monochrome)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(monochrome.rect(), color)
    painter.end()
    return monochrome


def _format_metadata_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return str(value)


def _flatten_metadata_entries(
    value: Any,
    prefix: str = "",
) -> list[tuple[str, str]]:
    if isinstance(value, dict):
        if not value:
            return [(prefix or "(root)", "{}")]

        entries: list[tuple[str, str]] = []
        for key, nested_value in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            entries.extend(_flatten_metadata_entries(nested_value, next_prefix))
        return entries

    if isinstance(value, list):
        if not value:
            return [(prefix or "(root)", "[]")]

        entries: list[tuple[str, str]] = []
        for index, nested_value in enumerate(value):
            next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            entries.extend(_flatten_metadata_entries(nested_value, next_prefix))
        return entries

    return [(prefix or "(root)", _format_metadata_value(value))]


def _normalize_changes_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self._update_elided_text()

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                max(0, self.width()),
            )
        )


class EditMetadataDialog(QDialog):
    def __init__(
        self,
        raw_metadata: dict[str, Any],
        *,
        appid: str | None = None,
        app_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Metadata")
        self.setModal(True)
        self.resize(1080, 560)
        self._column_width_ratio = (4, 3)
        self._header_width_ratio = (2, 1)

        entries = _flatten_metadata_entries(raw_metadata)
        readonly_keys = {
            "appinfo.appid",
            "appinfo.common.gameid",
        }
        self._appid = appid
        self._original_entries = dict(entries)
        self._search_text = ""
        action_icon_color = self.palette().placeholderText().color()
        readonly_text_color = self.palette().placeholderText().color()
        readonly_background_color = self.palette().alternateBase().color()

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(16, 16, 16, 16)
        dialog_layout.setSpacing(12)

        header_row = QWidget(self)
        header_row_layout = QHBoxLayout(header_row)
        self._header_row_layout = header_row_layout
        header_row_layout.setContentsMargins(0, 0, 0, 0)
        header_row_layout.setSpacing(12)

        self._app_name_label = ElidedLabel(app_name or "", header_row)
        self._app_name_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        self._app_name_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        header_row_layout.addWidget(self._app_name_label)
        header_row_layout.addStretch(1)

        self._search_input = QLineEdit(header_row)
        self._search_input.setPlaceholderText("Search by Key or Value")
        search_icon = QIcon.fromTheme(
            "edit-find",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
        )
        self._search_input.addAction(
            QIcon(_monochrome_icon_pixmap(search_icon, 16, action_icon_color)),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_table_filter)
        header_row_layout.addWidget(self._search_input, 0, Qt.AlignmentFlag.AlignRight)
        dialog_layout.addWidget(header_row)

        metadata_table = QTableWidget(len(entries), 2, self)
        self._metadata_table = metadata_table
        metadata_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        metadata_table.verticalHeader().setVisible(False)
        metadata_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        metadata_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        metadata_table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        metadata_table.setAlternatingRowColors(True)
        metadata_table.setShowGrid(False)
        metadata_table.setWordWrap(True)
        metadata_table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background: transparent;
                color: palette(text);
            }
            QTableWidget::item:focus {
                outline: none;
            }
            """
        )
        metadata_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        metadata_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )

        for row, (key, value) in enumerate(entries):
            key_item = QTableWidgetItem(key)
            value_item = QTableWidgetItem(value)
            key_item.setFlags(
                key_item.flags()
                & ~Qt.ItemFlag.ItemIsEditable
                & ~Qt.ItemFlag.ItemIsSelectable
            )
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            if key in readonly_keys:
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item.setForeground(readonly_text_color)
                value_item.setBackground(readonly_background_color)
            metadata_table.setItem(row, 0, key_item)
            metadata_table.setItem(row, 1, value_item)

        def start_value_edit(row: int, column: int) -> None:
            if column != 1:
                return
            key_item = metadata_table.item(row, 0)
            if key_item is not None and key_item.text() in readonly_keys:
                return
            item = metadata_table.item(row, column)
            if item is not None:
                metadata_table.editItem(item)

        metadata_table.cellDoubleClicked.connect(start_value_edit)
        metadata_table.cellActivated.connect(start_value_edit)
        metadata_table.setSortingEnabled(True)
        metadata_table.sortItems(0, Qt.SortOrder.AscendingOrder)
        dialog_layout.addWidget(metadata_table)
        self._apply_table_filter("")

        dialog_actions = QWidget(self)
        dialog_actions_layout = QHBoxLayout(dialog_actions)
        dialog_actions_layout.setContentsMargins(0, 0, 0, 0)
        dialog_actions_layout.setSpacing(12)
        dialog_actions_layout.addStretch(1)

        save_icon = QIcon.fromTheme(
            "document-save",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
        )
        save_button = QPushButton(
            QIcon(_monochrome_icon_pixmap(save_icon, 24, action_icon_color)),
            "Save",
            dialog_actions,
        )
        save_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        save_button.setMinimumHeight(40)
        save_button.setMaximumWidth(360)
        save_button.setIconSize(QSize(24, 24))
        save_button.clicked.connect(self._save_changes)
        dialog_actions_layout.addWidget(save_button)

        cancel_icon = QIcon.fromTheme(
            "dialog-cancel",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton),
        )
        cancel_button = QPushButton(
            QIcon(_monochrome_icon_pixmap(cancel_icon, 24, action_icon_color)),
            "Cancel",
            dialog_actions,
        )
        cancel_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        cancel_button.setMinimumHeight(40)
        cancel_button.setMaximumWidth(360)
        cancel_button.setIconSize(QSize(24, 24))
        cancel_button.clicked.connect(self.reject)
        dialog_actions_layout.addWidget(cancel_button)

        dialog_actions_layout.setStretch(0, 4)
        dialog_actions_layout.setStretch(1, 1)
        dialog_actions_layout.setStretch(2, 1)
        dialog_layout.addWidget(dialog_actions)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_column_ratio()
        self._apply_header_layout()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_column_ratio()
        self._apply_header_layout()

    def _save_changes(self) -> None:
        changes: list[dict[str, str]] = []
        for row in range(self._metadata_table.rowCount()):
            key_item = self._metadata_table.item(row, 0)
            value_item = self._metadata_table.item(row, 1)
            if key_item is None or value_item is None:
                continue

            key = key_item.text()
            old_value = self._original_entries.get(key, "")
            new_value = value_item.text()
            if new_value != old_value:
                changes.append(
                    {
                        "key": key,
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                )

        payload = {
            "appid": self._appid,
            "changes": changes,
        }

        try:
            changes_path = Path.cwd() / "user-changes.json"
            existing_payload: list[dict[str, Any]] = []
            if changes_path.exists():
                existing_data = json.loads(changes_path.read_text(encoding="utf-8"))
                existing_payload = _normalize_changes_payload(existing_data)

            merged = False
            for app_entry in existing_payload:
                if str(app_entry.get("appid")) != str(self._appid):
                    continue

                existing_changes = app_entry.get("changes")
                if not isinstance(existing_changes, list):
                    existing_changes = []
                    app_entry["changes"] = existing_changes

                existing_changes_by_key = {
                    str(item.get("key")): item
                    for item in existing_changes
                    if isinstance(item, dict) and item.get("key") is not None
                }
                for change in changes:
                    existing_change = existing_changes_by_key.get(change["key"])
                    if existing_change is None:
                        existing_changes.append(change)
                        continue

                    if not existing_change.get("old_value"):
                        existing_change["old_value"] = change["old_value"]
                    existing_change["new_value"] = change["new_value"]

                merged = True
                break

            if not merged:
                existing_payload.append(payload)

            changes_path.write_text(
                json.dumps(existing_payload, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Edit Metadata", str(exc))
            return

        self.accept()

    def _apply_table_filter(self, text: str) -> None:
        self._search_text = text.strip().casefold()

        for row in range(self._metadata_table.rowCount()):
            key_item = self._metadata_table.item(row, 0)
            value_item = self._metadata_table.item(row, 1)
            if key_item is None or value_item is None:
                self._metadata_table.setRowHidden(row, True)
                continue

            key_text = key_item.text()
            value_text = value_item.text()
            matches = not self._search_text or (
                self._search_text in key_text.casefold()
                or self._search_text in value_text.casefold()
            )
            self._metadata_table.setRowHidden(row, not matches)

    def _apply_column_ratio(self) -> None:
        viewport_width = self._metadata_table.viewport().width()
        if viewport_width <= 0:
            return

        total_ratio = self._column_width_ratio[0] + self._column_width_ratio[1]
        key_width = int(viewport_width * self._column_width_ratio[0] / total_ratio)
        value_width = max(0, viewport_width - key_width)
        self._metadata_table.setColumnWidth(0, key_width)
        self._metadata_table.setColumnWidth(1, value_width)

    def _apply_header_layout(self) -> None:
        header_width = self._header_row_layout.parentWidget().width()
        if header_width <= 0:
            return

        content_width = max(0, header_width)
        search_width = int(content_width * self._header_width_ratio[1] / sum(self._header_width_ratio))
        name_width = max(0, int(self.width() / 2) - 16)
        self._header_row_layout.setContentsMargins(0, 0, 0, 0)
        self._search_input.setFixedWidth(search_width)
        self._search_input.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._app_name_label.setFixedWidth(name_width)
