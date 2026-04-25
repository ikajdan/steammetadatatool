from __future__ import annotations

import os
from pathlib import Path

_APP_DATA_DIRNAME = "steammetadatatool"


def xdg_data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path

    return Path.home() / ".local" / "share"


def app_data_dir() -> Path:
    return xdg_data_home() / _APP_DATA_DIRNAME


def app_data_path(*parts: str) -> Path:
    return app_data_dir().joinpath(*parts)
