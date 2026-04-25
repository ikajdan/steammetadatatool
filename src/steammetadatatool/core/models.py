from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SetValue = tuple[list[str], Any]
MetadataValues = dict[str, Any]
MetadataMap = dict[int, MetadataValues]


@dataclass(frozen=True)
class AppSummary:
    appid: int
    name: str


@dataclass(frozen=True)
class OverrideInput:
    name: str | None = None
    sort_as: str | None = None
    aliases: list[str] | None = None
    developer: str | None = None
    publisher: str | None = None
    original_release_date: str | None = None
    steam_release_date: str | None = None
    set_values: list[SetValue] | None = None


@dataclass(frozen=True)
class CliRequest:
    path: Path | None
    appids: list[int] | None
    overrides: OverrideInput = field(default_factory=OverrideInput)
    metadata_file: Path | None = None
    write_out: Path | None = None
    dry_run: bool = False
    as_json: bool = False


@dataclass(frozen=True)
class CliExecutionResult:
    lines: list[str]
    written_path: Path | None = None
