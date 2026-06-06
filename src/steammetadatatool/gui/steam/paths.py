# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from steammetadatatool.core.appinfo import steam_base_paths
from steammetadatatool.gui.steam.text_vdf import parse_text_vdf_object

_STEAM64_TO_ACCOUNT_ID_OFFSET = 76561197960265728


@dataclass(frozen=True)
class SteamUser:
    steamid: str
    account_id: str
    account_name: str
    persona_name: str
    avatar_path: Path | None
    is_most_recent: bool


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


def steam_users() -> list[SteamUser]:
    found_users: list[SteamUser] = []
    seen_account_ids: set[str] = set()

    for base in steam_base_paths():
        loginusers_path = base / "config" / "loginusers.vdf"
        if not loginusers_path.is_file():
            continue

        data = parse_text_vdf_object(
            loginusers_path.read_text(encoding="utf-8", errors="replace")
        )
        users = data.get("users")
        if not isinstance(users, dict):
            continue

        avatar_dir = base / "config" / "avatarcache"
        for steamid, user_data in users.items():
            if (
                not isinstance(steamid, str)
                or not steamid.startswith("7656119")
                or not isinstance(user_data, dict)
            ):
                continue

            account_id = str(int(steamid) - _STEAM64_TO_ACCOUNT_ID_OFFSET)
            if account_id in seen_account_ids:
                continue

            avatar_path = avatar_dir / f"{steamid}.png"
            found_users.append(
                SteamUser(
                    steamid=steamid,
                    account_id=account_id,
                    account_name=str(user_data.get("AccountName") or ""),
                    persona_name=str(user_data.get("PersonaName") or ""),
                    avatar_path=avatar_path if avatar_path.is_file() else None,
                    is_most_recent=str(user_data.get("MostRecent")).casefold() == "1",
                )
            )
            seen_account_ids.add(account_id)

    return sorted(
        found_users,
        key=lambda user: (
            not user.is_most_recent,
            (user.persona_name or user.account_name or user.account_id).casefold(),
        ),
    )


def steam_grid_dir(account_id: str | None = None) -> Path:
    if account_id is not None:
        for base in steam_base_paths():
            userdata_dir = base / "userdata" / account_id
            if userdata_dir.is_dir():
                return userdata_dir / "config" / "grid"

        base_paths = steam_base_paths()
        if base_paths:
            return base_paths[0] / "userdata" / account_id / "config" / "grid"

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
