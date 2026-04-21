# SteamMetadataTool

Reads and rewrites Steam client's `appinfo.vdf`. This lets you:

- List app IDs and names from your local Steam install.
- Dump a specific app record as JSON.
- Make simple edits to the name, sort-as, aliases, release dates, etc.

## Quickstart

List apps:

```bash
python main.py
```

List apps from an explicit file:

```bash
python main.py /path/to/appinfo.vdf
```

Dump one app as JSON:

```bash
python main.py /path/to/appinfo.vdf --appid 730 --json | python -m json.tool
```

## Editing

These flags change the output you see, but do not write back to disk unless you also use `--write-out` or `--in-place`.

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--name "Counter-Strike (Modded)" \
	--sort-as "CS" \
	--aliases "csgo, cs2" \
	--steam-release-date 2000-11-08 \
	--json
```

Apply per-app changes from a JSON file:

```bash
python main.py /path/to/appinfo.vdf \
	--changes-file data/example-changes.json \
	--appid 730 \
	--json
```

### Generic editing with `--set`

Set an arbitrary KV path using dot notation:

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--set appinfo.common.sortas=CS \
	--set appinfo.common.original_release_date=946684800 \
	--json
```

## Write-back

Modifies the appinfo in memory, then writes it back to disk. You can choose to write to a new file or rewrite the original.

### Write to a new file

Writes the modified appinfo to a new file, leaving the original unchanged.

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--name "Counter-Strike (Modded)" \
	--aliases "csgo, cs2" \
	--write-out /tmp/appinfo.vdf
```

Write using per-app changes from a file:

```bash
python main.py /path/to/appinfo.vdf \
	--changes-file data/example-changes.json \
	--write-out /tmp/appinfo.vdf
```

### Rewrite in place

Rewrites the original file with the modified appinfo.

```bash
python main.py /path/to/appinfo.vdf \
	--appid 10 \
	--name "Counter-Strike (Modded)" \
	--in-place
```
