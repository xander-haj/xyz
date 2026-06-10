# Zelda3 Randomizer Instructions

This randomizer is an early, conservative first pass. It randomizes dungeon chest item values in the extracted YAML files before `compile_resources.py` builds `zelda3_assets.dat`.

It does not yet randomize overworld secrets, dungeon pot secrets, NPC gifts, shops, boss prizes, entrances, exits, holes, sprites, or room layouts.

## Basic Workflow

Run commands from the project root.

On Windows, the command is usually `python`. On macOS/Linux, use the project's virtual environment if your system Python does not have PyYAML:

```bash
venv/bin/python assets/restool-randomize.py --seed my-first-seed
```

In every example below, `12345` and `my-first-seed` are example seed values. You can type either one exactly, or replace it with your own seed text. The same seed gives the same randomization.

## If You Already Extracted Assets

If you already ran this command:

```bash
python assets/restool.py --extract-from-rom
```

then the YAML files already exist in `assets/dungeon/` and `assets/overworld/`. You can run:

```bash
python assets/restool-randomize.py --seed my-first-seed
```

Then compile the randomized YAML into `zelda3_assets.dat`:

```bash
python assets/restool.py
```

Run the game normally. The compiled `zelda3_assets.dat` now contains the randomized chest data.

## Fresh Workflow

If you want to start from clean extracted ROM assets, run extraction without compiling:

```bash
python assets/restool.py --extract-from-rom --no-build
```

Then randomize dungeon chest items:

```bash
python assets/restool-randomize.py --seed my-first-seed
```

Then compile the randomized assets:

```bash
python assets/restool.py
```

Run the game normally. The compiled `zelda3_assets.dat` now contains the randomized chest data.

## Making a New Seed Before Compiling

If you run the randomizer and decide you want a different seed before running `python assets/restool.py`, re-extract clean YAML first:

```bash
python assets/restool.py --extract-from-rom --no-build
```

Then run the randomizer again with a new seed:

```bash
python assets/restool-randomize.py --seed another-seed
```

Then compile:

```bash
python assets/restool.py
```

This matters because the randomizer writes into the extracted YAML files. Re-extracting first resets those YAML files back to the original ROM data so the new seed starts clean.

## Important Safety Notes

Running `python assets/restool.py --extract-from-rom` without `--no-build` extracts fresh YAML from the ROM and then compiles immediately. That overwrites randomized YAML before the game is built.

Small-key chest items are not shuffled by default.

Big-key-locked chest locations are not shuffled by default.

Sprite key drops are not touched by this first version.

## Seeds

Use `--seed` to make a run reproducible:

```bash
python assets/restool-randomize.py --seed 12345
```

If you omit `--seed`, the tool generates a random seed and prints it.

## Spoiler Logs

By default, the tool writes a spoiler log here:

```text
assets/randomizer-spoilers/<seed>.md
```

Use a custom spoiler path:

```bash
python assets/restool-randomize.py --seed 12345 --spoiler my-spoiler.md
```

Disable spoiler output:

```bash
python assets/restool-randomize.py --seed 12345 --no-spoiler
```

## Dry Runs

Use `--dry-run` to preview what would happen without writing YAML files:

```bash
python assets/restool-randomize.py --seed 12345 --dry-run
```

This still writes a spoiler log unless `--no-spoiler` is also provided.

## Exclusions

Exclude a dungeon room:

```bash
python assets/restool-randomize.py --seed 12345 --exclude-room 260
```

Exclude a specific chest location:

```bash
python assets/restool-randomize.py --seed 12345 --exclude-location room:260:chest:0
```

Exclude an item id:

```bash
python assets/restool-randomize.py --seed 12345 --exclude-item 0x32
```

Exclude an item category:

```bash
python assets/restool-randomize.py --seed 12345 --exclude-category big-key
```

Supported categories are:

- `item`
- `small-key`
- `big-key`
- `map`
- `compass`

Repeated and comma-separated exclusions are both allowed:

```bash
python assets/restool-randomize.py --seed 12345 --exclude-room 260,261 --exclude-room 262
```

## Advanced Safety Options

Include small-key chest items in the shuffle:

```bash
python assets/restool-randomize.py --seed 12345 --include-small-keys
```

Include big-key-locked chest locations in the shuffle:

```bash
python assets/restool-randomize.py --seed 12345 --include-big-chests
```

These options can create rougher seeds because this first version does not yet have a full progression logic solver.

## Current Limitations

This is not a complete traditional randomizer yet. It is the first stable workflow slice:

- deterministic seed handling
- dungeon chest item shuffling
- excluded rooms, locations, items, and categories
- small-key isolation
- big-key-locked chest isolation
- spoiler log generation

Future work should add overworld checks, pot/secret checks, scripted rewards, shops, boss prizes, an item-location catalog, and a progression logic solver.
