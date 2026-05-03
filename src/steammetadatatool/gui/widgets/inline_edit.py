# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLineEdit


class InlineDetailLineEdit(QLineEdit):
    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        hint.setWidth(24)
        return hint

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setWidth(280)
        return hint
