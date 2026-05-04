# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class EmptyStateOverlay(QWidget):
    def __init__(
        self,
        icon: QIcon,
        title: str,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addStretch(1)

        content = QWidget(self)
        content.setAutoFillBackground(False)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        icon_label = QLabel(self)
        icon_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        icon_label.setAutoFillBackground(False)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        icon_label.setStyleSheet("background: transparent;")
        icon_pixmap = icon.pixmap(32, 32)
        if not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        content_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_column = QWidget(content)
        text_column.setAutoFillBackground(False)
        text_column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(title, self)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setAutoFillBackground(False)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        title_label.setStyleSheet(
            "background: transparent; color: palette(placeholder-text);"
        )
        text_layout.addWidget(title_label)

        if description:
            description_label = QLabel(description, self)
            description_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            description_label.setAutoFillBackground(False)
            description_label.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground,
                True,
            )
            description_label.setWordWrap(True)
            description_label.setStyleSheet(
                "background: transparent; color: palette(mid);"
            )
            text_layout.addWidget(description_label)

        content_layout.addWidget(text_column, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(content, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
