# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QImageReader,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.gui.data.app_data import app_data_path
from steammetadatatool.gui.data.json_helpers import validate_json_file_version
from steammetadatatool.gui.dialogs.button_order import primary_action_first
from steammetadatatool.gui.dialogs.edit_metadata import ElidedLabel
from steammetadatatool.gui.dialogs.message_box import show_critical, show_warning
from steammetadatatool.gui.services.icons import monochrome_icon_pixmap
from steammetadatatool.gui.services.theme import COLORS
from steammetadatatool.gui.steam.assets import (
    STEAM_GRID_BASENAME_SUFFIXES as _STEAM_GRID_BASENAME_SUFFIXES,
)
from steammetadatatool.gui.steam.assets import (
    STEAM_GRID_EXTENSIONS as _STEAM_GRID_EXTENSIONS,
)
from steammetadatatool.gui.steam.assets import (
    cached_icon_path_for_app,
    default_icon_path_for_app,
    original_icon_path_for_cached_icon,
)
from steammetadatatool.gui.steam.paths import steam_grid_dir
from steammetadatatool.gui.widgets.toast import ToastMessage

_CUSTOM_ASSET_DIRS = {
    "capsule_path": "capsule",
    "header_path": "header",
    "hero_path": "hero",
    "logo_path": "logo",
    "icon_path": "icon",
}

_ASSETS_MANIFEST_VERSION = 1
_ASSET_NAV_BUTTON_SIZE = 44
_ASSET_NAV_SCROLLBAR_GAP = 8
_ASSET_VARIANT_SPACING = 14
_ASSET_INACTIVE_FRAME_WIDTH = 1.0
_ASSET_ACTIVE_FRAME_WIDTH = 2.0
_ASSET_VARIANT_FRAME_PADDING = int(_ASSET_ACTIVE_FRAME_WIDTH)
_ASSET_SNAP_VISIBLE_THRESHOLD = 0.60
_ASSET_PREVIEW_CORNER_RADIUS = 16.0
_ASSET_VARIANT_FRAME_RADIUS = _ASSET_PREVIEW_CORNER_RADIUS + (
    _ASSET_VARIANT_FRAME_PADDING
)
_ASSET_PREVIEW_MIN_WIDTHS = {
    "capsule_path": 150,
    "header_path": 260,
    "hero_path": 320,
    "logo_path": 180,
    "icon_path": 48,
}
_ASSET_PREVIEW_MAX_WIDTHS = {
    "capsule_path": 230,
    "header_path": 380,
    "hero_path": 720,
    "logo_path": 320,
    "icon_path": 64,
}
_CUSTOM_ASSET_IMAGE_FILTER = (
    "Images (*.png *.jpg *.jpeg);;"
    "PNG images (*.png);;"
    "JPEG images (*.jpg *.jpeg);;"
    "All files (*)"
)
_CUSTOM_ICON_ASSET_IMAGE_FILTER = (
    "Images (*.png *.jpg *.jpeg *.ico);;"
    "PNG images (*.png);;"
    "JPEG images (*.jpg *.jpeg);;"
    "Icon files (*.ico);;"
    "All files (*)"
)
_APPIMAGE_EXTERNAL_ENV_KEYS = (
    "APPDIR",
    "APPIMAGE",
    "ARGV0",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QML2_IMPORT_PATH",
)


def _load_pixmap(path: str | Path) -> QPixmap:
    path_text = str(path)
    pixmap = QPixmap(path_text)
    if not pixmap.isNull():
        return pixmap

    reader = QImageReader(path_text)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        return QPixmap()

    return QPixmap.fromImage(image)


def _assets_manifest_path() -> Path:
    return app_data_path("assets.json")


def _assets_dir() -> Path:
    return app_data_path("assets")


def _external_desktop_environment() -> dict[str, str]:
    env = os.environ.copy()
    original_ld_library_path = env.pop("ORIGINAL_LD_LIBRARY_PATH", None)
    if original_ld_library_path:
        env["LD_LIBRARY_PATH"] = original_ld_library_path
    else:
        env.pop("LD_LIBRARY_PATH", None)

    appdir = env.get("APPDIR")
    for key in _APPIMAGE_EXTERNAL_ENV_KEYS:
        env.pop(key, None)

    if appdir:
        xdg_data_dirs = env.get("XDG_DATA_DIRS")
        if xdg_data_dirs:
            filtered_xdg_data_dirs = ":".join(
                path
                for path in xdg_data_dirs.split(":")
                if path and not path.startswith(f"{appdir}/")
            )
            if filtered_xdg_data_dirs:
                env["XDG_DATA_DIRS"] = filtered_xdg_data_dirs
            else:
                env.pop("XDG_DATA_DIRS", None)

    return env


def _open_local_directory(path: Path) -> bool:
    if sys.platform.startswith("linux") and (
        os.environ.get("APPIMAGE") or os.environ.get("APPDIR")
    ):
        try:
            subprocess.Popen(
                ["xdg-open", str(path)],
                env=_external_desktop_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            pass
        else:
            return True

    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _custom_asset_key_name(asset_key: str) -> str:
    return _CUSTOM_ASSET_DIRS[asset_key]


def _load_assets_manifest() -> dict[str, object]:
    path = _assets_manifest_path()
    if not path.exists():
        return {"version": _ASSETS_MANIFEST_VERSION}

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": _ASSETS_MANIFEST_VERSION}

    version = data.get("version")
    if version is not None:
        validate_json_file_version(
            version,
            current_version=_ASSETS_MANIFEST_VERSION,
            file_description="assets manifest",
        )
    else:
        data["version"] = _ASSETS_MANIFEST_VERSION

    return data


def _selected_asset_names_for_app(appid: str | None) -> dict[str, str]:
    if not appid:
        return {}

    try:
        manifest = _load_assets_manifest()
    except (OSError, ValueError):
        return {}

    app_entry = manifest.get(str(appid))
    if not isinstance(app_entry, dict):
        return {}

    return {
        str(key): str(value)
        for key, value in app_entry.items()
        if isinstance(value, str) and value
    }


def _custom_asset_paths_for_app(appid: str | None) -> dict[str, list[str]]:
    custom_assets = {key: [] for key in _CUSTOM_ASSET_DIRS}
    if not appid:
        return custom_assets

    base_dir = _assets_dir() / appid
    if not base_dir.is_dir():
        return custom_assets

    for key, dirname in _CUSTOM_ASSET_DIRS.items():
        asset_dir = base_dir / dirname
        if not asset_dir.is_dir():
            continue

        supported_suffixes = {".png", ".jpg", ".jpeg"}
        if key == "icon_path":
            supported_suffixes.add(".ico")

        custom_assets[key] = [
            str(path)
            for path in sorted(asset_dir.iterdir())
            if path.is_file() and path.suffix.lower() in supported_suffixes
        ]

    return custom_assets


def _steam_grid_target(appid: str, asset_key: str, source: Path) -> Path:
    source_suffix = source.suffix.lower()
    if source_suffix not in _STEAM_GRID_EXTENSIONS:
        raise ValueError(f"Unsupported Steam grid asset extension: {source.suffix}")

    return (
        steam_grid_dir()
        / f"{appid}{_STEAM_GRID_BASENAME_SUFFIXES[asset_key]}{source_suffix}"
    )


def _cleanup_old_grid_asset_files(final_path: Path) -> None:
    base_path = final_path.with_suffix("")
    for suffix in _STEAM_GRID_EXTENSIONS:
        candidate = base_path.with_suffix(suffix)
        if candidate != final_path and (candidate.exists() or candidate.is_symlink()):
            candidate.unlink()


def _remove_grid_asset_files(grid_dir: Path, appid: str, asset_key: str) -> None:
    base_path = grid_dir / f"{appid}{_STEAM_GRID_BASENAME_SUFFIXES[asset_key]}"
    for suffix in _STEAM_GRID_EXTENSIONS:
        candidate = base_path.with_suffix(suffix)
        if candidate.exists() or candidate.is_symlink():
            candidate.unlink()


def _replace_with_file_copy(
    source: Path, target: Path, *, cleanup_grid_extensions: bool = False
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if cleanup_grid_extensions:
        _cleanup_old_grid_asset_files(target)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.write_bytes(source.read_bytes())


def _custom_asset_target(appid: str, asset_key: str, source: Path) -> Path:
    asset_dir = _assets_dir() / appid / _custom_asset_key_name(asset_key)
    suffix = source.suffix.lower()
    stem = source.stem.strip() or _custom_asset_key_name(asset_key)
    target = asset_dir / f"{stem}{suffix}"
    index = 2
    while target.exists():
        target = asset_dir / f"{stem}-{index}{suffix}"
        index += 1
    return target


def _apply_icon_asset(appid: str, source: Path) -> None:
    cached_icon_path = cached_icon_path_for_app(appid)
    if cached_icon_path is None:
        raise FileNotFoundError(f"No cached Steam icon was found for app {appid}.")

    backup_path = original_icon_path_for_cached_icon(cached_icon_path)
    if not backup_path.exists() and cached_icon_path.exists():
        backup_path.write_bytes(cached_icon_path.read_bytes())

    pixmap = _load_pixmap(source)
    if pixmap.isNull():
        raise ValueError(f"Could not load icon asset: {source}")

    resized = pixmap.scaled(
        32,
        32,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not resized.save(str(cached_icon_path), "JPG"):
        raise OSError(f"Could not write Steam icon cache file: {cached_icon_path}")


def _restore_icon_asset(appid: str) -> None:
    cached_icon_path = cached_icon_path_for_app(appid)
    if cached_icon_path is None:
        raise FileNotFoundError(f"No cached Steam icon was found for app {appid}.")

    original_icon_path = original_icon_path_for_cached_icon(cached_icon_path)
    if original_icon_path.is_file():
        original_icon_path.replace(cached_icon_path)


def _write_selected_assets_manifest(
    appid: str, selected_paths_by_key: dict[str, Path]
) -> None:
    manifest_path = _assets_manifest_path()
    manifest = _load_assets_manifest()
    manifest["version"] = _ASSETS_MANIFEST_VERSION

    app_entry = manifest.get(appid)
    if not isinstance(app_entry, dict):
        app_entry = {}

    for asset_key in _CUSTOM_ASSET_DIRS:
        app_entry.pop(_custom_asset_key_name(asset_key), None)
    app_entry.pop("preset", None)

    for asset_key, source_path in selected_paths_by_key.items():
        app_entry[_custom_asset_key_name(asset_key)] = source_path.name

    hero_path = selected_paths_by_key.get("hero_path")
    if hero_path is not None:
        preset_path = hero_path.parent.parent / "preset" / f"{hero_path.stem}.json"
        if preset_path.is_file():
            app_entry["preset"] = preset_path.name

    if app_entry:
        manifest[appid] = app_entry
    else:
        manifest.pop(appid, None)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _default_hero_preset_path(appid: str) -> Path:
    return _assets_dir() / appid / "preset" / "default.json"


class PreviewPixmapLabel(QLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        preferred_size: QSize,
        parent: QWidget | None = None,
        *,
        corner_radius: float = 10.0,
        round_letterboxed_source: bool = True,
        placeholder_background_color: QColor | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_pixmap: QPixmap | None = None
        self._placeholder_pixmap = placeholder
        self._preferred_size = preferred_size
        self._corner_radius = corner_radius
        self._round_letterboxed_source = round_letterboxed_source
        self._placeholder_background_color = placeholder_background_color
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._refresh_pixmap()

    def set_preferred_size(self, size: QSize) -> None:
        if self._preferred_size == size:
            return

        self._preferred_size = QSize(size)
        self.updateGeometry()
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def sizeHint(self) -> QSize:
        return QSize(self._preferred_size)

    def minimumSizeHint(self) -> QSize:
        return QSize(1, 1)

    def _refresh_pixmap(self) -> None:
        pixmap = self._source_pixmap or self._placeholder_pixmap
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            return

        if self._source_pixmap is None:
            self.setFrameShape(
                QFrame.Shape.StyledPanel
                if self._corner_radius <= 0
                else QFrame.Shape.NoFrame
            )
            self.setPixmap(self._placeholder_display_pixmap())
            return

        self.setFrameShape(QFrame.Shape.NoFrame)
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self._round_letterboxed_source or scaled.size() == self.size():
            self.setPixmap(self._rounded_pixmap(scaled))
        else:
            self.setPixmap(self._clipped_canvas_pixmap(scaled))

    def _placeholder_display_pixmap(self) -> QPixmap:
        target_size = self.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return QPixmap()

        canvas = QPixmap(target_size)
        canvas.fill(
            self._placeholder_background_color or self.palette().alternateBase().color()
        )

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
        return self._rounded_pixmap(canvas)

    def _rounded_pixmap(self, pixmap: QPixmap) -> QPixmap:
        if self._corner_radius <= 0:
            return pixmap

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

    def _clipped_canvas_pixmap(self, pixmap: QPixmap) -> QPixmap:
        target_size = self.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return QPixmap()

        canvas = QPixmap(target_size)
        canvas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._corner_radius > 0:
            path = QPainterPath()
            path.addRoundedRect(
                0,
                0,
                float(target_size.width()),
                float(target_size.height()),
                self._corner_radius,
                self._corner_radius,
            )
            painter.setClipPath(path)

        x = (target_size.width() - pixmap.width()) // 2
        y = (target_size.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)
        painter.end()
        return canvas


class RatioPreviewPixmapLabel(PreviewPixmapLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        preferred_size: QSize,
        ratio_width: int,
        ratio_height: int,
        parent: QWidget | None = None,
        *,
        corner_radius: float = 16.0,
        round_letterboxed_source: bool = True,
        placeholder_background_color: QColor | None = None,
    ) -> None:
        super().__init__(
            placeholder,
            preferred_size,
            parent,
            corner_radius=corner_radius,
            round_letterboxed_source=round_letterboxed_source,
            placeholder_background_color=placeholder_background_color,
        )
        self._ratio_width = ratio_width
        self._ratio_height = ratio_height
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return max(1, int(width * self._ratio_height / self._ratio_width))

    def sizeHint(self) -> QSize:
        width = self._preferred_size.width()
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return QSize(1, self.heightForWidth(1))

    def resizeEvent(self, event) -> None:
        target_height = self.heightForWidth(max(1, self.width()))
        if (
            self.minimumHeight() != target_height
            or self.maximumHeight() != target_height
        ):
            self.setMinimumHeight(target_height)
            self.setMaximumHeight(target_height)
        super().resizeEvent(event)


class AssetVariantFrame(QFrame):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        path: str,
        is_custom: bool,
        on_select: Callable[[], None] | None = None,
        show_selection_frame: bool = True,
        is_selectable: bool = True,
        participates_in_selection: bool = True,
        is_add_placeholder: bool = False,
    ) -> None:
        super().__init__(parent)
        self.asset_path = path
        self.is_custom = is_custom
        self.participates_in_selection = participates_in_selection
        self.is_add_placeholder = is_add_placeholder
        self._on_select = on_select
        self._is_selected = False
        self._show_selection_frame = show_selection_frame
        self._show_active_frame = True
        self._is_selectable = is_selectable
        self._is_pressed = False
        self.setObjectName("assetVariantFrame")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if is_selectable
            else Qt.CursorShape.ArrowCursor
        )

    def set_selected(self, selected: bool, *, show_active_frame: bool = True) -> None:
        self._is_selected = selected
        self._show_active_frame = show_active_frame
        if not self._show_selection_frame:
            self.setToolTip("")
            self.update()
            return

        self.setToolTip("Selected asset" if selected and show_active_frame else "")
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._show_selection_frame:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = _ASSET_VARIANT_FRAME_PADDING - (_ASSET_INACTIVE_FRAME_WIDTH / 2)
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        if self.is_add_placeholder:
            background_color = QColor(
                COLORS["border"] if self.underMouse() else COLORS["button"]
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background_color)
            painter.drawRoundedRect(
                rect,
                _ASSET_VARIANT_FRAME_RADIUS,
                _ASSET_VARIANT_FRAME_RADIUS,
            )

        if self.is_add_placeholder:
            if self._is_selected and self._show_active_frame:
                pen = QPen(
                    self.palette().highlight().color(), _ASSET_ACTIVE_FRAME_WIDTH
                )
            elif self._is_pressed:
                pen = QPen(QColor(COLORS["highlight"]), _ASSET_INACTIVE_FRAME_WIDTH)
            elif self.underMouse():
                pen = QPen(QColor(COLORS["accent"]), _ASSET_INACTIVE_FRAME_WIDTH)
            else:
                pen = QPen(QColor(COLORS["border_light"]), _ASSET_INACTIVE_FRAME_WIDTH)
        elif self._is_selected and self._show_active_frame:
            pen = QPen(self.palette().highlight().color(), _ASSET_ACTIVE_FRAME_WIDTH)
        else:
            pen = QPen(self.palette().mid().color(), _ASSET_INACTIVE_FRAME_WIDTH)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = _ASSET_VARIANT_FRAME_PADDING - (pen.widthF() / 2)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(inset, inset, -inset, -inset),
            _ASSET_VARIANT_FRAME_RADIUS,
            _ASSET_VARIANT_FRAME_RADIUS,
        )
        painter.end()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if self.is_add_placeholder:
            self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._is_pressed = False
        if self.is_add_placeholder:
            self.update()

    def mousePressEvent(self, event) -> None:
        if (
            self.is_add_placeholder
            and self._is_selectable
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self._is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        was_pressed = self._is_pressed
        self._is_pressed = False
        if (
            self._on_select is not None
            and self._is_selectable
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
            and (was_pressed or not self.is_add_placeholder)
        ):
            self._on_select()
            self.update()
            event.accept()
            return
        if self.is_add_placeholder:
            self.update()
        super().mouseReleaseEvent(event)


class AssetNavButton(QToolButton):
    def __init__(self, arrow_type: Qt.ArrowType, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setArrowType(arrow_type)
        self.setAutoRaise(False)
        self.setFixedSize(_ASSET_NAV_BUTTON_SIZE, _ASSET_NAV_BUTTON_SIZE)
        self.setIconSize(QSize(22, 22))

    def paintEvent(self, event) -> None:
        if self.property("assetNavHidden"):
            return

        palette = self.palette()
        if not self.isEnabled():
            background_color = QColor(COLORS["background_alt"])
            border_color = QColor(COLORS["button"])
            arrow_color = palette.mid().color().lighter(145)
        elif self.isDown():
            background_color = QColor(COLORS["button_pressed"])
            border_color = QColor(COLORS["highlight"])
            arrow_color = palette.buttonText().color()
        elif self.underMouse():
            background_color = QColor(COLORS["border"])
            border_color = QColor(COLORS["accent"])
            arrow_color = palette.buttonText().color()
        else:
            background_color = QColor(COLORS["button"])
            border_color = QColor(COLORS["border_light"])
            arrow_color = palette.buttonText().color()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border_color, 2.0))
        painter.setBrush(background_color)
        painter.drawEllipse(self.rect().adjusted(2, 2, -3, -3))

        if self.arrowType() == Qt.ArrowType.LeftArrow:
            arrow_text = "←"
        elif self.arrowType() == Qt.ArrowType.RightArrow:
            arrow_text = "→"
        else:
            painter.end()
            return

        font = QFont(painter.font())
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(arrow_color)
        painter.drawText(
            self.rect().adjusted(0, -2, 0, -2),
            Qt.AlignmentFlag.AlignCenter,
            arrow_text,
        )
        painter.end()


class EditAssetsDialog(QDialog):
    def __init__(
        self,
        assets: dict[str, str],
        *,
        appid: str | None = None,
        app_name: str | None = None,
        initial_asset_key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SteamMetadataTool")
        self.setModal(True)
        self.resize(1080, 760)
        self.setMinimumSize(720, 520)
        self._scroll_area: QScrollArea | None = None
        self._asset_cards: dict[str, QWidget] = {}
        self._asset_variants: dict[str, list[AssetVariantFrame]] = {}
        self._asset_variant_row_layouts: dict[str, QHBoxLayout] = {}
        self._asset_variant_scroll_areas: dict[str, QScrollArea] = {}
        self._asset_variant_control_rows: dict[str, QWidget] = {}
        self._asset_variant_buttons: dict[str, tuple[QToolButton, QToolButton]] = {}
        self._asset_variant_preview_labels: dict[str, list[PreviewPixmapLabel]] = {}
        self._asset_variant_sizes: dict[str, tuple[int, int]] = {}
        self._asset_variant_ratios: dict[str, tuple[int, int] | None] = {}
        self._asset_variant_counts: dict[str, int] = {}
        self._asset_scroll_animations: dict[str, QPropertyAnimation] = {}
        self._asset_unapplied_labels: dict[str, QLabel] = {}
        self._unapplied_count_label: QLabel | None = None
        self._toast = ToastMessage(self, bottom_margin=80)
        self._initial_asset_key = initial_asset_key
        self._did_initial_asset_scroll = False
        self._initial_asset_scroll_attempts = 0
        self._appid = str(appid) if appid is not None else None
        if self._appid is not None:
            default_icon_path = default_icon_path_for_app(self._appid)
            if default_icon_path is not None:
                assets = dict(assets)
                assets["icon_path"] = str(default_icon_path)
        self._custom_assets_by_key = _custom_asset_paths_for_app(appid)
        self._selected_custom_paths_by_key: dict[str, Path] = {}
        self._default_selected_asset_keys: set[str] = set()
        saved_asset_names = _selected_asset_names_for_app(self._appid)
        for key, paths in self._custom_assets_by_key.items():
            saved_name = saved_asset_names.get(_custom_asset_key_name(key))
            if saved_name is None:
                continue

            matching_path = next(
                (Path(path) for path in paths if Path(path).name == saved_name),
                None,
            )
            if matching_path is not None:
                self._selected_custom_paths_by_key[key] = matching_path
        self._initial_selected_custom_paths_by_key = dict(
            self._selected_custom_paths_by_key
        )

        action_icon_color = self.palette().placeholderText().color()

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
        self._app_name_label.setMinimumWidth(0)
        self._app_name_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        header_row_layout.addWidget(self._app_name_label)

        unapplied_count_label = QLabel(header_row)
        self._unapplied_count_label = unapplied_count_label
        unapplied_count_label.setStyleSheet(
            "font-size: 13px;"
            " font-weight: 600;"
            " padding: 3px 8px;"
            " border-radius: 10px;"
            f" color: {self.palette().highlightedText().color().name()};"
            f" background: {self.palette().highlight().color().name()};"
        )
        unapplied_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unapplied_count_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        unapplied_count_label.setVisible(False)
        header_row_layout.addWidget(unapplied_count_label)
        header_row_layout.addStretch(1)

        folder_icon = QIcon.fromTheme(
            "folder-open",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
        )
        open_folder_button = QPushButton(
            QIcon(monochrome_icon_pixmap(folder_icon, 18, action_icon_color, 6)),
            "Open Assets Folder",
            header_row,
        )
        open_folder_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        open_folder_button.setMinimumHeight(40)
        open_folder_button.setMinimumWidth(210)
        open_folder_button.setMaximumWidth(360)
        open_folder_button.setIconSize(QSize(24, 18))
        open_folder_button.clicked.connect(self._open_asset_folder)
        header_row_layout.addWidget(open_folder_button, 0, Qt.AlignmentFlag.AlignRight)
        dialog_layout.addWidget(header_row)

        heading_separator = QFrame(self)
        heading_separator.setFrameShape(QFrame.Shape.HLine)
        heading_separator.setFrameShadow(QFrame.Shadow.Sunken)
        dialog_layout.addWidget(heading_separator)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area = scroll
        dialog_layout.addWidget(scroll, 1)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        scroll.setWidget(content)

        assets_container = QWidget(content)
        assets_layout = QVBoxLayout(assets_container)
        assets_layout.setContentsMargins(0, 0, 0, 0)
        assets_layout.setSpacing(18)
        content_layout.addWidget(assets_container)
        content_layout.addStretch(1)

        asset_specs: list[tuple[str, str, tuple[int, int], tuple[int, int] | None]] = [
            ("capsule_path", "Capsule", (230, 345), (2, 3)),
            ("header_path", "Header", (380, 178), (460, 215)),
            ("hero_path", "Hero", (720, 232), (96, 31)),
            ("logo_path", "Logo", (320, 100), None),
            ("icon_path", "Icon", (48, 48), None),
        ]

        for key, title, size, ratio in asset_specs:
            card = self._create_asset_card(
                key=key,
                title=title,
                original_path=assets.get(key, "-"),
                custom_paths=self._custom_assets_by_key.get(key, []),
                size=size,
                ratio=ratio,
            )
            self._asset_cards[key] = card
            assets_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
            if key != asset_specs[-1][0]:
                separator = QFrame(assets_container)
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                assets_layout.addWidget(separator)

        dialog_actions = QWidget(self)
        dialog_actions_layout = QHBoxLayout(dialog_actions)
        dialog_actions_layout.setContentsMargins(0, 0, 0, 0)
        dialog_actions_layout.setSpacing(12)

        dialog_actions_layout.addStretch(1)

        apply_icon = QIcon.fromTheme(
            "dialog-ok-apply",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
        )
        self._apply_button = QPushButton(
            QIcon(monochrome_icon_pixmap(apply_icon, 24, action_icon_color)),
            "Apply",
            dialog_actions,
        )
        self._apply_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._apply_button.setFixedSize(QSize(160, 40))
        self._apply_button.setIconSize(QSize(24, 24))
        self._apply_button.clicked.connect(self._apply_selected_assets)

        cancel_icon = QIcon.fromTheme(
            "dialog-cancel",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton),
        )
        cancel_button = QPushButton(
            QIcon(monochrome_icon_pixmap(cancel_icon, 24, action_icon_color)),
            "Cancel",
            dialog_actions,
        )
        cancel_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        cancel_button.setFixedSize(QSize(160, 40))
        cancel_button.setIconSize(QSize(24, 24))
        cancel_button.clicked.connect(self.reject)

        action_buttons = (
            (self._apply_button, cancel_button)
            if primary_action_first()
            else (cancel_button, self._apply_button)
        )
        for button in action_buttons:
            dialog_actions_layout.addWidget(button)

        dialog_actions_layout.setStretch(0, 3)
        dialog_actions_layout.setStretch(1, 1)
        dialog_actions_layout.setStretch(2, 1)
        dialog_layout.addWidget(dialog_actions)
        self._refresh_unapplied_state()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_header_layout()
        QTimer.singleShot(0, self._refresh_asset_variant_rows)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_header_layout()
        QTimer.singleShot(0, self._refresh_asset_variant_rows)
        if self._initial_asset_key is not None and not self._did_initial_asset_scroll:
            self._initial_asset_scroll_attempts = 0
            self._queue_initial_asset_scroll()

    def _apply_header_layout(self) -> None:
        header_width = self._header_row_layout.parentWidget().width()
        if header_width <= 0:
            return

        title_width = max(0, int(header_width / 2) - 16)
        self._app_name_label.setFixedWidth(
            min(title_width, self._app_name_label.natural_text_width())
        )

    def _queue_initial_asset_scroll(self) -> None:
        delay_ms = 0 if self._initial_asset_scroll_attempts == 0 else 50
        QTimer.singleShot(delay_ms, self._scroll_to_initial_asset)

    def _scroll_to_initial_asset(self) -> None:
        if self._initial_asset_key is None or self._did_initial_asset_scroll:
            return

        did_scroll = self._scroll_to_asset(self._initial_asset_key)
        if did_scroll:
            self._did_initial_asset_scroll = True
            return

        self._initial_asset_scroll_attempts += 1
        if self._initial_asset_scroll_attempts < 10:
            self._queue_initial_asset_scroll()

    def _scroll_to_asset(self, key: str) -> bool:
        if self._scroll_area is None:
            return False

        card = self._asset_cards.get(key)
        if card is None:
            return False

        content = self._scroll_area.widget()
        if content is None:
            return False

        layout = content.layout()
        if layout is not None:
            layout.activate()
        content.updateGeometry()
        content.adjustSize()

        scroll_bar = self._scroll_area.verticalScrollBar()
        target_y = card.mapTo(content, QPoint(0, 0)).y()
        top_margin = 8
        target_value = max(0, min(target_y - top_margin, scroll_bar.maximum()))
        scroll_bar.setValue(target_value)
        return scroll_bar.maximum() > 0 and scroll_bar.value() == target_value

    def _create_asset_card(
        self,
        *,
        key: str,
        title: str,
        original_path: str,
        custom_paths: list[str],
        size: tuple[int, int],
        ratio: tuple[int, int] | None,
    ) -> QWidget:
        card = QFrame(self)
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 10, 0, 14)
        layout.setSpacing(10)

        title_row = QWidget(card)
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(12)

        title_label = QLabel(title, title_row)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        title_row_layout.addWidget(title_label)

        unapplied_label = QLabel("Unapplied", title_row)
        unapplied_label.setStyleSheet(
            "font-size: 12px;"
            " font-weight: 600;"
            " padding: 2px 7px;"
            " border-radius: 9px;"
            f" color: {self.palette().highlightedText().color().name()};"
            f" background: {self.palette().highlight().color().name()};"
        )
        unapplied_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unapplied_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        unapplied_label.setVisible(False)
        self._asset_unapplied_labels[key] = unapplied_label
        title_row_layout.addWidget(unapplied_label)
        title_row_layout.addStretch(1)
        layout.addWidget(title_row)
        layout.addSpacing(28)
        show_selection_frame = True
        draw_variant_frame = True
        self._asset_variant_counts[key] = 1 + len(custom_paths)

        controls_row = QWidget(card)
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, _ASSET_NAV_SCROLLBAR_GAP, 0)
        controls_layout.setSpacing(10)

        left_button = AssetNavButton(Qt.ArrowType.LeftArrow, controls_row)
        left_button.setToolTip("Show previous assets")
        left_button.clicked.connect(lambda: self._scroll_asset_variants(key, -1))
        controls_layout.addWidget(left_button, 0, Qt.AlignmentFlag.AlignVCenter)

        variants_scroll = QScrollArea(card)
        variants_scroll.setWidgetResizable(False)
        variants_scroll.setFrameShape(QFrame.Shape.NoFrame)
        variants_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        variants_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        variants_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        controls_layout.addWidget(variants_scroll, 1)

        right_button = AssetNavButton(Qt.ArrowType.RightArrow, controls_row)
        right_button.setToolTip("Show next assets")
        right_button.clicked.connect(lambda: self._scroll_asset_variants(key, 1))
        controls_layout.addWidget(right_button, 0, Qt.AlignmentFlag.AlignVCenter)

        variants_row = QWidget(variants_scroll)
        variants_layout = QHBoxLayout(variants_row)
        variants_layout.setContentsMargins(0, 0, 0, 0)
        variants_layout.setSpacing(_ASSET_VARIANT_SPACING)
        variants_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        variants_row.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._asset_variants[key] = []
        self._asset_variant_preview_labels[key] = []
        self._asset_variant_row_layouts[key] = variants_layout
        self._asset_variant_sizes[key] = size
        self._asset_variant_ratios[key] = ratio
        self._asset_variant_scroll_areas[key] = variants_scroll
        self._asset_variant_control_rows[key] = controls_row
        self._asset_variant_buttons[key] = (left_button, right_button)
        variants_scroll.horizontalScrollBar().valueChanged.connect(
            lambda _value, asset_key=key: self._update_asset_variant_buttons(asset_key)
        )
        variants_scroll.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum, asset_key=key: (
                self._update_asset_variant_buttons(asset_key)
            )
        )

        variants_layout.addWidget(
            self._create_asset_variant(
                asset_key=key,
                path=original_path,
                size=size,
                ratio=ratio,
                is_current=key not in self._selected_custom_paths_by_key,
                is_custom=False,
                show_selection_frame=draw_variant_frame,
                is_selectable=show_selection_frame,
                parent=variants_row,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        for custom_path in custom_paths:
            variants_layout.addWidget(
                self._create_asset_variant(
                    asset_key=key,
                    path=custom_path,
                    size=size,
                    ratio=ratio,
                    is_current=(
                        self._selected_custom_paths_by_key.get(key) == Path(custom_path)
                    ),
                    is_custom=True,
                    show_selection_frame=draw_variant_frame,
                    is_selectable=show_selection_frame,
                    parent=variants_row,
                ),
                0,
                Qt.AlignmentFlag.AlignTop,
            )

        variants_layout.addWidget(
            self._create_add_asset_variant(
                asset_key=key,
                size=size,
                ratio=ratio,
                parent=variants_row,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        variants_scroll.setWidget(variants_row)
        layout.addWidget(controls_row)
        QTimer.singleShot(
            0, lambda asset_key=key: self._finalize_asset_variant_row(asset_key)
        )
        return card

    def _create_asset_variant(
        self,
        *,
        asset_key: str,
        path: str,
        size: tuple[int, int],
        ratio: tuple[int, int] | None,
        is_current: bool,
        is_custom: bool,
        show_selection_frame: bool,
        is_selectable: bool,
        parent: QWidget,
        on_select: Callable[[], None] | None = None,
        placeholder_pixmap: QPixmap | None = None,
        placeholder_background_color: QColor | None = None,
        participates_in_selection: bool = True,
        is_add_placeholder: bool = False,
    ) -> QWidget:
        preview_width, preview_height = size
        variant = AssetVariantFrame(
            parent,
            path=path,
            is_custom=is_custom,
            on_select=on_select
            if on_select is not None
            else lambda: self._select_asset_variant(asset_key, variant),
            show_selection_frame=show_selection_frame,
            is_selectable=is_selectable,
            participates_in_selection=participates_in_selection,
            is_add_placeholder=is_add_placeholder,
        )
        variant_layout = QVBoxLayout(variant)
        variant_layout.setContentsMargins(
            _ASSET_VARIANT_FRAME_PADDING,
            _ASSET_VARIANT_FRAME_PADDING,
            _ASSET_VARIANT_FRAME_PADDING,
            _ASSET_VARIANT_FRAME_PADDING,
        )
        variant_layout.setSpacing(0)

        preview = self._create_preview_label(
            asset_key,
            size,
            ratio,
            placeholder_pixmap=placeholder_pixmap,
            placeholder_background_color=placeholder_background_color,
        )
        if ratio is None:
            preview.setMinimumSize(preview_width, preview_height)
            preview.setMaximumHeight(preview_height)
        else:
            preview.setFixedSize(preview_width, preview.heightForWidth(preview_width))
        self._set_preview_source(preview, path)
        variant_layout.addWidget(preview, 0, Qt.AlignmentFlag.AlignTop)
        self._asset_variants.setdefault(asset_key, []).append(variant)
        self._asset_variant_preview_labels.setdefault(asset_key, []).append(preview)
        variant.setFixedSize(
            preview.sizeHint()
            + QSize(_ASSET_VARIANT_FRAME_PADDING * 2, _ASSET_VARIANT_FRAME_PADDING * 2)
        )
        variant.set_selected(
            is_current,
            show_active_frame=participates_in_selection,
        )
        return variant

    def _create_add_asset_variant(
        self,
        *,
        asset_key: str,
        size: tuple[int, int],
        ratio: tuple[int, int] | None,
        parent: QWidget,
    ) -> QWidget:
        preview_width, preview_height = size
        return self._create_asset_variant(
            asset_key=asset_key,
            path="-",
            size=size,
            ratio=ratio,
            is_current=False,
            is_custom=True,
            show_selection_frame=True,
            is_selectable=True,
            parent=parent,
            on_select=lambda: self._add_asset_variant(asset_key),
            placeholder_pixmap=self._add_asset_pixmap(
                preview_width,
                preview_height,
                asset_key=asset_key,
            ),
            placeholder_background_color=QColor(Qt.GlobalColor.transparent),
            participates_in_selection=False,
            is_add_placeholder=True,
        )

    def _select_asset_variant(
        self, asset_key: str, selected_variant: AssetVariantFrame
    ) -> None:
        for variant in self._asset_variants.get(asset_key, []):
            if not variant.participates_in_selection:
                continue
            variant.set_selected(
                variant is selected_variant,
                show_active_frame=True,
            )
        if selected_variant.is_custom:
            self._selected_custom_paths_by_key[asset_key] = Path(
                selected_variant.asset_path
            )
            self._default_selected_asset_keys.discard(asset_key)
        else:
            self._selected_custom_paths_by_key.pop(asset_key, None)
            self._default_selected_asset_keys.add(asset_key)
        self._refresh_unapplied_state()

    def _add_asset_variant(self, asset_key: str) -> None:
        if self._appid is None:
            show_warning(self, "Edit Assets", "No app id is available.")
            return

        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select Asset Image",
            str(_assets_dir() / self._appid / _custom_asset_key_name(asset_key)),
            (
                _CUSTOM_ICON_ASSET_IMAGE_FILTER
                if asset_key == "icon_path"
                else _CUSTOM_ASSET_IMAGE_FILTER
            ),
        )
        if not selected_path:
            return

        source_path = Path(selected_path)
        supported_suffixes = {".png", ".jpg", ".jpeg"}
        if asset_key == "icon_path":
            supported_suffixes.add(".ico")
        if source_path.suffix.lower() not in supported_suffixes:
            show_warning(
                self,
                "Edit Assets",
                f"Unsupported asset extension: {source_path.suffix}",
            )
            return

        try:
            target_path = _custom_asset_target(self._appid, asset_key, source_path)
            _replace_with_file_copy(source_path, target_path)
        except OSError as exc:
            show_critical(self, "Edit Assets", str(exc))
            return

        self._custom_assets_by_key.setdefault(asset_key, []).append(str(target_path))
        self._insert_custom_asset_variant(asset_key, target_path)

    def _insert_custom_asset_variant(self, asset_key: str, path: Path) -> None:
        row_layout = self._asset_variant_row_layouts.get(asset_key)
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        row_widget = scroll_area.widget() if scroll_area is not None else None
        size = self._asset_variant_sizes.get(asset_key)
        if row_layout is None or row_widget is None or size is None:
            return

        ratio = self._asset_variant_ratios.get(asset_key)
        self._asset_variant_counts[asset_key] = (
            self._asset_variant_counts.get(asset_key, 0) + 1
        )
        variant = self._create_asset_variant(
            asset_key=asset_key,
            path=str(path),
            size=size,
            ratio=ratio,
            is_current=False,
            is_custom=True,
            show_selection_frame=True,
            is_selectable=True,
            parent=row_widget,
        )
        row_layout.insertWidget(
            max(0, row_layout.count() - 1),
            variant,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        self._resize_asset_variants(asset_key)
        self._select_asset_variant(asset_key, variant)
        self._finalize_asset_variant_row(asset_key)
        QTimer.singleShot(0, lambda: self._scroll_new_asset_variant(asset_key, variant))

    def _scroll_new_asset_variant(
        self, asset_key: str, variant: AssetVariantFrame
    ) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        if scroll_area is None:
            return

        target = variant.x() + variant.width() - scroll_area.viewport().width()
        self._animate_asset_variant_scroll(asset_key, target)

    def _unapplied_asset_keys(self) -> set[str]:
        unapplied: set[str] = set()
        for asset_key in _CUSTOM_ASSET_DIRS:
            initial_path = self._initial_selected_custom_paths_by_key.get(asset_key)
            selected_path = self._selected_custom_paths_by_key.get(asset_key)
            if selected_path != initial_path:
                unapplied.add(asset_key)
        return unapplied

    def _refresh_unapplied_state(self) -> None:
        unapplied_asset_keys = self._unapplied_asset_keys()
        for asset_key, label in self._asset_unapplied_labels.items():
            label.setVisible(asset_key in unapplied_asset_keys)
        unapplied_count = len(unapplied_asset_keys)
        if self._unapplied_count_label is not None:
            self._unapplied_count_label.setText(f"{unapplied_count} unapplied")
            self._unapplied_count_label.setVisible(unapplied_count > 0)
        self._apply_button.setEnabled(bool(unapplied_asset_keys))

    def _apply_selected_assets(self) -> None:
        if self._appid is None:
            show_warning(self, "Edit Assets", "No app id is available.")
            return

        unapplied_asset_keys = self._unapplied_asset_keys()
        if not unapplied_asset_keys:
            return

        try:
            grid_dir = steam_grid_dir()
            for asset_key in _STEAM_GRID_BASENAME_SUFFIXES:
                if asset_key not in unapplied_asset_keys:
                    continue

                if asset_key in self._default_selected_asset_keys:
                    _remove_grid_asset_files(grid_dir, self._appid, asset_key)
                    continue

                source_path = self._selected_custom_paths_by_key.get(asset_key)
                if source_path is None:
                    continue

                _replace_with_file_copy(
                    source_path,
                    _steam_grid_target(self._appid, asset_key, source_path),
                    cleanup_grid_extensions=True,
                )

            if "hero_path" in unapplied_asset_keys:
                hero_path = self._selected_custom_paths_by_key.get("hero_path")
                if hero_path is not None:
                    preset_path = (
                        hero_path.parent.parent / "preset" / f"{hero_path.stem}.json"
                    )
                    if preset_path.is_file():
                        _replace_with_file_copy(
                            preset_path,
                            grid_dir / f"{self._appid}.json",
                        )
                elif "hero_path" in self._default_selected_asset_keys:
                    default_preset_path = _default_hero_preset_path(self._appid)
                    preset_target = grid_dir / f"{self._appid}.json"
                    if default_preset_path.is_file():
                        _replace_with_file_copy(default_preset_path, preset_target)
                    elif preset_target.exists() or preset_target.is_symlink():
                        preset_target.unlink()

            if "icon_path" in unapplied_asset_keys:
                icon_path = self._selected_custom_paths_by_key.get("icon_path")
                if icon_path is not None:
                    _apply_icon_asset(self._appid, icon_path)
                elif "icon_path" in self._default_selected_asset_keys:
                    _restore_icon_asset(self._appid)

            _write_selected_assets_manifest(
                self._appid,
                dict(self._selected_custom_paths_by_key),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            show_critical(self, "Edit Assets", str(exc))
            return

        self._initial_selected_custom_paths_by_key = dict(
            self._selected_custom_paths_by_key
        )
        self._default_selected_asset_keys.clear()
        self._refresh_unapplied_state()
        self._show_status_message("Assets saved")

    def _open_asset_folder(self) -> None:
        if self._appid is None:
            show_warning(self, "Edit Assets", "No app id is available.")
            return

        app_assets_dir = _assets_dir() / self._appid
        try:
            app_assets_dir.mkdir(parents=True, exist_ok=True)
            for dirname in sorted(set(_CUSTOM_ASSET_DIRS.values()) | {"preset"}):
                (app_assets_dir / dirname).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            show_critical(self, "Edit Assets", str(exc))
            return

        did_open = _open_local_directory(app_assets_dir)
        if not did_open:
            show_warning(
                self,
                "Edit Assets",
                f"Could not open asset folder:\n{app_assets_dir}",
            )

    def _show_status_message(self, message: str) -> None:
        self._toast.show_message(message)

    def _scroll_asset_variants(self, asset_key: str, direction: int) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        variants = self._asset_variants.get(asset_key, [])
        if scroll_area is None or not variants:
            return

        scroll_bar = scroll_area.horizontalScrollBar()
        current = scroll_bar.value()
        viewport_width = scroll_area.viewport().width()
        tolerance = 8

        if direction < 0:
            candidates = [
                (index, variant)
                for index, variant in enumerate(variants)
                if variant.x() < current + tolerance
            ]
            if not candidates:
                target = 0
            else:
                index, variant = candidates[-1]
                if (
                    self._asset_variant_visible_fraction(
                        variant,
                        viewport_start=current,
                        viewport_width=viewport_width,
                    )
                    >= _ASSET_SNAP_VISIBLE_THRESHOLD
                    and index > 0
                ):
                    variant = variants[index - 1]
                target = variant.x()
        else:
            viewport_end = current + viewport_width
            candidates = [
                (index, variant)
                for index, variant in enumerate(variants)
                if variant.x() + variant.width() > viewport_end - tolerance
            ]
            if not candidates:
                target = scroll_bar.maximum()
            else:
                index, variant = candidates[0]
                if (
                    self._asset_variant_visible_fraction(
                        variant,
                        viewport_start=current,
                        viewport_width=viewport_width,
                    )
                    >= _ASSET_SNAP_VISIBLE_THRESHOLD
                    and index < len(variants) - 1
                ):
                    variant = variants[index + 1]
                target = variant.x() + variant.width() - viewport_width

        self._animate_asset_variant_scroll(asset_key, target)

    def _asset_variant_visible_fraction(
        self,
        variant: QWidget,
        *,
        viewport_start: int,
        viewport_width: int,
    ) -> float:
        variant_start = variant.x()
        variant_end = variant_start + variant.width()
        viewport_end = viewport_start + viewport_width
        visible_width = max(
            0,
            min(variant_end, viewport_end) - max(variant_start, viewport_start),
        )
        return visible_width / max(1, variant.width())

    def _animate_asset_variant_scroll(self, asset_key: str, target: int) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        if scroll_area is None:
            return

        scroll_bar = scroll_area.horizontalScrollBar()
        bounded_target = max(0, min(target, scroll_bar.maximum()))
        animation = self._asset_scroll_animations.get(asset_key)
        if (
            animation is not None
            and animation.state() != QPropertyAnimation.State.Stopped
        ):
            animation.stop()

        if scroll_bar.value() == bounded_target:
            return

        animation = QPropertyAnimation(scroll_bar, b"value", self)
        animation.setDuration(260)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(scroll_bar.value())
        animation.setEndValue(bounded_target)
        self._asset_scroll_animations[asset_key] = animation
        animation.start()

    def _update_asset_variant_buttons(self, asset_key: str) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        controls_row = self._asset_variant_control_rows.get(asset_key)
        buttons = self._asset_variant_buttons.get(asset_key)
        if scroll_area is None or controls_row is None or buttons is None:
            return

        left_button, right_button = buttons
        row_widget = scroll_area.widget()
        scroll_bar = scroll_area.horizontalScrollBar()
        maximum = scroll_bar.maximum()
        value = scroll_bar.value()

        content_width = row_widget.width() if row_widget is not None else 0
        available_width = max(0, scroll_area.viewport().contentsRect().width())
        has_overflow = content_width > available_width

        for button, arrow_type in (
            (left_button, Qt.ArrowType.LeftArrow),
            (right_button, Qt.ArrowType.RightArrow),
        ):
            button.setProperty("assetNavHidden", False)
            button.setArrowType(arrow_type)
            button.style().unpolish(button)
            button.style().polish(button)

        left_button.setEnabled(has_overflow and value > 0)
        right_button.setEnabled(has_overflow and value < maximum)

    def _refresh_asset_variant_buttons(self) -> None:
        for asset_key in self._asset_variant_scroll_areas:
            self._update_asset_variant_buttons(asset_key)

    def _refresh_asset_variant_rows(self) -> None:
        for asset_key in self._asset_variant_scroll_areas:
            self._resize_asset_variants(asset_key)
            self._finalize_asset_variant_row(asset_key)

    def _finalize_asset_variant_row(self, asset_key: str) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        if scroll_area is None:
            return

        row_widget = scroll_area.widget()
        if row_widget is not None:
            row_layout = row_widget.layout()
            if row_layout is not None:
                row_layout.setSpacing(_ASSET_VARIANT_SPACING)
                row_layout.invalidate()
                row_layout.activate()
            target_size = row_widget.sizeHint()
            row_widget.setFixedSize(target_size)
            scroll_area.setMinimumHeight(target_size.height())
            scroll_area.setMaximumHeight(target_size.height())

        self._update_asset_variant_buttons(asset_key)

    def _resize_asset_variants(self, asset_key: str) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        variants = self._asset_variants.get(asset_key, [])
        previews = self._asset_variant_preview_labels.get(asset_key, [])
        base_size = self._asset_variant_sizes.get(asset_key)
        if scroll_area is None or base_size is None:
            return

        base_width, base_height = base_size
        ratio = self._asset_variant_ratios.get(asset_key)
        available_width = max(
            1,
            scroll_area.viewport().contentsRect().width() - _ASSET_VARIANT_SPACING,
        )
        max_width = min(base_width, _ASSET_PREVIEW_MAX_WIDTHS[asset_key])
        min_width = min(max_width, _ASSET_PREVIEW_MIN_WIDTHS[asset_key])
        target_width = max(min_width, min(max_width, available_width))

        if ratio is None:
            scale = target_width / max(1, base_width)
            target_height = max(1, int(base_height * scale))
        else:
            ratio_width, ratio_height = ratio
            target_height = max(1, int(target_width * ratio_height / ratio_width))

        target_size = QSize(target_width, target_height)
        for preview in previews:
            preview.set_preferred_size(target_size)
            preview.setFixedSize(target_size)

        for variant in variants:
            variant.setFixedSize(
                target_size
                + QSize(
                    _ASSET_VARIANT_FRAME_PADDING * 2,
                    _ASSET_VARIANT_FRAME_PADDING * 2,
                )
            )

    def _create_preview_label(
        self,
        asset_key: str,
        size: tuple[int, int],
        ratio: tuple[int, int] | None,
        *,
        placeholder_pixmap: QPixmap | None = None,
        placeholder_background_color: QColor | None = None,
    ) -> PreviewPixmapLabel:
        preview_width, preview_height = size
        placeholder = placeholder_pixmap or self._missing_asset_pixmap(
            preview_width,
            preview_height,
            question_mark_scale=0.6 if asset_key == "icon_path" else 0.8,
        )
        round_letterboxed_source = asset_key not in {"hero_path", "logo_path"}
        if ratio is not None:
            ratio_width, ratio_height = ratio
            preview = RatioPreviewPixmapLabel(
                placeholder,
                QSize(preview_width, preview_height),
                ratio_width,
                ratio_height,
                corner_radius=_ASSET_PREVIEW_CORNER_RADIUS,
                round_letterboxed_source=round_letterboxed_source,
                placeholder_background_color=placeholder_background_color,
            )
            preview.setMinimumWidth(0)
            return preview

        preview = PreviewPixmapLabel(
            placeholder,
            QSize(preview_width, preview_height),
            corner_radius=_ASSET_PREVIEW_CORNER_RADIUS,
            round_letterboxed_source=round_letterboxed_source,
            placeholder_background_color=placeholder_background_color,
        )
        return preview

    def _set_preview_source(self, label: PreviewPixmapLabel, path: str) -> None:
        if path in {"", "-"}:
            label.set_source_pixmap(None)
            return

        pixmap = _load_pixmap(path)
        label.set_source_pixmap(pixmap if not pixmap.isNull() else None)

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

    def _add_asset_pixmap(self, width: int, height: int, *, asset_key: str) -> QPixmap:
        icon_size = min(width, height, 32)
        icon_color = self.palette().placeholderText().color()
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        add_icon = QIcon.fromTheme(
            "list-add",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder),
        )
        symbol_scale = 0.5 if asset_key == "icon_path" else 0.8
        symbol_size = max(8, int(icon_size * symbol_scale))
        symbol = monochrome_icon_pixmap(add_icon, symbol_size, icon_color)
        x = (pixmap.width() - symbol.width()) // 2
        y = (pixmap.height() - symbol.height()) // 2
        painter.drawPixmap(x, y, symbol)
        painter.end()
        return pixmap
