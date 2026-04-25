from __future__ import annotations

import re
from pathlib import Path

from steammetadatatool.core.appinfo import steam_base_paths

_STEAM64_TO_ACCOUNT_ID_OFFSET = 76561197960265728
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


def most_recent_steam_account_id(base: Path) -> str | None:
    loginusers_path = base / "config" / "loginusers.vdf"
    if not loginusers_path.is_file():
        return None

    data = parse_text_vdf_object(
        loginusers_path.read_text(encoding="utf-8", errors="replace")
    )
    users = data.get("users")
    if not isinstance(users, dict):
        return None

    for steamid, user_data in users.items():
        if not isinstance(steamid, str) or not steamid.startswith("7656119"):
            continue
        if not isinstance(user_data, dict):
            continue
        if str(user_data.get("MostRecent")).casefold() == "1":
            return str(int(steamid) - _STEAM64_TO_ACCOUNT_ID_OFFSET)

    return None


def steam_grid_dir() -> Path:
    for base in steam_base_paths():
        account_id = most_recent_steam_account_id(base)
        if account_id is not None:
            return base / "userdata" / account_id / "config" / "grid"

    for base in steam_base_paths():
        userdata_dir = base / "userdata"
        if not userdata_dir.is_dir():
            continue

        user_dirs = sorted(
            path
            for path in userdata_dir.iterdir()
            if path.is_dir() and path.name.isdigit()
        )
        if user_dirs:
            return user_dirs[0] / "config" / "grid"

    raise FileNotFoundError(
        "No Steam userdata directory with a numeric user id was found."
    )


def steam_librarycache_dir_for_app(appid: str) -> Path | None:
    for base in steam_base_paths():
        app_cache_dir = base / "appcache" / "librarycache" / appid
        if app_cache_dir.is_dir():
            return app_cache_dir
    return None


def cached_icon_path_for_app(appid: str) -> Path | None:
    app_cache_dir = steam_librarycache_dir_for_app(appid)
    if app_cache_dir is None:
        return None

    candidates = sorted(
        path
        for path in app_cache_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".jpg"
        and len(path.stem) == 40
        and all(char in "0123456789abcdef" for char in path.stem)
    )
    if candidates:
        return candidates[0]

    for subdir in sorted(path for path in app_cache_dir.iterdir() if path.is_dir()):
        candidates = sorted(
            path
            for path in subdir.iterdir()
            if path.is_file()
            and path.suffix.lower() == ".jpg"
            and len(path.stem) == 40
            and all(char in "0123456789abcdef" for char in path.stem)
        )
        if candidates:
            return candidates[0]

    return None
