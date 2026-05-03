# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path


def is_steam_running() -> bool:
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return False

    for proc_dir in proc_root.iterdir():
        if not proc_dir.name.isdigit():
            continue

        process_name = _read_proc_text(proc_dir / "comm").casefold()
        if process_name in {"steam", "steamwebhelper"}:
            return True

        cmdline = _read_proc_cmdline(proc_dir / "cmdline").casefold()
        if Path(cmdline.split("\0", 1)[0]).name in {"steam", "steamwebhelper"}:
            return True
        if "/app/bin/steam" in cmdline:
            return True

    return False


def _read_proc_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _read_proc_cmdline(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace").strip("\0")
    except OSError:
        return ""
