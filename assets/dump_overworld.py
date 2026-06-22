"""dump_overworld.py

Writes the overworld visual data needed by the dev viewer into explicit intermediate files.
The dump is intentionally separate from zelda3_assets.dat
so renderer bugs can be debugged against source assets instead of a packed blob.
"""
import os

from dump_overworld_sprites import (
  dump_sprite_graphics,
  dump_sprite_palettes,
  normalize_sprite_sets,
)
from dump_overworld_sprite_oam import dump_sprite_oam_tables
from dump_overworld_special import normalize_special_exits
from dump_overworld_gravestones import dump_gravestone_records
from dump_overworld_interactions import normalize_interactions, secret_runtime_tables
from dump_overworld_metadata import (
  build_hole_slot_metadata,
  normalize_header_metadata,
  normalize_navigation_metadata,
)
from dump_overworld_map32 import (
  HI_PTR_TABLE,
  LO_PTR_TABLE,
  MAP32_COUNT,
  SCREEN_COUNT,
  dump_map32_streams,
)
from dump_overworld_palettes import (
  OW_BG_AUX12_PALETTE,
  OW_BG_AUX3_PALETTE,
  OW_BG_MAIN_PALETTE,
  dump_palettes,
)
from dump_overworld_tile_attributes import read_generated_map8_tile_attributes
from dump_overworld_support import (
  ensure_dir,
  extract_array,
  parse_matrix,
  parse_numbers,
  read_text,
  uint16le,
  write_bytes,
  write_json,
)
import tables
import util
import overworld_static_overlays
import yaml


OUT_DIR = "overworld_dump"
MAP32_TO_MAP16_COUNT = 2218

AREA_HEADS_TABLE = 0x82A5EC
MAP16_TO_MAP8_TABLE = 0x8F8000
MAP16_TO_MAP8_WORDS = 3752 * 4
OW_AREA_TOPOLOGY_STRIDE = 192
OW_AREA_SIZE_CODES = {
  "small": 0,
  "big": 1,
  "large": 1,
  "wide": 2,
  "tall": 3,
}
OW_AREA_SIZE_NAMES = {
  0: "small",
  1: "big",
  2: "wide",
  3: "tall",
}
OW_AREA_SIZE_OFFSETS = {
  "small": (0,),
  "big": (0, 1, 8, 9),
  "wide": (0, 1),
  "tall": (0, 8),
}
OW_HEADER_PALETTE_AREAS = 128
OW_SPECIAL_AREA_ROOMS = {
  0x81: 0x182,
  0x82: 0x182,
  0x88: 0x189,
  0x89: 0x182,
  0x8a: 0x182,
  0x93: 0x189,
  0x94: 0x181,
  0x97: 0x180,
}

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GRAVESTONES_C = os.path.join(PROJECT_ROOT, "src", "overworld_gravestones.c")
LOAD_GFX_C = os.path.join(PROJECT_ROOT, "src", "load_gfx.c")
OVERWORLD_C = os.path.join(PROJECT_ROOT, "src", "overworld.c")


def main(source_root=None, out_dir=OUT_DIR, generated_root=None):
  manifest = {
    "format": "zelda3-overworld-dump-v2",
    "screen_count": SCREEN_COUNT,
    "map32_per_screen": MAP32_COUNT,
    "source_addresses": {
      "high_pointer_table": hex(HI_PTR_TABLE),
      "low_pointer_table": hex(LO_PTR_TABLE),
      "area_heads": hex(AREA_HEADS_TABLE),
      "map16_to_map8": hex(MAP16_TO_MAP8_TABLE),
      "overworld_bg_main_palette": hex(OW_BG_MAIN_PALETTE),
      "overworld_bg_aux12_palette": hex(OW_BG_AUX12_PALETTE),
      "overworld_bg_aux3_palette": hex(OW_BG_AUX3_PALETTE),
    },
    "files": {},
  }

  ensure_dir(out_dir)
  dump_map32_streams(manifest, out_dir, source_root)
  dump_map_tables(manifest, out_dir, generated_root)
  dump_bg_graphics(manifest, out_dir, generated_root)
  dump_palettes(manifest, out_dir, generated_root, read_generated_words)
  dump_sprite_graphics(manifest, out_dir)
  dump_sprite_palettes(manifest, out_dir)
  dump_area_metadata(manifest, out_dir, generated_root)
  dump_source_tables(manifest, out_dir, generated_root)
  dump_overlay_metadata(manifest, out_dir)

  write_json(os.path.join(out_dir, "manifest.json"), manifest)
  print_required_files(out_dir)


def dump_map_tables(manifest, out_dir=OUT_DIR, generated_root=None):
  table_dir = os.path.join(out_dir, "tables")
  ensure_dir(table_dir)

  map32_to_map16 = read_map32_to_map16(generated_root)
  map16_to_map8 = read_generated_words(generated_root, ("tables", "map16_to_map8.json"),
                                       util.ROM.get_words(MAP16_TO_MAP8_TABLE, MAP16_TO_MAP8_WORDS))
  write_json(os.path.join(table_dir, "map32_to_map16.json"), {
    "source": "ROM map32 definition banks 0x838000,0x83b400,0x848000,0x84b400",
    "entries": map32_to_map16,
  })
  write_bytes(os.path.join(table_dir, "map16_to_map8.bin"), uint16le(map16_to_map8))
  write_json(os.path.join(table_dir, "map16_to_map8.json"), {
    "source_address": hex(MAP16_TO_MAP8_TABLE),
    "words": map16_to_map8,
  })

  manifest["files"]["tile_tables"] = {
    "map32_to_map16": "tables/map32_to_map16.json",
    "map16_to_map8_bin": "tables/map16_to_map8.bin",
    "map16_to_map8_json": "tables/map16_to_map8.json",
  }


def dump_bg_graphics(manifest, out_dir=OUT_DIR, generated_root=None):
  gfx_dir = os.path.join(out_dir, "gfx", "bg")
  ensure_dir(gfx_dir)
  entries = []
  for index, address in enumerate(tables.kCompBgPtrs):
    generated = read_generated_bytes(generated_root, ("gfx", "bg", "%03d.bin" % index))
    if generated is None:
      decoded, compressed_length = util.decomp(address, util.ROM.get_byte, False, True)
      generated = util.ROM.get_bytes(address, compressed_length)
    else:
      decoded, compressed_length = generated, len(generated)
    write_bytes(os.path.join(gfx_dir, "%03d.bin" % index), generated)
    entries.append({
      "index": index,
      "address": hex(address),
      "compressed_length": compressed_length,
      "decoded_length": len(decoded),
    })
  write_json(os.path.join(gfx_dir, "manifest.json"), {"entries": entries})
  manifest["files"]["bg_graphics"] = {
    "compressed_pack": "gfx/bg/%03d.bin",
    "manifest": "gfx/bg/manifest.json",
  }


def dump_area_metadata(manifest, out_dir=OUT_DIR, generated_root=None):
  table_dir = os.path.join(out_dir, "tables")
  ensure_dir(table_dir)
  area_data = {area: load_area_yaml(area, generated_root) for area in range(SCREEN_COUNT)}
  topology = build_area_topology(area_data)
  hole_slots = build_hole_slot_metadata(area_data)
  area_heads = topology["parents"][:64]
  area_parent_ids = topology["parents"]
  area_sizes = topology["sizes"]
  map_is_small = [0] * OW_AREA_TOPOLOGY_STRIDE
  aux_tile_theme = [0] * 128
  bg_palette = [0] * SCREEN_COUNT
  special_slots = special_exit_payloads_by_slot(area_data)
  headers = []

  for area in range(SCREEN_COUNT):
    data = area_data.get(area)
    header = data.get("Header", {}) if data else {}
    special_exits = normalize_special_exits(data.get("Exits", []) if data else [])

    headers.append({
      "area": area,
      "exists": data is not None,
      "name": header.get("name"),
      "size": header.get("size"),
      "gfx": header.get("gfx"),
      "palette": header.get("palette"),
      "header": normalize_header_metadata(header),
      "interactions": normalize_interactions(area, data),
      "navigation": normalize_navigation_metadata(
        data, {row: slot for (slot_area, row), slot in hole_slots.items() if slot_area == area}),
      "special_exits": special_exits,
      "sprite_sets": normalize_sprite_sets(data),
      "static_overlays": overworld_static_overlays.normalize_static_overlay_rows(
        data.get("Overlays", []) if data else [], area),
    })

    if data is None or area_parent_ids[area] != area:
      continue
    for child in topology["children"].get(area, [area]):
      map_is_small[child] = 1 if area_sizes[child] == 0 else 0
    if area < len(aux_tile_theme):
      area_write(aux_tile_theme, area, area, header["gfx"], topology["children"])
    if area < len(bg_palette):
      area_write(bg_palette, area, area, bg_palette_value(area, data, special_slots, area_data),
                 topology["children"])

  write_json(os.path.join(table_dir, "area_metadata.json"), {
    "area_heads": area_heads,
    "area_parent_ids": area_parent_ids,
    "area_sizes": area_sizes,
    "map_is_small": map_is_small,
    "aux_tile_theme_indexes": aux_tile_theme,
    "bg_palette_indexes": bg_palette,
    "headers": headers,
  })
  manifest["files"]["area_metadata"] = "tables/area_metadata.json"


def dump_source_tables(manifest, out_dir=OUT_DIR, generated_root=None):
  table_dir = os.path.join(out_dir, "tables")
  ensure_dir(table_dir)
  gravestones = read_text(GRAVESTONES_C)
  load_gfx = read_text(LOAD_GFX_C)
  overworld = read_text(OVERWORLD_C)
  data = {
    "main_tilesets": parse_matrix(extract_array(load_gfx, "kMainTilesets")),
    "aux_tilesets": parse_matrix(extract_array(load_gfx, "kAuxTilesets")),
    "ambient_sound_names": tables.kAmbientSoundName,
    "music_names": tables.kMusicNames,
    "map8_tile_attributes": read_generated_map8_tile_attributes(
      generated_root, read_generated_words, util.ROM),
    "sprite_tilesets": [list(row) for row in tables.kSpriteTilesets],
    "sprite_names": tables.kSpriteNames[:256],
    "sprite_init_flags3": tables.kSpriteInit_Flags3,
    "sprite_oam": dump_sprite_oam_tables(),
    "secret_item_names": [tables.kSecretNames[i] for i in sorted(tables.kSecretNames)],
    "secret_spawn_runtime": secret_runtime_tables(),
    "gravestones": dump_gravestone_records(gravestones, util.ROM.get_word, generated_root),
    "various_packs": parse_numbers(extract_array(overworld, "kVariousPacks")),
    "ow_bg_pal_info": parse_numbers(extract_array(load_gfx, "kOwBgPalInfo")),
    "ow_spr_pal_info": parse_numbers(extract_array(load_gfx, "kOwSprPalInfo")),
    "offset_base_x": parse_numbers(extract_array(overworld, "kOverworld_OffsetBaseX")),
    "offset_base_y": parse_numbers(extract_array(overworld, "kOverworld_OffsetBaseY")),
    "sp_exit_spr_gfx": parse_numbers(extract_array(overworld, "kSpExit_SprGfx")),
    "sp_exit_aux_gfx": parse_numbers(extract_array(overworld, "kSpExit_AuxGfx")),
    "sp_exit_left_edge": parse_numbers(extract_array(overworld, "kSpExit_LeftEdgeOfMap")),
    "sp_exit_pal_bg": parse_numbers(extract_array(overworld, "kSpExit_PalBg")),
    "sp_exit_pal_spr": parse_numbers(extract_array(overworld, "kSpExit_PalSpr")),
    "sp_exit_top": parse_numbers(extract_array(overworld, "kSpExit_Top")),
  }
  data["overworld_special_gfx_group"] = data["sp_exit_aux_gfx"]
  data["overworld_special_pal_group"] = data["sp_exit_pal_bg"]
  data["overworld_special_sprite_gfx_group"] = data["sp_exit_spr_gfx"]
  data["overworld_special_sprite_palette"] = data["sp_exit_pal_spr"]
  write_json(os.path.join(table_dir, "source_tables.json"), data)
  manifest["files"]["source_tables"] = "tables/source_tables.json"


def dump_overlay_metadata(manifest, out_dir=OUT_DIR):
  table_dir = os.path.join(out_dir, "tables")
  ensure_dir(table_dir)
  data = {
    "secondary_overlay_streams": [
      overlay(0x93, "triforce_room_overlay", 0x88, "add", True),
      overlay(0x94, "pyramid_curtain_overlay", 0x80, "add", True),
      overlay(0x95, "birds_eye_woods_underlay", 0x03, "add", False, "underlay"),
      overlay(0x96, "death_mountain_panorama", 0x5b, "add", False, "raw"),
      overlay(0x97, "master_grove_mist", 0x80, "add", True),
      overlay(0x9c, "dark_mountain_lava", 0x43, "add", False, "underlay"),
      overlay(0x9d, "lost_woods_mist", 0x00, "add", True),
      overlay(0x9e, "lost_woods_tree_cover", 0x00, "add", True),
      overlay(0x9f, "rain_overlay", 0x70, "add", True),
    ],
    "normal_atlas_overlay_rules": [
      {"condition": "context_low == 0x00", "stream": 0x9d},
      {"condition": "light context_low in [0x03,0x05,0x07]", "stream": 0x95},
      {"condition": "dark context_low in [0x03,0x05,0x07]", "stream": 0x9c},
      {"condition": "raw_screen == 0x70", "stream": 0x9f},
    ],
  }
  write_json(os.path.join(table_dir, "overlay_metadata.json"), data)
  manifest["files"]["overlay_metadata"] = "tables/overlay_metadata.json"


def read_map32_to_map16(generated_root=None):
  generated = read_generated_map32_to_map16(generated_root)
  if generated is not None:
    return generated
  entries = []
  bases = [0x838000, 0x83B400, 0x848000, 0x84B400]
  for index in range(MAP32_TO_MAP16_COUNT):
    banks = [read_map32_definition_bank(base + index * 6) for base in bases]
    for slot in range(4):
      entries.append([banks[0][slot], banks[1][slot], banks[2][slot], banks[3][slot]])
  return entries


def read_generated_bytes(generated_root, parts):
  if not generated_root:
    return None
  path = os.path.join(generated_root, *parts)
  if not os.path.exists(path):
    return None
  return open(path, "rb").read()


def read_generated_words(generated_root, parts, fallback):
  if not generated_root:
    return fallback
  path = os.path.join(generated_root, *parts)
  if not os.path.exists(path):
    return fallback
  import json
  return json.load(open(path, "r"))["words"]


def read_generated_map32_to_map16(generated_root):
  if not generated_root:
    return None
  path = os.path.join(generated_root, "map32_to_map16.txt")
  if not os.path.exists(path):
    return None
  entries = []
  for line in open(path, "r"):
    if ":" not in line:
      continue
    values = line.split(":", 1)[1]
    entries.append([int(part.strip()) for part in values.split(",")])
  return entries


def read_map32_definition_bank(address):
  raw = [util.ROM.get_byte(address + i) for i in range(6)]
  return [
    raw[0] | ((raw[4] >> 4) << 8),
    raw[1] | ((raw[4] & 0x0f) << 8),
    raw[2] | ((raw[5] >> 4) << 8),
    raw[3] | ((raw[5] & 0x0f) << 8),
  ]


def load_area_yaml(area, generated_root=None):
  if generated_root:
    generated_path = os.path.join(generated_root, "overworld", "overworld-%d.yaml" % area)
    if os.path.exists(generated_path):
      with open(generated_path, "r") as file:
        return yaml.safe_load(file)
  path = os.path.join("overworld", "overworld-%d.yaml" % area)
  if not os.path.exists(path):
    return None
  with open(path, "r") as file:
    return yaml.safe_load(file)


def is_area_head(area):
  return area >= 128 or util.ROM.get_byte(AREA_HEADS_TABLE + (area & 63)) == (area & 63)


def build_area_topology(area_data):
  parents = list(range(OW_AREA_TOPOLOGY_STRIDE))
  sizes = [0] * OW_AREA_TOPOLOGY_STRIDE
  children = {area: [area] for area in range(SCREEN_COUNT)}
  for world_base in (0, 64):
    covered = {}
    for y in range(8):
      for x in range(8):
        area = world_base + y * 8 + x
        if area in covered:
          continue
        data = area_data.get(area)
        if data is None:
          raise ValueError("Missing overworld YAML for generated area head %d." % area)
        size = canonical_area_size(area, data.get("Header", {}).get("size"))
        validate_topology_fit(area, x, y, size)
        owned = []
        for offset in OW_AREA_SIZE_OFFSETS[size]:
          child = area + offset
          if child in covered:
            raise ValueError("Overworld area %d is covered by both %d and %d." % (
              child, covered[child], area))
          if offset and area_data.get(child) is not None:
            raise ValueError(
              "Overworld child area %d has YAML but is owned by parent area %d." % (
                child, area))
          covered[child] = area
          parents[child] = area
          sizes[child] = OW_AREA_SIZE_CODES[size]
          owned.append(child)
        children[area] = owned
  for area in range(128, SCREEN_COUNT):
    data = area_data.get(area)
    if data is None:
      raise ValueError("Missing overworld YAML for special area %d." % area)
    size = canonical_area_size(area, data.get("Header", {}).get("size"))
    parents[area] = area
    sizes[area] = OW_AREA_SIZE_CODES[size]
    children[area] = [area]
  return {"children": children, "parents": parents, "sizes": sizes}


def special_exit_payloads_by_slot(area_data):
  """Return kSpExit payloads keyed by room-derived special-exit slot."""
  slots = {}
  for data in (entry for entry in area_data.values() if entry is not None):
    for row in data.get("Exits", []):
      room = row.get("room")
      if room is None or "special_exit" not in row:
        continue
      if 0x180 <= room <= 0x18F:
        slots[room - 0x180] = row["special_exit"]
  return slots


def special_area_slot(area, area_data):
  """Resolve the special-exit visual slot used by one special map."""
  if area < 128:
    return None
  for row in (area_data.get(area) or {}).get("Exits", []):
    room = row.get("room")
    if room is not None and 0x180 <= room <= 0x18F and "special_exit" in row:
      return room - 0x180
  room = OW_SPECIAL_AREA_ROOMS.get(area)
  if room is not None:
    return room - 0x180
  return None


def bg_palette_value(area, data, special_slots, area_data):
  """Derive the generated 160-entry BG palette assignment without using $04C635."""
  header = data.get("Header", {}) if data else {}
  palette = header.get("palette", -1)
  if area < OW_HEADER_PALETTE_AREAS and palette >= 0:
    return palette
  slot = special_area_slot(area, area_data)
  if slot is not None and slot in special_slots:
    return special_slots[slot]["pal_bg"]
  if palette >= 0:
    return palette
  return 0


def canonical_area_size(area, value):
  if value not in OW_AREA_SIZE_CODES:
    raise ValueError("Overworld Header.size in area %d must be small, big, wide, or tall." % area)
  return OW_AREA_SIZE_NAMES[OW_AREA_SIZE_CODES[value]]


def validate_topology_fit(area, x, y, size):
  if size in ("big", "wide") and x >= 7:
    raise ValueError("Overworld Header.size %s in area %d crosses the east world edge." % (
      size, area))
  if size in ("big", "tall") and y >= 7:
    raise ValueError("Overworld Header.size %s in area %d crosses the south world edge." % (
      size, area))


def area_write(values, area, key, value, children_by_parent):
  values[key] = value
  for child in children_by_parent.get(area, [area])[1:]:
    child_key = key + child - area
    if child_key < len(values):
      values[child_key] = value


def overlay(screen, name, context_screen, operation, half, composite="overlay"):
  return {
    "stream": screen,
    "name": name,
    "context_screen": context_screen,
    "composite": composite,
    "blend": {
      "operation": operation,
      "half": half,
    },
  }


def print_required_files(out_dir=OUT_DIR):
  print("Overworld dump written to %s" % out_dir)
  print("Viewer input files:")
  for path in [
    "%s/manifest.json" % out_dir,
    "%s/map32/high_compressed/%%03d.bin" % out_dir,
    "%s/map32/low_compressed/%%03d.bin" % out_dir,
    "%s/map32/decoded/%%03d.json" % out_dir,
    "%s/map32/words/%%03d.bin" % out_dir,
    "%s/tables/map32_to_map16.json" % out_dir,
    "%s/tables/map16_to_map8.bin" % out_dir,
    "%s/tables/map16_to_map8.json" % out_dir,
    "%s/tables/area_metadata.json" % out_dir,
    "%s/tables/source_tables.json" % out_dir,
    "%s/tables/overlay_metadata.json" % out_dir,
    "%s/gfx/bg/%%03d.bin" % out_dir,
    "%s/gfx/bg/manifest.json" % out_dir,
    "%s/gfx/sprite/%%03d.bin" % out_dir,
    "%s/gfx/sprite/manifest.json" % out_dir,
    "%s/palettes/overworld_bg_main.bin" % out_dir,
    "%s/palettes/overworld_bg_main.json" % out_dir,
    "%s/palettes/overworld_bg_aux12.bin" % out_dir,
    "%s/palettes/overworld_bg_aux12.json" % out_dir,
    "%s/palettes/overworld_bg_aux3.bin" % out_dir,
    "%s/palettes/overworld_bg_aux3.json" % out_dir,
    "%s/palettes/sprite_aux3.bin" % out_dir,
    "%s/palettes/sprite_misc.bin" % out_dir,
    "%s/palettes/sprite_main.bin" % out_dir,
    "%s/palettes/sprite_aux1.bin" % out_dir,
    "%s/palettes/sprite_sword.bin" % out_dir,
    "%s/palettes/sprite_shield.bin" % out_dir,
    "%s/palettes/sprite_armor.bin" % out_dir,
  ]:
    print("  " + path)
