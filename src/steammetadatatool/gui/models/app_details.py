# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from steammetadatatool.core.appinfo import AppInfoFile
from steammetadatatool.core.keyvalues import kv_deep_get
from steammetadatatool.core.services import (
    metadata_values_from_change_entries,
    parse_aliases,
)
from steammetadatatool.gui.steam.assets import asset_paths_for_app

INLINE_EDIT_METADATA_KEYS = {
    "name": "appinfo.common.name",
    "sort_as": "appinfo.common.sortas",
    "aliases": "appinfo.common.aliases",
    "developer": "appinfo.extended.developer",
    "publisher": "appinfo.extended.publisher",
    "release_date": "appinfo.common.original_release_date",
}

INLINE_DETAIL_EDITOR_STYLE = """
QLineEdit {
    background: transparent;
    border: 1px solid transparent;
    padding: 0;
}

QLineEdit:hover {
    background-color: palette(alternate-base);
    border-color: palette(mid);
}

QLineEdit:focus {
    background-color: palette(base);
    border-color: palette(highlight);
}

QLineEdit:disabled {
    background: transparent;
    border-color: transparent;
}
"""

DETAIL_VALUE_LEFT_INSET = 3


def library_logo_position(data: dict[str, Any]) -> dict[str, Any] | None:
    position = kv_deep_get(
        data,
        "appinfo",
        "common",
        "library_assets_full",
        "library_logo",
        "logo_position",
    )
    if isinstance(position, dict):
        return position

    position = kv_deep_get(data, "appinfo", "common", "library_assets", "logo_position")
    if isinstance(position, dict):
        return position

    position = kv_deep_get(
        data, "common", "library_assets_full", "library_logo", "logo_position"
    )
    if isinstance(position, dict):
        return position

    position = kv_deep_get(data, "common", "library_assets", "logo_position")
    return position if isinstance(position, dict) else None


def float_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None


def common_value(data: dict[str, Any], key: str) -> Any:
    value = kv_deep_get(data, "appinfo", "common", key)
    if value is not None:
        return value
    return kv_deep_get(data, "common", key)


def extended_value(data: dict[str, Any], key: str) -> Any:
    value = kv_deep_get(data, "appinfo", "extended", key)
    if value is not None:
        return value
    return kv_deep_get(data, "extended", key)


def aliases_value(data: dict[str, Any]) -> Any:
    value = extended_value(data, "aliases")
    if value is not None:
        return value

    value = common_value(data, "aliases")
    if value is not None:
        return value

    return None


def sort_as_value(data: dict[str, Any]) -> Any:
    value = common_value(data, "sortas")
    if value is not None:
        return value

    value = extended_value(data, "sortas")
    if value is not None:
        return value

    return None


def format_aliases(value: Any) -> str:
    if value is None:
        return "–"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "–"
    raw = str(value).strip()
    return raw or "–"


def format_release_date(value: Any) -> str:
    if value is None:
        return "–"

    unix_value: int | None = None
    if isinstance(value, int):
        unix_value = value
    elif isinstance(value, str) and value.isdigit():
        unix_value = int(value)

    if unix_value is None:
        text = str(value).strip()
        return text or "–"

    if unix_value <= 0:
        return "–"

    try:
        return datetime.fromtimestamp(unix_value, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return str(unix_value)


def release_date_details(data: dict[str, Any]) -> tuple[str, str]:
    original_release_date = format_release_date(
        common_value(data, "original_release_date")
    )
    if original_release_date != "–":
        return original_release_date, "original_release_date"

    steam_release_date = format_release_date(common_value(data, "steam_release_date"))
    if steam_release_date != "–":
        return steam_release_date, "steam_release_date"

    return "–", "original_release_date"


def detail_text_to_metadata_value(detail_key: str, text: str) -> str:
    value = "" if text == "–" else text.strip()
    if detail_key == "aliases":
        return ", ".join(parse_aliases(value))
    return value


def merge_metadata_override_values(
    base: dict[str, Any], updates: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(base)
    update_set_values = updates.get("set_values")
    for key, value in updates.items():
        if key != "set_values":
            merged[key] = value

    if update_set_values:
        set_values_by_path: dict[tuple[str, ...], tuple[list[str], Any]] = {}
        for item in base.get("set_values") or []:
            path, value = item
            set_values_by_path[tuple(path)] = (path, value)
        for path, value in update_set_values:
            set_values_by_path[tuple(path)] = (path, value)
        merged["set_values"] = list(set_values_by_path.values())

    return merged


def metadata_overrides_from_apps_payload(
    payload: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for index, app_entry in enumerate(payload):
        raw_appid = app_entry.get("appid")
        try:
            appid = int(raw_appid)
        except (TypeError, ValueError):
            raise ValueError(f"apps[{index}].appid must be a positive integer")
        if appid <= 0:
            raise ValueError(f"apps[{index}].appid must be a positive integer")

        changes = app_entry.get("changes", [])
        if not isinstance(changes, list):
            raise ValueError(f"apps[{index}].changes must be an array")

        values = metadata_values_from_change_entries(
            changes,
            where=f"apps[{index}].changes",
        )
        out[appid] = merge_metadata_override_values(out.get(appid, {}), values)
    return out


def has_meaningful_metadata(
    value: Any,
    *,
    ignored_keys: frozenset[str] = frozenset({"appid", "name"}),
) -> bool:
    if value is None:
        return False

    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key in ignored_keys:
                continue
            if has_meaningful_metadata(nested_value, ignored_keys=ignored_keys):
                return True
        return False

    if isinstance(value, (list, tuple, set)):
        return any(
            has_meaningful_metadata(item, ignored_keys=ignored_keys) for item in value
        )

    if isinstance(value, str):
        return bool(value.strip())

    return True


def matches_game_filter(data: dict[str, Any]) -> bool:
    app_type = str(common_value(data, "type") or "").strip().casefold()
    if app_type != "game":
        return False

    return has_meaningful_metadata(data)


def details_for_app(app: Any) -> dict[str, Any]:
    name = (app.name or "").strip()
    asset_paths = asset_paths_for_app(app.appid)
    release_date, release_date_key = release_date_details(app.data)
    return {
        "_raw_metadata": app.data,
        "appid": str(app.appid),
        "name": name or "–",
        "sort_as": str(sort_as_value(app.data) or "–"),
        "aliases": format_aliases(aliases_value(app.data)),
        "developer": str(extended_value(app.data, "developer") or "–"),
        "publisher": str(extended_value(app.data, "publisher") or "–"),
        "release_date": release_date,
        "_release_date_key": release_date_key,
        "header_path": asset_paths["header_path"],
        "capsule_path": asset_paths["capsule_path"],
        "hero_path": asset_paths["hero_path"],
        "logo_path": asset_paths["logo_path"],
        "logo_position": library_logo_position(app.data),
        "icon_path": asset_paths["icon_path"],
    }


def read_app_rows(
    path: Path,
) -> tuple[list[tuple[int, str]], dict[int, dict[str, Any]], dict[int, bool]]:
    rows: list[tuple[int, str]] = []
    details_by_appid: dict[int, dict[str, Any]] = {}
    filter_matches_by_appid: dict[int, bool] = {}

    with AppInfoFile.open(path) as appinfo:
        for app in appinfo.iter_apps():
            name = (app.name or "").strip()
            if not name:
                continue

            rows.append((app.appid, name))
            filter_matches_by_appid[app.appid] = matches_game_filter(app.data)
            details_by_appid[app.appid] = details_for_app(app)

    return rows, details_by_appid, filter_matches_by_appid
