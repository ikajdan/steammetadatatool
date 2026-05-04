# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from steammetadatatool.core.appinfo import find_steam_appinfo_path
from steammetadatatool.core.models import OverrideInput
from steammetadatatool.core.services import load_metadata_file, write_modified_appinfo
from steammetadatatool.gui.data.app_data import app_data_path


def apply_metadata_file_silently(path: str | None) -> None:
    metadata_path = app_data_path("metadata.json")
    if not metadata_path.exists():
        return

    metadata_overrides = load_metadata_file(metadata_path)
    if not metadata_overrides:
        return

    appinfo_path = Path(path).expanduser() if path else find_steam_appinfo_path()
    if appinfo_path is None or not appinfo_path.is_file():
        raise ValueError("Could not locate appinfo.vdf")

    write_modified_appinfo(
        path=appinfo_path,
        appids=set(metadata_overrides.keys()),
        overrides=OverrideInput(),
        metadata_overrides=metadata_overrides,
        write_out=None,
        create_backup=True,
        backup_once_per_day=True,
    )
