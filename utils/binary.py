from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import BinaryIO


class BinaryReader:
    __slots__ = ("_f",)

    def __init__(self, f: BinaryIO):
        self._f = f

    def tell(self) -> int:
        return self._f.tell()

    def seek(self, pos: int, whence: int = io.SEEK_SET) -> int:
        return self._f.seek(pos, whence)

    def read(self, n: int) -> bytes:
        b = self._f.read(n)
        if len(b) != n:
            raise EOFError(f"expected {n} bytes, got {len(b)}")
        return b

    def u8(self) -> int:
        return self.read(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.read(4))[0]


def read_cstring(reader: BinaryReader, encoding: str = "utf-8") -> str:
    chunks: list[bytes] = []
    while True:
        b = reader.read(1)
        if b == b"\x00":
            break
        chunks.append(b)
    return b"".join(chunks).decode(encoding, errors="replace")


def read_cstring_utf16le(reader: BinaryReader) -> str:

    chunks: list[bytes] = []
    while True:
        b = reader.read(2)
        if b == b"\x00\x00":
            break
        chunks.append(b)
    return b"".join(chunks).decode("utf-16le", errors="replace")


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: int
