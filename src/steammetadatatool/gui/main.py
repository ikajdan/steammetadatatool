# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    QVariantAnimation,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool import __version__
from steammetadatatool.core.appinfo import (
    AppInfoFile,
    find_steam_appinfo_path,
)
from steammetadatatool.core.keyvalues1 import kv_deep_get
from steammetadatatool.core.models import OverrideInput
from steammetadatatool.core.services import (
    load_metadata_file,
    metadata_values_from_change_entries,
    write_modified_appinfo,
)
from steammetadatatool.gui.app_data import app_data_path
from steammetadatatool.gui.app_theme import apply_theme
from steammetadatatool.gui.asset_optimizer import run_asset_optimization_prompt
from steammetadatatool.gui.edit_assets_dialog import EditAssetsDialog
from steammetadatatool.gui.edit_metadata_dialog import EditMetadataDialog
from steammetadatatool.gui.missing_appinfo_dialog import (
    select_appinfo_file_after_detection_failed,
    select_missing_appinfo_file,
)
from steammetadatatool.gui.steam_process import is_steam_running
from steammetadatatool.gui.steam_user import asset_paths_for_app


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


def _has_meaningful_metadata(
    value: Any,
    *,
    ignored_keys: frozenset[str] = frozenset({"appid", "name"}),
) -> bool:
    if value is None:
        return False

    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key in ignored_keys:
                continue
            if _has_meaningful_metadata(nested_value, ignored_keys=ignored_keys):
                return True
        return False

    if isinstance(value, (list, tuple, set)):
        return any(
            _has_meaningful_metadata(item, ignored_keys=ignored_keys) for item in value
        )

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _matches_game_filter(data: dict[str, Any]) -> bool:
    app_type = str(_common_value(data, "type") or "").strip().casefold()
    if app_type != "game":
        return False

    return _has_meaningful_metadata(data)


class PreviewPixmapLabel(QLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        parent: QWidget | None = None,
        *,
        corner_radius: float = 0.0,
        show_placeholder_frame: bool = True,
        show_inactive_border: bool = False,
        pixmap_alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ) -> None:
        super().__init__(parent)
        self._source_pixmap: QPixmap | None = None
        self._placeholder_pixmap = placeholder
        self._corner_radius = corner_radius
        self._show_placeholder_frame = show_placeholder_frame
        self._show_inactive_border = show_inactive_border
        self._hovered = False
        self._click_handler: Callable[[], None] | None = None
        self._click_enabled = True
        self._show_click_overlay = False
        self._overlay_icon = QIcon()
        self._overlay_opacity = 0.0
        self._overlay_animation = QVariantAnimation(self)
        self._overlay_animation.setDuration(250)
        self._overlay_animation.setStartValue(0.0)
        self._overlay_animation.setEndValue(1.0)
        self._overlay_animation.valueChanged.connect(self._on_overlay_opacity_changed)
        self.setAlignment(pixmap_alignment)
        self.setFrameShape(
            QFrame.Shape.StyledPanel
            if self._show_placeholder_frame
            else QFrame.Shape.NoFrame
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMouseTracking(True)

    def set_click_handler(
        self,
        handler: Callable[[], None] | None,
        overlay_icon: QIcon | None = None,
        *,
        show_overlay: bool = True,
    ) -> None:
        self._click_handler = handler
        self._show_click_overlay = handler is not None and show_overlay
        if overlay_icon is not None:
            self._overlay_icon = overlay_icon
        if not self._show_click_overlay or not self._click_enabled:
            self._overlay_animation.stop()
            self._overlay_opacity = 0.0
        self._refresh_cursor()
        self.update()

    def set_click_enabled(self, enabled: bool) -> None:
        self._click_enabled = enabled
        if not enabled:
            self._overlay_animation.stop()
            self._overlay_opacity = 0.0
        elif self._hovered:
            self._animate_overlay(visible=True)
        self._refresh_cursor()
        self.update()

    def _refresh_cursor(self) -> None:
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._click_handler is not None and self._click_enabled
            else Qt.CursorShape.ArrowCursor
        )

    def _on_overlay_opacity_changed(self, value) -> None:
        try:
            self._overlay_opacity = float(value)
        except (TypeError, ValueError):
            self._overlay_opacity = 0.0
        self.update()

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._refresh_pixmap()

    def set_placeholder_pixmap(self, pixmap: QPixmap) -> None:
        self._placeholder_pixmap = pixmap
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._animate_overlay(visible=True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._animate_overlay(visible=False)
        super().leaveEvent(event)

    def _animate_overlay(self, *, visible: bool) -> None:
        if not self._show_click_overlay or not self._click_enabled:
            self._overlay_opacity = 0.0
            self._overlay_animation.stop()
            self.update()
            return

        self._overlay_animation.stop()
        self._overlay_animation.setStartValue(self._overlay_opacity)
        self._overlay_animation.setEndValue(1.0 if visible else 0.0)
        self._overlay_animation.start()

    def mouseReleaseEvent(self, event) -> None:
        if (
            self._click_handler is not None
            and self._click_enabled
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self._click_handler()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_inactive_border()
        if (
            self._click_handler is None
            or not self._click_enabled
            or not self._show_click_overlay
            or self._overlay_opacity <= 0.0
        ):
            return

        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        pixmap_rect = pixmap.rect()
        pixmap_rect.moveTo(self._pixmap_top_left(pixmap))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        overlay_size = 30
        margin = 10
        overlay_rect = pixmap_rect.adjusted(
            pixmap_rect.width() - overlay_size - margin,
            margin,
            -margin,
            -(pixmap_rect.height() - overlay_size - margin),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setOpacity(self._overlay_opacity)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(overlay_rect, 10, 10)

        icon = self._overlay_icon.pixmap(16, 16)
        if not icon.isNull():
            x = overlay_rect.x() + (overlay_rect.width() - icon.width()) // 2
            y = overlay_rect.y() + (overlay_rect.height() - icon.height()) // 2
            painter.drawPixmap(x, y, icon)
        painter.end()

    def _paint_inactive_border(self) -> None:
        if not self._show_inactive_border:
            return

        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        pixmap_rect = QRectF(pixmap.rect())
        pixmap_rect.moveTo(self._pixmap_top_left(pixmap))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.palette().mid().color(), 1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border_rect = pixmap_rect.adjusted(0.5, 0.5, -0.5, -0.5)
        if self._corner_radius > 0:
            painter.drawRoundedRect(
                border_rect,
                self._corner_radius,
                self._corner_radius,
            )
        else:
            painter.drawRect(border_rect)
        painter.end()

    def _pixmap_top_left(self, pixmap: QPixmap) -> QPoint:
        alignment = self.alignment()
        if alignment & Qt.AlignmentFlag.AlignLeft:
            x = 0
        elif alignment & Qt.AlignmentFlag.AlignRight:
            x = self.width() - pixmap.width()
        else:
            x = (self.width() - pixmap.width()) // 2

        if alignment & Qt.AlignmentFlag.AlignTop:
            y = 0
        elif alignment & Qt.AlignmentFlag.AlignBottom:
            y = self.height() - pixmap.height()
        else:
            y = (self.height() - pixmap.height()) // 2

        return QPoint(x, y)

    def _refresh_pixmap(self) -> None:
        pixmap = self._source_pixmap or self._placeholder_pixmap
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            return

        if self._source_pixmap is None:
            self.setFrameShape(
                QFrame.Shape.StyledPanel
                if self._show_placeholder_frame and self._corner_radius <= 0
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
        if self._corner_radius > 0:
            return self._rounded_pixmap(canvas)
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
        show_inactive_border: bool = False,
        pixmap_alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ) -> None:
        super().__init__(
            placeholder,
            parent,
            corner_radius=corner_radius,
            show_placeholder_frame=show_placeholder_frame,
            show_inactive_border=show_inactive_border,
            pixmap_alignment=pixmap_alignment,
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


class LoadingSpinner(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(48, 48)

    def start(self) -> None:
        self._angle = 0
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)

        color = self.palette().midlight().color()
        pen = QPen(color, 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        radius = min(self.width(), self.height()) / 2 - 8
        for index in range(12):
            color.setAlpha(40 + index * 16)
            pen.setColor(color)
            painter.setPen(pen)
            painter.drawLine(0, int(-radius), 0, int(-radius + 8))
            painter.rotate(30)

        painter.end()

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()


class ListLoadingOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.addStretch(1)

        self._spinner = LoadingSpinner(self)
        layout.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignCenter)

        text = QLabel("Loading apps...", self)
        text.setAutoFillBackground(False)
        text.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        text.setStyleSheet("color: palette(midlight);")
        layout.addWidget(text, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def start(self) -> None:
        self.show()
        self.raise_()
        self._spinner.start()

    def stop(self) -> None:
        self._spinner.stop()
        self.hide()


def _details_for_app(app: Any) -> dict[str, Any]:
    name = (app.name or "").strip()
    asset_paths = asset_paths_for_app(app.appid)
    return {
        "_raw_metadata": app.data,
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


def _read_app_rows(
    path: Path,
) -> tuple[list[tuple[int, str]], dict[int, dict[str, Any]], dict[int, bool]]:
    rows: list[tuple[int, str]] = []
    details_by_appid: dict[int, dict[str, Any]] = {}
    filter_matches_by_appid: dict[int, bool] = {}

    with AppInfoFile.open(path) as appinfo:
        for app in appinfo.iter_apps():
            name = (app.name or "").strip()
            if not name:
                continue

            rows.append((app.appid, name))
            filter_matches_by_appid[app.appid] = _matches_game_filter(app.data)
            details_by_appid[app.appid] = _details_for_app(app)

    return rows, details_by_appid, filter_matches_by_appid


class AppLoadWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    @Slot()
    def run(self) -> None:
        try:
            path_obj = Path(self._path).expanduser()
            if not path_obj.is_file():
                raise FileNotFoundError(f"Path is not a file:\n{path_obj}")

            rows, details_by_appid, filter_matches_by_appid = _read_app_rows(path_obj)
            self.loaded.emit(
                (path_obj, rows, details_by_appid, filter_matches_by_appid)
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


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
        self._detail_labels: dict[str, QLabel] = {}
        self._asset_image_labels: dict[str, QLabel] = {}
        self._asset_boxes: dict[str, QWidget] = {}
        self._assets_heading: QLabel | None = None
        self._assets_separator: QFrame | None = None
        self._assets_widget: QWidget | None = None
        self._appinfo_required_widgets: list[QWidget] = []
        self._appinfo_required_preview_labels: list[PreviewPixmapLabel] = []
        self._filter_matches_by_appid: dict[int, bool] = {}
        self._list_loading_overlay: ListLoadingOverlay | None = None
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
            show_inactive_border=True,
        )
        self._edit_overlay_icon = QIcon(
            _monochrome_icon_pixmap(
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
            QIcon(_monochrome_icon_pixmap(search_icon, 16, search_icon_color)),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_table_filter)

        filter_icon = QIcon.fromTheme(
            "view-filter",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        )
        self._filter_button = QToolButton()
        button_size = self._search_input.sizeHint().height()
        filter_icon_color = self.palette().placeholderText().color()
        self._filter_button.setIcon(
            QIcon(_monochrome_icon_pixmap(filter_icon, 18, filter_icon_color))
        )
        self._filter_button.setToolTip("Show only games with metadata")
        self._filter_button.setAutoRaise(True)
        self._filter_button.setCheckable(True)
        self._filter_button.setFixedSize(button_size, button_size)
        self._filter_button.setIconSize(self._filter_button.size() * 0.55)
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
        list_layout.setSpacing(8)

        search_row = QWidget()
        search_row_layout = QHBoxLayout(search_row)
        search_row_layout.setContentsMargins(0, 0, 0, 0)
        search_row_layout.setSpacing(8)
        search_row_layout.addWidget(self._search_input, 1)
        search_row_layout.addWidget(self._filter_button, 0)

        table_stack = QWidget()
        table_stack_layout = QStackedLayout(table_stack)
        table_stack_layout.setContentsMargins(0, 0, 0, 0)
        table_stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        table_stack_layout.addWidget(self._table)

        list_loading_overlay = ListLoadingOverlay(table_stack)
        list_loading_overlay.hide()
        self._list_loading_overlay = list_loading_overlay
        table_stack_layout.addWidget(list_loading_overlay)

        list_layout.addWidget(table_stack)

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
        details_content_layout.setContentsMargins(0, 0, 0, 0)
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
        details_form_container.installEventFilter(self)
        details_content_layout.addWidget(
            details_form_container, 2, Qt.AlignmentFlag.AlignTop
        )

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
                value_label = QLabel("–")
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
        root_layout.setContentsMargins(10, 11, 10, 10)
        root_layout.setSpacing(11)
        root_layout.addWidget(search_row, 0)

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
        actions_layout.setContentsMargins(8, 0, 8, 8)
        actions_layout.setSpacing(12)

        metadata_icon = QIcon.fromTheme(
            "document-edit",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
        )
        metadata_button_icon = QIcon(
            _monochrome_icon_pixmap(
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
            _monochrome_icon_pixmap(assets_icon, 24, filter_icon_color, right_padding=0)
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
        self._set_details(None)
        self._refresh_appinfo_required_widgets()

    def _open_edit_metadata_dialog(self) -> None:
        appid = self._current_selected_appid()
        if appid is None:
            QMessageBox.information(
                self,
                "Edit Metadata",
                "Select an app to view its metadata.",
            )
            return

        details = self._details_by_appid.get(appid)
        raw_metadata = details.get("_raw_metadata") if details is not None else None
        if not isinstance(raw_metadata, dict):
            QMessageBox.information(
                self,
                "Edit Metadata",
                "No metadata is available for the selected app.",
            )
            return

        dialog = EditMetadataDialog(
            raw_metadata,
            appid=details.get("appid") if details is not None else None,
            app_name=details.get("name") if details is not None else None,
            on_save=lambda changes, selected_appid=appid: (
                self._apply_saved_metadata_changes(selected_appid, changes)
            ),
            parent=self,
        )
        dialog.exec()

    def _apply_saved_metadata_changes(
        self, appid: int, changes: list[dict[str, str]]
    ) -> bool:
        if self._appinfo_path is None:
            raise ValueError("No appinfo.vdf path is loaded.")

        metadata_path = app_data_path("metadata.json")
        metadata_overrides = load_metadata_file(metadata_path)
        values = dict(metadata_overrides.get(appid, {}))
        values.update(
            metadata_values_from_change_entries(
                changes,
                where=f"apps[{appid}].changes",
            )
        )
        if not values:
            return True

        if not self._confirm_appinfo_write_when_steam_running():
            return False

        write_modified_appinfo(
            path=self._appinfo_path,
            appids={appid},
            overrides=OverrideInput(),
            metadata_overrides={appid: values},
            write_out=None,
        )
        self._refresh_app_from_disk(appid)
        return True

    def _confirm_appinfo_write_when_steam_running(self) -> bool:
        if not is_steam_running():
            return True

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setText("Steam is currently running and may overwrite changes.")
        message_box.setInformativeText(
            "It is recommended to close Steam before making changes to appinfo.vdf.\n\n"
            "Do you want to write changes anyway?"
        )
        cancel_button = message_box.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole
        )
        write_anyway_button = message_box.addButton(
            "Write Anyway", QMessageBox.ButtonRole.AcceptRole
        )
        message_box.setDefaultButton(cancel_button)
        message_box.exec()

        return message_box.clickedButton() is write_anyway_button

    def _open_edit_assets_dialog(self, initial_asset_key: str | None = None) -> None:
        appid = self._current_selected_appid()
        if appid is None:
            QMessageBox.information(
                self,
                "Edit Assets",
                "Select an app to view its assets.",
            )
            return

        details = self._details_by_appid.get(appid)
        if details is None:
            QMessageBox.information(
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
        QMessageBox.critical(self, "SteamMetadataTool", message)

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
        self._refresh_appinfo_required_widgets()

        try:
            rows, details_by_appid, filter_matches_by_appid = _read_app_rows(path_obj)
        except Exception as exc:
            QMessageBox.critical(self, "SteamMetadataTool", str(exc))
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

    def _refresh_app_from_disk(self, appid: int) -> None:
        if self._appinfo_path is None:
            raise ValueError("No appinfo.vdf path is loaded.")

        with AppInfoFile.open(self._appinfo_path) as appinfo:
            for app in appinfo.iter_apps(appids=[appid]):
                details = _details_for_app(app)
                self._details_by_appid[appid] = details
                self._filter_matches_by_appid[appid] = _matches_game_filter(app.data)
                self._update_table_row_for_app(appid, str(details.get("name", "–")))
                if self._current_selected_appid() == appid:
                    self._set_details(details)
                self._apply_table_filter(self._search_input.text())
                return

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
        self._set_capsule_preview((details or {}).get("capsule_path", "-"))
        for key, label in self._detail_labels.items():
            fallback = "-" if key in self._asset_image_specs else "–"
            label.setText((details or {}).get(key, fallback))

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
        if watched is self._details_form_container and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        }:
            self._sync_capsule_preview_size()
        return super().eventFilter(watched, event)

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
            matches_search = not self._search_text or (
                self._search_text in appid_text.casefold()
                or self._search_text in name_text.casefold()
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
    parser.add_argument(
        "--optimize-assets",
        action="store_true",
        help=("Resize custom asset files to the minimum required dimensions"),
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to appinfo.vdf (defaults to auto-detected Steam install)",
    )
    args = parser.parse_args()

    if args.optimize_assets:
        return run_asset_optimization_prompt()

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
