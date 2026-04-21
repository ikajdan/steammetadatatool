from __future__ import annotations

import argparse
from pathlib import Path

from utils.appinfo import find_steam_appinfo_path
from utils.changes import _load_changes_file
from utils.overrides import (
    _has_any_overrides,
    _parse_aliases,
    _parse_set_arg,
    _print_appinfo,
    _write_changes_if_requested,
    _write_modified_appinfo,
)


def _build_parser() -> argparse.ArgumentParser:
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
        "--write-changes-file",
        dest="write_changes_file",
        type=Path,
        help="Also write effective changes to this JSON file (append by appid, overwrite existing entries)",
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
        help="Print modified records without writing any files",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Print full record(s) as JSON (otherwise prints a compact list)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    file_changes = {}
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
    if args.dry_run and args.write_changes_file:
        parser.error("--dry-run cannot be used together with --write-changes-file")

    has_overrides = _has_any_overrides(args) or bool(file_changes)
    if has_overrides and not args.dry_run:
        if not args.appid and not file_changes:
            parser.error(
                "Write-back requires at least one --appid or a non-empty --changes-file"
            )

        appids = (
            {int(a) for a in args.appid} if args.appid else set(file_changes.keys())
        )
        path = _write_modified_appinfo(path=path, args=args, file_changes=file_changes)
        _write_changes_if_requested(appids=appids, args=args, file_changes=file_changes)
        return 0

    _print_appinfo(path=path, args=args, file_changes=file_changes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
