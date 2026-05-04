# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtCore import QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget


class ToastMessage(QLabel):
    def __init__(self, parent: QWidget, *, bottom_margin: int = 24) -> None:
        super().__init__(parent)
        self._bottom_margin = bottom_margin
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide_animated)
        self._animation: QParallelAnimationGroup | None = None
        self._is_animating = False
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "background: palette(highlight);"
            " color: palette(highlighted-text);"
            " border-radius: 12px;"
            " padding: 5px 12px;"
            " font-weight: 600;"
        )
        self.hide()
        parent.installEventFilter(self)

    def show_message(self, message: str, timeout_ms: int = 3000) -> None:
        self._stop_animation()
        self.setText(message)
        self.adjustSize()
        target_position = self._target_position()
        self.move(target_position + QPoint(0, 10))
        self._opacity_effect.setOpacity(0.0)
        self.show()
        self.raise_()
        self._animate(
            end_position=target_position,
            end_opacity=1.0,
            duration_ms=170,
        )
        self._timer.start(timeout_ms)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        }:
            self._reposition()
        return super().eventFilter(watched, event)

    def _reposition(self) -> None:
        if self._is_animating:
            return

        self.move(self._target_position())

    def _target_position(self) -> QPoint:
        parent = self.parentWidget()
        if parent is None:
            return self.pos()

        side_margin = 24
        x = max(side_margin, int((parent.width() - self.width()) / 2))
        y = max(side_margin, parent.height() - self.height() - self._bottom_margin)
        return QPoint(x, y)

    def _hide_animated(self) -> None:
        if not self.isVisible():
            return

        self._stop_animation()
        self._animate(
            end_position=self._target_position() + QPoint(0, 10),
            end_opacity=0.0,
            duration_ms=130,
            hide_when_finished=True,
        )

    def _animate(
        self,
        *,
        end_position: QPoint,
        end_opacity: float,
        duration_ms: int,
        hide_when_finished: bool = False,
    ) -> None:
        position_animation = QPropertyAnimation(self, b"pos", self)
        position_animation.setDuration(duration_ms)
        position_animation.setStartValue(self.pos())
        position_animation.setEndValue(end_position)
        position_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        opacity_animation = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        opacity_animation.setDuration(duration_ms)
        opacity_animation.setStartValue(self._opacity_effect.opacity())
        opacity_animation.setEndValue(end_opacity)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        animation = QParallelAnimationGroup(self)
        animation.addAnimation(position_animation)
        animation.addAnimation(opacity_animation)
        animation.finished.connect(
            lambda: self._finish_animation(animation, hide_when_finished)
        )
        self._animation = animation
        self._is_animating = True
        animation.start()

    def _finish_animation(
        self,
        animation: QParallelAnimationGroup,
        hide_when_finished: bool,
    ) -> None:
        if self._animation is not animation:
            return

        self._animation = None
        self._is_animating = False
        if hide_when_finished:
            self.hide()
        else:
            self._reposition()
        animation.deleteLater()

    def _stop_animation(self) -> None:
        if self._animation is None:
            self._is_animating = False
            return

        animation = self._animation
        self._animation = None
        self._is_animating = False
        animation.stop()
        animation.deleteLater()
