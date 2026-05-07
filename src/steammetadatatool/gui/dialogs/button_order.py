# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import sys


def primary_action_first() -> bool:
    if sys.platform.startswith("win"):
        return True

    desktop_name = " ".join(
        value
        for key in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION")
        if (value := os.environ.get(key))
    ).casefold()

    if "gnome" in desktop_name:
        return False

    if "kde" in desktop_name or "plasma" in desktop_name:
        return True

    return True
