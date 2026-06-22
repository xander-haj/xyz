"""
Navigation and header metadata helpers for dump_overworld.py.
"""


def normalize_header_metadata(header):
  """Return the full header fields that compile into overworld property tables."""
  return dict(header or {})


def normalize_navigation_metadata(area_data, hole_slots=None):
  """Return ZScream-style overworld navigation/editing domains for one area."""
  if not area_data:
    return empty_navigation()
  return {
    "travel": [normalize_travel(entry) for entry in area_data.get("Travel", [])],
    "entrances": [normalize_entrance(entry) for entry in area_data.get("Entrances", [])],
    "holes": [
      normalize_hole(entry, (hole_slots or {}).get(row_index))
      for row_index, entry in enumerate(area_data.get("Holes", []))
    ],
    "exits": [normalize_exit(entry) for entry in area_data.get("Exits", [])],
  }


def empty_navigation():
  return {"travel": [], "entrances": [], "holes": [], "exits": []}


def normalize_travel(entry):
  record = dict(entry)
  if "bird_travel_id" in entry:
    record.update({
      "type": "bird_travel",
      "display_name": "Bird travel %d" % entry["bird_travel_id"],
      "source_table": "kBirdTravel_*",
    })
  else:
    record.update({
      "type": "whirlpool",
      "display_name": "Whirlpool from area 0x%02X" % entry.get("whirlpool_src_area", 0),
      "source_table": "kBirdTravel_* / kWhirlpoolAreas",
    })
  add_pixel_fields(record)
  record["source"] = "overworld Travel YAML row compiled by print_overworld_tables"
  return record


def normalize_entrance(entry):
  record = dict(entry)
  if record.get("deleted") is True:
    record.update({
      "type": "entrance",
      "display_name": "Entrance %d DELETED" % entry["index"],
      "source": "overworld Entrances YAML deleted slot compiled to kOverworld_Entrance_*",
      "source_table": "kOverworld_Entrance_*",
    })
    return record
  record.update({
    "type": "entrance",
    "display_name": "Entrance %d -> %d" % (entry["index"], entry["entrance_id"]),
    "grid_x": entry["x"],
    "grid_y": entry["y"],
    "source": "overworld Entrances YAML row compiled to kOverworld_Entrance_*",
    "source_table": "kOverworld_Entrance_*",
  })
  return record


def normalize_hole(entry, slot=None):
  record = dict(entry)
  if "index" not in record and slot is not None:
    record["index"] = slot
  if record.get("deleted") is True:
    record.update({
      "type": "hole",
      "display_name": "Fall hole %d DELETED" % record["index"],
      "source": "overworld Holes YAML deleted slot compiled to kFallHole_*",
      "source_table": "kFallHole_*",
    })
    return record
  record.update({
    "type": "hole",
    "display_name": "Fall hole %d -> %d" % (record["index"], entry["entrance_id"]),
    "grid_x": entry["x"],
    "grid_y": entry["y"],
    "source": "overworld Holes YAML row compiled to kFallHole_*",
    "source_table": "kFallHole_*",
  })
  return record


def build_hole_slot_metadata(area_data_by_area):
  """Return area,row_index to fixed hole slot, preserving legacy compiler sort."""
  slots = {}
  used = {}
  legacy = []
  for area, data in sorted((area_data_by_area or {}).items()):
    for row_index, row in enumerate((data or {}).get("Holes", [])):
      if "index" in row:
        slot = row["index"]
        slots[(area, row_index)] = slot
        used[slot] = (area, row_index)
      elif row.get("deleted") is True:
        continue
      else:
        pos = row["x"] << 1 | ((row["y"] - 8) & 0x3F) << 7
        legacy.append((row["entrance_id"], pos, area, row_index))
  for _entrance_id, _pos, area, row_index in sorted(legacy):
    for slot in range(0x13):
      if slot not in used:
        slots[(area, row_index)] = slot
        used[slot] = (area, row_index)
        break
  return slots


def normalize_exit(entry):
  record = dict(entry)
  if record.get("deleted") is True:
    record.update({
      "type": "exit",
      "display_name": "Exit %d DELETED" % entry["index"],
      "source": "overworld Exits YAML deleted slot compiled to kExitData_*",
      "source_table": "kExitData_*",
    })
    return record
  record.update({
    "type": "exit",
    "display_name": "Exit %d from room %d" % (entry["index"], entry["room"]),
    "source": "overworld Exits YAML row compiled to kExitData_*",
    "source_table": "kExitData_*",
  })
  add_pixel_fields(record)
  if "door" in entry:
    record["door_display"] = "%s @ %d,%d" % (entry["door"][0], entry["door"][1], entry["door"][2])
  if "special_exit" in entry:
    record["source_table"] = "kExitData_* / kSpExit_*"
  return record


def add_pixel_fields(record):
  xy = record.get("xy")
  if isinstance(xy, list) and len(xy) >= 2:
    record["pixel_x"] = xy[0]
    record["pixel_y"] = xy[1]
