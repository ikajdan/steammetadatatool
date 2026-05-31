#!/bin/sh
# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

set -eu

repo_dir_path="$(unset CDPATH && cd "$(dirname "$0")/.." && echo "$PWD")"
domain=steammetadatatool
copyright_holder='Ignacy Kajdan'
msgid_bugs_address='https://github.com/ikajdan/steammetadatatool/issues'
spdx_copyright_text='# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>'
spdx_license_identifier='# SPDX-License''-Identifier: GPL-3.0-or-later'
i18n_dir="${TRANSLATIONS_DIR:-${repo_dir_path}/data/i18n}"
desktop_file="${DESKTOP_FILE:-${repo_dir_path}/data/io.github.ikajdan.steammetadatatool.desktop}"
metainfo_file="${METAINFO_FILE:-${repo_dir_path}/data/io.github.ikajdan.steammetadatatool.metainfo.xml}"
metainfo_its="${METAINFO_ITS:-/usr/share/gettext/its/metainfo.its}"
pot_file="${i18n_dir}/${domain}.pot"

usage() {
    printf '%s\n' "Usage: $0 extract"
    printf '%s\n' "       $0 init LOCALE"
    printf '%s\n' "       $0 update [LOCALE ...]"
    printf '%s\n' "       $0 compile [LOCALE ...]"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf '%s %s\n' 'Missing required command:' "$1" >&2
        exit 1
    fi
}

require_gettext() {
    require_command xgettext
    require_command msgfmt
    require_command msgmerge
    require_command msginit
}

relative_path() {
    case "$1" in
        "${repo_dir_path}"/*) printf '%s\n' "${1#"${repo_dir_path}/"}" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

locale_po_path() {
    printf '%s/%s/LC_MESSAGES/%s.po\n' "$i18n_dir" "$1" "$domain"
}

locale_mo_path() {
    printf '%s/%s/LC_MESSAGES/%s.mo\n' "$i18n_dir" "$1" "$domain"
}

existing_locales() {
    if [ ! -d "$i18n_dir" ]; then
        return
    fi

    find "$i18n_dir" -mindepth 1 -maxdepth 1 -type d -exec sh -c \
        'for dir_path do test -f "$dir_path/LC_MESSAGES/steammetadatatool.po" && basename "$dir_path"; done' \
        sh {} + | sort
}

write_python_source_list() {
    (
        cd "$repo_dir_path"
        find src -type f -name '*.py' | sort
    ) >"$1"
}

write_pot_spdx_header() {
    output_file="$1"
    headerless_file="$2"

    awk '
        /^msgid ""$/ { found_header = 1 }
        found_header { print }
    ' "$output_file" >"$headerless_file"

    {
        printf '%s\n' "$spdx_copyright_text"
        printf '%s\n' "$spdx_license_identifier"
        cat "$headerless_file"
    } >"$output_file"
}

extract_messages() {
    require_gettext
    if [ ! -f "$metainfo_its" ]; then
        printf '%s %s\n' 'Missing gettext metainfo ITS rules:' "$metainfo_its" >&2
        exit 1
    fi

    mkdir -p "$i18n_dir"
    tmp_dir_path="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir_path"' EXIT INT TERM
    python_sources_file="${tmp_dir_path}/python-sources"

    write_python_source_list "$python_sources_file"

    (
        cd "$repo_dir_path"
        xgettext \
            --language=Python \
            --from-code=UTF-8 \
            --keyword=_ \
            --keyword=ngettext:1,2 \
            --package-name="$domain" \
            --copyright-holder="$copyright_holder" \
            --msgid-bugs-address="$msgid_bugs_address" \
            --output="$pot_file" \
            --files-from="$python_sources_file"

        xgettext \
            --language=Desktop \
            --from-code=UTF-8 \
            --join-existing \
            --package-name="$domain" \
            --copyright-holder="$copyright_holder" \
            --msgid-bugs-address="$msgid_bugs_address" \
            --output="$pot_file" \
            "$(relative_path "$desktop_file")"

        xgettext \
            --its="$metainfo_its" \
            --join-existing \
            --package-name="$domain" \
            --copyright-holder="$copyright_holder" \
            --msgid-bugs-address="$msgid_bugs_address" \
            --output="$pot_file" \
            "$(relative_path "$metainfo_file")"
    )

    write_pot_spdx_header "$pot_file" "${tmp_dir_path}/pot-headerless"
    printf '%s %s\n' 'Wrote' "$(relative_path "$pot_file")"
}

init_locale() {
    require_gettext
    if [ "$#" -ne 1 ]; then
        usage >&2
        exit 1
    fi

    locale_name="$1"
    po_path="$(locale_po_path "$locale_name")"
    if [ -f "$po_path" ]; then
        printf '%s\n' "$(relative_path "$po_path") already exists." >&2
        exit 1
    fi

    if [ ! -f "$pot_file" ]; then
        extract_messages
    fi

    mkdir -p "$(dirname "$po_path")"
    msginit \
        --no-translator \
        --locale="$locale_name" \
        --input="$pot_file" \
        --output-file="$po_path"
    printf '%s %s\n' 'Created' "$(relative_path "$po_path")"
}

update_locales() {
    require_gettext
    extract_messages

    if [ "$#" -gt 0 ]; then
        locales="$*"
    else
        locales="$(existing_locales)"
    fi

    for locale_name in $locales; do
        po_path="$(locale_po_path "$locale_name")"
        if [ ! -f "$po_path" ]; then
            printf '%s %s\n' 'Missing' "$(relative_path "$po_path")" >&2
            exit 1
        fi
        msgmerge --update --backup=none "$po_path" "$pot_file"
        printf '%s %s\n' 'Updated' "$(relative_path "$po_path")"
    done
}

strip_desktop_translations() {
    sed '/^\(Name\|GenericName\|Comment\)\[[^]]*\]=/d' "$desktop_file" >"$1"
}

strip_metainfo_translations() {
    sed '/<\(name\|summary\|p\|keyword\)[^>]* xml:lang="[^"]*"/d' \
        "$metainfo_file" >"$1"
}

compile_locales() {
    require_gettext
    if [ ! -f "$metainfo_its" ]; then
        printf '%s %s\n' 'Missing gettext metainfo ITS rules:' "$metainfo_its" >&2
        exit 1
    fi

    if [ "$#" -gt 0 ]; then
        locales="$*"
    else
        locales="$(existing_locales)"
    fi

    tmp_dir_path="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir_path"' EXIT INT TERM
    desktop_template="${tmp_dir_path}/template.desktop"
    desktop_output="${tmp_dir_path}/output.desktop"
    metainfo_template="${tmp_dir_path}/template.metainfo.xml"
    metainfo_output="${tmp_dir_path}/output.metainfo.xml"

    strip_desktop_translations "$desktop_template"
    cp "$desktop_template" "$desktop_output"
    strip_metainfo_translations "$metainfo_template"
    cp "$metainfo_template" "$metainfo_output"

    for locale_name in $locales; do
        po_path="$(locale_po_path "$locale_name")"
        mo_path="$(locale_mo_path "$locale_name")"
        if [ ! -f "$po_path" ]; then
            printf '%s %s\n' 'Missing' "$(relative_path "$po_path")" >&2
            exit 1
        fi

        mkdir -p "$(dirname "$mo_path")"
        msgfmt --check --output-file="$mo_path" "$po_path"

        msgfmt \
            --desktop \
            --template="$desktop_output" \
            --locale="$locale_name" \
            --output-file="${desktop_output}.next" \
            "$po_path"
        mv "${desktop_output}.next" "$desktop_output"

        msgfmt \
            --xml \
            --language=metainfo \
            --template="$metainfo_output" \
            --locale="$locale_name" \
            --output-file="${metainfo_output}.next" \
            "$po_path"
        mv "${metainfo_output}.next" "$metainfo_output"

        printf '%s %s\n' 'Compiled' "$(relative_path "$mo_path")"
    done

    cp "$desktop_output" "$desktop_file"
    cp "$metainfo_output" "$metainfo_file"
    printf '%s\n' 'Refreshed translated desktop and metainfo files.'
}

if [ "$#" -lt 1 ]; then
    usage >&2
    exit 1
fi

command_name="$1"
shift

case "$command_name" in
    extract) extract_messages "$@" ;;
    init) init_locale "$@" ;;
    update) update_locales "$@" ;;
    compile) compile_locales "$@" ;;
    -h|--help|help) usage ;;
    *)
        usage >&2
        exit 1
        ;;
esac
