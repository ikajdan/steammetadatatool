# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from .appinfo import find_steam_appinfo_path
from .models import CliExecutionResult, CliRequest
from .services import (
    effective_metadata_for_appids,
    has_any_overrides,
    load_metadata_file,
    print_appinfo_lines,
    write_metadata_file,
    write_modified_appinfo,
)


def execute_cli_request(request: CliRequest) -> CliExecutionResult:
    has_cli_overrides = has_any_overrides(request.overrides)
    metadata_overrides = {}
    if request.metadata_file is not None:
        if request.metadata_file.exists():
            metadata_overrides = load_metadata_file(request.metadata_file)
        elif not has_cli_overrides:
            metadata_overrides = load_metadata_file(request.metadata_file)

    path = request.path or find_steam_appinfo_path()
    if path is None or not path.exists():
        raise ValueError("Could not locate appinfo.vdf")

    if request.dry_run and request.write_out:
        raise ValueError("--dry-run cannot be used together with --write-out")

    has_overrides = has_cli_overrides or bool(metadata_overrides)
    if has_overrides and not request.dry_run:
        if not request.appids and not metadata_overrides:
            raise ValueError(
                "Write-back requires at least one --appid or a non-empty --metadata-file"
            )

        appids = (
            {int(a) for a in request.appids}
            if request.appids
            else set(metadata_overrides.keys())
        )
        written_path = write_modified_appinfo(
            path=Path(path),
            appids=appids,
            overrides=request.overrides,
            metadata_overrides=metadata_overrides,
            write_out=request.write_out,
            create_backup=not request.no_backup,
        )

        if request.metadata_file is not None:
            effective_metadata = effective_metadata_for_appids(
                appids=appids,
                overrides=request.overrides,
                metadata_overrides=metadata_overrides,
            )
            write_metadata_file(
                request.metadata_file,
                effective_metadata,
                source_path=Path(path),
            )

        return CliExecutionResult(lines=[], written_path=written_path)

    lines = print_appinfo_lines(
        path=Path(path),
        appids=request.appids,
        overrides=request.overrides,
        metadata_overrides=metadata_overrides,
        as_json=request.as_json,
    )
    return CliExecutionResult(lines=lines, written_path=None)
