from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.appinfo import AppInfoFile, find_steam_appinfo_path
from utils.writer import rewrite_appinfo

ChangeMap = dict[int, dict[str, Any]]


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
    candidate = path.with_name(path.name + ".bak." + stamp)
    if not candidate.exists():
        return candidate

    for i in range(1, 1000):
        candidate_i = path.with_name(path.name + ".bak." + stamp + f".{i}")
        if not candidate_i.exists():
            return candidate_i

    raise RuntimeError("could not find a free backup filename")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="steam_appinfo_parser",
        description="Read Steam client's appcache/appinfo.vdf (binary) and print app info.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to appinfo.vdf (defaults to auto-detected Steam install)",
    )
    parser.add_argument("--appid", type=int, action="append", help="Filter by appid")

    parser.add_argument("--name", help="Override common.name")
    parser.add_argument("--sort-as", dest="sort_as", help="Override common.sortas")
    parser.add_argument(
        "--aliases",
        type=_parse_aliases,
        help='Override common.aliases (comma-separated or JSON array, e.g. "foo,bar" or ["foo","bar"])',
    )
    parser.add_argument("--developer", help="Override extended.developer")
    parser.add_argument("--publisher", help="Override extended.publisher")
    parser.add_argument(
        "--original-release-date",
        dest="original_release_date",
        help="Override common.original_release_date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--steam-release-date",
        dest="steam_release_date",
        help="Override common.steam_release_date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        type=_parse_set_arg,
        help="Generic override: PATH=VALUE (PATH uses dots, e.g. common.name=Foo)",
    )
    parser.add_argument(
        "--changes-file",
        dest="changes_file",
        type=Path,
        help="Apply per-app overrides from a JSON file (see data/example-changes.json)",
    )

    parser.add_argument(
        "--write-out",
        dest="write_out",
        type=Path,
        help="Write a modified appinfo.vdf to this path instead of overwriting the input",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Do not write any files; only print resulting records",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Print full record(s) as JSON (otherwise prints a compact list)",
    )
    args = parser.parse_args()

    file_changes: ChangeMap = {}
    if args.changes_file is not None:
        try:
            file_changes = _load_changes_file(args.changes_file)
        except argparse.ArgumentTypeError as e:
            parser.error(str(e))

    path: Path | None
    if args.path:
        path = Path(args.path)
    else:
        path = find_steam_appinfo_path()

    if path is None or not path.exists():
        parser.error("Could not locate appinfo.vdf")

    if args.dry_run and args.write_out:
        parser.error("--dry-run cannot be used together with --write-out")

    has_overrides = _has_any_overrides(args) or bool(file_changes)
    should_write = has_overrides and not args.dry_run

    if should_write:
        if not args.appid and not file_changes:
            parser.error(
                "Write-back requires at least one --appid or a non-empty --changes-file"
            )

        appids = (
            {int(a) for a in args.appid} if args.appid else set(file_changes.keys())
        )

        if args.write_out is not None:
            out_path = args.write_out
            rewrite_appinfo(
                in_path=path,
                out_path=out_path,
                appids_to_modify=appids,
                apply_overrides=lambda kv, appid: _apply_overrides_for_app(
                    kv, appid, args, file_changes
                ),
            )
            path = out_path
        else:
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
            finally:
                if tmp_path.exists():
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
