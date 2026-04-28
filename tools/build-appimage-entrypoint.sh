#!/bin/sh
# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

set -eu

APP_NAME=SteamMetadataTool
APPIMAGETOOL_URL=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
APPIMAGETOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0

: "${APP_VERSION:?APP_VERSION must be set}"
: "${OUTPUT_DIR:?OUTPUT_DIR must be set}"

export DEBIAN_FRONTEND=noninteractive

apt_get() {
    if [ "$(id -u)" -eq 0 ]; then
        apt-get "$@"
        return
    fi

    if ! command -v sudo >/dev/null 2>&1; then
        printf '%s\n' 'This script needs root privileges or sudo to install build packages.' >&2
        exit 1
    fi

    sudo --preserve-env=DEBIAN_FRONTEND apt-get "$@"
}

if [ ! -f pyproject.toml ]; then
    printf '%s\n' 'Run this script from the repository root.' >&2
    exit 1
fi

for required_file in \
    data/io.github.ikajdan.steammetadatatool.desktop \
    data/io.github.ikajdan.steammetadatatool.metainfo.xml \
    data/sc-apps-steammetadatatool.svg
do
    if [ ! -f "${required_file}" ]; then
        printf '%s %s\n' 'Missing required AppImage metadata file:' "${required_file}" >&2
        exit 1
    fi
done

APPIMAGE_PATH="${OUTPUT_DIR}/${APP_NAME}-${APP_VERSION}-x86_64.AppImage"

BUILD_PACKAGES='
    ca-certificates
    curl
    file
    patchelf
    python3
    python3-pip
    squashfs-tools
'

RUNTIME_PACKAGES='
    fonts-noto-core
    fonts-noto-mono
    fonts-noto-ui-core
    libbz2-1.0
    libdbus-1-3
    libegl1
    libfontconfig1
    libfreetype6
    libgl1
    libglib2.0-0
    libpcre3
    libx11-6
    libxcb-cursor0
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-render-util0
    libxcb-shape0
    libxcb-xfixes0
    libxcb-xinerama0
    libxcb-xinput0
    libxcb1
    libxext6
    libxkbcommon-x11-0
    libxrender1
    papirus-icon-theme
    zlib1g
'

apt_get update
apt_get install --assume-yes --no-install-recommends ${BUILD_PACKAGES}

curl --fail --location --show-error \
    "${APPIMAGETOOL_URL}" \
    --output /opt/appimagetool
printf 'Checking downloaded file hash: '
printf '%s  %s\n' "${APPIMAGETOOL_SHA256}" /opt/appimagetool | sha256sum --check -
chmod +x /opt/appimagetool

python3 -m pip install --user --break-system-packages --upgrade uv
export PATH="${HOME}/.local/bin:${PATH}"
uv python install 3.11
APPIMAGE_PYTHON="$(uv python find 3.11)"
APPIMAGE_PYTHON_HOME="$(dirname "$(dirname "${APPIMAGE_PYTHON}")")"

rm -rf AppDir build /tmp/appimage-debs
rm -f "${APP_NAME}"*.AppImage

mkdir -p "${OUTPUT_DIR}" AppDir/opt AppDir/usr/bin /tmp/appimage-debs
cp -aL "${APPIMAGE_PYTHON_HOME}" AppDir/opt/python3.11
test -x AppDir/opt/python3.11/bin/python3.11
patchelf --set-interpreter /lib64/ld-linux-x86-64.so.2 AppDir/opt/python3.11/bin/python3.11
AppDir/opt/python3.11/bin/python3.11 -m pip install \
    --break-system-packages \
    --ignore-installed \
    '.[gui]'
rm -f AppDir/opt/python3.11/bin/pyside6-* AppDir/opt/python3.11/bin/steammetadatatool-*

apt_get clean
apt_get install \
    --assume-yes \
    --download-only \
    --no-install-recommends \
    --reinstall \
    ${RUNTIME_PACKAGES}
cp /var/cache/apt/archives/*.deb /tmp/appimage-debs/
for deb in /tmp/appimage-debs/*.deb; do
    dpkg-deb -x "${deb}" AppDir
done

install -Dm644 data/io.github.ikajdan.steammetadatatool.desktop \
    AppDir/usr/share/applications/io.github.ikajdan.steammetadatatool.desktop
install -Dm644 data/io.github.ikajdan.steammetadatatool.metainfo.xml \
    AppDir/usr/share/metainfo/io.github.ikajdan.steammetadatatool.metainfo.xml
install -Dm644 data/sc-apps-steammetadatatool.svg \
    AppDir/usr/share/icons/hicolor/scalable/apps/steammetadatatool.svg
cp AppDir/usr/share/applications/io.github.ikajdan.steammetadatatool.desktop \
    AppDir/io.github.ikajdan.steammetadatatool.desktop
cp AppDir/usr/share/icons/hicolor/scalable/apps/steammetadatatool.svg \
    AppDir/steammetadatatool.svg

cat > AppDir/AppRun <<'APP_RUN_EOF'
#!/bin/sh
set -eu

APPDIR="${APPDIR:-.}"
PYTHON_HOME="${APPDIR}/opt/python3.11"

export APPDIR
export PATH="${PYTHON_HOME}/bin:${PATH:-}"
export XDG_DATA_DIRS="${APPDIR}/usr/local/share:${APPDIR}/usr/share:${XDG_DATA_DIRS:-}"
export QT_QPA_PLATFORMTHEME=""
export QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
export QT_PLUGIN_PATH="${PYTHON_HOME}/lib/python3.11/site-packages/PySide6/Qt/plugins"
export LD_LIBRARY_PATH="${PYTHON_HOME}/lib:${PYTHON_HOME}/lib/python3.11/site-packages/PySide6:${PYTHON_HOME}/lib/python3.11/site-packages/PySide6/Qt/lib:${PYTHON_HOME}/lib/python3.11/site-packages/shiboken6:${APPDIR}/usr/lib/x86_64-linux-gnu:${APPDIR}/lib/x86_64-linux-gnu:${APPDIR}/lib/x86_64:${LD_LIBRARY_PATH:-}"

exec /lib64/ld-linux-x86-64.so.2 "${PYTHON_HOME}/bin/python3.11" -m steammetadatatool.gui.main "$@"
APP_RUN_EOF
chmod +x AppDir/AppRun

rm -rf \
    AppDir/opt/python3.11/share/man \
    AppDir/usr/share/doc \
    AppDir/usr/share/lintian \
    AppDir/usr/share/man

ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 \
    /opt/appimagetool AppDir "${APPIMAGE_PATH}"
