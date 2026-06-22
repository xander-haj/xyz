"""Validate overworld navigation metadata against fixed ROM table shapes."""

from __future__ import annotations

from pathlib import Path

import yaml

NAVIGATION_KINDS = {
  "metadata.travel",
  "metadata.entrance",
  "metadata.hole",
  "metadata.exit",
}
NAVIGATION_KEYS = {"Travel", "Entrances", "Holes", "Exits"}

BIRD_TRAVEL_SLOTS = 9
WHIRLPOOL_SLOTS = 8
ENTRANCE_SLOTS = 129
HOLE_SLOTS = 0x13
EXIT_SLOTS = 0x4F
SPECIAL_EXIT_ROOM_MIN = 0x180
SPECIAL_EXIT_ROOM_MAX = 0x18F

DOOR_TYPES = {"wooden", "bombable", "sanctuary", "palace"}
SPECIAL_EXIT_BYTE_FIELDS = {"spr_gfx", "aux_gfx", "pal_bg", "pal_spr"}
SPECIAL_EXIT_WORD_FIELDS = {"top", "bottom", "left", "right", "left_edge_of_map"}
SPECIAL_EXIT_INT16_FIELDS = {"unk4", "unk5", "unk6", "unk7"}


def is_navigation_operation(operation: dict) -> bool:
  """Return true when a metadata operation touches navigation tables."""
  if operation.get("kind") in NAVIGATION_KINDS:
    return True
  path = operation.get("path", [])
  key = path[0] if isinstance(path, list) and path else path
  return key in NAVIGATION_KEYS


def validate_navigation_tables(overworld_dir: Path) -> None:
  """Validate generated overworld YAML before compile_resources sees it."""
  state = {
    "bird_slots": set(),
    "whirlpools": 0,
    "whirlpool_sources": {},
    "entrances": {},
    "holes": {},
    "legacy_holes": [],
    "exits": {},
    "special_exits": {},
  }
  for path in sorted(overworld_dir.glob("overworld-*.yaml"), key=area_from_path):
    area = area_from_path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_travel(area, data.get("Travel") or [], state)
    validate_entrances(area, data.get("Entrances") or [], state)
    validate_holes(area, data.get("Holes") or [], state)
    validate_exits(area, data.get("Exits") or [], state)
  require_exact_slots("bird travel", state["bird_slots"], BIRD_TRAVEL_SLOTS)
  require_count("whirlpool travel", state["whirlpools"], WHIRLPOOL_SLOTS)
  require_exact_slots("entrance", state["entrances"], ENTRANCE_SLOTS)
  assign_legacy_hole_slots(state)
  require_exact_slots("hole", state["holes"], HOLE_SLOTS)
  require_exact_slots("exit", state["exits"], EXIT_SLOTS)


def validate_travel(area: int, rows: list, state: dict) -> None:
  """Validate kBirdTravel_* and kWhirlpoolAreas source rows."""
  for row_index, row in enumerate(rows):
    require_dict(row, "Travel", area, row_index)
    if deleted_row(row, "Travel", area, row_index):
      raise row_error("Travel", area, row_index, "deleted travel rows are not supported.")
    validate_destination_pairs(row, "Travel", area, row_index)
    has_bird_slot = "bird_travel_id" in row
    has_whirlpool_source = "whirlpool_src_area" in row
    if has_bird_slot == has_whirlpool_source:
      raise row_error("Travel", area, row_index,
                      "row must define exactly one of bird_travel_id or whirlpool_src_area.")
    if has_bird_slot:
      slot = int_field(row, "bird_travel_id", "Travel", area, row_index, 0, BIRD_TRAVEL_SLOTS - 1)
      require_unique_slot(state["bird_slots"], slot, "bird travel", area, row_index)
    else:
      source = int_field(row, "whirlpool_src_area", "Travel", area, row_index, 0, 0x9F)
      require_unique_slot(state["whirlpool_sources"], source, "whirlpool source", area, row_index)
      state["whirlpools"] += 1


def validate_entrances(area: int, rows: list, state: dict) -> None:
  """Validate kOverworld_Entrance_* source rows."""
  for row_index, row in enumerate(rows):
    require_dict(row, "Entrances", area, row_index)
    slot = int_field(row, "index", "Entrances", area, row_index, 0, ENTRANCE_SLOTS - 1)
    require_unique_slot(state["entrances"], slot, "entrance", area, row_index)
    if deleted_row(row, "Entrances", area, row_index):
      continue
    int_field(row, "x", "Entrances", area, row_index, 0, 0x3F)
    int_field(row, "y", "Entrances", area, row_index, 0, 0x3F)
    int_field(row, "entrance_id", "Entrances", area, row_index, 0, 0xFF)


def validate_holes(area: int, rows: list, state: dict) -> None:
  """Validate kFallHole_* source rows."""
  for row_index, row in enumerate(rows):
    require_dict(row, "Holes", area, row_index)
    slot = None
    if "index" in row:
      slot = int_field(row, "index", "Holes", area, row_index, 0, HOLE_SLOTS - 1)
      require_unique_slot(state["holes"], slot, "hole", area, row_index)
    if deleted_row(row, "Holes", area, row_index):
      if slot is None:
        raise row_error("Holes", area, row_index, "deleted rows need index.")
      continue
    x = int_field(row, "x", "Holes", area, row_index, 0, 0x3F)
    y = int_field(row, "y", "Holes", area, row_index, 8, 0x3F)
    entrance_id = int_field(row, "entrance_id", "Holes", area, row_index, 0, 0xFF)
    if slot is None:
      pos = x << 1 | ((y - 8) & 0x3F) << 7
      state["legacy_holes"].append((entrance_id, pos, area, row_index))


def validate_exits(area: int, rows: list, state: dict) -> None:
  """Validate kExitData_* and kSpExit_* source rows."""
  for row_index, row in enumerate(rows):
    require_dict(row, "Exits", area, row_index)
    slot = int_field(row, "index", "Exits", area, row_index, 0, EXIT_SLOTS - 1)
    require_unique_slot(state["exits"], slot, "exit", area, row_index)
    if deleted_row(row, "Exits", area, row_index):
      continue
    room = int_field(row, "room", "Exits", area, row_index, 0, 0xFFFF)
    validate_destination_pairs(row, "Exits", area, row_index)
    validate_door(row.get("door"), area, row_index)
    validate_special_exit(row.get("special_exit"), room, area, row_index, state)


def deleted_row(row: dict, label: str, area: int, row_index: int) -> bool:
  """Return true for a ZScream-style fixed-slot deletion sentinel row."""
  if "deleted" not in row:
    return False
  if row["deleted"] is not True:
    raise row_error(label, area, row_index, "deleted must be true when present.")
  return True


def validate_destination_pairs(row: dict, label: str, area: int, row_index: int) -> None:
  """Validate paired fields shared by travel and exit tables."""
  for key in ("xy", "scroll_xy", "camera_xy"):
    validate_absolute_coordinate_pair(row, key, label, area, row_index)
  int_pair(row, "load_xy", label, area, row_index, 0, 0x3F)
  int_pair(row, "unk", label, area, row_index, -0x80, 0x7F)


def validate_absolute_coordinate_pair(row: dict, key: str, label: str,
                                      area: int, row_index: int) -> None:
  """Validate area-relative coordinates after applying the compiler area origin."""
  value = row.get(key)
  if not isinstance(value, list) or len(value) != 2:
    raise row_error(label, area, row_index, "%s must be a two-number list." % key)
  x = int_any(value[0], "%s.%s[0]" % (label, key), area, row_index)
  y = int_any(value[1], "%s.%s[1]" % (label, key), area, row_index)
  base_x, base_y = overworld_area_base(area)
  validate_uint16_coordinate(x + base_x, "%s.%s[0]" % (label, key), area, row_index)
  validate_uint16_coordinate(y + base_y, "%s.%s[1]" % (label, key), area, row_index)


def overworld_area_base(area: int) -> tuple[int, int]:
  """Return the same absolute overworld pixel origin used by compile_resources."""
  return (area & 7) << 9, (area & 56) << 6


def validate_uint16_coordinate(value: int, label: str, area: int, row_index: int) -> None:
  """Require a compiled absolute coordinate to fit the ROM's uint16 tables."""
  if value < 0 or value > 0xFFFF:
    raise row_error(label, area, row_index, "%s compiles outside uint16 range." % label)


def validate_door(value, area: int, row_index: int) -> None:
  """Validate the optional kExitData_NormalDoor/FancyDoor tuple."""
  if value is None:
    return
  if not isinstance(value, list) or len(value) != 3:
    raise row_error("Exits", area, row_index, "door must be [type, x, y].")
  if value[0] not in DOOR_TYPES:
    raise row_error("Exits", area, row_index, "door type %r is unsupported." % value[0])
  int_value(value[1], "Exits.door.x", area, row_index, 0, 0x3F)
  int_value(value[2], "Exits.door.y", area, row_index, 0, 0x3F)


def validate_special_exit(value, room: int, area: int, row_index: int,
                          state: dict | None = None) -> None:
  """Validate special-exit payloads against the 16 kSpExit_* slots."""
  special_room = SPECIAL_EXIT_ROOM_MIN <= room <= SPECIAL_EXIT_ROOM_MAX
  if value is None:
    if special_room:
      raise row_error("Exits", area, row_index, "special room 0x%03X needs special_exit." % room)
    return
  if not special_room:
    raise row_error("Exits", area, row_index, "special_exit needs room 0x180..0x18F.")
  if state is not None:
    require_unique_slot(state["special_exits"], room, "special exit room", area, row_index)
  require_dict(value, "Exits.special_exit", area, row_index)
  int_field(value, "dir", "Exits.special_exit", area, row_index, 0, 3)
  for key in SPECIAL_EXIT_BYTE_FIELDS:
    int_field(value, key, "Exits.special_exit", area, row_index, 0, 0xFF)
  for key in SPECIAL_EXIT_WORD_FIELDS:
    int_field(value, key, "Exits.special_exit", area, row_index, 0, 0xFFFF)
  for key in SPECIAL_EXIT_INT16_FIELDS:
    int_field(value, key, "Exits.special_exit", area, row_index, -0x8000, 0x7FFF)


def require_exact_slots(label: str, slots, count: int) -> None:
  """Require every fixed ROM slot to have exactly one YAML owner."""
  keys = set(slots.keys()) if isinstance(slots, dict) else set(slots)
  expected = set(range(count))
  if keys != expected:
    missing = sorted(expected - keys)
    extra = sorted(keys - expected)
    raise ValueError("%s slots must be exactly 0..%d; missing=%s extra=%s." %
                     (label, count - 1, missing, extra))


def assign_legacy_hole_slots(state: dict) -> None:
  """Assign old unindexed Holes rows to remaining fixed slots by previous sort order."""
  for _entrance_id, _pos, area, row_index in sorted(state["legacy_holes"]):
    for slot in range(HOLE_SLOTS):
      if slot not in state["holes"]:
        state["holes"][slot] = (area, row_index)
        break
    else:
      raise row_error("Holes", area, row_index, "no free hole slots remain.")


def require_count(label: str, actual: int, expected: int) -> None:
  """Require a fixed-count ROM table to stay fully populated."""
  if actual != expected:
    raise ValueError("%s rows must total %d, got %d." % (label, expected, actual))


def require_unique_slot(slots, slot: int, label: str, area: int, row_index: int) -> None:
  """Reject duplicate fixed-slot records before compile_resources asserts."""
  if slot in slots:
    raise row_error(label, area, row_index, "duplicate slot %d." % slot)
  if isinstance(slots, dict):
    slots[slot] = (area, row_index)
  else:
    slots.add(slot)


def require_dict(row, label: str, area: int, row_index: int) -> None:
  """Require one YAML row to be an object."""
  if not isinstance(row, dict):
    raise row_error(label, area, row_index, "row must be an object.")


def int_pair(row: dict, key: str, label: str, area: int, row_index: int,
             minimum: int, maximum: int) -> None:
  """Validate a two-integer YAML pair."""
  value = row.get(key)
  if not isinstance(value, list) or len(value) != 2:
    raise row_error(label, area, row_index, "%s must be a two-number list." % key)
  int_value(value[0], "%s.%s[0]" % (label, key), area, row_index, minimum, maximum)
  int_value(value[1], "%s.%s[1]" % (label, key), area, row_index, minimum, maximum)


def int_any(value, label: str, area: int, row_index: int) -> int:
  """Validate and return one unbounded integer value."""
  if not isinstance(value, int):
    raise row_error(label, area, row_index, "%s must be an integer." % label)
  return value


def int_field(row: dict, key: str, label: str, area: int, row_index: int,
              minimum: int, maximum: int) -> int:
  """Validate and return one integer field."""
  if key not in row:
    raise row_error(label, area, row_index, "missing %s." % key)
  return int_value(row[key], "%s.%s" % (label, key), area, row_index, minimum, maximum)


def int_value(value, label: str, area: int, row_index: int, minimum: int, maximum: int) -> int:
  """Validate one integer value and range."""
  if not isinstance(value, int):
    raise row_error(label, area, row_index, "%s must be an integer." % label)
  if value < minimum or value > maximum:
    raise row_error(label, area, row_index, "%s must be %d..%d." % (label, minimum, maximum))
  return value


def row_error(label: str, area: int, row_index: int, message: str) -> ValueError:
  """Create a navigation validation error with area and row context."""
  return ValueError("%s area %d row %d: %s" % (label, area, row_index, message))


def area_from_path(path: Path) -> int:
  """Parse the numeric area id from overworld-N.yaml."""
  return int(path.stem.rsplit("-", 1)[1])
