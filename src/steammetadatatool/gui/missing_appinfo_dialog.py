# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _existing_parent_dir(path_obj: Path) -> Path:
    current = path_obj if path_obj.is_dir() else path_obj.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return current if current.is_dir() else Path.home()


def _select_appinfo_file(parent: QWidget, initial_dir: Path) -> Path | None:
    selected_path, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        "Select appinfo.vdf",
        str(_existing_parent_dir(initial_dir)),
        "Steam appinfo (appinfo.vdf);;VDF files (*.vdf);;All files (*)",
    )
    if not selected_path:
        return None

    return Path(selected_path)


class MissingAppInfoDialog(QDialog):
    def __init__(
        self,
        missing_path: Path | None,
        initial_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._initial_dir = initial_dir
        self.selected_path: Path | None = None
        self.setWindowTitle("SteamMetadataTool")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(16)

        heading = QLabel("Steam Metadata File not Found", self)
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        if missing_path is None:
            description_text = (
                "SteamMetadataTool needs appinfo.vdf file to list apps and show "
                "the metadata. The file could not be found automatically."
            )
        else:
            description_text = (
                "SteamMetadataTool needs appinfo.vdf file to list apps and show "
                "the metadata. The selected path is not a valid appinfo.vdf file:"
            )
        description = QLabel(description_text, self)
        description.setWordWrap(True)
        layout.addWidget(description)

        if missing_path is not None:
            path_panel = QFrame(self)
            path_panel.setFrameShape(QFrame.Shape.NoFrame)
            path_layout = QVBoxLayout(path_panel)
            path_layout.setContentsMargins(0, 0, 0, 0)
            path_layout.setSpacing(4)

            path_label = QLabel(str(missing_path), path_panel)
            path_label.setWordWrap(True)
            path_label.setTextInteractionFlags(
                path_label.textInteractionFlags()
                | Qt.TextInteractionFlag.TextSelectableByMouse
            )
            path_label.setStyleSheet(
                f"color: {self.palette().text().color().name()};"
                " font-family: monospace;"
            )
            path_layout.addWidget(path_label)
            layout.addWidget(path_panel)

        next_step = QLabel(
            "Choose a correct appinfo.vdf file to continue.",
            self,
        )
        next_step.setWordWrap(True)
        layout.addWidget(next_step)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 2, 0, 0)
        actions.setSpacing(10)
        actions.addStretch(1)
        select_button = QPushButton("Select File...", self)
        select_button.setMinimumHeight(36)
        select_button.setMinimumWidth(140)
        select_button.clicked.connect(self._select_file)
        actions.addWidget(select_button)
        quit_button = QPushButton("Quit", self)
        quit_button.setMinimumHeight(36)
        quit_button.setMinimumWidth(100)
        quit_button.clicked.connect(self.reject)
        actions.addWidget(quit_button)
        layout.addLayout(actions)

    def _select_file(self) -> None:
        selected_path = _select_appinfo_file(self, self._initial_dir)
        if selected_path is None:
            return

        self.selected_path = selected_path
        self.accept()


def select_missing_appinfo_file(parent: QWidget, missing_path: Path) -> Path | None:
    parent_dir = _existing_parent_dir(missing_path)
    dialog = MissingAppInfoDialog(missing_path, parent_dir, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_path

    QApplication.quit()
    return None


def select_appinfo_file_after_detection_failed(parent: QWidget) -> Path | None:
    dialog = MissingAppInfoDialog(None, Path.home(), parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_path

    QApplication.quit()
    return None
