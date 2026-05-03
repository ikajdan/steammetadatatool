# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtWidgets import QStyledItemDelegate, QWidget


class LeftPaddingItemDelegate(QStyledItemDelegate):
    def __init__(self, left_padding: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._left_padding = left_padding

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        option.rect.adjust(self._left_padding, 0, 0, 0)
