from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ChangeMap = dict[int, dict[str, Any]]
CHANGE_FIELDS = (
    "name",
    "sort_as",
    "aliases",
    "developer",
    "publisher",
    "original_release_date",
    "steam_release_date",
)


def _build_override_values(raw: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "appid",
        "name",
        "sort_as",
        "aliases",
        "developer",
        "publisher",
        "original_release_date",
        "steam_release_date",
    }
    unknown_keys = [k for k in raw.keys() if k not in allowed_keys]
    if unknown_keys:
        raise argparse.ArgumentTypeError(
            f"unknown field(s): {', '.join(sorted(unknown_keys))}"
        )

    values: dict[str, Any] = {}

    if "name" in raw:
        if not isinstance(raw["name"], str):
            raise argparse.ArgumentTypeError("name must be a string")
        values["name"] = raw["name"]

    if "sort_as" in raw:
        if not isinstance(raw["sort_as"], str):
            raise argparse.ArgumentTypeError("sort_as must be a string")
        values["sort_as"] = raw["sort_as"]

    if "aliases" in raw:
        aliases = raw["aliases"]
        if not isinstance(aliases, list) or not all(
            isinstance(x, str) for x in aliases
        ):
            raise argparse.ArgumentTypeError("aliases must be an array of strings")
        values["aliases"] = [x.strip() for x in aliases if x.strip()]

    if "developer" in raw:
        if not isinstance(raw["developer"], str):
            raise argparse.ArgumentTypeError("developer must be a string")
        values["developer"] = raw["developer"]

    if "publisher" in raw:
        if not isinstance(raw["publisher"], str):
            raise argparse.ArgumentTypeError("publisher must be a string")
        values["publisher"] = raw["publisher"]

    if "original_release_date" in raw:
        if not isinstance(raw["original_release_date"], str):
            raise argparse.ArgumentTypeError(
                "original_release_date must be a string (YYYY-MM-DD)"
            )
        values["original_release_date"] = raw["original_release_date"]

    if "steam_release_date" in raw:
        if not isinstance(raw["steam_release_date"], str):
            raise argparse.ArgumentTypeError(
                "steam_release_date must be a string (YYYY-MM-DD)"
            )
        values["steam_release_date"] = raw["steam_release_date"]

    return values


def _load_changes_file(path: Path) -> ChangeMap:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise argparse.ArgumentTypeError(f"could not read --changes-file: {e}")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"invalid JSON in --changes-file: {e}")

    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("--changes-file must contain a JSON object")

    apps = payload.get("apps")
    if not isinstance(apps, list):
        raise argparse.ArgumentTypeError("--changes-file must contain an 'apps' array")

    out: ChangeMap = {}
    for i, app_raw in enumerate(apps):
        where = f"apps[{i}]"
        if not isinstance(app_raw, dict):
            raise argparse.ArgumentTypeError(f"{where} must be an object")

        appid = app_raw.get("appid")
        if not isinstance(appid, int) or isinstance(appid, bool) or appid <= 0:
            raise argparse.ArgumentTypeError(
                f"{where}.appid must be a positive integer"
            )

        try:
            values = _build_override_values(app_raw)
        except argparse.ArgumentTypeError as e:
            raise argparse.ArgumentTypeError(f"{where}: {e}")

        if appid in out:
            out[appid].update(values)
        else:
            out[appid] = values

    return out


def _changes_map_to_apps(changes: ChangeMap) -> list[dict[str, Any]]:
    apps: list[dict[str, Any]] = []
    for appid in sorted(changes.keys()):
        entry = {"appid": appid}
        for key in CHANGE_FIELDS:
            if key in changes[appid]:
                entry[key] = changes[appid][key]
        apps.append(entry)
    return apps


def _write_changes_file(path: Path, changes: ChangeMap) -> None:
    merged: ChangeMap = {}
    payload: dict[str, Any] = {}

    if path.exists():
        try:
            raw_text = path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except OSError as e:
            raise argparse.ArgumentTypeError(
                f"could not read --write-changes-file: {e}"
            )
        except json.JSONDecodeError as e:
            raise argparse.ArgumentTypeError(
                f"invalid JSON in --write-changes-file target: {e}"
            )

        if not isinstance(payload, dict):
            raise argparse.ArgumentTypeError(
                "--write-changes-file target must contain a JSON object"
            )

        try:
            merged = _load_changes_file(path)
        except argparse.ArgumentTypeError as e:
            raise argparse.ArgumentTypeError(f"invalid existing changes file: {e}")

    for appid, values in changes.items():
        if appid in merged:
            merged[appid].update(values)
        else:
            merged[appid] = dict(values)

    output = {
        "format": payload.get("format", "appinfo-changes"),
        "version": payload.get("version", 1),
        "created_at": payload.get("created_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apps": _changes_map_to_apps(merged),
    }

    try:
        path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as e:
        raise argparse.ArgumentTypeError(f"could not write --write-changes-file: {e}")
