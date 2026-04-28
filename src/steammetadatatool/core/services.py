# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .appinfo import AppInfoFile
from .models import AppSummary, MetadataMap, OverrideInput, SetValue
from .writer import rewrite_appinfo


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


def load_metadata_file(path: Path) -> MetadataMap:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not read --metadata-file: {exc}")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in --metadata-file: {exc}")

    apps = _normalize_metadata_apps_payload(payload)

    out: MetadataMap = {}
    for i, app_raw in enumerate(apps):
        where = f"apps[{i}]"
        if not isinstance(app_raw, dict):
            raise ValueError(f"{where} must be an object")

        appid = _parse_metadata_appid(app_raw.get("appid"), where=where)

        if "changes" in app_raw:
            values = _build_override_values_from_change_entries(app_raw, where=where)
        else:
            values = _build_override_values(app_raw, where=where)

        if appid in out:
            out[appid].update(values)
        else:
            out[appid] = values

    return out


def write_metadata_file(
    path: Path, metadata: MetadataMap, *, source_path: Path | None = None
) -> None:
    existing_entries: list[dict[str, Any]] = []
    if path.exists():
        try:
            raw_text = path.read_text(encoding="utf-8")
            existing_payload = json.loads(raw_text)
        except OSError as exc:
            raise ValueError(f"could not read --metadata-file: {exc}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in --metadata-file target: {exc}")
        existing_entries = _normalize_metadata_apps_payload(existing_payload)

    generated_entries = _metadata_map_to_apps(metadata, source_path=source_path)
    for generated_entry in generated_entries:
        generated_appid = str(generated_entry["appid"])
        merged = False
        for existing_entry in existing_entries:
            if str(existing_entry.get("appid")) != generated_appid:
                continue

            existing_changes = existing_entry.get("changes")
            if not isinstance(existing_changes, list):
                existing_changes = []
                existing_entry["changes"] = existing_changes

            existing_changes_by_key = {
                str(item.get("key")): item
                for item in existing_changes
                if isinstance(item, dict) and item.get("key") is not None
            }
            for generated_change in generated_entry.get("changes", []):
                if not isinstance(generated_change, dict):
                    continue
                key = str(generated_change.get("key"))
                existing_change = existing_changes_by_key.get(key)
                if existing_change is None:
                    existing_changes.append(generated_change)
                    continue

                if not existing_change.get("old_value"):
                    existing_change["old_value"] = generated_change.get("old_value", "")
                existing_change["new_value"] = generated_change.get("new_value", "")

            merged = True
            break

        if not merged:
            existing_entries.append(generated_entry)

    try:
        path.write_text(
            json.dumps(existing_entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ValueError(f"could not write --metadata-file: {exc}")


def print_appinfo_lines(
    *,
    path: Path,
    appids: list[int] | None,
    overrides: OverrideInput,
    metadata_overrides: MetadataMap,
    as_json: bool,
) -> list[str]:
    lines: list[str] = []
    with AppInfoFile.open(path) as appinfo:
        if as_json:
            for app in appinfo.iter_apps(appids=appids):
                _apply_overrides_for_app(
                    app.data, app.appid, overrides, metadata_overrides
                )
                payload = asdict(app)
                payload["last_updated"] = app.last_updated.isoformat()
                payload["sha1"] = app.sha1.hex()
                payload["binary_data_sha1"] = (
                    app.binary_data_sha1.hex() if app.binary_data_sha1 else None
                )
                lines.append(json.dumps(payload, ensure_ascii=False))
            return lines

        for app in appinfo.iter_apps(appids=appids):
            _apply_overrides_for_app(app.data, app.appid, overrides, metadata_overrides)
            name = app.name or ""
            lines.append(f"{app.appid}\t{name}")
    return lines


def write_modified_appinfo(
    *,
    path: Path,
    appids: set[int],
    overrides: OverrideInput,
    metadata_overrides: MetadataMap,
    write_out: Path | None,
) -> Path:
    if write_out is not None:
        rewrite_appinfo(
            in_path=path,
            out_path=write_out,
            appids_to_modify=appids,
            apply_overrides=lambda kv, appid: _apply_overrides_for_app(
                kv, appid, overrides, metadata_overrides
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
                kv, appid, overrides, metadata_overrides
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


def effective_metadata_for_appids(
    appids: set[int], overrides: OverrideInput, metadata_overrides: MetadataMap
) -> MetadataMap:
    out: MetadataMap = {}
    cli_values = _override_values(overrides)

    for appid in appids:
        values: dict[str, Any] = {}
        values.update(cli_values)
        if appid in metadata_overrides:
            values.update(metadata_overrides[appid])
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


def _metadata_map_to_apps(
    metadata: MetadataMap, *, source_path: Path | None = None
) -> list[dict[str, Any]]:
    app_context: dict[int, dict[str, Any]] = {}
    if source_path is not None:
        with AppInfoFile.open(source_path) as appinfo:
            for app in appinfo.iter_apps(appids=metadata.keys()):
                app_context[app.appid] = {
                    "flat": dict(_flatten_metadata_entries_for_metadata_file(app.data)),
                }

    apps: list[dict[str, Any]] = []
    for appid in sorted(metadata.keys()):
        entry: dict[str, Any] = {
            "appid": str(appid),
            "changes": [],
        }
        context = app_context.get(appid, {})
        for change in _change_entries_from_values(
            metadata[appid],
            old_values=context.get("flat", {}),
        ):
            entry["changes"].append(change)
        apps.append(entry)
    return apps


def _normalize_metadata_apps_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        apps = payload.get("apps")
        if isinstance(apps, list):
            return [item for item in apps if isinstance(item, dict)]
        return [payload]
    raise ValueError("--metadata-file must contain a JSON object or array")


def _parse_metadata_appid(appid_raw: Any, *, where: str) -> int:
    if isinstance(appid_raw, int) and not isinstance(appid_raw, bool) and appid_raw > 0:
        return appid_raw
    if isinstance(appid_raw, str) and appid_raw.isdigit():
        appid = int(appid_raw)
        if appid > 0:
            return appid
    raise ValueError(f"{where}.appid must be a positive integer")


def _parse_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    lowered = value.casefold()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def _key_to_internal_override(key: str, new_value: Any) -> tuple[str, Any]:
    generic_override = (
        "set_values",
        ([part for part in key.split(".") if part], _parse_scalar(new_value)),
    )

    if key in {"appinfo.common.name", "common.name"}:
        return "name", str(new_value)
    if key in {"appinfo.common.sortas", "common.sortas"}:
        return "sort_as", str(new_value)
    if key in {"appinfo.extended.developer", "extended.developer"}:
        return "developer", str(new_value)
    if key in {"appinfo.extended.publisher", "extended.publisher"}:
        return "publisher", str(new_value)
    if key in {
        "appinfo.common.original_release_date",
        "common.original_release_date",
    }:
        if (
            isinstance(new_value, str)
            and len(new_value) == 10
            and new_value[4] == "-"
            and new_value[7] == "-"
        ):
            return "original_release_date", new_value
        return generic_override
    if key in {
        "appinfo.common.steam_release_date",
        "common.steam_release_date",
    }:
        if (
            isinstance(new_value, str)
            and len(new_value) == 10
            and new_value[4] == "-"
            and new_value[7] == "-"
        ):
            return "steam_release_date", new_value
        return generic_override
    if key in {"appinfo.common.aliases", "common.aliases"}:
        return "aliases", parse_aliases(str(new_value))
    return generic_override


def _build_override_values_from_change_entries(
    raw: dict[str, Any], *, where: str
) -> dict[str, Any]:
    allowed_keys = {"appid", "changes"}
    unknown_keys = [k for k in raw.keys() if k not in allowed_keys]
    if unknown_keys:
        raise ValueError(
            f"{where}: unknown field(s): {', '.join(sorted(unknown_keys))}"
        )

    changes = raw.get("changes")
    if not isinstance(changes, list):
        raise ValueError(f"{where}.changes must be an array")

    values: dict[str, Any] = {}
    set_values: list[SetValue] = []
    for index, change in enumerate(changes):
        change_where = f"{where}.changes[{index}]"
        if not isinstance(change, dict):
            raise ValueError(f"{change_where} must be an object")

        key = change.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{change_where}.key must be a non-empty string")
        if "new_value" not in change:
            raise ValueError(f"{change_where}.new_value is required")

        internal_key, internal_value = _key_to_internal_override(
            key.strip(), change["new_value"]
        )
        if internal_key == "set_values":
            set_values.append(internal_value)
        else:
            values[internal_key] = internal_value

    if set_values:
        values["set_values"] = set_values
    return values


def _format_metadata_file_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _flatten_metadata_entries_for_metadata_file(
    value: Any,
    prefix: str = "",
) -> list[tuple[str, str]]:
    if isinstance(value, dict):
        if not value:
            return [(prefix or "(root)", "{}")]

        entries: list[tuple[str, str]] = []
        for key, nested_value in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            entries.extend(
                _flatten_metadata_entries_for_metadata_file(nested_value, next_prefix)
            )
        return entries

    if isinstance(value, list):
        if not value:
            return [(prefix or "(root)", "[]")]

        entries: list[tuple[str, str]] = []
        for index, nested_value in enumerate(value):
            next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            entries.extend(
                _flatten_metadata_entries_for_metadata_file(nested_value, next_prefix)
            )
        return entries

    return [(prefix or "(root)", _format_metadata_file_value(value))]


def _change_entries_from_values(
    values: dict[str, Any], *, old_values: dict[str, str]
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []

    def add_entry(key: str, new_value: Any) -> None:
        entries.append(
            {
                "key": key,
                "old_value": old_values.get(key, ""),
                "new_value": _format_metadata_file_value(new_value),
            }
        )

    if "name" in values:
        add_entry("appinfo.common.name", values["name"])
    if "sort_as" in values:
        add_entry("appinfo.common.sortas", values["sort_as"])
    if "aliases" in values:
        add_entry("appinfo.common.aliases", values["aliases"])
    if "developer" in values:
        add_entry("appinfo.extended.developer", values["developer"])
    if "publisher" in values:
        add_entry("appinfo.extended.publisher", values["publisher"])
    if "original_release_date" in values:
        add_entry(
            "appinfo.common.original_release_date", values["original_release_date"]
        )
    if "steam_release_date" in values:
        add_entry("appinfo.common.steam_release_date", values["steam_release_date"])

    set_values = values.get("set_values")
    if set_values:
        for path, value in set_values:
            add_entry(".".join(path), value)

    return entries


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
    metadata_overrides: MetadataMap,
) -> None:
    _apply_override_values(app_data, _override_values(overrides))
    metadata_values = metadata_overrides.get(appid)
    if metadata_values:
        _apply_override_values(app_data, metadata_values)


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
