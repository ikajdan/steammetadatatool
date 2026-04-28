# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import os
import struct
from dataclasses import dataclass
from typing import Any, BinaryIO, Callable

from .binary import BinaryReader, Color, read_cstring
from .keyvalues1 import KV1StringTable, read_kv1_object


@dataclass
class _AppPayload:
    info_state: int
    last_updated_unix: int
    token: int
    text_sha1: bytes
    change_number: int
    binary_sha1: bytes | None
    kv: dict[str, Any]


def _kv_to_text_vdf(obj: dict[str, Any], tabs: int = 0) -> bytes:
    out = bytearray()
    indent = b"\t" * tabs

    for key, value in obj.items():
        key_b = str(key).replace("\\", "\\\\").encode("utf-8", errors="replace")

        if isinstance(value, dict):
            out.extend(indent + b'"' + key_b + b'"' + b"\n")
            out.extend(indent + b"{" + b"\n")
            out.extend(_kv_to_text_vdf(value, tabs + 1))
            out.extend(indent + b"}" + b"\n")
        else:
            if isinstance(value, str):
                val_s = value.replace("\\", "\\\\")
            else:
                val_s = str(value)
            val_b = val_s.encode("utf-8", errors="replace")
            out.extend(
                indent + b'"' + key_b + b'"' + b"\t\t" + b'"' + val_b + b'"' + b"\n"
            )

    return bytes(out)


def _ensure_string(table: list[str], index_by_string: dict[str, int], s: str) -> int:
    idx = index_by_string.get(s)
    if idx is not None:
        return idx
    idx = len(table)
    table.append(s)
    index_by_string[s] = idx
    return idx


def _encode_kv_string_inline(s: str) -> bytes:
    return s.encode("utf-8", errors="replace") + b"\x00"


def _encode_kv_wstring(s: str) -> bytes:
    return s.encode("utf-16le", errors="replace") + b"\x00\x00"


def encode_kv1_object(
    obj: dict[str, Any],
    *,
    string_table: list[str] | None = None,
    index_by_string: dict[str, int] | None = None,
) -> bytes:
    out = bytearray()

    def write_name(name: str) -> None:
        if string_table is None:
            out.extend(_encode_kv_string_inline(name))
            return

        if index_by_string is None:
            raise ValueError(
                "index_by_string is required when string_table is provided"
            )

        idx = _ensure_string(string_table, index_by_string, name)
        out.extend(struct.pack("<I", idx))

    for key, value in obj.items():
        if isinstance(value, dict):
            out.append(0)
            write_name(str(key))
            out.extend(
                encode_kv1_object(
                    value,
                    string_table=string_table,
                    index_by_string=index_by_string,
                )
            )
        elif isinstance(value, str):
            out.append(1)
            write_name(str(key))
            out.extend(_encode_kv_string_inline(value))
        elif isinstance(value, bool):
            out.append(2)
            write_name(str(key))
            out.extend(struct.pack("<i", 1 if value else 0))
        elif isinstance(value, int):
            v = int(value)
            if -(2**31) <= v <= (2**31 - 1):
                out.append(2)
                write_name(str(key))
                out.extend(struct.pack("<i", v))
            elif 0 <= v <= (2**64 - 1):
                out.append(7)
                write_name(str(key))
                out.extend(struct.pack("<Q", v))
            else:
                raise OverflowError(f"int out of range for KV encoding: {v}")
        elif isinstance(value, float):
            out.append(3)
            write_name(str(key))
            out.extend(struct.pack("<f", float(value)))
        elif isinstance(value, Color):
            out.append(6)
            write_name(str(key))
            out.extend(bytes([value.r, value.g, value.b, value.a]))
        else:
            raise TypeError(
                f"cannot encode KV value type for key {key!r}: {type(value).__name__}"
            )

    out.append(8)
    return bytes(out)


def _read_app_payload(
    payload: bytes, *, version: int, string_table: KV1StringTable | None
) -> _AppPayload:
    r = BinaryReader(io.BytesIO(payload))

    info_state = r.u32()
    last_updated_unix = r.u32()
    token = r.u64()
    text_sha1 = r.read(20)
    change_number = r.u32()

    binary_sha1: bytes | None = None
    if version >= 40:
        binary_sha1 = r.read(20)

    kv = read_kv1_object(r, string_table=string_table)

    return _AppPayload(
        info_state=info_state,
        last_updated_unix=last_updated_unix,
        token=token,
        text_sha1=text_sha1,
        change_number=change_number,
        binary_sha1=binary_sha1,
        kv=kv,
    )


def _encode_app_payload(
    app: _AppPayload,
    *,
    version: int,
    string_table: list[str] | None,
    index_by_string: dict[str, int] | None,
) -> bytes:
    kv_bytes = encode_kv1_object(
        app.kv, string_table=string_table, index_by_string=index_by_string
    )

    app.text_sha1 = hashlib.sha1(_kv_to_text_vdf(app.kv)).digest()

    parts = [
        struct.pack("<I", app.info_state),
        struct.pack("<I", app.last_updated_unix),
        struct.pack("<Q", app.token),
        app.text_sha1,
        struct.pack("<I", app.change_number),
    ]

    if version >= 40:
        binary_sha1 = hashlib.sha1(kv_bytes).digest()
        parts.append(binary_sha1)

    parts.append(kv_bytes)
    return b"".join(parts)


def _read_string_table_v41(f: BinaryIO, offset: int) -> list[str]:
    r = BinaryReader(f)
    cur = r.tell()
    r.seek(offset)
    count = r.u32()
    pool = [read_cstring(r, "utf-8") for _ in range(count)]
    r.seek(cur)
    return pool


def rewrite_appinfo(
    *,
    in_path: os.PathLike[str] | str,
    out_path: os.PathLike[str] | str,
    appids_to_modify: set[int],
    apply_overrides: Callable[[dict[str, Any], int], None],
) -> None:
    in_path = str(in_path)
    out_path = str(out_path)

    with open(in_path, "rb") as fin, open(out_path, "wb") as fout:
        rin = BinaryReader(fin)

        magic = rin.u32()
        version = magic & 0xFF
        magic_nover = magic >> 8

        if magic_nover != 0x07_56_44:
            raise ValueError(f"not an appinfo.vdf file (magic=0x{magic_nover:X})")
        if version < 39 or version > 41:
            raise ValueError(f"unsupported appinfo version: {version}")

        universe = rin.u32()

        string_pool: list[str] | None = None
        string_table: KV1StringTable | None = None
        string_table_offset_pos: int | None = None

        if version >= 41:
            string_table_offset = rin.i64()
            string_pool = _read_string_table_v41(fin, string_table_offset)
            string_table = KV1StringTable(tuple(string_pool))

        fout.write(struct.pack("<I", magic))
        fout.write(struct.pack("<I", universe))

        if version >= 41:
            string_table_offset_pos = fout.tell()
            fout.write(struct.pack("<q", 0))

        index_by_string: dict[str, int] | None = None
        if string_pool is not None:
            index_by_string = {s: i for i, s in enumerate(string_pool)}

        while True:
            appid = rin.u32()
            if appid == 0:
                break

            size = rin.u32()
            payload = rin.read(size)

            if appid in appids_to_modify:
                parsed = _read_app_payload(
                    payload, version=version, string_table=string_table
                )
                apply_overrides(parsed.kv, appid)
                new_payload = _encode_app_payload(
                    parsed,
                    version=version,
                    string_table=string_pool,
                    index_by_string=index_by_string,
                )
                fout.write(struct.pack("<I", appid))
                fout.write(struct.pack("<I", len(new_payload)))
                fout.write(new_payload)
            else:
                fout.write(struct.pack("<I", appid))
                fout.write(struct.pack("<I", size))
                fout.write(payload)

        fout.write(struct.pack("<I", 0))

        if version >= 41:
            if string_pool is None:
                string_pool = []
            string_table_offset_new = fout.tell()
            fout.write(struct.pack("<I", len(string_pool)))
            for s in string_pool:
                fout.write(s.encode("utf-8", errors="replace") + b"\x00")

            if string_table_offset_pos is None:
                raise RuntimeError(
                    "internal error: missing string table offset position"
                )

            fout.seek(string_table_offset_pos)
            fout.write(struct.pack("<q", string_table_offset_new))

            fout.seek(0, os.SEEK_END)
