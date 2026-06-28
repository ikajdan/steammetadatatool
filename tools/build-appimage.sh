#!/bin/sh
# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

set -eu

repo_dir_path="$(unset CDPATH && cd "$(dirname "$0")/.." && echo "$PWD")"
BUILD_DIR="${BUILD_DIR:-${repo_dir_path}/build}"
OUTPUT_DIR="${OUTPUT_DIR:-${BUILD_DIR}/appimage}"
WORK_DIR="${WORK_DIR:-${BUILD_DIR}/appimage-work}"

if [ ! -f "${repo_dir_path}/pyproject.toml" ]; then
    printf '%s\n' 'Cannot clearly determine the repository root. Bailing out.' >&2
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    printf '%s\n' 'Git is required to derive the AppImage version.' >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Docker is required to build the AppImage.' >&2
    exit 1
fi

PROJECT_VERSION="$(
    awk '
        /^\[project\]$/ { in_project = 1; next }
        /^\[/ { in_project = 0 }
        in_project && /^[[:space:]]*version[[:space:]]*=/ {
            sub(/^[^=]*=[[:space:]]*/, "")
            sub(/[[:space:]]*#.*/, "")
            gsub(/^[[:space:]]*"|"[[:space:]]*$/, "")
            print
            exit
        }
    ' "${repo_dir_path}/pyproject.toml"
)"

if [ -z "${PROJECT_VERSION}" ]; then
    printf '%s\n' 'Could not read project.version from pyproject.toml.' >&2
    exit 1
fi

if [ -z "${APP_VERSION:-}" ]; then
    GIT_HASH="$(git -C "${repo_dir_path}" rev-parse --short=12 HEAD)"
    APP_VERSION="${PROJECT_VERSION}.dev+g${GIT_HASH}"
fi
APPIMAGE_PATH="${OUTPUT_DIR}/SteamMetadataTool-${APP_VERSION}-x86_64.AppImage"
CONTAINER_REPO_DIR=/steammetadatatool
DOCKER_IMAGE="${DOCKER_IMAGE:-docker.io/library/ubuntu:24.04}"


remove_work_dir() {
    if [ ! -e "${WORK_DIR}" ]; then
        return
    fi

    if rm -rf "${WORK_DIR}" 2>/dev/null; then
        return
    fi

    if ! command -v sudo >/dev/null 2>&1; then
        printf '%s\n' "Could not remove ${WORK_DIR}; try removing it with elevated privileges." >&2
        return 1
    fi

    sudo chown -R "$(id -u):$(id -g)" "${WORK_DIR}"
    sudo chmod -R u+rwX "${WORK_DIR}"
    rm -rf "${WORK_DIR}"
}
trap remove_work_dir EXIT INT TERM

remove_work_dir
mkdir -p "${WORK_DIR}"

BUILD_CONTEXT_PATHS='
pyproject.toml
README.md
src
data
tools/build-appimage-entrypoint.sh
'

(
    cd "${repo_dir_path}"
    tar \
        --exclude=.git \
        --exclude=.venv \
        --exclude=build \
        --exclude=__pycache__ \
        --exclude='*.egg-info' \
        --exclude='*.pyc' \
        --exclude='*.pyo' \
        -cf - \
        ${BUILD_CONTEXT_PATHS}
) | tar -C "${WORK_DIR}" -xf -

mkdir -p "${OUTPUT_DIR}"

docker run -i --rm \
    --env "APP_VERSION=${APP_VERSION}" \
    --env OUTPUT_DIR=/out \
    --volume "${WORK_DIR}:${CONTAINER_REPO_DIR}:Z" \
    --volume "${OUTPUT_DIR}:/out:Z" \
    --workdir "${CONTAINER_REPO_DIR}" \
    --entrypoint /bin/sh \
    "${DOCKER_IMAGE}" \
    ./tools/build-appimage-entrypoint.sh

printf '\n%s %s\n' 'AppImage path:' "${APPIMAGE_PATH}"
