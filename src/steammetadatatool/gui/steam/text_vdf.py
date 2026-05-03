# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re

_TEXT_VDF_TOKEN_RE = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')


def parse_text_vdf_object(text: str) -> dict[str, object]:
    tokens = [
        quoted if quoted else brace
        for quoted, brace in _TEXT_VDF_TOKEN_RE.findall(text)
    ]
    index = 0

    def parse_object() -> dict[str, object]:
        nonlocal index
        parsed: dict[str, object] = {}

        while index < len(tokens):
            token = tokens[index]
            index += 1
            if token == "}":
                break
            if token == "{":
                continue

            if index >= len(tokens):
                break

            value_token = tokens[index]
            index += 1
            if value_token == "{":
                parsed[token] = parse_object()
            else:
                parsed[token] = value_token

        return parsed

    return parse_object()
