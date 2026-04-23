# SteamMetadataTool

A tool for reading and editing Steam client metadata.

- List app IDs and names from your local Steam install.
- Dump a specific app record as JSON.
- Make simple edits to the name, sort-as, aliases, release dates, etc.

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

## Editing

Apply per-app changes:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike (Modded)" \
  --sort-as "CS" \
  --aliases "csgo, cs2" \
  --steam-release-date 2000-11-08
```

Dry-run (no write):

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike (Modded)" \
  --dry-run
```

Write changes to a JSON file:

```bash
uv run steammetadatatool-cli \
  --appid 730 \
  --name "Counter-Strike 2 (Modded)" \
  --write-changes-file user-changes.json
```

Apply changes from a JSON file for a specific app:

```bash
uv run steammetadatatool-cli \
  --changes-file user-changes.json \
  --appid 730
```

Apply changes from a JSON file for all apps:

```bash
uv run steammetadatatool-cli \
  --changes-file user-changes.json
```

Set arbitrary KV path:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --set appinfo.common.sortas=CS \
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
