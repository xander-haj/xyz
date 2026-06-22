"""
Normalize the hard-coded overworld gravestone tables used by the runtime.
"""

import json
import os

from dump_overworld_support import extract_array, parse_numbers


GRAVE_COUNT = 15
GRAVE_AREA = 0x14
GRAVE_SIZE = 32
GRAVES_GFX = 0x0999C2
GRAVE_COORD_MAX = 4088
GRAVE_AREA_MAX = 0x3F
GRAVE_LOCAL_COORD_MAX = 0x3FF
GRAVE_U16_MAX = 0xFFFF
GRAVE_TABLE_FIELDS = ("x", "y", "tilemap_pos")


def dump_gravestone_records(source, rom_word=None, generated_root=None):
  generated = read_generated_records(generated_root)
  x_tile = generated_field(generated, "x") or source_numbers(source, "kOverworldGravestoneX", GRAVE_COUNT)
  y_tile = generated_field(generated, "y") or source_numbers(source, "kOverworldGravestoneY", GRAVE_COUNT)
  tilemap_pos = generated_field(generated, "tilemap_pos") or source_numbers(
    source, "kOverworldGravestoneTilemapPos", GRAVE_COUNT)
  counters = source_numbers(source, "kOverworldGravestoneCounter", GRAVE_COUNT)
  grave_gfx = read_grave_gfx(rom_word)
  rows = grave_rows(y_tile)
  return {
    "area": GRAVE_AREA,
    "format": "zelda3-overworld-gravestones-v1",
    "height": GRAVE_SIZE,
    "records": [
      grave_record(i, x_tile, y_tile, rows, tilemap_pos, counters, grave_gfx)
      for i in range(GRAVE_COUNT)
    ],
    "runtime_status": "compiled-source",
    "source": "src/overworld_gravestones.c",
    "source_tables": [
      "kOverworldGravestoneX",
      "kOverworldGravestoneY",
      "kOverworldGravestoneTilemapPos",
      "kOverworldGravestoneCounter",
    ],
    "width": GRAVE_SIZE,
    "zscream_tables": {
      "gfx": GRAVES_GFX,
      "tilemap_pos": 0x0999A4,
      "x_tile_pos": 0x099986,
      "y_tile_pos": 0x099968,
    },
  }


def source_numbers(source, name, expected_count):
  values = parse_numbers(extract_array(source, name))
  if len(values) != expected_count:
    raise Exception("%s has %d values; expected %d" % (name, len(values), expected_count))
  return values


def read_generated_records(generated_root):
  if not generated_root:
    return None
  path = os.path.join(generated_root, "tables", "overworld_gravestones.json")
  if not os.path.exists(path):
    return None
  data = json.load(open(path, "r"))
  if not isinstance(data, dict):
    raise Exception("Generated gravestone table must be an object")
  return data


def generated_field(generated, field):
  if not generated:
    return None
  if "records" in generated:
    return [record[field] for record in validate_generated_records(generated["records"])]
  if any(name in generated for name in GRAVE_TABLE_FIELDS):
    return validate_generated_flat_fields(generated)[field]
  return None


def validate_generated_flat_fields(generated):
  missing = [name for name in GRAVE_TABLE_FIELDS if name not in generated]
  if missing:
    raise Exception("Generated gravestone table is missing fields %s" % missing)
  return {
    name: validate_generated_field(name, generated[name])
    for name in GRAVE_TABLE_FIELDS
  }


def validate_generated_field(field, values):
  if not isinstance(values, list) or len(values) != GRAVE_COUNT:
    raise Exception("Generated gravestone field %s must have %d values" % (field, GRAVE_COUNT))
  return [validate_generated_value(field, i, value) for i, value in enumerate(values)]


def validate_generated_records(records):
  if not isinstance(records, list) or len(records) != GRAVE_COUNT:
    raise Exception("Generated gravestone records must have %d entries" % GRAVE_COUNT)
  return [validate_generated_record(i, record) for i, record in enumerate(records)]


def validate_generated_record(row_index, record):
  if not isinstance(record, dict):
    raise Exception("Generated gravestone record %d must be an object" % row_index)
  index = validate_generated_value("index", row_index, record.get("index"))
  if index != row_index:
    raise Exception("Generated gravestone record %d has index %d" % (row_index, index))
  x = validate_generated_value("x", index, record.get("x"))
  y = validate_generated_value("y", index, record.get("y"))
  area = validate_generated_area(index, record.get("area", area_from_world(x, y)))
  tilemap_pos = validate_generated_value(
    "tilemap_pos", index, record.get("tilemap_pos", record.get("tilemapPos")))
  validate_record_tilemap(index, area, x, y, tilemap_pos)
  return {"area": area, "index": index, "tilemap_pos": tilemap_pos, "x": x, "y": y}


def validate_generated_value(field, index, value):
  if isinstance(value, bool) or not isinstance(value, int):
    raise Exception("Generated gravestone %s[%d] must be an integer" % (field, index))
  if field in ("x", "y") and (value < 0 or value > GRAVE_COORD_MAX):
    raise Exception("Generated gravestone %s[%d] must be 0..%d" % (
      field, index, GRAVE_COORD_MAX))
  if field == "tilemap_pos":
    validate_tilemap_pos(index, value)
  return value


def validate_generated_area(index, value):
  if isinstance(value, bool) or not isinstance(value, int):
    raise Exception("Generated gravestone area[%d] must be an integer" % index)
  if value < 0 or value > GRAVE_AREA_MAX:
    raise Exception("Generated gravestone area[%d] must be 0..0x%02x" % (
      index, GRAVE_AREA_MAX))
  return value


def validate_tilemap_pos(index, value):
  if value < 0 or value > GRAVE_U16_MAX:
    raise Exception("Generated gravestone tilemap_pos[%d] must be 0..0xffff" % index)
  if value & 1:
    raise Exception("Generated gravestone tilemap_pos[%d] must be even" % index)


def validate_record_tilemap(index, area, x, y, tilemap_pos):
  local_x = x - (area & 7) * 512
  local_y = y - (area >> 3) * 512
  if local_x < 0 or local_x > GRAVE_LOCAL_COORD_MAX:
    raise Exception("Generated gravestone x[%d] is outside area 0x%02x" % (index, area))
  if local_y < 0 or local_y > GRAVE_LOCAL_COORD_MAX:
    raise Exception("Generated gravestone y[%d] is outside area 0x%02x" % (index, area))
  expected = (((local_y // 16) << 6) | ((local_x // 16) & 0x3F)) << 1
  if tilemap_pos != expected:
    raise Exception("Generated gravestone tilemap_pos[%d] is 0x%04x; expected 0x%04x" % (
      index, tilemap_pos, expected))


def read_grave_gfx(rom_word):
  if not rom_word:
    return [None] * GRAVE_COUNT
  return [rom_word(GRAVES_GFX + i * 2) for i in range(GRAVE_COUNT)]


def grave_rows(y_tile):
  rows = {}
  trigger_rows = sorted({y + 16 for y in y_tile}, reverse=True)
  for grave_index, y in enumerate(y_tile):
    trigger_y = y + 16
    rows[grave_index] = {
      "row_index": trigger_rows.index(trigger_y),
      "trigger_y": trigger_y,
    }
  return rows


def grave_record(index, x_tile, y_tile, rows, tilemap_pos, counters, grave_gfx):
  area = area_from_world(x_tile[index], y_tile[index])
  word = tilemap_pos[index] >> 1
  return {
    "area": area,
    "counter": counters[index],
    "gfx": grave_gfx[index],
    "height": GRAVE_SIZE,
    "index": index,
    "local_x": x_tile[index] - (area & 7) * 512,
    "local_y": y_tile[index] - (area >> 3) * 512,
    "requires_dash": index == 0x0d,
    "row_index": rows[index]["row_index"],
    "special": special_kind(index),
    "tilemap_grid_x": word & 0x3f,
    "tilemap_grid_y": word >> 6,
    "tilemap_pos": tilemap_pos[index],
    "trigger_x": x_tile[index],
    "trigger_y": rows[index]["trigger_y"],
    "width": GRAVE_SIZE,
    "x": x_tile[index],
    "y": y_tile[index],
  }


def area_from_world(x, y):
  return (y // 512) * 8 + (x // 512)


def special_kind(index):
  if index == 0x0d:
    return "stairs"
  if index == 0x0e:
    return "hole"
  return None
