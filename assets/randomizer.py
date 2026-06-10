# randomizer.py -- Conservative YAML-backed item randomizer helpers.
#
# This module implements the first randomizer slice for the zelda3 asset pipeline:
# deterministic shuffling of dungeon chest item values that already live in
# extracted YAML files. It intentionally avoids structural YAML fields, scripted
# NPC rewards, overworld secrets, dungeon pot secrets, and sprite key drops until
# those systems have dedicated logic and validation.

from dataclasses import dataclass
import json
import os
import random
from typing import Iterable

import yaml


# Item ids that need special treatment to avoid obvious first-pass softlocks.
SMALL_KEY_ITEM = 0x24
BIG_KEY_ITEM = 0x32
COMPASS_ITEM = 0x25
MAP_ITEM = 0x33
DEFAULT_MASTERLIST_PATH = "randomizer-masterlist.json"
SAFE_MODE = "safe"
LAMP_ITEM = 0x12
FIRE_ROD_ITEM = 0x07
SAFE_MODE_LIGHT_ITEMS = {LAMP_ITEM, FIRE_ROD_ITEM}
SAFE_MODE_LIGHT_LOCATIONS = {
  "room:260:chest:0",
  "room:85:chest:0",
  "room:128:chest:0",
}


# Human-readable labels used in spoiler logs. Unknown ids remain safe because the
# compiler only cares about the numeric item id.
ITEM_NAMES = {
  FIRE_ROD_ITEM: "Fire Rod",
  LAMP_ITEM: "Lamp",
  SMALL_KEY_ITEM: "Small Key",
  BIG_KEY_ITEM: "Big Key",
  COMPASS_ITEM: "Compass",
  MAP_ITEM: "Dungeon Map",
}


# Represents one chest entry inside one dungeon YAML file.
# room is the dungeon room id, slot is the zero-based index within Chests,
# item is the numeric Link_ReceiveItem id, and big_chest preserves the YAML
# exclamation marker that makes the runtime require a big key for the location.
@dataclass
class ChestLocation:
  room: int
  slot: int
  item: int
  big_chest: bool

  # Returns the stable id users can pass to --exclude-location.
  def location_id(self) -> str:
    return f"room:{self.room}:chest:{self.slot}"

  # Returns the item category used by exclusion and safety filters.
  def category(self) -> str:
    if self.item == SMALL_KEY_ITEM:
      return "small-key"
    if self.item == BIG_KEY_ITEM:
      return "big-key"
    if self.item == COMPASS_ITEM:
      return "compass"
    if self.item == MAP_ITEM:
      return "map"
    return "item"

  # Converts the in-memory item back to the YAML representation expected by
  # compile_resources.py, preserving the big-chest marker when needed.
  def to_yaml_value(self):
    return f"{self.item}!" if self.big_chest else self.item


# Captures the randomizer settings after CLI parsing so the engine can stay free
# of argparse-specific details.
@dataclass
class RandomizerOptions:
  seed: str
  dungeon_dir: str
  spoiler_path: str | None
  dry_run: bool
  include_small_keys: bool
  include_big_chests: bool
  exclude_rooms: set[int]
  exclude_locations: set[str]
  exclude_items: set[int]
  exclude_categories: set[str]
  mode: str = SAFE_MODE


# Normalizes comma-separated and repeated CLI values into one flat list.
# values is an iterable of optional strings; each string may contain commas.
# Returns stripped non-empty entries in original order.
def split_csv_values(values: Iterable[str] | None) -> list[str]:
  if not values:
    return []
  result = []
  for value in values:
    for part in value.split(","):
      part = part.strip()
      if part:
        result.append(part)
  return result


# Parses comma-separated integer values. Supports decimal and 0x-prefixed hex
# because item ids are commonly discussed in both formats.
# values is an iterable of CLI strings; label appears in any validation error.
# Returns a set of parsed integers.
def parse_int_set(values: Iterable[str] | None, label: str) -> set[int]:
  result = set()
  for value in split_csv_values(values):
    try:
      result.add(int(value, 0))
    except ValueError as exc:
      raise ValueError(f"Invalid {label}: {value}") from exc
  return result


# Converts a YAML chest value into a ChestLocation. The extractor writes normal
# chests as integers and big-key-locked chest entries as strings like "27!".
# room and slot identify where the value came from.
def parse_chest_value(room: int, slot: int, value) -> ChestLocation:
  if isinstance(value, int):
    return ChestLocation(room=room, slot=slot, item=value, big_chest=False)
  if isinstance(value, str) and value.endswith("!"):
    return ChestLocation(room=room, slot=slot, item=int(value[:-1], 0), big_chest=True)
  raise ValueError(f"Unsupported chest value in room {room}, slot {slot}: {value!r}")


# Loads every dungeon YAML file that has a numeric dungeon-N.yaml name.
# dungeon_dir is relative to assets/ unless the caller supplies an absolute path.
# Returns a dict of room id to parsed YAML dict.
def load_dungeon_files(dungeon_dir: str) -> dict[int, dict]:
  rooms = {}
  for name in sorted(os.listdir(dungeon_dir)):
    if not name.startswith("dungeon-") or not name.endswith(".yaml"):
      continue
    room_text = name[len("dungeon-"):-len(".yaml")]
    if not room_text.isdigit():
      continue
    room = int(room_text)
    path = os.path.join(dungeon_dir, name)
    with open(path, "r") as handle:
      rooms[room] = yaml.safe_load(handle)
  return rooms


# Writes the parsed dungeon YAML files back to disk after item values have been
# replaced. Only files whose Chests list changed are written.
# rooms is the mutable room data dict, and changed_rooms names the room ids to save.
def write_changed_dungeon_files(
  dungeon_dir: str,
  rooms: dict[int, dict],
  changed_rooms: set[int],
) -> None:
  for room in sorted(changed_rooms):
    path = os.path.join(dungeon_dir, f"dungeon-{room}.yaml")
    with open(path, "w") as handle:
      yaml.safe_dump(rooms[room], handle, sort_keys=False, default_flow_style=False)


# Finds every chest-bearing location in loaded room data.
# rooms is the parsed YAML dict keyed by room id.
# Returns ChestLocation entries in deterministic room/slot order.
def collect_chests(rooms: dict[int, dict]) -> list[ChestLocation]:
  locations = []
  for room in sorted(rooms):
    for slot, value in enumerate(rooms[room].get("Chests", [])):
      locations.append(parse_chest_value(room, slot, value))
  return locations


# Creates default eligibility options for reporting which locations are included
# when the user does not enable extra categories or set exclusions.
def default_masterlist_options() -> RandomizerOptions:
  return RandomizerOptions(
    seed="vanilla-masterlist", dungeon_dir="dungeon", spoiler_path=None, dry_run=True,
    include_small_keys=False,
    include_big_chests=False,
    exclude_rooms=set(),
    exclude_locations=set(),
    exclude_items=set(),
    exclude_categories=set(),
  )


# Converts one chest location into a JSON-safe masterlist entry.
def location_to_masterlist_entry(location: ChestLocation, options: RandomizerOptions) -> dict:
  return {
    "id": location.location_id(),
    "room": location.room,
    "slot": location.slot,
    "item": location.item,
    "category": location.category(),
    "big_chest": location.big_chest,
    "randomized_by_default": is_eligible(location, options),
  }


# Generates a vanilla masterlist from the currently extracted dungeon YAML.
# The caller should run this immediately after clean extraction and before
# randomization so restore has a trustworthy source of vanilla chest values.
def generate_masterlist(dungeon_dir: str, masterlist_path: str = DEFAULT_MASTERLIST_PATH) -> dict:
  rooms = load_dungeon_files(dungeon_dir)
  locations = collect_chests(rooms)
  default_options = default_masterlist_options()
  manifest = {
    "version": 1,
    "mode": "dungeon-chest-item-shuffle",
    "dungeon_dir": dungeon_dir,
    "total_locations": len(locations),
    "randomized_by_default": sum(1 for location in locations if is_eligible(location, default_options)),
    "locations": [location_to_masterlist_entry(location, default_options) for location in locations],
  }
  with open(masterlist_path, "w") as handle:
    json.dump(manifest, handle, indent=2)
    handle.write("\n")
  return manifest


# Loads and validates the generated vanilla masterlist file.
def load_masterlist(masterlist_path: str = DEFAULT_MASTERLIST_PATH) -> dict:
  with open(masterlist_path, "r") as handle:
    manifest = json.load(handle)
  if manifest.get("version") != 1 or "locations" not in manifest:
    raise ValueError(f"Unsupported randomizer masterlist format: {masterlist_path}")
  return manifest


# Restores dungeon chest YAML values from a previously generated vanilla masterlist.
def restore_from_masterlist(dungeon_dir: str, masterlist_path: str = DEFAULT_MASTERLIST_PATH) -> dict:
  rooms = load_dungeon_files(dungeon_dir)
  manifest = load_masterlist(masterlist_path)
  changed_rooms = set()
  restored_locations = 0

  for entry in manifest["locations"]:
    room = int(entry["room"])
    slot = int(entry["slot"])
    item = int(entry["item"])
    big_chest = bool(entry["big_chest"])
    vanilla = ChestLocation(room=room, slot=slot, item=item, big_chest=big_chest)

    if room not in rooms or slot >= len(rooms[room].get("Chests", [])):
      raise ValueError(f"Masterlist location is missing from extracted YAML: {entry['id']}")

    if rooms[room]["Chests"][slot] != vanilla.to_yaml_value():
      rooms[room]["Chests"][slot] = vanilla.to_yaml_value()
      changed_rooms.add(room)
      restored_locations += 1

  write_changed_dungeon_files(dungeon_dir, rooms, changed_rooms)
  return {
    "total_locations": len(manifest["locations"]),
    "restored_locations": restored_locations,
    "changed_rooms": len(changed_rooms),
    "masterlist_path": masterlist_path,
  }


# Decides whether a chest location can participate in the current shuffle.
# The filters intentionally default to conservative behavior: small keys stay
# fixed, and big-key-locked chests stay fixed unless explicitly enabled.
def is_eligible(location: ChestLocation, options: RandomizerOptions) -> bool:
  if location.room in options.exclude_rooms:
    return False
  if location.location_id() in options.exclude_locations:
    return False
  if location.item in options.exclude_items:
    return False
  if location.category() in options.exclude_categories:
    return False
  if location.big_chest and not options.include_big_chests:
    return False
  if location.item == SMALL_KEY_ITEM and not options.include_small_keys:
    return False
  return True


# Produces stable user-facing text for one item id.
def describe_item(item: int) -> str:
  name = ITEM_NAMES.get(item, "Item")
  return f"{item} ({name})"


# Adjusts a completed shuffle so Safe Mode always leaves Lamp or Fire Rod in
# one of the three early Lamp chest locations needed before the castle throne.
def enforce_safe_mode_light_access(
  locations: list[ChestLocation],
  shuffled_items: list[int],
) -> None:
  early_indexes = [
    index for index, location in enumerate(locations)
    if location.location_id() in SAFE_MODE_LIGHT_LOCATIONS
  ]
  if any(shuffled_items[index] in SAFE_MODE_LIGHT_ITEMS for index in early_indexes):
    return

  light_index = next(
    (index for index, item in enumerate(shuffled_items) if item in SAFE_MODE_LIGHT_ITEMS),
    None,
  )
  if light_index is None or not early_indexes:
    raise ValueError("Safe Mode needs Lamp or Fire Rod and at least one early Lamp location in the item pool.")

  target_index = early_indexes[0]
  shuffled_items[target_index], shuffled_items[light_index] = shuffled_items[light_index], shuffled_items[target_index]


# Applies the shuffled item values back into the parsed YAML room structures.
# locations are the original eligible positions; shuffled_items are the new item
# ids in matching order. Returns room ids that changed.
def apply_shuffled_items(
  rooms: dict[int, dict],
  locations: list[ChestLocation],
  shuffled_items: list[int],
) -> set[int]:
  changed_rooms = set()
  for location, item in zip(locations, shuffled_items):
    if location.item == item:
      continue
    changed = ChestLocation(room=location.room, slot=location.slot, item=item, big_chest=location.big_chest)
    rooms[location.room]["Chests"][location.slot] = changed.to_yaml_value()
    changed_rooms.add(location.room)
  return changed_rooms


# Writes a Markdown spoiler log that records the seed, safety settings, excluded
# categories, and every changed chest location.
def write_spoiler(
  path: str,
  seed: str,
  before: list[ChestLocation],
  after_items: list[int],
  options: RandomizerOptions,
) -> None:
  output_dir = os.path.dirname(path)
  if output_dir:
    os.makedirs(output_dir, exist_ok=True)
  with open(path, "w") as handle:
    handle.write(f"# Zelda3 Randomizer Spoiler\n\n")
    handle.write(f"- Seed: `{seed}`\n")
    handle.write(f"- Mode: `{options.mode}` dungeon chest item shuffle\n")
    handle.write(f"- Small keys included: `{options.include_small_keys}`\n")
    handle.write(f"- Big-key-locked chests included: `{options.include_big_chests}`\n\n")
    handle.write("## Exclusions\n\n")
    handle.write(f"- Rooms: `{sorted(options.exclude_rooms)}`\n")
    handle.write(f"- Locations: `{sorted(options.exclude_locations)}`\n")
    handle.write(f"- Items: `{sorted(options.exclude_items)}`\n")
    handle.write(f"- Categories: `{sorted(options.exclude_categories)}`\n\n")
    handle.write("## Chest Assignments\n\n")
    for location, item in zip(before, after_items):
      handle.write(
        f"- `{location.location_id()}`: {describe_item(location.item)} -> {describe_item(item)}\n"
      )


# Runs the first-pass randomizer workflow: load dungeon YAML, collect eligible
# chest entries, shuffle their item ids with the requested seed, write changed
# YAML unless this is a dry run, and emit a spoiler log if requested.
def randomize_dungeon_chests(options: RandomizerOptions) -> dict:
  rooms = load_dungeon_files(options.dungeon_dir)
  all_locations = collect_chests(rooms)
  eligible = [location for location in all_locations if is_eligible(location, options)]
  if len(eligible) < 2:
    raise ValueError("Need at least two eligible chest locations to randomize.")

  rng = random.Random(options.seed)
  shuffled_items = [location.item for location in eligible]
  rng.shuffle(shuffled_items)

  if options.mode == SAFE_MODE:
    enforce_safe_mode_light_access(eligible, shuffled_items)

  changed_rooms = apply_shuffled_items(rooms, eligible, shuffled_items)

  if not options.dry_run:
    if not os.path.isfile(DEFAULT_MASTERLIST_PATH):
      generate_masterlist(options.dungeon_dir, DEFAULT_MASTERLIST_PATH)
    write_changed_dungeon_files(options.dungeon_dir, rooms, changed_rooms)
  if options.spoiler_path:
    write_spoiler(options.spoiler_path, options.seed, eligible, shuffled_items, options)

  return {
    "total_chests": len(all_locations),
    "eligible_chests": len(eligible),
    "changed_chests": sum(1 for location, item in zip(eligible, shuffled_items) if location.item != item),
    "changed_rooms": len(changed_rooms),
    "spoiler_path": options.spoiler_path,
    "dry_run": options.dry_run,
    "mode": options.mode,
  }
