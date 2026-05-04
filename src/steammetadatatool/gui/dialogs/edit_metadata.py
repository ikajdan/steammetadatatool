# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.gui.data.app_data import app_data_path
from steammetadatatool.gui.data.json_helpers import validate_json_file_version
from steammetadatatool.gui.dialogs.message_box import show_critical
from steammetadatatool.gui.services.icons import monochrome_icon_pixmap
from steammetadatatool.gui.widgets.empty_state import EmptyStateOverlay
from steammetadatatool.gui.widgets.toast import ToastMessage

_METADATA_FILE_VERSION = 1


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


def _normalize_metadata_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        version = data.get("version")
        if version is not None:
            validate_json_file_version(
                version,
                current_version=_METADATA_FILE_VERSION,
                file_description="metadata file",
            )

        apps = data.get("apps")
        if isinstance(apps, list):
            return [item for item in apps if isinstance(item, dict)]
        if version is not None:
            return []
        return [data]
    return []


def _metadata_payload(apps: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {"version": _METADATA_FILE_VERSION}
    if apps:
        payload["apps"] = apps
    return payload


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


class RevertMetadataValueDelegate(QStyledItemDelegate):
    def __init__(
        self,
        revert_icon: QIcon,
        should_show_revert: Callable[[str, str], bool],
        revert_entry: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._revert_icon = revert_icon
        self._should_show_revert = should_show_revert
        self._revert_entry = revert_entry

    def paint(self, painter, option, index) -> None:
        key = self._key_for_index(index)
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if key is None or not self._should_show_revert(key, str(value or "")):
            super().paint(painter, option, index)
            return

        text_option = QStyleOptionViewItem(option)
        text_option.rect = option.rect.adjusted(0, 0, -32, 0)
        super().paint(painter, text_option, index)
        self._revert_icon.paint(
            painter,
            self._revert_icon_rect(option.rect),
            Qt.AlignmentFlag.AlignCenter,
        )

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return super().editorEvent(event, model, option, index)
        if event.button() != Qt.MouseButton.LeftButton:
            return super().editorEvent(event, model, option, index)
        if not self._revert_icon_rect(option.rect).contains(event.position().toPoint()):
            return super().editorEvent(event, model, option, index)

        key = self._key_for_index(index)
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if key is None or not self._should_show_revert(key, str(value or "")):
            return super().editorEvent(event, model, option, index)

        self._revert_entry(key)
        return True

    def _key_for_index(self, index) -> str | None:
        key_index = index.sibling(index.row(), 0)
        key = key_index.data(Qt.ItemDataRole.DisplayRole)
        return str(key) if key is not None else None

    def _revert_icon_rect(self, cell_rect) -> QRect:
        size = 24
        margin = 4
        return QRect(
            cell_rect.right() - size - margin + 1,
            cell_rect.top() + max(0, int((cell_rect.height() - size) / 2)),
            size,
            size,
        )


class EditMetadataDialog(QDialog):
    def __init__(
        self,
        raw_metadata: dict[str, Any],
        *,
        appid: str | None = None,
        app_name: str | None = None,
        on_save: Callable[
            [list[dict[str, str]], list[dict[str, Any]]], bool | dict[str, Any]
        ]
        | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SteamMetadataTool")
        self.setModal(True)
        self.resize(1080, 560)
        self.setMinimumSize(720, 520)
        self._column_width_ratio = (4, 3)
        self._header_width_ratio = (2, 1)

        entries = _flatten_metadata_entries(raw_metadata)
        readonly_keys = {
            "appinfo.appid",
            "appinfo.common.gameid",
        }
        self._appid = appid
        self._on_save = on_save
        self._readonly_keys = readonly_keys
        self._original_entries = dict(entries)
        self._default_entries = dict(entries)
        self._saved_change_keys: set[str] = set()
        self._saved_entries = self._entries_with_saved_changes(dict(entries))
        self._search_text = ""
        self._apply_button: QPushButton | None = None
        self._empty_search_overlay: EmptyStateOverlay | None = None
        self._toast = ToastMessage(self, bottom_margin=80)
        action_icon_color = self.palette().placeholderText().color()
        self._readonly_text_color = self.palette().placeholderText().color()
        self._revert_icon = QIcon(
            monochrome_icon_pixmap(
                QIcon.fromTheme(
                    "edit-undo",
                    self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack),
                ),
                16,
                action_icon_color,
            )
        )
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(10, 11, 10, 10)
        dialog_layout.setSpacing(11)

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
            QIcon(monochrome_icon_pixmap(search_icon, 16, action_icon_color)),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_table_filter)
        header_row_layout.addWidget(self._search_input, 0, Qt.AlignmentFlag.AlignRight)
        dialog_layout.addWidget(header_row)

        metadata_table = QTableWidget(len(self._saved_entries), 2, self)
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
        metadata_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        metadata_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        metadata_table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        metadata_table.setAlternatingRowColors(True)
        metadata_table.setShowGrid(False)
        metadata_table.setWordWrap(True)
        metadata_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        metadata_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        metadata_table.setItemDelegateForColumn(
            1,
            RevertMetadataValueDelegate(
                self._revert_icon,
                self._should_show_revert_for_key,
                self._revert_entry,
                metadata_table,
            ),
        )

        self._set_metadata_rows(self._saved_entries)

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
        metadata_table.itemChanged.connect(self._on_metadata_item_changed)
        metadata_table.setSortingEnabled(True)
        metadata_table.sortItems(0, Qt.SortOrder.AscendingOrder)

        table_stack = QWidget(self)
        table_stack_layout = QStackedLayout(table_stack)
        table_stack_layout.setContentsMargins(0, 0, 0, 0)
        table_stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        table_stack_layout.addWidget(metadata_table)

        empty_search_overlay = EmptyStateOverlay(
            QIcon(monochrome_icon_pixmap(search_icon, 40, action_icon_color)),
            "No Results Found",
            parent=table_stack,
        )
        empty_search_overlay.hide()
        self._empty_search_overlay = empty_search_overlay
        table_stack_layout.addWidget(empty_search_overlay)

        dialog_layout.addWidget(table_stack)
        self._apply_table_filter("")
        self._refresh_unsaved_change_styles()

        dialog_actions = QWidget(self)
        dialog_actions_layout = QHBoxLayout(dialog_actions)
        dialog_actions_layout.setContentsMargins(0, 0, 0, 0)
        dialog_actions_layout.setSpacing(12)
        dialog_actions_layout.addStretch(1)

        apply_icon = QIcon.fromTheme(
            "dialog-ok-apply",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
        )
        apply_button = QPushButton(
            QIcon(monochrome_icon_pixmap(apply_icon, 24, action_icon_color)),
            "Apply",
            dialog_actions,
        )
        self._apply_button = apply_button
        apply_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        apply_button.setMinimumHeight(40)
        apply_button.setMaximumWidth(360)
        apply_button.setIconSize(QSize(24, 24))
        apply_button.setEnabled(False)
        apply_button.clicked.connect(self._save_changes)
        dialog_actions_layout.addWidget(apply_button)

        cancel_icon = QIcon.fromTheme(
            "dialog-cancel",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton),
        )
        cancel_button = QPushButton(
            QIcon(monochrome_icon_pixmap(cancel_icon, 24, action_icon_color)),
            "Close",
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
        self._refresh_apply_button_state()

    def _entries_with_saved_changes(self, entries: dict[str, str]) -> dict[str, str]:
        if self._appid is None:
            return entries

        metadata_path = app_data_path("metadata.json")
        if not metadata_path.exists():
            return entries

        try:
            existing_data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return entries

        saved_entries = dict(entries)
        for app_entry in _normalize_metadata_payload(existing_data):
            if str(app_entry.get("appid")) != str(self._appid):
                continue

            changes = app_entry.get("changes")
            if not isinstance(changes, list):
                continue

            for change in changes:
                if not isinstance(change, dict):
                    continue

                key = change.get("key")
                if not isinstance(key, str) or "new_value" not in change:
                    continue

                if "old_value" in change:
                    self._default_entries[key] = _format_metadata_value(
                        change["old_value"]
                    )
                self._saved_change_keys.add(key)
                saved_entries[key] = _format_metadata_value(change["new_value"])

        return saved_entries

    def _set_metadata_rows(self, entries: dict[str, str]) -> None:
        self._metadata_table.blockSignals(True)
        sorting_enabled = self._metadata_table.isSortingEnabled()
        self._metadata_table.setSortingEnabled(False)
        self._metadata_table.setRowCount(len(entries))
        for row, (key, value) in enumerate(entries.items()):
            key_item = QTableWidgetItem(key)
            value_item = QTableWidgetItem(value)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if key in self._readonly_keys:
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item.setForeground(self._readonly_text_color)
            self._metadata_table.setItem(row, 0, key_item)
            self._metadata_table.setItem(row, 1, value_item)
        self._metadata_table.setSortingEnabled(sorting_enabled)
        if sorting_enabled:
            self._metadata_table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._metadata_table.blockSignals(False)
        self._apply_table_filter(self._search_text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_column_ratio()
        self._apply_header_layout()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_column_ratio()
        self._apply_header_layout()
        self._select_first_visible_row()

    def _save_changes(self) -> None:
        changes: list[dict[str, str]] = []
        current_entries = self._current_entries()
        for key, new_value in current_entries.items():
            old_value = self._original_entries.get(key, "")
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
            metadata_path = app_data_path("metadata.json")
            existing_payload: list[dict[str, Any]] = []
            if metadata_path.exists():
                existing_data = json.loads(metadata_path.read_text(encoding="utf-8"))
                existing_payload = _normalize_metadata_payload(existing_data)

            changes_to_apply = list(changes)
            merged = False
            for app_entry in existing_payload:
                if str(app_entry.get("appid")) != str(self._appid):
                    continue

                existing_changes = app_entry.get("changes")
                if not isinstance(existing_changes, list):
                    existing_changes = []
                    app_entry["changes"] = existing_changes

                existing_default_values = {
                    str(item.get("key")): _format_metadata_value(
                        item.get("old_value", "")
                    )
                    for item in existing_changes
                    if isinstance(item, dict) and item.get("key") is not None
                }
                changes_to_save = [
                    change
                    for change in changes
                    if change["new_value"]
                    != existing_default_values.get(change["key"], change["old_value"])
                ]
                changed_keys = {change["key"] for change in changes}
                changed_keys_to_save = {change["key"] for change in changes_to_save}
                restored_changes_to_apply = [
                    {
                        "key": key,
                        "old_value": _format_metadata_value(
                            existing_default_values.get(key, "")
                        ),
                        "new_value": current_entries[key],
                    }
                    for key in existing_default_values
                    if key in current_entries
                    and key not in changed_keys
                    and current_entries[key] == existing_default_values[key]
                ]
                changes_to_apply.extend(restored_changes_to_apply)
                existing_changes[:] = [
                    item
                    for item in existing_changes
                    if not isinstance(item, dict)
                    or str(item.get("key")) not in current_entries
                    or str(item.get("key")) in changed_keys_to_save
                    or current_entries.get(str(item.get("key")))
                    == _format_metadata_value(item.get("new_value"))
                ]
                existing_changes_by_key = {
                    str(item.get("key")): item
                    for item in existing_changes
                    if isinstance(item, dict) and item.get("key") is not None
                }
                for change in changes_to_save:
                    existing_change = existing_changes_by_key.get(change["key"])
                    if existing_change is None:
                        existing_changes.append(change)
                        continue

                    if not existing_change.get("old_value"):
                        existing_change["old_value"] = change["old_value"]
                    existing_change["new_value"] = change["new_value"]

                merged = True
                break

            if not merged and changes:
                existing_payload.append(payload)

            existing_payload = [
                app_entry
                for app_entry in existing_payload
                if str(app_entry.get("appid")) != str(self._appid)
                or not isinstance(app_entry.get("changes"), list)
                or app_entry["changes"]
                or set(app_entry) - {"appid", "changes"}
            ]

            refreshed_metadata: dict[str, Any] | None = None
            if self._on_save is not None:
                save_result = self._on_save(changes_to_apply, existing_payload)
                if save_result is False:
                    return
                if isinstance(save_result, dict):
                    refreshed_metadata = save_result

            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps(
                    _metadata_payload(existing_payload),
                    indent=2,
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
        except (OSError, json.JSONDecodeError) as exc:
            show_critical(self, "Edit Metadata", str(exc))
            return
        except Exception as exc:
            show_critical(self, "Edit Metadata", str(exc))
            return

        if refreshed_metadata is not None:
            self._original_entries = dict(_flatten_metadata_entries(refreshed_metadata))
        else:
            self._original_entries = dict(current_entries)
        self._default_entries = dict(self._original_entries)
        self._saved_change_keys = self._saved_change_keys_from_payload(existing_payload)
        self._saved_entries = self._entries_with_saved_changes(
            dict(self._original_entries)
        )
        self._set_metadata_rows(self._saved_entries)
        self._refresh_unsaved_change_styles()
        self._show_status_message("Metadata saved")

    def _saved_change_keys_from_payload(
        self, payload: list[dict[str, Any]]
    ) -> set[str]:
        keys: set[str] = set()
        for app_entry in payload:
            if str(app_entry.get("appid")) != str(self._appid):
                continue

            changes = app_entry.get("changes")
            if not isinstance(changes, list):
                continue

            for change in changes:
                if not isinstance(change, dict):
                    continue

                key = change.get("key")
                if isinstance(key, str):
                    keys.add(key)

        return keys

    def _show_status_message(self, message: str) -> None:
        self._toast.show_message(message)

    def _current_entries(self) -> dict[str, str]:
        entries: dict[str, str] = {}
        for row in range(self._metadata_table.rowCount()):
            key_item = self._metadata_table.item(row, 0)
            value_item = self._metadata_table.item(row, 1)
            if key_item is None or value_item is None:
                continue
            entries[key_item.text()] = value_item.text()
        return entries

    def _on_metadata_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 1:
            return

        key_item = self._metadata_table.item(item.row(), 0)
        if key_item is None:
            return

        self._set_unsaved_change_style(item, key_item.text())
        self._metadata_table.viewport().update()
        self._refresh_apply_button_state()

    def _refresh_unsaved_change_styles(self) -> None:
        for row in range(self._metadata_table.rowCount()):
            key_item = self._metadata_table.item(row, 0)
            value_item = self._metadata_table.item(row, 1)
            if key_item is None or value_item is None:
                continue
            self._set_unsaved_change_style(value_item, key_item.text())
        self._metadata_table.viewport().update()
        self._refresh_apply_button_state()

    def _has_unsaved_changes(self) -> bool:
        current_entries = self._current_entries()
        return any(
            current_entries.get(key, "") != saved_value
            for key, saved_value in self._saved_entries.items()
        )

    def _refresh_apply_button_state(self) -> None:
        if self._apply_button is not None:
            self._apply_button.setEnabled(self._has_unsaved_changes())

    def _revert_entry(self, key: str) -> None:
        value_item = self._value_item_for_key(key)
        if value_item is None:
            return
        value_item.setText(
            self._default_entries.get(key, self._original_entries.get(key, ""))
        )

    def _value_item_for_key(self, key: str) -> QTableWidgetItem | None:
        row = self._row_for_key(key)
        if row is not None:
            return self._metadata_table.item(row, 1)
        return None

    def _row_for_key(self, key: str) -> int | None:
        for row in range(self._metadata_table.rowCount()):
            key_item = self._metadata_table.item(row, 0)
            if key_item is not None and key_item.text() == key:
                return row
        return None

    def _should_show_revert_for_key(self, key: str, value: str) -> bool:
        default_value = self._default_entries.get(
            key, self._original_entries.get(key, "")
        )
        return value != default_value

    def _set_unsaved_change_style(self, item: QTableWidgetItem, key: str) -> None:
        font = item.font()
        value = item.text()
        is_unsaved = value != self._saved_entries.get(key, "")
        is_saved_edit = not is_unsaved and (
            key in self._saved_change_keys
            or value != self._original_entries.get(key, "")
        )
        if font.italic() == is_unsaved and font.bold() == is_saved_edit:
            return

        font.setItalic(is_unsaved)
        font.setBold(is_saved_edit)
        item.setFont(font)

    def _apply_table_filter(self, text: str) -> None:
        self._search_text = text.strip().casefold()

        first_visible_row: int | None = None
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
            if matches and first_visible_row is None:
                first_visible_row = row

        show_empty_search = (
            self._metadata_table.rowCount() > 0
            and first_visible_row is None
            and bool(self._search_text)
        )
        self._set_empty_search_visible(show_empty_search)

        self._select_first_visible_row()
        self._metadata_table.viewport().update()

    def _set_empty_search_visible(self, visible: bool) -> None:
        if self._empty_search_overlay is None:
            return

        self._empty_search_overlay.setVisible(visible)
        if visible:
            self._empty_search_overlay.raise_()

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
        search_width = int(
            content_width * self._header_width_ratio[1] / sum(self._header_width_ratio)
        )
        name_width = max(0, int(self.width() / 2) - 16)
        self._header_row_layout.setContentsMargins(0, 0, 0, 0)
        self._search_input.setFixedWidth(search_width)
        self._search_input.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._app_name_label.setFixedWidth(name_width)

    def _select_first_visible_row(self) -> None:
        for row in range(self._metadata_table.rowCount()):
            if self._metadata_table.isRowHidden(row):
                continue

            item = self._metadata_table.item(row, 1) or self._metadata_table.item(
                row, 0
            )
            if item is None:
                continue

            self._metadata_table.setCurrentItem(item)
            return

        self._metadata_table.clearSelection()
