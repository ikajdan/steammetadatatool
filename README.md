# SteamMetadataTool

Reads and rewrites Steam client's `appinfo.vdf`. This lets you:

- List app IDs and names from your local Steam install.
- Dump a specific app record as JSON.
- Make simple edits to the name, sort-as, aliases, release dates, etc.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

To launch the GUI, run:

```bash
python -m gui
```

List apps:

```bash
python main.py /path/to/appinfo.vdf
```

Dump an app as a JSON:

```bash
python main.py /path/to/appinfo.vdf --appid 730 --json | python -m json.tool
```

## Editing

Apply per-app changes using override flags:

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--name "Counter-Strike (Modded)" \
	--sort-as "CS" \
	--aliases "csgo, cs2" \
	--steam-release-date 2000-11-08
```

Print the modified appinfo without writing to disk:

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--name "Counter-Strike (Modded)" \
	--dry-run
```

Apply per-app changes from a JSON file:

```bash
python main.py /path/to/appinfo.vdf \
	--changes-file data/example-changes.json \
	--appid 730 \
	--json
```

Persist the effective per-app changes to a JSON changes file:

```bash
python main.py /path/to/appinfo.vdf \
	--appid 730 \
	--name "Counter-Strike 2 (Modded)" \
	--write-changes-file data/my-changes.json
```

If the target changes file already exists, entries are merged by `appid`. Existing app entries are updated, and new app entries are appended.

Set an arbitrary KV path using dot notation:

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--set appinfo.common.sortas=CS \
	--set appinfo.common.original_release_date=946684800 \
	--json
```

### Write to a new file

By default, override flags rewrite the original file in place and create a `.bak` backup.
Use `--write-out` to write to a separate file instead.

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--name "Counter-Strike (Modded)" \
	--aliases "csgo, cs2" \
	--write-out /tmp/appinfo.vdf
```
