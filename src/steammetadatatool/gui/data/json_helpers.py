# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any


def validate_json_file_version(
    version: Any, *, current_version: int, file_description: str
) -> None:
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError(f"{file_description}: version must be a positive integer")
    if version > current_version:
        raise ValueError(
            f"{file_description}: unsupported version {version} "
            f"(latest supported is {current_version})"
        )
