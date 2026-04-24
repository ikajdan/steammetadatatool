from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.gui.edit_metadata_dialog import (
    ElidedLabel,
    _monochrome_icon_pixmap,
)

_CUSTOM_ASSET_DIRS = {
    "capsule_path": "capsule",
    "header_path": "header",
    "hero_path": "hero",
    "logo_path": "logo",
    "icon_path": "icon",
}

_ASSET_CATEGORY_SIDE_PADDING = 0
_ASSET_NAV_BUTTON_SIZE = 44
_ASSET_NAV_SCROLLBAR_GAP = 8


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _custom_asset_paths_for_app(appid: str | None) -> dict[str, list[str]]:
    custom_assets = {key: [] for key in _CUSTOM_ASSET_DIRS}
    if not appid:
        return custom_assets

    base_dir = _project_root() / "assets" / appid
    if not base_dir.is_dir():
        return custom_assets

    supported_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    for key, dirname in _CUSTOM_ASSET_DIRS.items():
        asset_dir = base_dir / dirname
        if not asset_dir.is_dir():
            continue

        custom_assets[key] = [
            str(path)
            for path in sorted(asset_dir.iterdir())
            if path.is_file() and path.suffix.lower() in supported_suffixes
        ]

    return custom_assets


class PreviewPixmapLabel(QLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        preferred_size: QSize,
        parent: QWidget | None = None,
        *,
        corner_radius: float = 10.0,
    ) -> None:
        super().__init__(parent)
        self._source_pixmap: QPixmap | None = None
        self._placeholder_pixmap = placeholder
        self._preferred_size = preferred_size
        self._corner_radius = corner_radius
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def sizeHint(self) -> QSize:
        return QSize(self._preferred_size)

    def minimumSizeHint(self) -> QSize:
        return QSize(self._preferred_size)

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
        self.setPixmap(self._rounded_pixmap(scaled))

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
    ) -> None:
        super().__init__(
            placeholder,
            preferred_size,
            parent,
            corner_radius=corner_radius,
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
        return self.sizeHint()

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
        on_select: Callable[[], None] | None = None,
        show_selection_frame: bool = True,
    ) -> None:
        super().__init__(parent)
        self._on_select = on_select
        self._is_selected = False
        self._show_selection_frame = show_selection_frame
        self.setObjectName("assetVariantFrame")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if show_selection_frame
            else Qt.CursorShape.ArrowCursor
        )

    def set_selected(self, selected: bool) -> None:
        self._is_selected = selected
        if not self._show_selection_frame:
            self.setToolTip("")
            self.setStyleSheet("#assetVariantFrame { border: none; }")
            return

        border_color = (
            self.palette().highlight().color().name()
            if selected
            else self.palette().mid().color().name()
        )
        border_width = 2
        border_style = "solid" if selected else "double"
        self.setToolTip("Selected asset" if selected else "")
        self.setStyleSheet(
            "#assetVariantFrame {"
            f" border: {border_width}px {border_style} {border_color};"
            " border-radius: 16px; "
            "}"
        )

    def mouseReleaseEvent(self, event) -> None:
        if (
            self._on_select is not None
            and self._show_selection_frame
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self._on_select()
            event.accept()
            return
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
        base_button_color = palette.button().color()
        visible_border_color = palette.light().color().lighter(135)
        if not self.isEnabled():
            background_color = base_button_color.lighter(104)
            border_color = visible_border_color
            arrow_color = palette.mid().color().lighter(145)
        elif self.isDown():
            background_color = palette.midlight().color()
            border_color = visible_border_color
            arrow_color = palette.buttonText().color()
        elif self.underMouse():
            background_color = palette.light().color()
            border_color = visible_border_color
            arrow_color = palette.buttonText().color()
        else:
            background_color = base_button_color.lighter(112)
            border_color = visible_border_color
            arrow_color = palette.buttonText().color()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border_color, 2.0))
        painter.setBrush(background_color)
        painter.drawEllipse(self.rect().adjusted(2, 2, -3, -3))

        center = self.rect().center()
        arrow_width = 8
        arrow_height = 14
        arrow_offset = 1
        path = QPainterPath()
        if self.arrowType() == Qt.ArrowType.LeftArrow:
            center.setX(center.x() - arrow_offset)
            path.moveTo(center.x() - arrow_width // 2, center.y())
            path.lineTo(center.x() + arrow_width // 2, center.y() - arrow_height // 2)
            path.lineTo(center.x() + arrow_width // 2, center.y() + arrow_height // 2)
        elif self.arrowType() == Qt.ArrowType.RightArrow:
            center.setX(center.x() + arrow_offset)
            path.moveTo(center.x() + arrow_width // 2, center.y())
            path.lineTo(center.x() - arrow_width // 2, center.y() - arrow_height // 2)
            path.lineTo(center.x() - arrow_width // 2, center.y() + arrow_height // 2)
        else:
            painter.end()
            return

        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(arrow_color)
        painter.drawPath(path)
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
        self.setWindowTitle("Edit Assets")
        self.setModal(True)
        self.resize(1080, 760)
        self.setMinimumSize(720, 520)
        self._scroll_area: QScrollArea | None = None
        self._asset_cards: dict[str, QWidget] = {}
        self._asset_variants: dict[str, list[AssetVariantFrame]] = {}
        self._asset_variant_scroll_areas: dict[str, QScrollArea] = {}
        self._asset_variant_control_rows: dict[str, QWidget] = {}
        self._asset_variant_buttons: dict[str, tuple[QToolButton, QToolButton]] = {}
        self._initial_asset_key = initial_asset_key
        self._did_initial_asset_scroll = False
        self._initial_asset_scroll_attempts = 0
        self._custom_assets_by_key = _custom_asset_paths_for_app(appid)

        action_icon_color = self.palette().placeholderText().color()

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
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        header_row_layout.addWidget(self._app_name_label)
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
            ("capsule_path", "Capsule", (260, 390), (2, 3)),
            ("header_path", "Header", (420, 196), (460, 215)),
            ("hero_path", "Hero", (960, 310), (96, 31)),
            ("logo_path", "Logo", (384, 120), None),
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

        close_icon = QIcon.fromTheme(
            "dialog-close",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
        )
        close_button = QPushButton(
            QIcon(_monochrome_icon_pixmap(close_icon, 24, action_icon_color)),
            "Close",
            dialog_actions,
        )
        close_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        close_button.setMinimumHeight(40)
        close_button.setMaximumWidth(360)
        close_button.setIconSize(QSize(24, 24))
        close_button.clicked.connect(self.accept)
        dialog_actions_layout.addWidget(close_button)

        dialog_actions_layout.setStretch(0, 4)
        dialog_actions_layout.setStretch(1, 1)
        dialog_layout.addWidget(dialog_actions)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._refresh_asset_variant_buttons)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._initial_asset_key is not None and not self._did_initial_asset_scroll:
            self._initial_asset_scroll_attempts = 0
            self._queue_initial_asset_scroll()

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
        layout.setContentsMargins(
            _ASSET_CATEGORY_SIDE_PADDING,
            14,
            _ASSET_CATEGORY_SIDE_PADDING,
            14,
        )
        layout.setSpacing(10)

        title_label = QLabel(title, card)
        title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(title_label)
        show_selection_frame = bool(custom_paths)

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
        variants_layout.setSpacing(16)
        self._asset_variants[key] = []
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
                is_current=True,
                show_selection_frame=show_selection_frame,
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
                    is_current=False,
                    show_selection_frame=show_selection_frame,
                    parent=variants_row,
                ),
                0,
                Qt.AlignmentFlag.AlignTop,
            )

        variants_layout.addStretch(1)
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
        show_selection_frame: bool,
        parent: QWidget,
    ) -> QWidget:
        preview_width, preview_height = size
        variant = AssetVariantFrame(
            parent,
            on_select=lambda: self._select_asset_variant(asset_key, variant),
            show_selection_frame=show_selection_frame,
        )
        variant_layout = QVBoxLayout(variant)
        variant_layout.setContentsMargins(0, 0, 0, 0)
        variant_layout.setSpacing(0)

        preview = self._create_preview_label(size, ratio)
        preview.setMaximumWidth(preview_width)
        if ratio is None:
            preview.setMinimumSize(preview_width, preview_height)
            preview.setMaximumHeight(preview_height)
        self._set_preview_source(preview, path)
        variant_layout.addWidget(preview, 0, Qt.AlignmentFlag.AlignTop)
        self._asset_variants.setdefault(asset_key, []).append(variant)
        variant.set_selected(is_current)
        return variant

    def _select_asset_variant(
        self, asset_key: str, selected_variant: AssetVariantFrame
    ) -> None:
        for variant in self._asset_variants.get(asset_key, []):
            variant.set_selected(variant is selected_variant)

    def _scroll_asset_variants(self, asset_key: str, direction: int) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        variants = self._asset_variants.get(asset_key, [])
        if scroll_area is None or not variants:
            return

        scroll_bar = scroll_area.horizontalScrollBar()
        positions = sorted(variant.x() for variant in variants)
        current = scroll_bar.value()
        tolerance = 8

        if direction < 0:
            candidates = [
                position for position in positions if position < current - tolerance
            ]
            target = candidates[-1] if candidates else 0
        else:
            candidates = [
                position for position in positions if position > current + tolerance
            ]
            target = candidates[0] if candidates else scroll_bar.maximum()

        scroll_bar.setValue(max(0, min(target, scroll_bar.maximum())))

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

        content_width = row_widget.sizeHint().width() if row_widget is not None else 0
        available_width = max(0, scroll_area.viewport().contentsRect().width())
        has_overflow = content_width > available_width

        for button, arrow_type in (
            (left_button, Qt.ArrowType.LeftArrow),
            (right_button, Qt.ArrowType.RightArrow),
        ):
            button.setProperty("assetNavHidden", not has_overflow)
            button.setArrowType(arrow_type if has_overflow else Qt.ArrowType.NoArrow)
            button.style().unpolish(button)
            button.style().polish(button)

        left_button.setEnabled(has_overflow and value > 0)
        right_button.setEnabled(has_overflow and value < maximum)

    def _refresh_asset_variant_buttons(self) -> None:
        for asset_key in self._asset_variant_scroll_areas:
            self._update_asset_variant_buttons(asset_key)

    def _finalize_asset_variant_row(self, asset_key: str) -> None:
        scroll_area = self._asset_variant_scroll_areas.get(asset_key)
        if scroll_area is None:
            return

        row_widget = scroll_area.widget()
        if row_widget is not None:
            target_height = row_widget.sizeHint().height()
            scroll_area.setMinimumHeight(target_height)
            scroll_area.setMaximumHeight(target_height)

        self._update_asset_variant_buttons(asset_key)

    def _create_preview_label(
        self,
        size: tuple[int, int],
        ratio: tuple[int, int] | None,
    ) -> PreviewPixmapLabel:
        preview_width, preview_height = size
        placeholder = self._missing_asset_pixmap(preview_width, preview_height)
        if ratio is not None:
            ratio_width, ratio_height = ratio
            preview = RatioPreviewPixmapLabel(
                placeholder,
                QSize(preview_width, preview_height),
                ratio_width,
                ratio_height,
                corner_radius=16.0,
            )
            preview.setMinimumWidth(0)
            return preview

        preview = PreviewPixmapLabel(
            placeholder,
            QSize(preview_width, preview_height),
            corner_radius=16.0,
        )
        return preview

    def _set_preview_source(self, label: PreviewPixmapLabel, path: str) -> None:
        if path in {"", "-"}:
            label.set_source_pixmap(None)
            return

        pixmap = QPixmap(path)
        label.set_source_pixmap(pixmap if not pixmap.isNull() else None)

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
