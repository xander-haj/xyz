# restool-randomize.py -- CLI entry point for zelda3 randomizer workflows.
#
# This script is intentionally separate from restool.py so normal extraction and
# compilation remain stable. The first workflow randomizes only YAML-backed
# dungeon chest item ids, using a deterministic seed and conservative defaults
# that avoid small-key and big-key-locked chest softlock traps.

import argparse
import os
import secrets

from randomizer import RandomizerOptions
from randomizer import DEFAULT_MASTERLIST_PATH
from randomizer import SAFE_MODE
from randomizer import generate_masterlist
from randomizer import parse_int_set
from randomizer import randomize_dungeon_chests
from randomizer import restore_from_masterlist
from randomizer import split_csv_values


# Moves execution into assets/ so dungeon YAML paths match compile_resources.py.
ASSETS_DIR = os.path.dirname(__file__)
os.chdir(ASSETS_DIR)


# Builds and returns the command-line parser for the randomizer entry point.
# Parameters: none.
# Returns: configured argparse.ArgumentParser.
def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description="Randomize extracted zelda3 asset YAML before compiling zelda3_assets.dat.",
    allow_abbrev=False,
  )
  parser.add_argument("--seed", help="Seed text. If omitted, a random hex seed is generated.")
  parser.add_argument("--dry-run", action="store_true", help="Create a spoiler log without writing YAML files.")
  parser.add_argument("--no-spoiler", action="store_true", help="Do not write a spoiler log.")
  parser.add_argument("--spoiler", help="Spoiler log path. Defaults to randomizer-spoilers/<seed>.md.")
  parser.add_argument("--dungeon-dir", default="dungeon", help="Directory containing dungeon-N.yaml files.")
  parser.add_argument("--mode", default=SAFE_MODE, choices=[SAFE_MODE], help="Randomizer mode to apply.")
  parser.add_argument(
    "--masterlist",
    default=DEFAULT_MASTERLIST_PATH,
    help="Vanilla masterlist path used for generation and restore.",
  )
  parser.add_argument(
    "--generate-masterlist",
    action="store_true",
    help="Write the vanilla masterlist from currently extracted YAML and exit.",
  )
  parser.add_argument(
    "--restore-vanilla",
    action="store_true",
    help="Restore dungeon chest YAML from the vanilla masterlist and exit.",
  )
  parser.add_argument("--include-small-keys", action="store_true", help="Allow small-key chest items to shuffle.")
  parser.add_argument(
    "--include-big-chests",
    action="store_true",
    help="Allow big-key-locked chest locations to shuffle.",
  )
  parser.add_argument("--exclude-room", action="append", help="Room id to exclude. Can be repeated or comma-separated.")
  parser.add_argument("--exclude-location", action="append", help="Location id to exclude, such as room:260:chest:0.")
  parser.add_argument("--exclude-item", action="append", help="Item id to exclude. Supports decimal or 0x hex.")
  parser.add_argument(
    "--exclude-category",
    action="append",
    help="Category to exclude: item, small-key, big-key, map, or compass.",
  )
  return parser


# Converts parsed argparse values into RandomizerOptions.
# Parameters:
#   args - argparse namespace returned by build_parser().parse_args().
# Returns: RandomizerOptions used by the randomizer engine.
def options_from_args(args: argparse.Namespace) -> RandomizerOptions:
  seed = args.seed or secrets.token_hex(8)
  spoiler_path = None
  if not args.no_spoiler:
    spoiler_path = args.spoiler or os.path.join("randomizer-spoilers", f"{seed}.md")

  return RandomizerOptions(
    seed=seed,
    dungeon_dir=args.dungeon_dir,
    spoiler_path=spoiler_path,
    dry_run=args.dry_run,
    include_small_keys=args.include_small_keys,
    include_big_chests=args.include_big_chests,
    exclude_rooms=parse_int_set(args.exclude_room, "room id"),
    exclude_locations=set(split_csv_values(args.exclude_location)),
    exclude_items=parse_int_set(args.exclude_item, "item id"),
    exclude_categories=set(split_csv_values(args.exclude_category)),
    mode=args.mode,
  )


# Program entry point. Parses CLI options, executes the chest randomizer, and
# prints a compact summary suitable for batch files or terminal use.
# Parameters: none.
# Returns: process exit code integer.
def main() -> int:
  parser = build_parser()
  args = parser.parse_args()

  if args.generate_masterlist and args.restore_vanilla:
    parser.error("--generate-masterlist and --restore-vanilla cannot be used together.")

  if args.generate_masterlist:
    manifest = generate_masterlist(args.dungeon_dir, args.masterlist)
    print(f"Masterlist: {args.masterlist}")
    print(f"Total chest locations: {manifest['total_locations']}")
    print(f"Randomized by default: {manifest['randomized_by_default']}")
    return 0

  if args.restore_vanilla:
    result = restore_from_masterlist(args.dungeon_dir, args.masterlist)
    print(f"Masterlist: {result['masterlist_path']}")
    print(f"Total chest locations: {result['total_locations']}")
    print(f"Restored chest locations: {result['restored_locations']}")
    print(f"Changed dungeon files: {result['changed_rooms']}")
    return 0

  options = options_from_args(args)
  result = randomize_dungeon_chests(options)

  print(f"Seed: {options.seed}")
  print(f"Mode: {result['mode']}")
  print(f"Total chest locations: {result['total_chests']}")
  print(f"Eligible chest locations: {result['eligible_chests']}")
  print(f"Changed chest locations: {result['changed_chests']}")
  print(f"Changed dungeon files: {result['changed_rooms']}")
  if result["dry_run"]:
    print("Dry run: YAML files were not written.")
  if result["spoiler_path"]:
    print(f"Spoiler log: {result['spoiler_path']}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
