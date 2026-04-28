<!--
SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later
-->

<div id="top"></div>

<br>

<h1 align="center">
  <img src="data/sc-apps-steammetadatatool.svg" alt="SteamMetadataTool Logo" width="192" height="auto"/>
  <br><br>
  SteamMetadataTool
  <br><br>
</h1>

<p align="center">
  <a href="#top">Overview</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#editing">Editing</a> •
  <a href="#license">License</a>
</p>

SteamMetadataTool is a desktop and command-line utility for inspecting and customizing game metadata used by the Steam client. It can browse installed apps, export metadata, and apply local overrides without replacing the original workflow.

- List app IDs and game names from a local Steam installation.
- Export app records as JSON for inspection or backup.
- Edit names, sort-as values, aliases, release dates, and other metadata fields.
- Set custom Steam library artwork, including capsules, headers, heroes, logos, and icons.
- Preview, save, and apply metadata overrides.

The GUI provides a searchable app list, metadata filtering, app detail preview, and dialog for editing metadata values. It also shows Steam library assets and supports choosing between original and custom artwork variants from per-app asset folders.

> [!NOTE]
> This tool is not affiliated with Valve Corporation or Steam.
>
> Steam is a registered trademark of Valve Corporation and is referenced solely for descriptive purposes.

## Installation

The tool is split into two components: a CLI and a GUI.

### CLI

To install the CLI only:

```bash
uv sync
```

### GUI

To install the GUI and CLI together:

```bash
uv sync --extra gui
```

## Usage

### CLI

List apps:

```bash
uv run steammetadatatool-cli
```

Dump an app as JSON:

```bash
uv run steammetadatatool-cli --appid 730 --json | python -m json.tool
```

### GUI

```bash
uv run --extra gui steammetadatatool-gui
```

## Steam Library Assets

Steam Library assets are images that represent games in the Steam Library. They are used to display game information and artwork in the library view. The required assets and their specifications are as follows:

| Asset   | Required size                   |
| ------- | ------------------------------- |
| Capsule | 600 px by 900 px                |
| Header  | 920 px by 430 px                |
| Hero    | 3840 px by 1240 px              |
| Logo    | 1280 px wide and/or 720 px tall |
| Icon    | 184 px by 184 px                |

The full specification can be found at: <https://partner.steamgames.com/doc/store/assets>.

## Editing

Apply per-app metadata overrides:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --sort-as "cs" \
  --aliases "cs, 16" \
  --steam-release-date 2000-11-08
```

Dry-run (no write):

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --dry-run
```

Write metadata overrides to a JSON file:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --metadata-file metadata.json
```

Apply metadata overrides from a JSON file for a specific app:

```bash
uv run steammetadatatool-cli \
  --metadata-file metadata.json \
  --appid 730
```

Apply metadata overrides from a JSON file for all apps:

```bash
uv run steammetadatatool-cli \
  --metadata-file metadata.json
```

Set arbitrary KV path:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --set appinfo.common.sortas="cs" \
  --set appinfo.common.original_release_date=946684800
```

### Write to a new file

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike (Modded)" \
  --aliases "csgo, cs2" \
  --write-out /tmp/appinfo.vdf
```

## License

This project is licensed under the GNU General Public License version 3 or later. See the [LICENSE](LICENSE.md) file for details. The application logo is not covered by the GNU GPL v3 or later and may not be used without prior permission.
