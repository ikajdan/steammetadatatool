# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

DOMAIN = "steammetadatatool"
ENV_LOCALE = "STEAMMETADATATOOL_LOCALE"
ENV_TRANSLATIONS_DIR = "STEAMMETADATATOOL_TRANSLATIONS_DIR"

_translation: gettext.NullTranslations = gettext.NullTranslations()


def configure_gettext(
    *,
    language: str | None = None,
    localedir: str | Path | None = None,
) -> None:
    global _translation

    languages = _requested_languages(language)
    _translation = gettext.translation(
        DOMAIN,
        localedir=str(localedir or translations_dir()),
        languages=languages,
        fallback=True,
    )


def gettext_message(message: str) -> str:
    return _translation.gettext(message)


def ngettext_message(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


def translations_dir() -> Path:
    configured = os.environ.get(ENV_TRANSLATIONS_DIR)
    if configured:
        return Path(configured).expanduser()

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "i18n"
        if candidate.is_dir():
            return candidate

    return Path("/usr/share/locale")


def _requested_languages(language: str | None) -> list[str] | None:
    requested = language or os.environ.get(ENV_LOCALE)
    if requested:
        return [requested]

    locale_name, _encoding = locale.getlocale()
    return [locale_name] if locale_name else None


_ = gettext_message
ngettext = ngettext_message
