from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.core.appinfo import (
    AppInfoFile,
    find_steam_appinfo_path,
    steam_base_paths,
)
from steammetadatatool.core.keyvalues1 import kv_deep_get


def _steam_librarycache_roots() -> list[Path]:
    return [base / "appcache" / "librarycache" for base in steam_base_paths()]


def _librarycache_dir_for_app(appid: int) -> Path | None:
    for root in _steam_librarycache_roots():
        app_cache_dir = root / str(appid)
        if app_cache_dir.is_dir():
            return app_cache_dir
    return None


def _find_asset_file(base_dir: Path, *filenames: str) -> str:
    """Find an asset file in base_dir or its subdirectories.

    Checks each filename in order, first at the root, then in subdirectories.
    Returns the path to the first file found, or "-" if none found.
    """
    for filename in filenames:
        root_path = base_dir / filename
        if root_path.is_file():
            return str(root_path)

        try:
            for subdir in base_dir.iterdir():
                if subdir.is_dir():
                    candidate = subdir / filename
                    if candidate.is_file():
                        return str(candidate)
        except (OSError, PermissionError):
            pass

    return "-"


def _cached_icon_path(appid: int) -> str:
    app_cache_dir = _librarycache_dir_for_app(appid)
    if app_cache_dir is None:
        return "-"

    candidates = sorted(
        p
        for p in app_cache_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".jpg"
        and len(p.stem) == 40
        and all(ch in "0123456789abcdef" for ch in p.stem)
    )
    if candidates:
        return str(candidates[0])

    try:
        for subdir in app_cache_dir.iterdir():
            if subdir.is_dir():
                candidates = sorted(
                    p
                    for p in subdir.iterdir()
                    if p.is_file()
                    and p.suffix.lower() == ".jpg"
                    and len(p.stem) == 40
                    and all(ch in "0123456789abcdef" for ch in p.stem)
                )
                if candidates:
                    return str(candidates[0])
    except (OSError, PermissionError):
        pass

    return "-"


def _asset_paths_for_app(appid: int) -> dict[str, str]:
    app_cache_dir = _librarycache_dir_for_app(appid)
    if app_cache_dir is None:
        return {
            "header_path": "-",
            "capsule_path": "-",
            "hero_path": "-",
            "logo_path": "-",
            "icon_path": "-",
        }

    return {
        "header_path": _find_asset_file(
            app_cache_dir, "header.jpg", "library_header.jpg", "header_2x.jpg"
        ),
        "capsule_path": _find_asset_file(
            app_cache_dir,
            "library_600x900.jpg",
            "library_600x900_2x.jpg",
            "library_capsule.jpg",
        ),
        "hero_path": _find_asset_file(
            app_cache_dir, "library_hero.jpg", "library_hero_2x.jpg"
        ),
        "logo_path": _find_asset_file(app_cache_dir, "logo.png", "logo_2x.png"),
        "icon_path": _cached_icon_path(appid),
    }


def _library_logo_position(data: dict[str, Any]) -> dict[str, Any] | None:
    position = kv_deep_get(
        data,
        "appinfo",
        "common",
        "library_assets_full",
        "library_logo",
        "logo_position",
    )
    if isinstance(position, dict):
        return position

    position = kv_deep_get(data, "appinfo", "common", "library_assets", "logo_position")
    if isinstance(position, dict):
        return position

    position = kv_deep_get(
        data, "common", "library_assets_full", "library_logo", "logo_position"
    )
    if isinstance(position, dict):
        return position

    position = kv_deep_get(data, "common", "library_assets", "logo_position")
    return position if isinstance(position, dict) else None


def _float_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None


def _monochrome_icon_pixmap(icon: QIcon, size: int, color: QColor) -> QPixmap:
    pixmap = icon.pixmap(size, size)
    if pixmap.isNull():
        return pixmap

    monochrome = QPixmap(pixmap.size())
    monochrome.fill(Qt.GlobalColor.transparent)

    painter = QPainter(monochrome)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(monochrome.rect(), color)
    painter.end()
    return monochrome


def _common_value(data: dict[str, Any], key: str) -> Any:
    value = kv_deep_get(data, "appinfo", "common", key)
    if value is not None:
        return value
    return kv_deep_get(data, "common", key)


def _extended_value(data: dict[str, Any], key: str) -> Any:
    value = kv_deep_get(data, "appinfo", "extended", key)
    if value is not None:
        return value
    return kv_deep_get(data, "extended", key)


def _aliases_value(data: dict[str, Any]) -> Any:
    value = _common_value(data, "aliases")
    if value is not None:
        return value

    value = _extended_value(data, "aliases")
    if value is not None:
        return value

    return None


def _sort_as_value(data: dict[str, Any]) -> Any:
    value = _common_value(data, "sortas")
    if value is not None:
        return value

    value = _extended_value(data, "sortas")
    if value is not None:
        return value

    return None


def _format_aliases(value: Any) -> str:
    if value is None:
        return "–"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "–"
    raw = str(value).strip()
    return raw or "–"


def _format_release_date(value: Any) -> str:
    if value is None:
        return "–"

    unix_value: int | None = None
    if isinstance(value, int):
        unix_value = value
    elif isinstance(value, str) and value.isdigit():
        unix_value = int(value)

    if unix_value is None:
        text = str(value).strip()
        return text or "–"

    if unix_value <= 0:
        return "–"

    try:
        return datetime.fromtimestamp(unix_value, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return str(unix_value)


class PreviewPixmapLabel(QLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        parent: QWidget | None = None,
        *,
        corner_radius: float = 0.0,
        show_placeholder_frame: bool = True,
    ) -> None:
        super().__init__(parent)
        self._source_pixmap: QPixmap | None = None
        self._placeholder_pixmap = placeholder
        self._corner_radius = corner_radius
        self._show_placeholder_frame = show_placeholder_frame
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(
            QFrame.Shape.StyledPanel
            if self._show_placeholder_frame
            else QFrame.Shape.NoFrame
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._refresh_pixmap()

    def set_placeholder_pixmap(self, pixmap: QPixmap) -> None:
        self._placeholder_pixmap = pixmap
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        pixmap = self._source_pixmap or self._placeholder_pixmap
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            return

        if self._source_pixmap is None:
            self.setFrameShape(
                QFrame.Shape.StyledPanel
                if self._show_placeholder_frame
                else QFrame.Shape.NoFrame
            )
            self.setPixmap(self._placeholder_display_pixmap())
            return

        self.setFrameShape(QFrame.Shape.NoFrame)
        scaled_pixmap = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self._corner_radius > 0:
            scaled_pixmap = self._rounded_pixmap(scaled_pixmap)
        self.setPixmap(scaled_pixmap)

    def _placeholder_display_pixmap(self) -> QPixmap:
        target_size = self.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return QPixmap()

        canvas = QPixmap(target_size)
        canvas.fill(self.palette().alternateBase().color())

        icon_size = min(target_size.width(), target_size.height(), 32)
        placeholder = self._placeholder_pixmap.scaled(
            icon_size,
            icon_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = (target_size.width() - placeholder.width()) // 2
        y = (target_size.height() - placeholder.height()) // 2
        painter.drawPixmap(x, y, placeholder)
        painter.end()
        return canvas

    def _rounded_pixmap(self, pixmap: QPixmap) -> QPixmap:
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0,
            0,
            float(pixmap.width()),
            float(pixmap.height()),
            self._corner_radius,
            self._corner_radius,
        )
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return rounded


class RatioPreviewPixmapLabel(PreviewPixmapLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        ratio_width: int,
        ratio_height: int,
        parent: QWidget | None = None,
        *,
        corner_radius: float = 0.0,
        show_placeholder_frame: bool = True,
    ) -> None:
        super().__init__(
            placeholder,
            parent,
            corner_radius=corner_radius,
            show_placeholder_frame=show_placeholder_frame,
        )
        self._ratio_width = ratio_width
        self._ratio_height = ratio_height

    def resizeEvent(self, event) -> None:
        target_height = max(
            1, int(self.width() * self._ratio_height / self._ratio_width)
        )
        if (
            self.minimumHeight() != target_height
            or self.maximumHeight() != target_height
        ):
            self.setMinimumHeight(target_height)
            self.setMaximumHeight(target_height)
        super().resizeEvent(event)


class LeftPaddingItemDelegate(QStyledItemDelegate):
    def __init__(self, left_padding: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._left_padding = left_padding

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        option.rect.adjust(self._left_padding, 0, 0, 0)


class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SteamMetadataTool")
        self.resize(1200, 560)
        self.setMinimumSize(980, 520)

        self._details_by_appid: dict[int, dict[str, Any]] = {}
        self._detail_labels: dict[str, QLabel] = {}
        self._asset_image_labels: dict[str, QLabel] = {}
        self._asset_boxes: dict[str, QWidget] = {}
        self._assets_heading: QLabel | None = None
        self._assets_separator: QFrame | None = None
        self._assets_widget: QWidget | None = None
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._composited_hero_cache: dict[tuple[str, str, str], QPixmap] = {}
        self._asset_image_specs: dict[str, tuple[int, int]] = {
            "header_path": (460, 215),
            "hero_path": (384, 124),
            "icon_path": (32, 32),
        }
        self._search_text = ""
        self._capsule_preview = RatioPreviewPixmapLabel(
            self._missing_asset_pixmap(32, 32),
            2,
            3,
            corner_radius=16,
        )

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by Name or App ID")
        search_icon = QIcon.fromTheme(
            "edit-find",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
        )
        search_icon_color = self.palette().placeholderText().color()
        self._search_input.addAction(
            QIcon(_monochrome_icon_pixmap(search_icon, 16, search_icon_color)),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_table_filter)

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

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_layout.addWidget(self._search_input)
        list_layout.addWidget(self._table)

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

        details_content_widget = QWidget()
        details_content_layout = QHBoxLayout(details_content_widget)
        details_content_layout.setContentsMargins(0, 0, 0, 0)
        details_content_layout.setSpacing(24)
        details_outer_layout.addWidget(details_content_widget)
        details_outer_layout.addSpacing(12)

        capsule_container = QWidget()
        capsule_layout = QVBoxLayout(capsule_container)
        capsule_layout.setContentsMargins(0, 0, 0, 0)
        capsule_layout.addWidget(self._capsule_preview)
        capsule_layout.setStretch(0, 1)
        self._capsule_preview.setMinimumWidth(220)
        details_content_layout.addWidget(capsule_container, 1)

        details_form_container = QWidget()
        details_content_layout.addWidget(details_form_container, 2)

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
            ("_separator_name_icon", ""),
            ("icon_path", "Icon"),
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

            if key in self._asset_image_specs:
                preview_width, preview_height = self._asset_image_specs[key]
                value_label = PreviewPixmapLabel(
                    self._missing_asset_pixmap(preview_width, preview_height),
                )
                value_label.setMinimumSize(preview_width, preview_height)
                value_label.setMaximumSize(preview_width, preview_height)
                self._asset_image_labels[key] = value_label
            else:
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
        assets_layout.setContentsMargins(0, 0, 0, 0)
        assets_layout.setSpacing(18)
        details_outer_layout.addWidget(assets_widget)

        def create_asset_box(
            key: str,
            title: str,
            size: tuple[int, int],
            ratio_width: int | None,
            ratio_height: int | None,
            corner_radius: float,
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
                )
                preview_label.setMinimumWidth(0)
            else:
                preview_label = PreviewPixmapLabel(
                    self._missing_asset_pixmap(preview_width, preview_height),
                    corner_radius=corner_radius,
                )
                preview_label.setMinimumSize(preview_width, preview_height)
                preview_label.setMaximumSize(preview_width, preview_height)
            self._asset_image_labels[key] = preview_label
            self._asset_boxes[key] = asset_box
            self._asset_image_specs[key] = size
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
            create_asset_box("hero_path", "Hero", (384, 124), 96, 31, 16)
        )

        assets_layout.addStretch(1)

        details_outer_layout.addStretch(1)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)
        layout.addWidget(list_widget, 5)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        details_scroll.setWidget(details_widget)

        layout.addWidget(details_scroll, 4)
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
            details_by_appid: dict[int, dict[str, Any]] = {}

            with AppInfoFile.open(path_obj) as appinfo:
                for app in appinfo.iter_apps():
                    name = (app.name or "").strip()
                    if not name:
                        continue

                    rows.append((app.appid, name))

                    asset_paths = _asset_paths_for_app(app.appid)

                    details_by_appid[app.appid] = {
                        "appid": str(app.appid),
                        "name": name or "–",
                        "sort_as": str(_sort_as_value(app.data) or "–"),
                        "aliases": _format_aliases(_aliases_value(app.data)),
                        "developer": str(_extended_value(app.data, "developer") or "–"),
                        "publisher": str(_extended_value(app.data, "publisher") or "–"),
                        "original_release_date": _format_release_date(
                            _common_value(app.data, "original_release_date")
                        ),
                        "steam_release_date": _format_release_date(
                            _common_value(app.data, "steam_release_date")
                        ),
                        "header_path": asset_paths["header_path"],
                        "capsule_path": asset_paths["capsule_path"],
                        "hero_path": asset_paths["hero_path"],
                        "logo_path": asset_paths["logo_path"],
                        "logo_position": _library_logo_position(app.data),
                        "icon_path": asset_paths["icon_path"],
                    }
        except Exception as exc:
            QMessageBox.critical(self, "SteamMetadataTool", str(exc))
            return

        self._details_by_appid = details_by_appid

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

    def _set_details(self, details: dict[str, Any] | None) -> None:
        self._set_capsule_preview((details or {}).get("capsule_path", "-"))
        for key, label in self._detail_labels.items():
            label.setText((details or {}).get(key, "-"))

        any_assets_visible = False
        for key in ("header_path", "hero_path"):
            asset_box = self._asset_boxes.get(key)
            path = str((details or {}).get(key, "-"))
            is_visible = path not in {"", "-"}
            if asset_box is not None:
                asset_box.setVisible(is_visible)
            any_assets_visible = any_assets_visible or is_visible

        for widget in (self._assets_heading, self._assets_separator, self._assets_widget):
            if widget is not None:
                widget.setVisible(any_assets_visible)

        for key, label in self._asset_image_labels.items():
            if key == "hero_path":
                self._set_hero_preview(label, details or {})
                continue
            self._set_asset_preview(label, (details or {}).get(key, "-"), key)

    def _set_capsule_preview(self, path: str) -> None:
        if path in {"", "-"}:
            self._capsule_preview.set_source_pixmap(None)
            return

        pixmap = self._cached_pixmap(path)
        if pixmap.isNull():
            self._capsule_preview.set_source_pixmap(None)
            return

        self._capsule_preview.set_source_pixmap(pixmap)

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
            label.setPixmap(self._missing_asset_pixmap(preview_width, preview_height))
            label.setText("")
            return

        pixmap = self._cached_pixmap(path)
        if pixmap.isNull():
            preview_width, preview_height = self._asset_image_specs[key]
            label.setPixmap(self._missing_asset_pixmap(preview_width, preview_height))
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
        width_pct = _float_value(logo_position.get("width_pct"))
        height_pct = _float_value(logo_position.get("height_pct"))
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

    def _missing_asset_pixmap(self, width: int, height: int) -> QPixmap:
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
        font.setPixelSize(max(12, int(icon_size * 0.8)))
        painter.setFont(font)
        painter.setPen(icon_color)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        return pixmap

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

    def _apply_table_filter(self, text: str) -> None:
        self._search_text = text.strip().casefold()

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
            matches = not self._search_text or (
                self._search_text in appid_text.casefold()
                or self._search_text in name_text.casefold()
            )
            self._table.setRowHidden(row, not matches)

            if matches and first_visible_row is None:
                first_visible_row = row
            if matches and row == current_row:
                current_row_visible = True

        if current_row_visible:
            return

        self._table.clearSelection()
        if first_visible_row is None:
            self._set_details(None)
            return

        self._table.selectRow(first_visible_row)


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
