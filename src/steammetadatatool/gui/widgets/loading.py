# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


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
