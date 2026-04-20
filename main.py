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


def _apply_overrides(app_data: dict[str, Any], args: argparse.Namespace) -> None:
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

    if args.name is not None:
        _deep_set(app_data, ["appinfo", "common", "name"], args.name)
        _deep_set(app_data, ["common", "name"], args.name)

    if args.sort_as is not None:
        _deep_set(app_data, ["appinfo", "common", "sortas"], args.sort_as)
        _deep_set(app_data, ["common", "sortas"], args.sort_as)

    if args.aliases is not None:
        aliases_s = ", ".join(args.aliases)
        _deep_set(app_data, ["appinfo", "common", "aliases"], aliases_s)
        _deep_set(app_data, ["common", "aliases"], aliases_s)

    if args.developer is not None:
        _deep_set(app_data, ["appinfo", "extended", "developer"], args.developer)
        _deep_set(app_data, ["extended", "developer"], args.developer)
        update_associations(["appinfo", "common"], "developer", args.developer)
        update_associations(["common"], "developer", args.developer)

    if args.publisher is not None:
        _deep_set(app_data, ["appinfo", "extended", "publisher"], args.publisher)
        _deep_set(app_data, ["extended", "publisher"], args.publisher)
        update_associations(["appinfo", "common"], "publisher", args.publisher)
        update_associations(["common"], "publisher", args.publisher)

    if args.original_release_date is not None:
        ts = _parse_date_to_unix(args.original_release_date)
        _deep_set(app_data, ["appinfo", "common", "original_release_date"], ts)
        _deep_set(app_data, ["common", "original_release_date"], ts)

    if args.steam_release_date is not None:
        ts = _parse_date_to_unix(args.steam_release_date)
        _deep_set(app_data, ["appinfo", "common", "steam_release_date"], ts)
        _deep_set(app_data, ["common", "steam_release_date"], ts)

    if args.set_values:
        for path, value in args.set_values:
            _deep_set(app_data, path, value)


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
        "--write-out",
        dest="write_out",
        type=Path,
        help="Write a modified appinfo.vdf to this path (does not modify the input)",
    )
    parser.add_argument(
        "--in-place",
        dest="in_place",
        action="store_true",
        help="Rewrite the input file in-place (creates a .bak backup)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Print full record(s) as JSON (otherwise prints a compact list)",
    )
    args = parser.parse_args()

    path: Path | None
    if args.path:
        path = Path(args.path)
    else:
        path = find_steam_appinfo_path()

    if path is None or not path.exists():
        parser.error("Could not locate appinfo.vdf")

    if args.write_out and args.in_place:
        parser.error("Use only one of --write-out or --in-place")

    if args.write_out or args.in_place:
        if not args.appid:
            parser.error("Write-back requires at least one --appid")
        if not _has_any_overrides(args):
            parser.error("Write-back requested but no override flags were provided")

        appids = {int(a) for a in args.appid}

        if args.write_out:
            out_path = args.write_out
            rewrite_appinfo(
                in_path=path,
                out_path=out_path,
                appids_to_modify=appids,
                apply_overrides=lambda kv: _apply_overrides(kv, args),
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
                    apply_overrides=lambda kv: _apply_overrides(kv, args),
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
                _apply_overrides(app.data, args)
                payload = asdict(app)
                payload["last_updated"] = app.last_updated.isoformat()
                payload["sha1"] = app.sha1.hex()
                payload["binary_data_sha1"] = (
                    app.binary_data_sha1.hex() if app.binary_data_sha1 else None
                )
                print(json.dumps(payload, ensure_ascii=False))
        else:
            for app in appinfo.iter_apps(appids=args.appid):
                _apply_overrides(app.data, args)
                name = app.name or ""
                print(f"{app.appid}\t{name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
