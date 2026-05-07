# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

COLORS = {
    "accent": "#66c0f4",
    "accent_hover": "#8fd8ff",
    "background": "#202225",
    "background_alt": "#232629",
    "background_input": "#181a1b",
    "border": "#3a3f44",
    "border_light": "#4a4f55",
    "button": "#2b2f33",
    "button_checked": "#35424d",
    "button_checked_disabled": "#2b343c",
    "button_checked_hover": "#404f5c",
    "button_checked_pressed": "#2d3944",
    "button_pressed": "#343a40",
    "highlight": "#3a82f7",
    "scrollbar": "#25282c",
    "scrollbar_handle": "#6a7178",
    "scrollbar_handle_hover": "#838b94",
    "scrollbar_handle_pressed": "#a1a9b2",
    "shadow": "#0b0c0d",
    "text": "#d0d3d6",
    "text_disabled": "#8a8f94",
    "text_inverse": "#ffffff",
    "window_dark": "#141617",
}

PALETTE_ROLES = (
    (QPalette.ColorRole.AlternateBase, COLORS["background_alt"]),
    (QPalette.ColorRole.Base, COLORS["background_input"]),
    (QPalette.ColorRole.BrightText, COLORS["text_inverse"]),
    (QPalette.ColorRole.Button, COLORS["button"]),
    (QPalette.ColorRole.ButtonText, COLORS["text"]),
    (QPalette.ColorRole.Dark, COLORS["window_dark"]),
    (QPalette.ColorRole.Highlight, COLORS["highlight"]),
    (QPalette.ColorRole.HighlightedText, COLORS["text_inverse"]),
    (QPalette.ColorRole.Light, COLORS["accent"]),
    (QPalette.ColorRole.Link, COLORS["accent"]),
    (QPalette.ColorRole.Mid, COLORS["border"]),
    (QPalette.ColorRole.Midlight, COLORS["border_light"]),
    (QPalette.ColorRole.PlaceholderText, COLORS["text_disabled"]),
    (QPalette.ColorRole.Shadow, COLORS["shadow"]),
    (QPalette.ColorRole.Text, COLORS["text"]),
    (QPalette.ColorRole.ToolTipBase, COLORS["button"]),
    (QPalette.ColorRole.ToolTipText, COLORS["text_inverse"]),
    (QPalette.ColorRole.Window, COLORS["background"]),
    (QPalette.ColorRole.WindowText, COLORS["text"]),
)

APP_STYLE = f"""
QDialog,
QMainWindow,
QWidget {{
    background-color: {COLORS["background"]};
    color: {COLORS["text"]};
}}

QLabel {{
    color: {COLORS["text"]};
}}

QToolTip {{
    background-color: {COLORS["button"]};
    border: 1px solid {COLORS["border"]};
    color: {COLORS["text_inverse"]};
    padding: 4px;
}}

QMenu {{
    background-color: {COLORS["background_alt"]};
    border: 1px solid {COLORS["border_light"]};
    border-radius: 6px;
    color: {COLORS["text"]};
    padding: 5px;
}}

QMenu::item {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: {COLORS["text"]};
    margin: 1px;
    padding: 7px 16px 7px 12px;
}}

QMenu::item:selected {{
    background-color: {COLORS["border"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["text_inverse"]};
}}

QMenu::item:pressed {{
    background-color: {COLORS["button_pressed"]};
    border-color: {COLORS["highlight"]};
    color: {COLORS["text_inverse"]};
}}

QMenu::item:disabled {{
    color: {COLORS["text_disabled"]};
}}

QMenu QToolButton#contextMenuActionButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: {COLORS["text"]};
    margin: 1px;
    padding: 7px 16px 7px 12px;
    text-align: left;
}}

QMenu QToolButton#contextMenuActionButton:hover {{
    background-color: {COLORS["border"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["text_inverse"]};
}}

QMenu QToolButton#contextMenuActionButton:pressed {{
    background-color: {COLORS["button_pressed"]};
    border-color: {COLORS["highlight"]};
    color: {COLORS["text_inverse"]};
}}

QPushButton {{
    background-color: {COLORS["button"]};
    border: 1px solid {COLORS["border_light"]};
    border-radius: 6px;
    color: {COLORS["text"]};
    font-weight: 600;
    padding: 6px 12px;
}}

QPushButton:hover {{
    background-color: {COLORS["border"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["text_inverse"]};
}}

QPushButton:pressed {{
    background-color: {COLORS["button_pressed"]};
    border-color: {COLORS["highlight"]};
}}

QPushButton:checked {{
    background-color: {COLORS["button_checked"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["text_inverse"]};
}}

QPushButton:checked:hover {{
    background-color: {COLORS["button_checked_hover"]};
    border-color: {COLORS["accent_hover"]};
}}

QPushButton:checked:pressed {{
    background-color: {COLORS["button_checked_pressed"]};
    border-color: {COLORS["accent"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["background_alt"]};
    border-color: {COLORS["button"]};
    color: {COLORS["text_disabled"]};
}}

QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: {COLORS["text"]};
    padding: 4px;
}}

QToolButton:hover {{
    background-color: {COLORS["border"]};
    border-color: {COLORS["border_light"]};
}}

QToolButton:pressed {{
    background-color: {COLORS["button_pressed"]};
    border-color: {COLORS["accent"]};
}}

QToolButton:checked {{
    background-color: {COLORS["button_checked"]};
    border-color: {COLORS["accent"]};
    color: {COLORS["text_inverse"]};
}}

QToolButton:checked:hover {{
    background-color: {COLORS["button_checked_hover"]};
    border-color: {COLORS["accent_hover"]};
}}

QToolButton:checked:pressed {{
    background-color: {COLORS["button_checked_pressed"]};
    border-color: {COLORS["accent"]};
}}

QToolButton:checked:disabled {{
    background-color: {COLORS["button_checked_disabled"]};
    border-color: {COLORS["border_light"]};
    color: {COLORS["text_disabled"]};
}}

QComboBox,
QDoubleSpinBox,
QLineEdit,
QPlainTextEdit,
QSpinBox,
QTextEdit {{
    background-color: {COLORS["background_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 5px;
    color: {COLORS["text"]};
    padding: 5px 7px;
    selection-background-color: {COLORS["highlight"]};
    selection-color: {COLORS["text_inverse"]};
}}

QComboBox:focus,
QDoubleSpinBox:focus,
QLineEdit:focus,
QPlainTextEdit:focus,
QSpinBox:focus,
QTextEdit:focus {{
    border-color: {COLORS["accent"]};
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["background"]};
    border: 1px solid {COLORS["border"]};
    color: {COLORS["text"]};
    selection-background-color: {COLORS["border"]};
    selection-color: {COLORS["text_inverse"]};
}}

QComboBox::drop-down {{
    background-color: {COLORS["border"]};
    border: 0;
    border-left: 1px solid {COLORS["border_light"]};
    width: 24px;
}}

QListWidget,
QTableWidget,
QTreeWidget {{
    alternate-background-color: {COLORS["background_alt"]};
    background-color: {COLORS["background_input"]};
    border: 1px solid {COLORS["border"]};
    color: {COLORS["text"]};
    gridline-color: {COLORS["button"]};
    selection-background-color: {COLORS["border"]};
    selection-color: {COLORS["text_inverse"]};
}}

QHeaderView::section {{
    background-color: {COLORS["background_alt"]};
    border: 0;
    border-bottom: 1px solid {COLORS["border"]};
    color: {COLORS["text_inverse"]};
    font-weight: 600;
    padding: 6px;
}}

QScrollArea {{
    background-color: {COLORS["background"]};
    border: 0;
}}

QScrollBar:horizontal {{
    background: {COLORS["scrollbar"]};
    border: 0;
    border-radius: 10px;
    height: 22px;
    margin: 3px;
}}

QScrollBar:vertical {{
    background: {COLORS["scrollbar"]};
    border: 0;
    border-radius: 10px;
    margin: 3px;
    width: 22px;
}}

QScrollBar::add-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::sub-page:horizontal {{
    background: transparent;
    border: 0;
    width: 0;
}}

QScrollBar::add-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    border: 0;
    height: 0;
}}

QScrollBar::handle:horizontal {{
    background: {COLORS["scrollbar_handle"]};
    border: 4px solid {COLORS["scrollbar"]};
    border-radius: 10px;
    min-width: 34px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {COLORS["scrollbar_handle_hover"]};
}}

QScrollBar::handle:horizontal:pressed {{
    background: {COLORS["scrollbar_handle_pressed"]};
}}

QScrollBar::handle:vertical {{
    background: {COLORS["scrollbar_handle"]};
    border: 4px solid {COLORS["scrollbar"]};
    border-radius: 10px;
    min-height: 34px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS["scrollbar_handle_hover"]};
}}

QScrollBar::handle:vertical:pressed {{
    background: {COLORS["scrollbar_handle_pressed"]};
}}

QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    background-color: {COLORS["border"]};
    border: 0;
    color: {COLORS["border"]};
}}

QFrame[frameShape="4"] {{
    max-height: 1px;
    min-height: 1px;
}}

QFrame[frameShape="5"] {{
    max-width: 1px;
    min-width: 1px;
}}
"""


class NoShortcutUnderlineStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None) -> int:
        if hint == QStyle.StyleHint.SH_UnderlineShortcut:
            return 0
        return super().styleHint(hint, option, widget, returnData)


def apply_theme(app: QApplication) -> None:
    app.setStyle(NoShortcutUnderlineStyle(QStyleFactory.create("Fusion")))
    _configure_appimage_theme(app)
    app.setPalette(_build_palette())
    app.setStyleSheet(APP_STYLE)


def _build_palette() -> QPalette:
    palette = QPalette()
    for role, color in PALETTE_ROLES:
        palette.setColor(role, QColor(color))
    return palette


def _configure_appimage_theme(app: QApplication) -> None:
    appdir = os.environ.get("APPDIR")
    if not appdir:
        return

    QIcon.setThemeSearchPaths(
        [str(Path(appdir) / "usr" / "share" / "icons")] + QIcon.themeSearchPaths()
    )
    QIcon.setThemeName("Papirus-Dark")
    app.setFont(QFont("Noto Sans UI", 11))
