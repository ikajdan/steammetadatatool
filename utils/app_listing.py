from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .appinfo import AppInfoFile


@dataclass(frozen=True)
class AppSummary:
    appid: int
    name: str


def list_app_summaries(path: str | Path) -> list[AppSummary]:
    summaries: list[AppSummary] = []
    with AppInfoFile.open(path) as appinfo:
        for app in appinfo.iter_apps():
            summaries.append(AppSummary(appid=app.appid, name=app.name or ""))
    return summaries
