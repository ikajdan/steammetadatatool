from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.appinfo import AppInfoFile
from utils.changes import ChangeMap, _write_changes_file
from utils.writer import rewrite_appinfo


def _deep_set(obj: dict[str, Any], path: list[str], value: Any) -> None:
    cur: dict[str, Any] = obj
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def _parse_set_arg(raw: str) -> tuple[list[str], Any]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected PATH=VALUE")
    path_s, value_s = raw.split("=", 1)
    path = [p for p in path_s.split(".") if p]
    if not path:
        raise argparse.ArgumentTypeError("empty PATH")

    value: Any = value_s
    if value_s.isdigit():
        value = int(value_s)
    return path, value


def _parse_date_to_unix(date_s: str) -> int:
    dt = datetime.strptime(date_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _parse_aliases(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as e:
            raise argparse.ArgumentTypeError(f"invalid JSON for --aliases: {e}")
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            raise argparse.ArgumentTypeError(
                "--aliases JSON must be an array of strings"
            )
        return [x.strip() for x in val if x.strip()]

    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def _cli_override_values(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if args.name is not None:
        values["name"] = args.name
    if args.sort_as is not None:
        values["sort_as"] = args.sort_as
    if args.aliases is not None:
        values["aliases"] = args.aliases
    if args.developer is not None:
        values["developer"] = args.developer
    if args.publisher is not None:
        values["publisher"] = args.publisher
    if args.original_release_date is not None:
        values["original_release_date"] = args.original_release_date
    if args.steam_release_date is not None:
        values["steam_release_date"] = args.steam_release_date
    return values


def _effective_changes_for_appids(
    appids: set[int], args: argparse.Namespace, file_changes: ChangeMap
) -> ChangeMap:
    out: ChangeMap = {}
    cli_values = _cli_override_values(args)

    for appid in appids:
        values: dict[str, Any] = {}
        values.update(cli_values)
        if appid in file_changes:
            values.update(file_changes[appid])
        if values:
            out[appid] = values

    return out


def _apply_override_values(app_data: dict[str, Any], values: dict[str, Any]) -> None:
    def update_associations(
        root_path: list[str], assoc_type: str, new_name: str
    ) -> None:
        cur: Any = app_data
        for p in root_path:
            if not isinstance(cur, dict):
                return
            cur = cur.get(p)
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


def _apply_overrides(app_data: dict[str, Any], args: argparse.Namespace) -> None:
    _apply_override_values(
        app_data,
        {
            "name": args.name,
            "sort_as": args.sort_as,
            "aliases": args.aliases,
            "developer": args.developer,
            "publisher": args.publisher,
            "original_release_date": args.original_release_date,
            "steam_release_date": args.steam_release_date,
            "set_values": args.set_values,
        },
    )


def _has_any_overrides(args: argparse.Namespace) -> bool:
    return any(
        v is not None
        for v in (
            args.name,
            args.sort_as,
            args.aliases,
            args.developer,
            args.publisher,
            args.original_release_date,
            args.steam_release_date,
        )
    ) or bool(args.set_values)


def _apply_overrides_for_app(
    app_data: dict[str, Any],
    appid: int,
    args: argparse.Namespace,
    file_changes: ChangeMap,
) -> None:
    _apply_overrides(app_data, args)
    file_values = file_changes.get(appid)
    if file_values:
        _apply_override_values(app_data, file_values)


def _timestamped_backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    candidate = path.with_name(path.name + "_" + stamp + ".bak")

    if candidate.exists():
        raise RuntimeError("backup filename already exists: " + str(candidate))

    return candidate


def _write_modified_appinfo(
    *,
    path: Path,
    args: argparse.Namespace,
    file_changes: ChangeMap,
) -> Path:
    appids = {int(a) for a in args.appid} if args.appid else set(file_changes.keys())

    if args.write_out is not None:
        rewrite_appinfo(
            in_path=path,
            out_path=args.write_out,
            appids_to_modify=appids,
            apply_overrides=lambda kv, appid: _apply_overrides_for_app(
                kv, appid, args, file_changes
            ),
        )
        return args.write_out

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
                kv, appid, args, file_changes
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


def _write_changes_if_requested(
    *,
    appids: set[int],
    args: argparse.Namespace,
    file_changes: ChangeMap,
) -> None:
    if args.write_changes_file is None:
        return

    effective_changes = _effective_changes_for_appids(appids, args, file_changes)
    _write_changes_file(args.write_changes_file, effective_changes)


def _print_appinfo(
    *,
    path: Path,
    args: argparse.Namespace,
    file_changes: ChangeMap,
) -> None:
    with AppInfoFile.open(path) as appinfo:
        if args.as_json:
            for app in appinfo.iter_apps(appids=args.appid):
                _apply_overrides_for_app(app.data, app.appid, args, file_changes)
                payload = asdict(app)
                payload["last_updated"] = app.last_updated.isoformat()
                payload["sha1"] = app.sha1.hex()
                payload["binary_data_sha1"] = (
                    app.binary_data_sha1.hex() if app.binary_data_sha1 else None
                )
                print(json.dumps(payload, ensure_ascii=False))
        else:
            for app in appinfo.iter_apps(appids=args.appid):
                _apply_overrides_for_app(app.data, app.appid, args, file_changes)
                name = app.name or ""
                print(f"{app.appid}\t{name}")
