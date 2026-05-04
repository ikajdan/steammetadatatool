# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from steammetadatatool.gui.services.icons import monochrome_icon_pixmap

_WINDOW_TITLE = "SteamMetadataTool"


def _prepare_message_box(message_box: QMessageBox) -> None:
    try:
        message_box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    except AttributeError:
        pass

    icon_color = message_box.palette().buttonText().color()
    for button in message_box.findChildren(QPushButton):
        icon = button.icon()
        if icon.isNull():
            continue

        icon_size = button.iconSize()
        size = max(icon_size.width(), icon_size.height(), 16)
        button.setIcon(monochrome_icon_pixmap(icon, size, icon_color))


def show_message(
    parent: QWidget | None,
    title: str,
    text: str,
    icon: QMessageBox.Icon,
    *,
    informative_text: str | None = None,
) -> None:
    message_box = QMessageBox(parent)
    message_box.setIcon(icon)
    message_box.setWindowTitle(_WINDOW_TITLE)
    message_box.setText(text)
    if informative_text:
        message_box.setInformativeText(informative_text)
    message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    _prepare_message_box(message_box)
    message_box.exec()


def show_information(parent: QWidget | None, title: str, text: str) -> None:
    show_message(parent, title, text, QMessageBox.Icon.Information)


def show_warning(parent: QWidget | None, title: str, text: str) -> None:
    show_message(parent, title, text, QMessageBox.Icon.Warning)


def show_critical(parent: QWidget | None, title: str, text: str) -> None:
    show_message(parent, title, text, QMessageBox.Icon.Critical)


def confirm_warning(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    informative_text: str,
    accept_text: str,
    reject_text: str,
) -> bool:
    message_box = QMessageBox(parent)
    message_box.setIcon(QMessageBox.Icon.Warning)
    message_box.setWindowTitle(_WINDOW_TITLE)
    message_box.setText(text)
    message_box.setInformativeText(informative_text)
    reject_button = message_box.addButton(
        reject_text, QMessageBox.ButtonRole.RejectRole
    )
    accept_button = message_box.addButton(
        accept_text, QMessageBox.ButtonRole.AcceptRole
    )
    message_box.setDefaultButton(reject_button)
    _prepare_message_box(message_box)
    message_box.exec()

    return message_box.clickedButton() is accept_button
