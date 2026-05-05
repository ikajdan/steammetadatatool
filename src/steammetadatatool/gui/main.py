# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QObject,
    QSize,
    Qt,
    QThread,
    QTimer,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool import __version__
from steammetadatatool.core.appinfo import (
    AppInfoFile,
    find_steam_appinfo_path,
)
from steammetadatatool.core.models import OverrideInput
from steammetadatatool.core.services import (
    METADATA_FILE_VERSION,
    load_metadata_file,
    metadata_values_from_change_entries,
    write_modified_appinfo,
)
from steammetadatatool.gui.data.app_data import app_data_path
from steammetadatatool.gui.dialogs.edit_assets import EditAssetsDialog
from steammetadatatool.gui.dialogs.edit_metadata import EditMetadataDialog
from steammetadatatool.gui.dialogs.message_box import (
    confirm_warning,
    show_critical,
    show_information,
)
from steammetadatatool.gui.dialogs.missing_appinfo import (
    select_appinfo_file_after_detection_failed,
    select_missing_appinfo_file,
)
from steammetadatatool.gui.models.app_details import (
    DETAIL_VALUE_LEFT_INSET,
    INLINE_DETAIL_EDITOR_STYLE,
    INLINE_EDIT_METADATA_KEYS,
    detail_text_to_metadata_value,
    details_for_app,
    float_value,
    matches_game_filter,
    merge_metadata_override_values,
    metadata_overrides_from_apps_payload,
    read_app_rows,
)
from steammetadatatool.gui.models.app_loader import AppLoadWorker
from steammetadatatool.gui.services.asset_optimizer import run_asset_optimization_prompt
from steammetadatatool.gui.services.icons import monochrome_icon_pixmap
from steammetadatatool.gui.services.metadata_apply import apply_metadata_file_silently
from steammetadatatool.gui.services.positions_importer import import_logo_position_files
from steammetadatatool.gui.services.search import normalized_search_text
from steammetadatatool.gui.services.theme import apply_theme
from steammetadatatool.gui.steam.process import is_steam_running
from steammetadatatool.gui.widgets.delegates import LeftPaddingItemDelegate
from steammetadatatool.gui.widgets.empty_state import EmptyStateOverlay
from steammetadatatool.gui.widgets.inline_edit import InlineDetailLineEdit
from steammetadatatool.gui.widgets.loading import ListLoadingOverlay
from steammetadatatool.gui.widgets.previews import (
    PreviewPixmapLabel,
    RatioPreviewPixmapLabel,
)
from steammetadatatool.gui.widgets.toast import ToastMessage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SteamMetadataTool")
        self.resize(1200, 560)
        self.setMinimumSize(980, 520)

        self._details_by_appid: dict[int, dict[str, Any]] = {}
        self._appinfo_path: Path | None = None
        self._load_thread: QThread | None = None
        self._load_worker: AppLoadWorker | None = None
        self._detail_labels: dict[str, QWidget] = {}
        self._detail_editors: dict[str, QLineEdit] = {}
        self._asset_image_labels: dict[str, QLabel] = {}
        self._asset_boxes: dict[str, QWidget] = {}
        self._assets_heading: QLabel | None = None
        self._assets_separator: QFrame | None = None
        self._assets_widget: QWidget | None = None
        self._appinfo_required_widgets: list[QWidget] = []
        self._appinfo_required_preview_labels: list[PreviewPixmapLabel] = []
        self._filter_matches_by_appid: dict[int, bool] = {}
        self._list_loading_overlay: ListLoadingOverlay | None = None
        self._empty_search_overlay: EmptyStateOverlay | None = None
        self._toast: ToastMessage | None = None
        self._search_drawer: QWidget | None = None
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._composited_hero_cache: dict[tuple[str, str, str], QPixmap] = {}
        self._asset_image_specs: dict[str, tuple[int, int]] = {
            "header_path": (460, 215),
            "hero_path": (384, 124),
            "icon_path": (32, 32),
        }
        self._search_text = ""
        self._setting_details = False
        self._allow_appinfo_write_while_steam_running = False
        self._capsule_preview = RatioPreviewPixmapLabel(
            self._missing_asset_pixmap(32, 32),
            2,
            3,
            corner_radius=16,
            show_inactive_border=True,
        )
        self._edit_overlay_icon = QIcon(
            monochrome_icon_pixmap(
                QIcon.fromTheme(
                    "document-edit",
                    self.style().standardIcon(
                        QStyle.StandardPixmap.SP_FileDialogDetailedView
                    ),
                ),
                16,
                QColor("white"),
            )
        )
        self._capsule_preview.set_click_handler(
            lambda: self._open_edit_assets_dialog("capsule_path"),
            self._edit_overlay_icon,
        )
        self._details_form_container: QWidget | None = None

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by Name or App ID")
        search_icon = QIcon.fromTheme(
            "edit-find",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
        )
        search_icon_color = self.palette().placeholderText().color()
        self._search_input.addAction(
            QIcon(monochrome_icon_pixmap(search_icon, 16, search_icon_color)),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(40)
        self._search_input.textChanged.connect(self._apply_table_filter)

        filter_icon = QIcon.fromTheme(
            "view-filter",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        )
        filter_icon_color = self.palette().placeholderText().color()
        filter_button_icon = QIcon(
            monochrome_icon_pixmap(filter_icon, 24, filter_icon_color, right_padding=0)
        )
        self._filter_button = QPushButton(filter_button_icon, "Games Only")
        self._filter_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._filter_button.setMinimumHeight(40)
        self._filter_button.setIconSize(QSize(24, 24))
        self._filter_button.setToolTip("Show only games with metadata")
        self._filter_button.setCheckable(True)
        self._filter_button.toggled.connect(
            lambda _checked: self._apply_table_filter(self._search_input.text())
        )
        self._appinfo_required_widgets.append(self._filter_button)

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
        self._table.setItemDelegateForColumn(
            1, LeftPaddingItemDelegate(10, self._table)
        )
        self._table.setSortingEnabled(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(
            lambda _item: self._open_edit_metadata_dialog()
        )

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        search_row = QWidget()
        search_row_layout = QHBoxLayout(search_row)
        search_row_layout.setContentsMargins(0, 14, 0, 8)
        search_row_layout.setSpacing(12)
        search_row_layout.addWidget(self._search_input, 1)
        search_row_layout.addWidget(self._filter_button, 0)
        search_row.hide()
        self._search_drawer = search_row

        table_stack = QWidget()
        table_stack_layout = QStackedLayout(table_stack)
        table_stack_layout.setContentsMargins(0, 0, 0, 0)
        table_stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        table_stack_layout.addWidget(self._table)

        empty_search_icon = QIcon.fromTheme(
            "edit-find",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
        )
        empty_search_overlay = EmptyStateOverlay(
            QIcon(monochrome_icon_pixmap(empty_search_icon, 48, search_icon_color)),
            "No Results Found",
            parent=table_stack,
        )
        empty_search_overlay.hide()
        self._empty_search_overlay = empty_search_overlay
        table_stack_layout.addWidget(empty_search_overlay)

        list_loading_overlay = ListLoadingOverlay(table_stack)
        list_loading_overlay.hide()
        self._list_loading_overlay = list_loading_overlay
        table_stack_layout.addWidget(list_loading_overlay)

        list_layout.addWidget(table_stack, 1)
        list_layout.addWidget(search_row, 0)

        details_widget = QWidget()
        details_widget.setMinimumWidth(500)
        details_outer_layout = QVBoxLayout(details_widget)
        details_outer_layout.setContentsMargins(8, 8, 8, 8)
        details_outer_layout.setSpacing(10)
        details_outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        details_heading = QLabel("Details")
        details_heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        details_outer_layout.addWidget(details_heading)

        heading_separator = QFrame()
        heading_separator.setFrameShape(QFrame.Shape.HLine)
        heading_separator.setFrameShadow(QFrame.Shadow.Sunken)
        details_outer_layout.addWidget(heading_separator)

        details_content_widget = QWidget()
        details_content_layout = QHBoxLayout(details_content_widget)
        details_content_layout.setContentsMargins(0, 12, 0, 0)
        details_content_layout.setSpacing(24)
        details_outer_layout.addWidget(details_content_widget)
        details_outer_layout.addSpacing(12)

        capsule_container = QWidget()
        capsule_container.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Preferred,
        )
        capsule_layout = QVBoxLayout(capsule_container)
        capsule_layout.setContentsMargins(0, 0, 0, 0)
        capsule_layout.addWidget(
            self._capsule_preview,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        capsule_layout.setStretch(0, 1)
        self._capsule_preview.setMinimumWidth(220)
        self._appinfo_required_preview_labels.append(self._capsule_preview)
        details_content_layout.addWidget(
            capsule_container, 0, Qt.AlignmentFlag.AlignTop
        )

        details_form_container = QWidget()
        self._details_form_container = details_form_container
        details_form_container.setMinimumWidth(250)
        details_form_container.installEventFilter(self)
        details_content_layout.addWidget(
            details_form_container, 2, Qt.AlignmentFlag.AlignTop
        )

        details_layout = QFormLayout(details_form_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setHorizontalSpacing(4)
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
            ("name", "Name"),
            ("appid", "App ID"),
            ("_separator_name_icon", ""),
            ("icon_path", "Icon"),
            ("_separator_1", ""),
            ("sort_as", "Sort As"),
            ("aliases", "Aliases"),
            ("_separator_2", ""),
            ("developer", "Developer"),
            ("publisher", "Publisher"),
            ("_separator_3", ""),
            ("release_date", "Release Date"),
        )
        for key, title in fields:
            if key.startswith("_separator_"):
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                details_layout.addRow(separator)
                continue

            title_label = QLabel(f"{title}:")
            title_label.setFixedWidth(140)
            title_label.setStyleSheet("font-weight: 600;")

            if key in self._asset_image_specs:
                preview_width, preview_height = self._asset_image_specs[key]
                value_label = PreviewPixmapLabel(
                    self._missing_asset_pixmap(
                        preview_width,
                        preview_height,
                        question_mark_scale=0.6 if key == "icon_path" else 1.0,
                    ),
                )
                value_label.setMinimumSize(preview_width, preview_height)
                value_label.setMaximumSize(preview_width, preview_height)
                value_label.set_click_handler(
                    lambda asset_key=key: self._open_edit_assets_dialog(asset_key),
                    show_overlay=False,
                )
                self._appinfo_required_preview_labels.append(value_label)
                self._asset_image_labels[key] = value_label
            else:
                if key in INLINE_EDIT_METADATA_KEYS:
                    value_label = InlineDetailLineEdit()
                    value_label.setMinimumWidth(0)
                    value_label.setSizePolicy(
                        QSizePolicy.Policy.Expanding,
                        QSizePolicy.Policy.Fixed,
                    )
                    value_label.setFrame(False)
                    value_label.setStyleSheet(INLINE_DETAIL_EDITOR_STYLE)
                    value_label.installEventFilter(self)
                    value_label.returnPressed.connect(
                        lambda detail_key=key: self._commit_inline_detail_edit(
                            detail_key
                        )
                    )
                    self._detail_editors[key] = value_label
                else:
                    value_label = QLabel("–")
                    value_label.setMinimumWidth(0)
                    value_label.setMaximumWidth(280)
                    value_label.setSizePolicy(
                        QSizePolicy.Policy.Maximum,
                        QSizePolicy.Policy.Preferred,
                    )
                    if key == "appid":
                        value_label.setIndent(DETAIL_VALUE_LEFT_INSET)
                    value_label.setAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    )
                    value_label.setWordWrap(True)
                    value_label.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse
                    )
            row_value_widget: QWidget = value_label
            if key == "icon_path":
                icon_container = QWidget()
                icon_container.setFixedSize(
                    self._asset_image_specs[key][0] + DETAIL_VALUE_LEFT_INSET,
                    self._asset_image_specs[key][1],
                )
                icon_container.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )
                icon_layout = QHBoxLayout(icon_container)
                icon_layout.setContentsMargins(DETAIL_VALUE_LEFT_INSET, 0, 0, 0)
                icon_layout.setSpacing(0)
                icon_layout.addWidget(value_label)
                row_value_widget = icon_container
            details_layout.addRow(title_label, row_value_widget)
            self._detail_labels[key] = value_label

        assets_heading = QLabel("Assets")
        assets_heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        self._assets_heading = assets_heading
        details_outer_layout.addWidget(assets_heading)

        assets_separator = QFrame()
        assets_separator.setFrameShape(QFrame.Shape.HLine)
        assets_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self._assets_separator = assets_separator
        details_outer_layout.addWidget(assets_separator)

        assets_widget = QWidget()
        self._assets_widget = assets_widget
        assets_layout = QVBoxLayout(assets_widget)
        assets_layout.setContentsMargins(0, 12, 0, 0)
        assets_layout.setSpacing(22)
        details_outer_layout.addWidget(assets_widget)

        def create_asset_box(
            key: str,
            title: str,
            size: tuple[int, int],
            ratio_width: int | None,
            ratio_height: int | None,
            corner_radius: float,
            pixmap_alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
        ) -> QWidget:
            asset_box = QWidget()
            asset_box_layout = QVBoxLayout(asset_box)
            asset_box_layout.setContentsMargins(0, 0, 0, 0)
            asset_box_layout.setSpacing(10)

            asset_label = QLabel(title)
            asset_label.setStyleSheet("font-weight: 600;")
            asset_box_layout.addWidget(asset_label)

            preview_width, preview_height = size
            if ratio_width is not None and ratio_height is not None:
                preview_label = RatioPreviewPixmapLabel(
                    self._missing_asset_pixmap(preview_width, preview_height),
                    ratio_width,
                    ratio_height,
                    corner_radius=corner_radius,
                    show_inactive_border=True,
                    pixmap_alignment=pixmap_alignment,
                )
                preview_label.setMinimumWidth(0)
            else:
                preview_label = PreviewPixmapLabel(
                    self._missing_asset_pixmap(preview_width, preview_height),
                    corner_radius=corner_radius,
                    show_inactive_border=True,
                    pixmap_alignment=pixmap_alignment,
                )
                preview_label.setMinimumSize(preview_width, preview_height)
                preview_label.setMaximumSize(preview_width, preview_height)
            self._asset_image_labels[key] = preview_label
            self._asset_boxes[key] = asset_box
            self._asset_image_specs[key] = size
            preview_label.set_click_handler(
                lambda asset_key=key: self._open_edit_assets_dialog(asset_key),
                self._edit_overlay_icon,
            )
            self._appinfo_required_preview_labels.append(preview_label)
            asset_box_layout.addWidget(preview_label)
            return asset_box

        header_box = create_asset_box("header_path", "Header", (460, 215), 460, 215, 16)
        header_box.setMinimumWidth(360)
        header_box.setMaximumWidth(460)
        header_box.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        assets_layout.addWidget(header_box, 0, Qt.AlignmentFlag.AlignTop)

        assets_layout.addWidget(
            create_asset_box(
                "hero_path",
                "Hero",
                (384, 124),
                96,
                31,
                16,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
        )

        assets_layout.addStretch(1)

        details_outer_layout.addStretch(1)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 12, 10, 10)
        root_layout.setSpacing(11)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.addWidget(list_widget, 5)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        details_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        details_scroll.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        details_scroll.setWidget(details_widget)

        details_panel = QWidget()
        details_panel_layout = QVBoxLayout(details_panel)
        details_panel_layout.setContentsMargins(0, 0, 0, 0)
        details_panel_layout.setSpacing(8)
        details_panel_layout.addWidget(details_scroll, 1)

        actions_container = QWidget()
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(8, 6, 8, 8)
        actions_layout.setSpacing(12)

        metadata_icon = QIcon.fromTheme(
            "document-edit",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
        )
        metadata_button_icon = QIcon(
            monochrome_icon_pixmap(
                metadata_icon, 24, filter_icon_color, right_padding=0
            )
        )
        edit_metadata_button = QPushButton(metadata_button_icon, "Edit Metadata")
        edit_metadata_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        edit_metadata_button.setMinimumHeight(40)
        edit_metadata_button.setIconSize(QSize(24, 24))
        edit_metadata_button.clicked.connect(self._open_edit_metadata_dialog)
        self._appinfo_required_widgets.append(edit_metadata_button)
        actions_layout.addWidget(edit_metadata_button)

        assets_icon = QIcon.fromTheme(
            "view-preview",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
        )
        assets_button_icon = QIcon(
            monochrome_icon_pixmap(assets_icon, 24, filter_icon_color, right_padding=0)
        )
        edit_assets_button = QPushButton(assets_button_icon, "Edit Assets")
        edit_assets_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        edit_assets_button.setMinimumHeight(40)
        edit_assets_button.setIconSize(QSize(24, 24))
        edit_assets_button.clicked.connect(self._open_edit_assets_dialog)
        self._appinfo_required_widgets.append(edit_assets_button)
        actions_layout.addWidget(edit_assets_button)

        details_panel_layout.addWidget(actions_container, 0)

        content_layout.addWidget(details_panel, 4)
        root_layout.addLayout(content_layout, 1)
        self.setCentralWidget(root)
        self._toast = ToastMessage(details_panel, bottom_margin=80)
        self._set_details(None)
        self._refresh_appinfo_required_widgets()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _open_edit_metadata_dialog(self) -> None:
        appid = self._current_selected_appid()
        if appid is None:
            show_information(
                self,
                "Edit Metadata",
                "Select an app to view its metadata.",
            )
            return

        details = self._details_by_appid.get(appid)
        raw_metadata = details.get("_raw_metadata") if details is not None else None
        if not isinstance(raw_metadata, dict):
            show_information(
                self,
                "Edit Metadata",
                "No metadata is available for the selected app.",
            )
            return

        dialog = EditMetadataDialog(
            raw_metadata,
            appid=details.get("appid") if details is not None else None,
            app_name=details.get("name") if details is not None else None,
            on_save=lambda changes, payload, selected_appid=appid: (
                self._apply_saved_metadata_changes(
                    selected_appid,
                    changes,
                    metadata_payload=payload,
                )
            ),
            parent=self,
        )
        dialog.exec()

    def _metadata_payload_apps(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"could not read metadata file: {exc}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in metadata file: {exc}")

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            version = payload.get("version")
            if version is not None:
                if (
                    not isinstance(version, int)
                    or isinstance(version, bool)
                    or version < 1
                ):
                    raise ValueError(
                        "metadata file: version must be a positive integer"
                    )
                if version > METADATA_FILE_VERSION:
                    raise ValueError(
                        "metadata file: unsupported version "
                        f"{version} (latest supported is {METADATA_FILE_VERSION})"
                    )

            apps = payload.get("apps")
            if isinstance(apps, list):
                return [item for item in apps if isinstance(item, dict)]
            if version is not None:
                return []
            return [payload]
        raise ValueError("metadata file must contain a JSON object or array")

    def _write_inline_metadata_change(
        self,
        appid: int,
        *,
        key: str,
        old_value: str,
        new_value: str,
    ) -> None:
        metadata_path = app_data_path("metadata.json")
        existing_payload = self._metadata_payload_apps(metadata_path)

        app_entry: dict[str, Any] | None = None
        for existing_entry in existing_payload:
            if str(existing_entry.get("appid")) == str(appid):
                app_entry = existing_entry
                break

        if app_entry is None:
            app_entry = {"appid": str(appid), "changes": []}
            existing_payload.append(app_entry)

        existing_changes = app_entry.get("changes")
        if not isinstance(existing_changes, list):
            existing_changes = []
            app_entry["changes"] = existing_changes

        change_entry: dict[str, Any] | None = None
        for existing_change in existing_changes:
            if not isinstance(existing_change, dict):
                continue
            if str(existing_change.get("key")) == key:
                change_entry = existing_change
                break

        base_value = old_value
        if change_entry is not None and "old_value" in change_entry:
            base_value = str(change_entry.get("old_value", ""))

        if new_value == base_value:
            if change_entry is not None:
                existing_changes.remove(change_entry)
        elif change_entry is None:
            existing_changes.append(
                {
                    "key": key,
                    "old_value": base_value,
                    "new_value": new_value,
                }
            )
        else:
            change_entry["old_value"] = base_value
            change_entry["new_value"] = new_value

        existing_payload = [
            entry
            for entry in existing_payload
            if str(entry.get("appid")) != str(appid)
            or not isinstance(entry.get("changes"), list)
            or entry["changes"]
            or set(entry) - {"appid", "changes"}
        ]

        payload: dict[str, Any] = {"version": METADATA_FILE_VERSION}
        if existing_payload:
            payload["apps"] = existing_payload

        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def _commit_inline_detail_edit(self, detail_key: str) -> None:
        editor = self._detail_editors.get(detail_key)
        if editor is None:
            return

        if self._save_inline_detail_edit(detail_key):
            editor.clearFocus()

    def _save_inline_detail_edit(self, detail_key: str) -> bool:
        if self._setting_details:
            return False

        editor = self._detail_editors.get(detail_key)
        appid = self._current_selected_appid()
        details = self._details_by_appid.get(appid) if appid is not None else None
        metadata_key = INLINE_EDIT_METADATA_KEYS.get(detail_key)
        if detail_key == "release_date" and details is not None:
            release_date_key = str(
                details.get("_release_date_key") or "original_release_date"
            )
            metadata_key = f"appinfo.common.{release_date_key}"
        if editor is None or appid is None or details is None or metadata_key is None:
            return False

        old_text = str(details.get(detail_key, ""))
        new_text = editor.text().strip()
        try:
            old_value = detail_text_to_metadata_value(detail_key, old_text)
            new_value = detail_text_to_metadata_value(detail_key, new_text)
            if new_value == old_value:
                if app_data_path("metadata.json").exists():
                    self._write_inline_metadata_change(
                        appid,
                        key=metadata_key,
                        old_value=old_value,
                        new_value=new_value,
                    )
                    self._show_status_message("Metadata saved")
                return True

            changes = [
                {
                    "key": metadata_key,
                    "old_value": old_value,
                    "new_value": new_value,
                }
            ]

            if not self._apply_saved_metadata_changes(appid, changes):
                editor.setText(old_text)
                return False
            self._write_inline_metadata_change(
                appid,
                key=metadata_key,
                old_value=old_value,
                new_value=new_value,
            )
            self._refresh_app_from_disk(appid)
            self._show_status_message("Metadata saved")
        except Exception as exc:
            show_critical(self, "Edit Details", str(exc))
            editor.setText(old_text)
            return False

        return True

    def _show_status_message(self, message: str) -> None:
        if self._toast is not None:
            self._toast.show_message(message)

    def _cancel_inline_detail_edit(self, detail_key: str) -> None:
        if self._setting_details:
            return

        editor = self._detail_editors.get(detail_key)
        appid = self._current_selected_appid()
        details = self._details_by_appid.get(appid) if appid is not None else None
        if editor is None or details is None:
            return

        editor.setText(str(details.get(detail_key, "–")))

    def _apply_saved_metadata_changes(
        self,
        appid: int,
        changes: list[dict[str, str]],
        *,
        metadata_payload: list[dict[str, Any]] | None = None,
    ) -> bool | dict[str, Any]:
        if self._appinfo_path is None:
            raise ValueError("No appinfo.vdf path is loaded.")

        metadata_path = app_data_path("metadata.json")
        metadata_overrides = (
            metadata_overrides_from_apps_payload(metadata_payload)
            if metadata_payload is not None
            else load_metadata_file(metadata_path)
            if metadata_path.exists()
            else {}
        )
        values = merge_metadata_override_values(
            dict(metadata_overrides.get(appid, {})),
            metadata_values_from_change_entries(
                changes,
                where=f"apps[{appid}].changes",
            ),
        )
        if not values:
            details = self._details_by_appid.get(appid)
            raw_metadata = details.get("_raw_metadata") if details is not None else None
            return raw_metadata if isinstance(raw_metadata, dict) else True

        if not self._confirm_appinfo_write_when_steam_running():
            return False

        write_modified_appinfo(
            path=self._appinfo_path,
            appids={appid},
            overrides=OverrideInput(),
            metadata_overrides={appid: values},
            write_out=None,
            create_backup=True,
            backup_once_per_day=True,
        )
        details = self._refresh_app_from_disk(appid)
        raw_metadata = details.get("_raw_metadata")
        return raw_metadata if isinstance(raw_metadata, dict) else True

    def _confirm_appinfo_write_when_steam_running(self) -> bool:
        if self._allow_appinfo_write_while_steam_running or not is_steam_running():
            return True

        accepted = confirm_warning(
            self,
            "Edit Metadata",
            "Steam is currently running and may overwrite changes.",
            informative_text=(
                "It is recommended to close Steam before making changes to "
                "appinfo.vdf.\n\nDo you want to write changes anyway?"
            ),
            accept_text="Write Anyway",
            reject_text="Cancel",
        )
        if accepted:
            self._allow_appinfo_write_while_steam_running = True

        return accepted

    def _open_edit_assets_dialog(self, initial_asset_key: str | None = None) -> None:
        appid = self._current_selected_appid()
        if appid is None:
            show_information(
                self,
                "Edit Assets",
                "Select an app to view its assets.",
            )
            return

        details = self._details_by_appid.get(appid)
        if details is None:
            show_information(
                self,
                "Edit Assets",
                "No asset information is available for the selected app.",
            )
            return

        dialog = EditAssetsDialog(
            {
                "header_path": str(details.get("header_path", "-")),
                "capsule_path": str(details.get("capsule_path", "-")),
                "hero_path": str(details.get("hero_path", "-")),
                "logo_path": str(details.get("logo_path", "-")),
                "icon_path": str(details.get("icon_path", "-")),
            },
            appid=details.get("appid") if details is not None else None,
            app_name=details.get("name") if details is not None else None,
            initial_asset_key=initial_asset_key,
            parent=self,
        )
        dialog.exec()

    def _load_apps_async(self, path: str) -> None:
        if self._load_thread is not None:
            return

        path_obj = Path(path).expanduser()
        if not path_obj.is_file():
            selected_path = select_missing_appinfo_file(self, path_obj)
            if selected_path is None:
                return

            self._load_apps_async(str(selected_path))
            return

        self._appinfo_path = None
        self._table.setRowCount(0)
        self._set_details(None)
        self._set_empty_search_visible(False)
        self._search_input.setEnabled(False)
        self._table.setEnabled(False)
        self._refresh_appinfo_required_widgets()
        if self._list_loading_overlay is not None:
            self._list_loading_overlay.start()

        thread = QThread(self)
        worker = AppLoadWorker(path)
        worker.moveToThread(thread)
        self._load_thread = thread
        self._load_worker = worker

        thread.started.connect(worker.run)
        worker.loaded.connect(self._apply_loaded_apps)
        worker.failed.connect(self._show_load_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._finish_async_load)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @Slot(object)
    def _apply_loaded_apps(self, payload: object) -> None:
        path_obj, rows, details_by_appid, filter_matches_by_appid = payload
        self._apply_loaded_app_rows(
            path_obj,
            rows,
            details_by_appid,
            filter_matches_by_appid,
        )

    @Slot(str)
    def _show_load_error(self, message: str) -> None:
        show_critical(self, "SteamMetadataTool", message)

    def _finish_async_load(self) -> None:
        has_loaded_appinfo = self._appinfo_path is not None
        self._search_input.setEnabled(has_loaded_appinfo)
        self._table.setEnabled(has_loaded_appinfo)
        if self._list_loading_overlay is not None:
            self._list_loading_overlay.stop()
        self._load_thread = None
        self._load_worker = None
        self._refresh_appinfo_required_widgets()

    def _load_apps(self, path: str) -> None:
        path_obj = Path(path).expanduser()
        if not path_obj.is_file():
            selected_path = select_missing_appinfo_file(self, path_obj)
            if selected_path is None:
                return

            self._load_apps(str(selected_path))
            return

        self._appinfo_path = None
        self._table.setRowCount(0)
        self._set_details(None)
        self._set_empty_search_visible(False)
        self._refresh_appinfo_required_widgets()

        try:
            rows, details_by_appid, filter_matches_by_appid = read_app_rows(path_obj)
        except Exception as exc:
            show_critical(self, "SteamMetadataTool", str(exc))
            return

        self._apply_loaded_app_rows(
            path_obj,
            rows,
            details_by_appid,
            filter_matches_by_appid,
        )

    def _apply_loaded_app_rows(
        self,
        path_obj: Path,
        rows: list[tuple[int, str]],
        details_by_appid: dict[int, dict[str, Any]],
        filter_matches_by_appid: dict[int, bool],
    ) -> None:
        self._appinfo_path = path_obj
        self._details_by_appid = details_by_appid
        self._filter_matches_by_appid = filter_matches_by_appid

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        for row, (appid, name) in enumerate(rows):
            appid_item = QTableWidgetItem()
            appid_item.setData(Qt.ItemDataRole.DisplayRole, appid)
            appid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            name_item = QTableWidgetItem(name)
            self._table.setItem(row, 0, appid_item)
            self._table.setItem(row, 1, name_item)
        self._table.setSortingEnabled(True)
        self._table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._apply_table_filter(self._search_input.text())
        self._refresh_appinfo_required_widgets()

    def _refresh_appinfo_required_widgets(self) -> None:
        enabled = self._appinfo_path is not None and self._load_thread is None
        for widget in self._appinfo_required_widgets:
            widget.setEnabled(enabled)
        for label in self._appinfo_required_preview_labels:
            label.set_click_enabled(enabled)

    def _refresh_app_from_disk(self, appid: int) -> dict[str, Any]:
        if self._appinfo_path is None:
            raise ValueError("No appinfo.vdf path is loaded.")

        with AppInfoFile.open(self._appinfo_path) as appinfo:
            for app in appinfo.iter_apps(appids=[appid]):
                details = details_for_app(app)
                self._details_by_appid[appid] = details
                self._filter_matches_by_appid[appid] = matches_game_filter(app.data)
                self._update_table_row_for_app(appid, str(details.get("name", "–")))
                if self._current_selected_appid() == appid:
                    self._set_details(details)
                self._apply_table_filter(self._search_input.text())
                return details

        raise ValueError(f"Could not reload app {appid} from appinfo.vdf.")

    def _update_table_row_for_app(self, appid: int, name: str) -> None:
        for row in range(self._table.rowCount()):
            appid_item = self._table.item(row, 0)
            if appid_item is None:
                continue

            try:
                row_appid = int(appid_item.text())
            except ValueError:
                continue

            if row_appid != appid:
                continue

            name_item = self._table.item(row, 1)
            if name_item is None:
                name_item = QTableWidgetItem()
                self._table.setItem(row, 1, name_item)
            name_item.setText(name)
            return

    def _current_selected_appid(self) -> int | None:
        selected = self._table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        appid_item = self._table.item(row, 0)
        if appid_item is None:
            return None

        try:
            return int(appid_item.text())
        except ValueError:
            return None

    def _set_details(self, details: dict[str, Any] | None) -> None:
        self._setting_details = True
        self._set_capsule_preview((details or {}).get("capsule_path", "-"))
        try:
            for key, widget in self._detail_labels.items():
                fallback = "-" if key in self._asset_image_specs else "–"
                value = str((details or {}).get(key, fallback))
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                    widget.setCursorPosition(0)
                    widget.setEnabled(details is not None)
                elif isinstance(widget, QLabel):
                    widget.setText(value)
        finally:
            self._setting_details = False

        any_assets_visible = False
        for key in ("header_path", "hero_path"):
            asset_box = self._asset_boxes.get(key)
            path = str((details or {}).get(key, "-"))
            is_visible = path not in {"", "-"}
            if asset_box is not None:
                asset_box.setVisible(is_visible)
            any_assets_visible = any_assets_visible or is_visible

        for widget in (
            self._assets_heading,
            self._assets_separator,
            self._assets_widget,
        ):
            if widget is not None:
                widget.setVisible(any_assets_visible)

        for key, label in self._asset_image_labels.items():
            if key == "hero_path":
                self._set_hero_preview(label, details or {})
                continue
            self._set_asset_preview(label, (details or {}).get(key, "-"), key)

        self._sync_capsule_preview_size()

    def _set_capsule_preview(self, path: str) -> None:
        if path in {"", "-"}:
            self._capsule_preview.set_source_pixmap(None)
            return

        pixmap = self._cached_pixmap(path)
        if pixmap.isNull():
            self._capsule_preview.set_source_pixmap(None)
            return

        self._capsule_preview.set_source_pixmap(pixmap)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        detail_key = next(
            (key for key, editor in self._detail_editors.items() if watched is editor),
            None,
        )
        if detail_key is not None:
            if event.type() == QEvent.Type.FocusOut:
                self._cancel_inline_detail_edit(detail_key)
            elif (
                event.type() == QEvent.Type.KeyPress
                and hasattr(event, "key")
                and event.key() == Qt.Key.Key_Escape
            ):
                self._cancel_inline_detail_edit(detail_key)
                if isinstance(watched, QLineEdit):
                    watched.clearFocus()
                return True

        if self._handle_window_shortcut(watched, event):
            return True

        if watched is self._details_form_container and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        }:
            self._sync_capsule_preview_size()
        return super().eventFilter(watched, event)

    def _handle_window_shortcut(self, watched: QObject, event: QEvent) -> bool:
        if not self.isActiveWindow() or event.type() != QEvent.Type.KeyPress:
            return False
        if not hasattr(event, "key") or not hasattr(event, "modifiers"):
            return False

        key = event.key()
        modifiers = event.modifiers()
        control_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        meaningful_modifiers = modifiers & (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )

        if key == Qt.Key.Key_F and control_pressed:
            self._toggle_search_drawer()
            return True

        if key == Qt.Key.Key_Slash and not meaningful_modifiers:
            if isinstance(watched, QLineEdit):
                return False
            self._toggle_search_drawer()
            return True

        if key == Qt.Key.Key_Escape and self._search_input.text():
            self._search_input.clear()
            self._search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return True
        if key == Qt.Key.Key_Escape and self._is_search_drawer_visible():
            self._set_search_drawer_visible(False)
            self._table.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return True

        if key not in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            return False
        if meaningful_modifiers:
            return False
        focus_widget = QApplication.focusWidget()
        if (
            focus_widget is not self._table
            and focus_widget is not self._table.viewport()
        ):
            return False

        self._open_edit_metadata_dialog()
        return True

    def _focus_search(self) -> None:
        if not self._search_input.isEnabled():
            return

        self._set_search_drawer_visible(True)
        self._search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search_input.selectAll()

    def _toggle_search_drawer(self) -> None:
        if not self._search_input.isEnabled():
            return

        is_visible = self._is_search_drawer_visible()
        self._set_search_drawer_visible(not is_visible)
        if not is_visible:
            self._search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self._search_input.selectAll()
        else:
            self._table.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _is_search_drawer_visible(self) -> bool:
        return self._search_drawer is not None and self._search_drawer.isVisible()

    def _set_search_drawer_visible(self, visible: bool) -> None:
        if self._search_drawer is None:
            return

        self._search_drawer.setVisible(visible)

    def _sync_capsule_preview_size(self) -> None:
        if self._details_form_container is None:
            return

        target_height = self._details_form_container.height()
        if target_height <= 0:
            target_height = self._details_form_container.sizeHint().height()
        if target_height <= 0:
            return

        target_width = max(1, int(target_height * 2 / 3))
        self._capsule_preview.setFixedWidth(target_width)
        capsule_container = self._capsule_preview.parentWidget()
        if capsule_container is not None:
            capsule_container.setFixedWidth(target_width)

    def _set_asset_preview(self, label: QLabel, path: str, key: str) -> None:
        if isinstance(label, PreviewPixmapLabel):
            if path in {"", "-"}:
                label.set_source_pixmap(None)
                return

            pixmap = self._cached_pixmap(path)
            label.set_source_pixmap(pixmap if not pixmap.isNull() else None)
            return

        if path in {"", "-"}:
            preview_width, preview_height = self._asset_image_specs[key]
            label.setPixmap(
                self._missing_asset_pixmap(
                    preview_width,
                    preview_height,
                    question_mark_scale=0.62 if key == "icon_path" else 0.8,
                )
            )
            label.setText("")
            return

        pixmap = self._cached_pixmap(path)
        if pixmap.isNull():
            preview_width, preview_height = self._asset_image_specs[key]
            label.setPixmap(
                self._missing_asset_pixmap(
                    preview_width,
                    preview_height,
                    question_mark_scale=0.62 if key == "icon_path" else 0.8,
                )
            )
            label.setText("")
            return

        preview_width, preview_height = self._asset_image_specs[key]
        label.setText("")
        label.setPixmap(
            pixmap.scaled(
                preview_width,
                preview_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_hero_preview(self, label: QLabel, details: dict[str, Any]) -> None:
        if not isinstance(label, PreviewPixmapLabel):
            self._set_asset_preview(
                label, str(details.get("hero_path", "-")), "hero_path"
            )
            return

        hero_path = str(details.get("hero_path", "-"))
        if hero_path in {"", "-"}:
            label.set_source_pixmap(None)
            return

        hero_pixmap = self._cached_pixmap(hero_path)
        if hero_pixmap.isNull():
            label.set_source_pixmap(None)
            return

        logo_path = str(details.get("logo_path", "-"))
        logo_position = details.get("logo_position")
        if logo_path in {"", "-"} or not isinstance(logo_position, dict):
            label.set_source_pixmap(hero_pixmap)
            return

        logo_pixmap = self._cached_pixmap(logo_path)
        if logo_pixmap.isNull():
            label.set_source_pixmap(hero_pixmap)
            return

        cache_key = (hero_path, logo_path, repr(sorted(logo_position.items())))
        cached_composed = self._composited_hero_cache.get(cache_key)
        if cached_composed is not None:
            label.set_source_pixmap(cached_composed)
            return

        composed = self._compose_hero_with_logo(
            hero_pixmap,
            logo_pixmap,
            logo_position,
        )
        final_pixmap = composed or hero_pixmap
        self._composited_hero_cache[cache_key] = final_pixmap
        label.set_source_pixmap(final_pixmap)

    def _cached_pixmap(self, path: str) -> QPixmap:
        cached = self._pixmap_cache.get(path)
        if cached is not None:
            return cached

        pixmap = QPixmap(path)
        self._pixmap_cache[path] = pixmap
        return pixmap

    def _compose_hero_with_logo(
        self,
        hero_pixmap: QPixmap,
        logo_pixmap: QPixmap,
        logo_position: dict[str, Any],
    ) -> QPixmap | None:
        side_padding = 32
        top_padding = 16
        bottom_padding = 128
        width_pct = float_value(logo_position.get("width_pct"))
        height_pct = float_value(logo_position.get("height_pct"))
        if width_pct is None or height_pct is None:
            return None

        available_width = max(1, hero_pixmap.width() - (side_padding * 2))
        available_height = max(1, hero_pixmap.height() - top_padding - bottom_padding)
        target_box_width = max(
            1,
            round(available_width * max(0.0, min(width_pct, 100.0)) / 100.0),
        )
        target_box_height = max(
            1,
            round(available_height * max(0.0, min(height_pct, 100.0)) / 100.0),
        )
        width_scale = target_box_width / max(1, logo_pixmap.width())
        height_scale = target_box_height / max(1, logo_pixmap.height())
        scale = min(width_scale, height_scale, 1.0)
        scaled_logo = logo_pixmap.scaled(
            max(1, round(logo_pixmap.width() * scale)),
            max(1, round(logo_pixmap.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if scaled_logo.isNull():
            return None

        pinned_position = str(logo_position.get("pinned_position") or "BottomLeft")
        horizontal_anchor = "left"
        vertical_anchor = "top"
        if pinned_position.endswith("Right"):
            horizontal_anchor = "right"
        elif pinned_position.endswith("Center"):
            horizontal_anchor = "center"

        if pinned_position.startswith("Bottom"):
            vertical_anchor = "bottom"
        elif pinned_position.startswith("Center") or pinned_position.startswith(
            "Middle"
        ):
            vertical_anchor = "center"

        scaled_canvas_width = scaled_logo.width()
        scaled_canvas_height = scaled_logo.height()
        x = 0.0
        y = 0.0
        if horizontal_anchor == "right":
            x = hero_pixmap.width() - scaled_canvas_width - side_padding
        elif horizontal_anchor == "left":
            x = side_padding
        elif horizontal_anchor == "center":
            x = (hero_pixmap.width() - scaled_canvas_width) / 2.0

        if vertical_anchor == "bottom":
            y = hero_pixmap.height() - scaled_canvas_height - bottom_padding
        elif vertical_anchor == "top":
            y = top_padding
        elif vertical_anchor == "center":
            y = (hero_pixmap.height() - scaled_canvas_height) / 2.0

        x = max(0, min(round(x), hero_pixmap.width() - scaled_canvas_width))
        y = max(0, min(round(y), hero_pixmap.height() - scaled_canvas_height))

        composed = QPixmap(hero_pixmap)
        painter = QPainter(composed)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(x, y, scaled_logo)
        painter.end()
        return composed

    def _missing_asset_pixmap(
        self,
        width: int,
        height: int,
        *,
        question_mark_scale: float = 0.8,
    ) -> QPixmap:
        icon_size = min(width, height, 32)
        icon_color = self.palette().placeholderText().color()
        background_color = self.palette().alternateBase().color()
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background_color)
        painter.drawRoundedRect(
            pixmap.rect().adjusted(1, 1, -1, -1),
            4,
            4,
        )

        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(10, int(icon_size * question_mark_scale)))
        painter.setFont(font)
        painter.setPen(icon_color)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        return pixmap

    def _on_selection_changed(self) -> None:
        appid = self._current_selected_appid()
        if appid is None:
            self._set_details(None)
            return

        self._set_details(self._details_by_appid.get(appid))

    def _set_empty_search_visible(self, visible: bool) -> None:
        if self._empty_search_overlay is None:
            return

        self._empty_search_overlay.setVisible(visible)
        if visible:
            self._empty_search_overlay.raise_()

    def _apply_table_filter(self, text: str) -> None:
        self._search_text = normalized_search_text(text)

        first_visible_row: int | None = None
        current_row = self._table.currentRow()
        current_row_visible = False

        for row in range(self._table.rowCount()):
            appid_item = self._table.item(row, 0)
            name_item = self._table.item(row, 1)
            if appid_item is None or name_item is None:
                self._table.setRowHidden(row, True)
                continue

            appid_text = appid_item.text()
            name_text = name_item.text()
            matches_search = not self._search_text or (
                self._search_text in normalized_search_text(appid_text)
                or self._search_text in normalized_search_text(name_text)
            )
            matches_filter = True
            if self._filter_button.isChecked():
                try:
                    matches_filter = self._filter_matches_by_appid.get(
                        int(appid_text), False
                    )
                except ValueError:
                    matches_filter = False

            matches = matches_search and matches_filter
            self._table.setRowHidden(row, not matches)

            if matches and first_visible_row is None:
                first_visible_row = row
            if matches and row == current_row:
                current_row_visible = True

        show_empty_search = (
            self._appinfo_path is not None
            and self._table.rowCount() > 0
            and first_visible_row is None
            and bool(self._search_text)
        )
        self._set_empty_search_visible(show_empty_search)

        if current_row_visible:
            return

        self._table.clearSelection()
        if first_visible_row is None:
            self._set_details(None)
            return

        self._table.selectRow(first_visible_row)
        focus_item = self._table.item(first_visible_row, 1) or self._table.item(
            first_visible_row, 0
        )
        if focus_item is not None:
            self._table.setCurrentItem(focus_item)


def main() -> int:
    parser = argparse.ArgumentParser(prog="steammetadatatool-gui")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--apply-metadata",
        action="store_true",
        help=("Apply all changes from the app data metadata.json and exit"),
    )
    action_group.add_argument(
        "--optimize-assets",
        action="store_true",
        help=("Resize custom asset files to the minimum required dimensions"),
    )
    action_group.add_argument(
        "--import-positions",
        dest="import_positions",
        action="store_true",
        help="Import logo position files into the local app data assets folder",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to appinfo.vdf (defaults to auto-detected Steam install)",
    )
    args = parser.parse_args()

    if args.apply_metadata:
        try:
            apply_metadata_file_silently(args.path)
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    if args.optimize_assets:
        return run_asset_optimization_prompt()

    if args.import_positions:
        try:
            import_logo_position_files()
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        return 0

    initial_path = args.path
    if not initial_path:
        detected_path = find_steam_appinfo_path()
        if detected_path:
            initial_path = str(detected_path)

    app = QApplication([])
    app.setApplicationName("SteamMetadataTool")
    app.setApplicationDisplayName("SteamMetadataTool")
    app.setDesktopFileName("io.github.ikajdan.steammetadatatool")
    apply_theme(app)
    window = MainWindow()
    initial_path_obj = Path(initial_path).expanduser() if initial_path else None
    if initial_path_obj is not None and not initial_path_obj.is_file():
        selected_path = select_missing_appinfo_file(window, initial_path_obj)
        if selected_path is not None:
            initial_path = str(selected_path)
        else:
            window.close()
            return 0

    if not initial_path:
        selected_path = select_appinfo_file_after_detection_failed(window)
        if selected_path is not None:
            initial_path = str(selected_path)
        else:
            window.close()
            return 0

    window.show()
    if initial_path:
        QTimer.singleShot(0, lambda: window._load_apps_async(initial_path))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
