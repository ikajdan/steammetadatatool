# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from steammetadatatool.gui.services.icons import monochrome_icon_pixmap
from steammetadatatool.gui.services.theme import COLORS
from steammetadatatool.gui.steam.paths import SteamUser
from steammetadatatool.i18n import _

_AVATAR_SIZE = 96
_TILE_SIZE = QSize(140, 138)
_TILE_COLUMNS = 3


def _steam_user_label(user: SteamUser) -> str:
    return user.persona_name or user.account_name or user.account_id


def _square_avatar_pixmap(source: QPixmap, size: int) -> QPixmap:
    scaled = source.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    if scaled.width() != size or scaled.height() != size:
        x = max(0, (scaled.width() - size) // 2)
        y = max(0, (scaled.height() - size) // 2)
        scaled = scaled.copy(x, y, size, size)

    return scaled


def _placeholder_avatar_pixmap(user: SteamUser, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(COLORS["background_alt"]))

    label = _steam_user_label(user).strip()
    letter = label[:1].upper() if label else "?"

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(COLORS["button"]))
    painter.drawRect(0, 0, size, size)

    font = QFont(painter.font())
    font.setBold(True)
    font.setPixelSize(42)
    painter.setFont(font)
    painter.setPen(QColor(COLORS["text"]))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()
    return pixmap


def _user_pixmap(user: SteamUser) -> QPixmap:
    if user.avatar_path is not None:
        source = QPixmap(str(user.avatar_path))
        if not source.isNull():
            return _square_avatar_pixmap(source, _AVATAR_SIZE)

    return _placeholder_avatar_pixmap(user, _AVATAR_SIZE)


def _info_pixmap(size: int, color: QColor) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = painter.pen()
    pen.setColor(color)
    pen.setWidthF(1.8)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = 2
    painter.drawEllipse(inset, inset, size - (inset * 2), size - (inset * 2))

    font = QFont(painter.font())
    font.setBold(False)
    font.setPixelSize(max(12, int(size * 0.58)))
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(
        pixmap.rect().adjusted(0, -1, 0, -1),
        Qt.AlignmentFlag.AlignCenter,
        "i",
    )
    painter.end()
    return pixmap


class AvatarLabel(QLabel):
    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        if self._pixmap.isNull():
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self._background_color())
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        painter.setClipPath(path)
        painter.drawPixmap(self.rect(), self._pixmap)
        painter.end()

    def _background_color(self) -> QColor:
        parent = self.parentWidget()
        if parent is not None and bool(parent.property("selected")):
            return QColor(COLORS["button_pressed"])
        if parent is not None and parent.underMouse():
            return QColor(COLORS["border"])
        return QColor(COLORS["background_alt"])


class SteamUserTile(QFrame):
    def __init__(
        self,
        user: SteamUser,
        *,
        on_select: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.account_id = user.account_id
        self._on_select = on_select
        self.setObjectName("steamUserTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(_TILE_SIZE)
        self.setStyleSheet(
            "QFrame#steamUserTile {"
            f" background: {COLORS['background_alt']};"
            f" border: 1px solid {COLORS['border_light']};"
            " border-radius: 8px;"
            "}"
            "QFrame#steamUserTile:hover {"
            f" background: {COLORS['border']};"
            f" border-color: {COLORS['accent']};"
            "}"
            "QFrame#steamUserTile[selected='true'] {"
            f" background: {COLORS['button_pressed']};"
            f" border-color: {COLORS['highlight']};"
            " border-width: 2px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(7)

        self._avatar = AvatarLabel(_user_pixmap(user), self)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        name = QLabel(_steam_user_label(user), self)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("background: transparent;font-size: 13px;font-weight: 600;")
        name.setWordWrap(True)
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(name, 1)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self._avatar.update()
        self.update()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._avatar.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._avatar.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self._on_select(self.account_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SteamUserDialog(QDialog):
    def __init__(self, users: list[SteamUser], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(580)
        self._users = users
        self._tiles: dict[str, SteamUserTile] = {}
        self._selected_account_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 22)
        layout.setSpacing(18)

        heading = QLabel(_("Choose Steam User"), self)
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)

        description = QLabel(
            _("Select the Steam account for library artwork changes."), self
        )
        description.setStyleSheet(f"color: {COLORS['text_disabled']};")
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addSpacing(4)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(20)
        for index, user in enumerate(users):
            tile = SteamUserTile(user, on_select=self._select_account, parent=self)
            self._tiles[user.account_id] = tile
            row = index // _TILE_COLUMNS
            column = index % _TILE_COLUMNS
            grid.addWidget(tile, row, column)

        layout.addLayout(grid)
        self._select_account(self._default_account_id())
        layout.addSpacing(4)

        details_row = QFrame(self)
        details_row.setObjectName("steamUserInfo")
        details_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        details_row.setStyleSheet(
            "QFrame#steamUserInfo {"
            f" background: {COLORS['background_alt']};"
            f" border: 1px solid {COLORS['border']};"
            " border-radius: 8px;"
            "}"
        )
        details_layout = QHBoxLayout(details_row)
        details_layout.setContentsMargins(10, 9, 10, 9)
        details_layout.setSpacing(10)

        info_label = QLabel(details_row)
        info_label.setStyleSheet("background: transparent;")
        info_label.setPixmap(_info_pixmap(32, self.palette().placeholderText().color()))
        info_label.setFixedSize(QSize(40, 44))
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details_layout.addWidget(info_label, 0, Qt.AlignmentFlag.AlignVCenter)

        details = QLabel(
            _(
                "Steam stores library artwork separately for each user account. "
                "The selected account is used when applying artwork updates. "
                "Metadata edits are written to shared Steam app data and apply to "
                "all users on this computer."
            ),
            details_row,
        )
        details.setStyleSheet(
            "background: transparent;"
            f"color: {COLORS['text_disabled']};"
            "font-size: 12px;"
            "padding-top: 2px;"
        )
        details.setWordWrap(True)
        details_layout.addWidget(details, 1)
        layout.addWidget(details_row)
        layout.addSpacing(8)

        action_icon_color = self.palette().placeholderText().color()
        actions = QWidget(self)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(12)

        apply_icon = QIcon.fromTheme(
            "dialog-ok-apply",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
        )
        select_button = QPushButton(
            QIcon(monochrome_icon_pixmap(apply_icon, 24, action_icon_color)),
            _("Select"),
            actions,
        )
        select_button.setIconSize(QSize(24, 24))
        select_button.clicked.connect(self.accept)

        if len(users) <= 2:
            select_button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            select_button.setMinimumHeight(40)
            select_button.setMaximumHeight(40)
        else:
            actions_layout.addStretch(1)
            select_button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )
            select_button.setFixedSize(QSize(190, 40))

        actions_layout.addWidget(select_button)

        layout.addWidget(actions)
        self.setFixedSize(self.sizeHint())

    @property
    def selected_account_id(self) -> str | None:
        return self._selected_account_id

    def _default_account_id(self) -> str:
        most_recent = next((user for user in self._users if user.is_most_recent), None)
        return (most_recent or self._users[0]).account_id

    def _select_account(self, account_id: str) -> None:
        self._selected_account_id = account_id
        for tile_account_id, tile in self._tiles.items():
            tile.set_selected(tile_account_id == account_id)
