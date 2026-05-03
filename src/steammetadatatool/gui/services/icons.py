# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def monochrome_icon_pixmap(
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
