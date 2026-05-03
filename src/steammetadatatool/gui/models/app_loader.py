# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from steammetadatatool.gui.models.app_details import read_app_rows


class AppLoadWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    @Slot()
    def run(self) -> None:
        try:
            path_obj = Path(self._path).expanduser()
            if not path_obj.is_file():
                raise FileNotFoundError(f"Path is not a file:\n{path_obj}")

            rows, details_by_appid, filter_matches_by_appid = read_app_rows(path_obj)
            self.loaded.emit(
                (path_obj, rows, details_by_appid, filter_matches_by_appid)
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()
