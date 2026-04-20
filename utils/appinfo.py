from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator

from .binary import BinaryReader, read_cstring
from .keyvalues1 import KV1StringTable, kv_deep_get, read_kv1_object


class Universe(IntEnum):
    INVALID = 0
    PUBLIC = 1
    BETA = 2
    INTERNAL = 3
    DEV = 4
    MAX = 5


@dataclass
class AppRecord:
    appid: int
    info_state: int
    last_updated: datetime
    token: int
    sha1: bytes
    change_number: int
    binary_data_sha1: bytes | None
    data: dict[str, Any]

    @property
    def name(self) -> str | None:
        return kv_deep_get(self.data, "common", "name") or kv_deep_get(
            self.data, "appinfo", "common", "name"
        )

    @property
    def app_type(self) -> str | None:
        return kv_deep_get(self.data, "common", "type") or kv_deep_get(
            self.data, "appinfo", "common", "type"
        )


class AppInfoFile:
    """Streaming reader for Steam client's binary appinfo.vdf (versions 39-41)."""

    def __init__(self, f: BinaryIO):
        self._f = f
        self.universe: Universe | None = None
        self.version: int | None = None
        self._string_table: KV1StringTable | None = None

    @staticmethod
    def open(path: os.PathLike[str] | str) -> "AppInfoFile":
        return AppInfoFile(open(path, "rb"))

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "AppInfoFile":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _read_header(self, reader: BinaryReader) -> None:
        magic = reader.u32()
        version = magic & 0xFF
        magic >>= 8

        if magic != 0x07_56_44:
            raise ValueError(f"unknown appinfo magic header: 0x{magic:X}")
        if version < 39 or version > 41:
            raise ValueError(f"unsupported appinfo version: {version}")

        self.version = int(version)
        self.universe = Universe(reader.u32())

        if self.version >= 41:
            string_table_offset = reader.i64()
            cur = reader.tell()
            reader.seek(string_table_offset)
            string_count = reader.u32()
            pool = [read_cstring(reader, "utf-8") for _ in range(string_count)]
            self._string_table = KV1StringTable(tuple(pool))
            reader.seek(cur)

    def iter_apps(self, *, appids: Iterable[int] | None = None) -> Iterator[AppRecord]:
        reader = BinaryReader(self._f)

        if self.version is None:
            self._read_header(reader)

        remaining: set[int] | None = None
        if appids is not None:
            remaining = {int(a) for a in appids}

        while True:
            appid = reader.u32()
            if appid == 0:
                return

            size = reader.u32()
            end = reader.tell() + size

            info_state = reader.u32()
            last_updated = datetime.fromtimestamp(reader.u32(), tz=timezone.utc)
            token = reader.u64()
            sha1 = reader.read(20)
            change_number = reader.u32()

            binary_data_sha1: bytes | None = None
            if (self.version or 0) >= 40:
                binary_data_sha1 = reader.read(20)

            should_yield = remaining is None or appid in remaining

            if should_yield:
                data = read_kv1_object(reader, string_table=self._string_table)
            else:
                reader.seek(end)
                data = {}

            if reader.tell() != end:
                reader.seek(end)

            if should_yield:
                yield AppRecord(
                    appid=appid,
                    info_state=info_state,
                    last_updated=last_updated,
                    token=token,
                    sha1=sha1,
                    change_number=change_number,
                    binary_data_sha1=binary_data_sha1,
                    data=data,
                )

                if remaining is not None:
                    remaining.discard(appid)
                    if not remaining:
                        return


def find_steam_appinfo_path() -> Path | None:
    if sys.platform.startswith("linux"):
        home = Path.home()
        candidates = [
            home / ".local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/data/Steam",
        ]
        for base in candidates:
            p = base / "appcache" / "appinfo.vdf"
            if p.exists():
                return p
        return None

    if sys.platform == "darwin":
        p = Path.home() / "Library/Application Support/Steam/appcache/appinfo.vdf"
        return p if p.exists() else None

    if sys.platform.startswith("win"):
        env = os.environ.get("PROGRAMFILES(X86)") or os.environ.get("PROGRAMFILES")
        if env:
            p = Path(env) / "Steam/appcache/appinfo.vdf"
            if p.exists():
                return p
        p = Path.home() / "AppData/Local/Steam/appcache/appinfo.vdf"
        return p if p.exists() else None

    return None
