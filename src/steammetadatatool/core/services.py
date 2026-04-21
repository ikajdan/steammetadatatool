from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .appinfo import AppInfoFile
from .models import AppSummary, ChangeMap, OverrideInput, SetValue
from .writer import rewrite_appinfo

CHANGE_FIELDS = (
    "name",
    "sort_as",
    "aliases",
    "developer",
    "publisher",
    "original_release_date",
    "steam_release_date",
)


def parse_set_arg(raw: str) -> SetValue:
    if "=" not in raw:
        raise ValueError("expected PATH=VALUE")
    path_s, value_s = raw.split("=", 1)
    path = [p for p in path_s.split(".") if p]
    if not path:
        raise ValueError("empty PATH")

    value: Any = value_s
    if value_s.isdigit():
        value = int(value_s)
    return path, value


def parse_aliases(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON for --aliases: {exc}")
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            raise ValueError("--aliases JSON must be an array of strings")
        return [x.strip() for x in val if x.strip()]

    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def has_any_overrides(overrides: OverrideInput) -> bool:
    return any(
        value is not None
        for value in (
            overrides.name,
            overrides.sort_as,
            overrides.aliases,
            overrides.developer,
            overrides.publisher,
            overrides.original_release_date,
            overrides.steam_release_date,
        )
    ) or bool(overrides.set_values)


def list_app_summaries(path: str | Path) -> list[AppSummary]:
    summaries: list[AppSummary] = []
    with AppInfoFile.open(path) as appinfo:
        for app in appinfo.iter_apps():
            summaries.append(AppSummary(appid=app.appid, name=app.name or ""))
    return summaries


def load_changes_file(path: Path) -> ChangeMap:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not read --changes-file: {exc}")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in --changes-file: {exc}")

    if not isinstance(payload, dict):
        raise ValueError("--changes-file must contain a JSON object")

    apps = payload.get("apps")
    if not isinstance(apps, list):
        raise ValueError("--changes-file must contain an 'apps' array")

    out: ChangeMap = {}
    for i, app_raw in enumerate(apps):
        where = f"apps[{i}]"
        if not isinstance(app_raw, dict):
            raise ValueError(f"{where} must be an object")

        appid = app_raw.get("appid")
        if not isinstance(appid, int) or isinstance(appid, bool) or appid <= 0:
            raise ValueError(f"{where}.appid must be a positive integer")

        values = _build_override_values(app_raw, where=where)

        if appid in out:
            out[appid].update(values)
        else:
            out[appid] = values

    return out


def write_changes_file(path: Path, changes: ChangeMap) -> None:
    merged: ChangeMap = {}
    payload: dict[str, Any] = {}

    if path.exists():
        try:
            raw_text = path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except OSError as exc:
            raise ValueError(f"could not read --write-changes-file: {exc}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in --write-changes-file target: {exc}")

        if not isinstance(payload, dict):
            raise ValueError("--write-changes-file target must contain a JSON object")

        merged = load_changes_file(path)

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
    except OSError as exc:
        raise ValueError(f"could not write --write-changes-file: {exc}")


def print_appinfo_lines(
    *,
    path: Path,
    appids: list[int] | None,
    overrides: OverrideInput,
    file_changes: ChangeMap,
    as_json: bool,
) -> list[str]:
    lines: list[str] = []
    with AppInfoFile.open(path) as appinfo:
        if as_json:
            for app in appinfo.iter_apps(appids=appids):
                _apply_overrides_for_app(app.data, app.appid, overrides, file_changes)
                payload = asdict(app)
                payload["last_updated"] = app.last_updated.isoformat()
                payload["sha1"] = app.sha1.hex()
                payload["binary_data_sha1"] = (
                    app.binary_data_sha1.hex() if app.binary_data_sha1 else None
                )
                lines.append(json.dumps(payload, ensure_ascii=False))
            return lines

        for app in appinfo.iter_apps(appids=appids):
            _apply_overrides_for_app(app.data, app.appid, overrides, file_changes)
            name = app.name or ""
            lines.append(f"{app.appid}\t{name}")
    return lines


def write_modified_appinfo(
    *,
    path: Path,
    appids: set[int],
    overrides: OverrideInput,
    file_changes: ChangeMap,
    write_out: Path | None,
) -> Path:
    if write_out is not None:
        rewrite_appinfo(
            in_path=path,
            out_path=write_out,
            appids_to_modify=appids,
            apply_overrides=lambda kv, appid: _apply_overrides_for_app(
                kv, appid, overrides, file_changes
            ),
        )
        return write_out

    tmp_dir = path.parent
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=tmp_dir,
        prefix=path.name + ".",
        suffix=".tmp",
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        rewrite_appinfo(
            in_path=path,
            out_path=tmp_path,
            appids_to_modify=appids,
            apply_overrides=lambda kv, appid: _apply_overrides_for_app(
                kv, appid, overrides, file_changes
            ),
        )

        backup_path = _timestamped_backup_path(path)
        path.replace(backup_path)
        tmp_path.replace(path)
        return path
    finally:
        if tmp_path.exists():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def effective_changes_for_appids(
    appids: set[int], overrides: OverrideInput, file_changes: ChangeMap
) -> ChangeMap:
    out: ChangeMap = {}
    cli_values = _override_values(overrides)

    for appid in appids:
        values: dict[str, Any] = {}
        values.update(cli_values)
        if appid in file_changes:
            values.update(file_changes[appid])
        if values:
            out[appid] = values

    return out


def _build_override_values(raw: dict[str, Any], *, where: str) -> dict[str, Any]:
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
        raise ValueError(
            f"{where}: unknown field(s): {', '.join(sorted(unknown_keys))}"
        )

    values: dict[str, Any] = {}

    if "name" in raw:
        if not isinstance(raw["name"], str):
            raise ValueError(f"{where}: name must be a string")
        values["name"] = raw["name"]

    if "sort_as" in raw:
        if not isinstance(raw["sort_as"], str):
            raise ValueError(f"{where}: sort_as must be a string")
        values["sort_as"] = raw["sort_as"]

    if "aliases" in raw:
        aliases = raw["aliases"]
        if not isinstance(aliases, list) or not all(
            isinstance(x, str) for x in aliases
        ):
            raise ValueError(f"{where}: aliases must be an array of strings")
        values["aliases"] = [x.strip() for x in aliases if x.strip()]

    if "developer" in raw:
        if not isinstance(raw["developer"], str):
            raise ValueError(f"{where}: developer must be a string")
        values["developer"] = raw["developer"]

    if "publisher" in raw:
        if not isinstance(raw["publisher"], str):
            raise ValueError(f"{where}: publisher must be a string")
        values["publisher"] = raw["publisher"]

    if "original_release_date" in raw:
        if not isinstance(raw["original_release_date"], str):
            raise ValueError(
                f"{where}: original_release_date must be a string (YYYY-MM-DD)"
            )
        values["original_release_date"] = raw["original_release_date"]

    if "steam_release_date" in raw:
        if not isinstance(raw["steam_release_date"], str):
            raise ValueError(
                f"{where}: steam_release_date must be a string (YYYY-MM-DD)"
            )
        values["steam_release_date"] = raw["steam_release_date"]

    return values


def _changes_map_to_apps(changes: ChangeMap) -> list[dict[str, Any]]:
    apps: list[dict[str, Any]] = []
    for appid in sorted(changes.keys()):
        entry = {"appid": appid}
        for key in CHANGE_FIELDS:
            if key in changes[appid]:
                entry[key] = changes[appid][key]
        apps.append(entry)
    return apps


def _deep_set(obj: dict[str, Any], path: list[str], value: Any) -> None:
    cur: dict[str, Any] = obj
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def _parse_date_to_unix(date_s: str) -> int:
    dt = datetime.strptime(date_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _override_values(overrides: OverrideInput) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if overrides.name is not None:
        values["name"] = overrides.name
    if overrides.sort_as is not None:
        values["sort_as"] = overrides.sort_as
    if overrides.aliases is not None:
        values["aliases"] = overrides.aliases
    if overrides.developer is not None:
        values["developer"] = overrides.developer
    if overrides.publisher is not None:
        values["publisher"] = overrides.publisher
    if overrides.original_release_date is not None:
        values["original_release_date"] = overrides.original_release_date
    if overrides.steam_release_date is not None:
        values["steam_release_date"] = overrides.steam_release_date
    if overrides.set_values:
        values["set_values"] = overrides.set_values
    return values


def _apply_overrides_for_app(
    app_data: dict[str, Any],
    appid: int,
    overrides: OverrideInput,
    file_changes: ChangeMap,
) -> None:
    _apply_override_values(app_data, _override_values(overrides))
    file_values = file_changes.get(appid)
    if file_values:
        _apply_override_values(app_data, file_values)


def _apply_override_values(app_data: dict[str, Any], values: dict[str, Any]) -> None:
    def update_associations(
        root_path: list[str], assoc_type: str, new_name: str
    ) -> None:
        cur: Any = app_data
        for part in root_path:
            if not isinstance(cur, dict):
                return
            cur = cur.get(part)
        if not isinstance(cur, dict):
            return

        assoc = cur.get("associations")
        if not isinstance(assoc, dict):
            cur["associations"] = {"0": {"type": assoc_type, "name": new_name}}
            return

        touched = False
        for entry in assoc.values():
            if isinstance(entry, dict) and entry.get("type") == assoc_type:
                entry["name"] = new_name
                touched = True

        if not touched:
            numeric = [
                int(k) for k in assoc.keys() if isinstance(k, str) and k.isdigit()
            ]
            nxt = str(max(numeric) + 1) if numeric else "0"
            assoc[nxt] = {"type": assoc_type, "name": new_name}

    name = values.get("name")
    if name is not None:
        _deep_set(app_data, ["appinfo", "common", "name"], name)
        _deep_set(app_data, ["common", "name"], name)

    sort_as = values.get("sort_as")
    if sort_as is not None:
        _deep_set(app_data, ["appinfo", "common", "sortas"], sort_as)
        _deep_set(app_data, ["common", "sortas"], sort_as)

    aliases = values.get("aliases")
    if aliases is not None:
        aliases_s = ", ".join(aliases)
        _deep_set(app_data, ["appinfo", "common", "aliases"], aliases_s)
        _deep_set(app_data, ["common", "aliases"], aliases_s)

    developer = values.get("developer")
    if developer is not None:
        _deep_set(app_data, ["appinfo", "extended", "developer"], developer)
        _deep_set(app_data, ["extended", "developer"], developer)
        update_associations(["appinfo", "common"], "developer", developer)
        update_associations(["common"], "developer", developer)

    publisher = values.get("publisher")
    if publisher is not None:
        _deep_set(app_data, ["appinfo", "extended", "publisher"], publisher)
        _deep_set(app_data, ["extended", "publisher"], publisher)
        update_associations(["appinfo", "common"], "publisher", publisher)
        update_associations(["common"], "publisher", publisher)

    original_release_date = values.get("original_release_date")
    if original_release_date is not None:
        ts = _parse_date_to_unix(original_release_date)
        _deep_set(app_data, ["appinfo", "common", "original_release_date"], ts)
        _deep_set(app_data, ["common", "original_release_date"], ts)

    steam_release_date = values.get("steam_release_date")
    if steam_release_date is not None:
        ts = _parse_date_to_unix(steam_release_date)
        _deep_set(app_data, ["appinfo", "common", "steam_release_date"], ts)
        _deep_set(app_data, ["common", "steam_release_date"], ts)

    set_values = values.get("set_values")
    if set_values:
        for path, value in set_values:
            _deep_set(app_data, path, value)


def _timestamped_backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    candidate = path.with_name(path.name + "_" + stamp + ".bak")

    if candidate.exists():
        raise RuntimeError("backup filename already exists: " + str(candidate))

    return candidate
