# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from steammetadatatool.gui.data.app_data import app_data_path
from steammetadatatool.gui.steam.paths import steam_grid_dir


def copy_logo_position_files() -> int:
    grid_dir = steam_grid_dir()
    copied_count = 0
    selected_hero_names = _selected_hero_names_by_appid()

    for source_path in sorted(grid_dir.glob("*.json")):
        appid = source_path.stem
        if not appid.isdigit() or not source_path.is_file():
            continue

        preset_name = _preset_name_for_hero(selected_hero_names.get(appid))
        target_path = app_data_path("assets", appid, "preset", preset_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_path.read_bytes())
        copied_count += 1

    return copied_count


def import_logo_position_files() -> int:
    copied_count = copy_logo_position_files()
    print_logo_position_import_summary(copied_count)
    return copied_count


def print_logo_position_import_summary(copied_count: int) -> None:
    if copied_count == 0:
        print("No logo position files were found to import.")
    elif copied_count == 1:
        print("Imported 1 logo position file.")
    else:
        print(f"Imported {copied_count} logo position files.")


def _selected_hero_names_by_appid() -> dict[str, str]:
    manifest_path = app_data_path("assets.json")
    if not manifest_path.is_file():
        return {}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(manifest, dict):
        return {}

    selected_names: dict[str, str] = {}
    for appid, raw_entry in manifest.items():
        if appid == "version" or not isinstance(raw_entry, dict):
            continue

        hero_name = _string_value(raw_entry.get("hero"))
        if hero_name is not None:
            selected_names[str(appid)] = hero_name

    return selected_names


def _string_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped or None


def _preset_name_for_hero(hero_name: str | None) -> str:
    if hero_name is None:
        return "0.json"

    stem = Path(hero_name).stem.strip()
    return f"{stem or '0'}.json"
