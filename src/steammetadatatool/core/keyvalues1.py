from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping

from .binary import BinaryReader, Color, read_cstring, read_cstring_utf16le


class KV1Type(IntEnum):
    NONE = 0
    STRING = 1
    INT32 = 2
    FLOAT32 = 3
    POINTER = 4
    WSTRING = 5
    COLOR = 6
    UINT64 = 7
    END = 8


@dataclass(frozen=True)
class KV1StringTable:
    strings: tuple[str, ...]

    def get(self, index: int) -> str:
        if 0 <= index < len(self.strings):
            return self.strings[index]
        raise IndexError(f"string table index out of range: {index}")


def _read_kv_name(reader: BinaryReader, string_table: KV1StringTable | None) -> str:
    if string_table is None:
        return read_cstring(reader, "utf-8")

    pos = reader.tell()
    idx = reader.u32()
    if 0 <= idx < len(string_table.strings):
        return string_table.strings[idx]
    reader.seek(pos)
    return read_cstring(reader, "utf-8")


def _read_kv_string_value(
    reader: BinaryReader, string_table: KV1StringTable | None
) -> str:
    if string_table is None:
        return read_cstring(reader, "utf-8")

    pos = reader.tell()
    idx = reader.u32()

    if 0 <= idx < len(string_table.strings):
        s = string_table.strings[idx]

        peek_pos = reader.tell()
        try:
            nxt = reader.u8()
        finally:
            reader.seek(peek_pos)

        if 0 <= nxt <= 8 and "\x00" not in s and len(s) <= 4096:
            return s

    reader.seek(pos)
    return read_cstring(reader, "utf-8")


def read_kv1_object(
    reader: BinaryReader, *, string_table: KV1StringTable | None = None
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    while True:
        type_pos = reader.tell()
        value_type = reader.u8()

        if value_type == KV1Type.END:
            return out

        name = _read_kv_name(reader, string_table)

        if value_type == KV1Type.NONE:
            out[name] = read_kv1_object(reader, string_table=string_table)
        elif value_type == KV1Type.STRING:
            out[name] = _read_kv_string_value(reader, string_table)
        elif value_type == KV1Type.INT32:
            out[name] = reader.i32()
        elif value_type == KV1Type.FLOAT32:
            out[name] = reader.f32()
        elif value_type == KV1Type.POINTER:
            out[name] = reader.u32()
        elif value_type == KV1Type.WSTRING:
            out[name] = read_cstring_utf16le(reader)
        elif value_type == KV1Type.COLOR:
            rgba = reader.read(4)
            out[name] = Color(rgba[0], rgba[1], rgba[2], rgba[3])
        elif value_type == KV1Type.UINT64:
            out[name] = reader.u64()
        else:
            raise ValueError(
                f"unknown KeyValues1 type byte: {value_type} at offset {type_pos}"
            )


def kv_deep_get(obj: Mapping[str, Any], *path: str) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, Mapping) or key not in cur:
            return None
        cur = cur[key]
    return cur
