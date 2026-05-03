# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from steammetadatatool.gui.steam.paths import steam_librarycache_dir_for_app

STEAM_GRID_BASENAME_SUFFIXES = {
    "capsule_path": "p",
    "header_path": "",
    "hero_path": "_hero",
    "logo_path": "_logo",
}
STEAM_GRID_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _find_asset_file(base_dir: Path, *filenames: str) -> str:
    for filename in filenames:
        root_path = base_dir / filename
        if root_path.is_file():
            return str(root_path)

        try:
            for subdir in base_dir.iterdir():
                if subdir.is_dir():
                    candidate = subdir / filename
                    if candidate.is_file():
                        return str(candidate)
        except (OSError, PermissionError):
            pass

    return "-"


def cached_icon_path_for_app(appid: str | int) -> Path | None:
    app_cache_dir = steam_librarycache_dir_for_app(str(appid))
    if app_cache_dir is None:
        return None

    try:
        candidates = sorted(
            path
            for path in app_cache_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() == ".jpg"
            and len(path.stem) == 40
            and all(char in "0123456789abcdef" for char in path.stem)
        )
    except (OSError, PermissionError):
        return None

    if candidates:
        return candidates[0]

    try:
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
    except (OSError, PermissionError):
        pass

    return None


def original_icon_path_for_cached_icon(cached_icon_path: Path) -> Path:
    return cached_icon_path.with_name(f"{cached_icon_path.stem}.orig.jpg")


def default_icon_path_for_app(appid: str | int) -> Path | None:
    cached_icon_path = cached_icon_path_for_app(appid)
    if cached_icon_path is None:
        return None

    original_icon_path = original_icon_path_for_cached_icon(cached_icon_path)
    return original_icon_path if original_icon_path.is_file() else cached_icon_path


def asset_paths_for_app(appid: int) -> dict[str, str]:
    app_cache_dir = steam_librarycache_dir_for_app(str(appid))
    if app_cache_dir is None:
        return {
            "header_path": "-",
            "capsule_path": "-",
            "hero_path": "-",
            "logo_path": "-",
            "icon_path": "-",
        }

    default_icon_path = default_icon_path_for_app(appid)
    return {
        "header_path": _find_asset_file(
            app_cache_dir, "header.jpg", "library_header.jpg", "header_2x.jpg"
        ),
        "capsule_path": _find_asset_file(
            app_cache_dir,
            "library_600x900.jpg",
            "library_600x900_2x.jpg",
            "library_capsule.jpg",
        ),
        "hero_path": _find_asset_file(
            app_cache_dir, "library_hero.jpg", "library_hero_2x.jpg"
        ),
        "logo_path": _find_asset_file(app_cache_dir, "logo.png", "logo_2x.png"),
        "icon_path": str(default_icon_path) if default_icon_path is not None else "-",
    }
