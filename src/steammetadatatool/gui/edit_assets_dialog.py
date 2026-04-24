from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.gui.edit_metadata_dialog import (
    ElidedLabel,
    _monochrome_icon_pixmap,
)


class PreviewPixmapLabel(QLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        preferred_size: QSize,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_pixmap: QPixmap | None = None
        self._placeholder_pixmap = placeholder
        self._preferred_size = preferred_size
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
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setPixmap(self._placeholder_display_pixmap())
            return

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setPixmap(
            pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

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


class RatioPreviewPixmapLabel(PreviewPixmapLabel):
    def __init__(
        self,
        placeholder: QPixmap,
        preferred_size: QSize,
        ratio_width: int,
        ratio_height: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(placeholder, preferred_size, parent)
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
        assets_layout.setSpacing(16)
        content_layout.addWidget(assets_container)
        content_layout.addStretch(1)

        asset_specs: list[tuple[str, str, tuple[int, int], tuple[int, int] | None]] = [
            ("capsule_path", "Capsule", (300, 450), (2, 3)),
            ("header_path", "Header", (460, 215), (460, 215)),
            ("hero_path", "Hero", (384, 124), (96, 31)),
            ("logo_path", "Logo", (384, 120), None),
            ("icon_path", "Icon", (48, 48), None),
        ]

        for key, title, size, ratio in asset_specs:
            card = self._create_asset_card(
                key=key,
                title=title,
                path=assets.get(key, "-"),
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

        if initial_asset_key is not None:
            QTimer.singleShot(
                0,
                lambda: self._scroll_to_asset(initial_asset_key),
            )

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

    def _scroll_to_asset(self, key: str) -> None:
        if self._scroll_area is None:
            return

        card = self._asset_cards.get(key)
        if card is None:
            return

        content = self._scroll_area.widget()
        if content is None:
            return

        scroll_bar = self._scroll_area.verticalScrollBar()
        target_y = card.mapTo(content, QPoint(0, 0)).y()
        top_margin = 8
        scroll_bar.setValue(max(0, min(target_y - top_margin, scroll_bar.maximum())))

    def _create_asset_card(
        self,
        *,
        key: str,
        title: str,
        path: str,
        size: tuple[int, int],
        ratio: tuple[int, int] | None,
    ) -> QWidget:
        card = QFrame(self)
        card.setFrameShape(QFrame.Shape.NoFrame)
        if key == "hero_path":
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
        else:
            card.setSizePolicy(
                QSizePolicy.Policy.Maximum,
                QSizePolicy.Policy.Maximum,
            )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title, card)
        title_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(title_label)

        preview_width, preview_height = size
        preview = self._create_preview_label(size, ratio)
        if key == "hero_path":
            preview.setMaximumWidth(16777215)
        else:
            preview.setMaximumWidth(preview_width)
        if ratio is None:
            preview.setMinimumSize(preview_width, preview_height)
            preview.setMaximumHeight(preview_height)
        self._set_preview_source(preview, path)
        layout.addWidget(preview)

        if key != "hero_path":
            card.setMaximumWidth(preview_width + 28)
        return card

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
            )
            preview.setMinimumWidth(0)
            return preview

        preview = PreviewPixmapLabel(
            placeholder,
            QSize(preview_width, preview_height),
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
