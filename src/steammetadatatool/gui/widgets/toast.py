# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


class ToastMessage(QLabel):
    def __init__(self, parent: QWidget, *, bottom_margin: int = 24) -> None:
        super().__init__(parent)
        self._bottom_margin = bottom_margin
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
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
        self.setText(message)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
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
        parent = self.parentWidget()
        if parent is None:
            return

        side_margin = 24
        x = max(side_margin, int((parent.width() - self.width()) / 2))
        y = max(side_margin, parent.height() - self.height() - self._bottom_margin)
        self.move(x, y)
