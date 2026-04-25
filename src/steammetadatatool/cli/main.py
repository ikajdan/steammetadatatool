from __future__ import annotations

import argparse
from pathlib import Path

from steammetadatatool import __version__
from steammetadatatool.core.models import CliRequest, OverrideInput
from steammetadatatool.core.services import parse_aliases, parse_set_arg
from steammetadatatool.core.use_cases import execute_cli_request


def _aliases_arg(raw: str) -> list[str]:
    try:
        return parse_aliases(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _set_arg(raw: str):
    try:
        return parse_set_arg(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steam_appinfo_parser",
        description="A tool for reading and editing Steam client metadata.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to appinfo.vdf (defaults to auto-detected Steam install)",
    )
    parser.add_argument("--appid", type=int, action="append", help="Filter by appid")

    parser.add_argument("--name", help="Override common.name")
    parser.add_argument("--sort-as", dest="sort_as", help="Override the sort-as name")
    parser.add_argument(
        "--aliases",
        type=_aliases_arg,
        help="Override aliases (comma-separated or JSON array)",
    )
    parser.add_argument("--developer", help="Override extended.developer")
    parser.add_argument("--publisher", help="Override extended.publisher")
    parser.add_argument(
        "--original-release-date",
        dest="original_release_date",
        help="Override the original release date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--steam-release-date",
        dest="steam_release_date",
        help="Override the release date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        type=_set_arg,
        help="Generic PATH=VALUE override (dot-separated PATH, VALUE can be JSON or a plain string)",
    )
    parser.add_argument(
        "--metadata-file",
        dest="metadata_file",
        type=Path,
        help="Path to the JSON file containing metadata overrides",
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
        help="Print the output as JSON instead of plain text",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    request = CliRequest(
        path=Path(args.path) if args.path else None,
        appids=args.appid,
        overrides=OverrideInput(
            name=args.name,
            sort_as=args.sort_as,
            aliases=args.aliases,
            developer=args.developer,
            publisher=args.publisher,
            original_release_date=args.original_release_date,
            steam_release_date=args.steam_release_date,
            set_values=args.set_values,
        ),
        metadata_file=args.metadata_file,
        write_out=args.write_out,
        dry_run=args.dry_run,
        as_json=args.as_json,
    )

    try:
        result = execute_cli_request(request)
    except ValueError as exc:
        parser.error(str(exc))

    for line in result.lines:
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
