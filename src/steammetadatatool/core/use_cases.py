from __future__ import annotations

from pathlib import Path

from .appinfo import find_steam_appinfo_path
from .models import CliExecutionResult, CliRequest
from .services import (
    effective_changes_for_appids,
    has_any_overrides,
    load_changes_file,
    print_appinfo_lines,
    write_changes_file,
    write_modified_appinfo,
)


def execute_cli_request(request: CliRequest) -> CliExecutionResult:
    file_changes = {}
    if request.changes_file is not None:
        file_changes = load_changes_file(request.changes_file)

    path = request.path or find_steam_appinfo_path()
    if path is None or not path.exists():
        raise ValueError("Could not locate appinfo.vdf")

    if request.dry_run and request.write_out:
        raise ValueError("--dry-run cannot be used together with --write-out")
    if request.dry_run and request.write_changes_file:
        raise ValueError("--dry-run cannot be used together with --write-changes-file")

    has_overrides = has_any_overrides(request.overrides) or bool(file_changes)
    if has_overrides and not request.dry_run:
        if not request.appids and not file_changes:
            raise ValueError(
                "Write-back requires at least one --appid or a non-empty --changes-file"
            )

        appids = (
            {int(a) for a in request.appids}
            if request.appids
            else set(file_changes.keys())
        )
        written_path = write_modified_appinfo(
            path=Path(path),
            appids=appids,
            overrides=request.overrides,
            file_changes=file_changes,
            write_out=request.write_out,
        )

        if request.write_changes_file is not None:
            effective_changes = effective_changes_for_appids(
                appids=appids,
                overrides=request.overrides,
                file_changes=file_changes,
            )
            write_changes_file(
                request.write_changes_file,
                effective_changes,
                source_path=Path(path),
            )

        return CliExecutionResult(lines=[], written_path=written_path)

    lines = print_appinfo_lines(
        path=Path(path),
        appids=request.appids,
        overrides=request.overrides,
        file_changes=file_changes,
        as_json=request.as_json,
    )
    return CliExecutionResult(lines=lines, written_path=None)
