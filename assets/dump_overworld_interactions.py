"""
Overworld hidden item and interaction metadata helpers for dump_overworld.py.
"""

import os

from dump_overworld_support import extract_array, parse_numbers, read_text
import tables

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPRITE_C = os.path.join(PROJECT_ROOT, "src", "sprite.c")

ENTRANCE_CODES = {
  0x80: "Hole",
  0x82: "Warp",
  0x84: "Staircase",
  0x86: "Bombable",
  0x88: "Switch",
}

SECRET_DISPLAY_NAMES = {
  0x00: "Nothing",
  0x01: "Green Rupee",
  0x02: "Hoarder",
  0x03: "Bee",
  0x04: "Random",
  0x05: "Bomb",
  0x06: "Heart",
  0x07: "Blue Rupee",
  0x08: "Small Key",
  0x09: "Arrow",
  0x0a: "Bomb",
  0x0b: "Heart",
  0x0c: "Small Magic",
  0x0d: "Big Magic",
  0x0e: "Cucco",
  0x0f: "Green Soldier",
  0x10: "Bush Stal",
  0x11: "Blue Soldier",
  0x12: "Landmine",
  0x13: "Green Rupee",
  0x14: "Fairy",
  0x15: "Heart",
  0x16: "Nothing",
  **ENTRANCE_CODES,
}

ENEMY_CODES = {0x02, 0x03, 0x0e, 0x0f, 0x10, 0x11, 0x12}
RANDOM_SECRET_CODES = [0x13, 0x14, 0x15, 0x16]
_SECRET_RUNTIME = None

SHOVEL_SPOTS = {
  0x2a: [{
    "x": 9,
    "y": 9,
    "name": "Buried Flute",
    "display_name": "Buried Flute",
    "behavior": "hardcoded_shovel_reward",
    "layer": "shovelSpots",
    "source": "Overworld_ToolAndTileInteraction screen 0x2A pos 0x492",
  }],
}


def normalize_interactions(area, area_data):
  """Return browser-friendly hidden interaction records for one overworld area."""
  if not area_data:
    return {"items": [], "shovel_spots": SHOVEL_SPOTS.get(area, [])}
  return {
    "items": [normalize_item(entry) for entry in area_data.get("Items", [])],
    "shovel_spots": SHOVEL_SPOTS.get(area, []),
  }


def normalize_item(entry):
  """Normalize one YAML Items row into explicit x/y/code/name fields."""
  raw_name = entry[2]
  code = parse_secret_code(raw_name)
  sprite_type = secret_sprite_type(code)
  behavior = secret_behavior(code, sprite_type)
  return {
    "x": entry[0],
    "y": entry[1],
    "behavior": behavior,
    "code": code,
    "display_name": secret_display_name(code, raw_name),
    "layer": secret_layer(code),
    "name": raw_name,
    "source": "overworld Items YAML row compiled to kOverworldSecrets",
    "source_table": "kOverworldSecrets",
    **sprite_fields(sprite_type),
    **secret_spawn_fields(sprite_type),
    **runtime_spawn_fields(code, sprite_type),
    **random_fields(code),
  }


def parse_secret_code(name):
  """Read the two-digit secret code prefix used in extracted YAML."""
  if not isinstance(name, str) or len(name) < 2:
    return None
  try:
    return int(name[:2], 16)
  except ValueError:
    return None


def secret_sprite_type(code):
  """Return the spawned sprite type for fixed low-code secrets."""
  if not isinstance(code, int) or code < 1 or code > 22:
    return None
  if code == 4:
    return None
  sprite_type = secret_runtime_tables()["sprite_types"][code - 1]
  return sprite_type or None


def secret_behavior(code, sprite_type):
  """Describe the runtime behavior bucket for one secret code."""
  if code in ENTRANCE_CODES:
    return "entrance_or_trigger"
  if code == 4:
    return "random_sprite_or_empty"
  if sprite_type is not None:
    return "fixed_sprite_spawn"
  return "no_spawn"


def secret_layer(code):
  """Return the Workbench layer that should own this secret record."""
  if code in ENTRANCE_CODES:
    return "secretEntrances"
  if code in ENEMY_CODES:
    return "secretEnemies"
  return "secretTreasure"


def secret_display_name(code, raw_name):
  """Return a human-readable name that follows runtime meaning over YAML quirks."""
  if code in SECRET_DISPLAY_NAMES:
    return SECRET_DISPLAY_NAMES[code]
  if isinstance(raw_name, str) and "-" in raw_name:
    return raw_name.split("-", 1)[1] or raw_name
  return raw_name or "Unknown"


def sprite_fields(sprite_type):
  """Return optional sprite metadata for one secret item record."""
  if sprite_type is None:
    return {}
  return {
    "sprite_type": sprite_type,
    "sprite_name": tables.kSpriteNames[sprite_type],
  }


def secret_spawn_fields(sprite_type):
  """Return source-backed Sprite_SpawnSecret visual state overrides."""
  if sprite_type is None:
    return {}
  fields = {"sprite_graphics": 0}
  if sprite_type == 0x3e:
    fields["oam_flags"] = 9
  return fields


def runtime_spawn_fields(code, sprite_type):
  """Return the runtime fields copied by Sprite_SpawnSecret for fixed sprites."""
  if sprite_type is None or not isinstance(code, int) or code < 1 or code > 22 or code == 4:
    return {}
  runtime = secret_runtime_tables()
  index = code - 1
  return {
    "ignore_projectile": runtime["ignore_projectile"][index],
    "spawn_ai_state": runtime["spawn_ai_state"][index],
    "spawn_x_offset": runtime["spawn_x_offset"][index],
    "z_velocity": runtime["z_velocity"][index],
  }


def random_fields(code):
  """Return the exact Sprite_SpawnSecret random choices for code 0x04."""
  if code != 4:
    return {}
  options = []
  for option_code in RANDOM_SECRET_CODES:
    sprite_type = secret_sprite_type(option_code)
    options.append({
      "code": option_code,
      "display_name": secret_display_name(option_code, None),
      **sprite_fields(sprite_type),
    })
  return {
    "random_options": options,
    "runtime_note": "Sprite_SpawnSecret chooses codes 0x13..0x16; outdoors can also drop nothing.",
  }


def secret_runtime_tables():
  """Parse Sprite_SpawnSecret runtime helper arrays from src/sprite.c."""
  global _SECRET_RUNTIME
  if _SECRET_RUNTIME is None:
    source = read_text(SPRITE_C)
    _SECRET_RUNTIME = {
      "sprite_types": parse_numbers(extract_array(source, "kSpawnSecretItems")),
      "ignore_projectile": parse_numbers(extract_array(source, "kSpawnSecretItem_IgnoreProj")),
      "spawn_ai_state": parse_numbers(extract_array(source, "kSpawnSecretItem_SpawnFlag")),
      "spawn_x_offset": parse_numbers(extract_array(source, "kSpawnSecretItem_XLo")),
      "z_velocity": parse_numbers(extract_array(source, "kSpawnSecretItem_ZVel")),
    }
  return _SECRET_RUNTIME
