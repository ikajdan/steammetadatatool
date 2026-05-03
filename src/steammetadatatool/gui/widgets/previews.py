# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QWidget,
)


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
