"""
Sprite graphics and metadata helpers for dump_overworld.py.
"""

import os

from dump_overworld_support import ensure_dir, uint16le, write_bytes, write_json
import tables
import util


SPRITE_AUX3_PALETTE = 0x9BD39E
SPRITE_AUX3_WORDS = 84
SPRITE_MISC_PALETTE = 0x9BD446
SPRITE_MISC_WORDS = 77
SPRITE_MAIN_PALETTE = 0x9BD218
SPRITE_MAIN_WORDS = 120
SPRITE_AUX1_PALETTE = 0x9BD4E0
SPRITE_AUX1_WORDS = 168
SPRITE_SWORD_PALETTE = 0x9BD630
SPRITE_SWORD_WORDS = 12
SPRITE_SHIELD_PALETTE = 0x9BD648
SPRITE_SHIELD_WORDS = 12
SPRITE_ARMOR_PALETTE = 0x9BD308
SPRITE_ARMOR_WORDS = 75
SPRITE_PACK_BYTES = 0x600
# Runtime item-animation OAM can reference sprite packs outside overworld sprite-set rows.
ITEM_ANIMATION_SPRITE_PACKS = {96}


def dump_sprite_graphics(manifest, out_dir):
  gfx_dir = os.path.join(out_dir, "gfx", "sprite")
  ensure_dir(gfx_dir)
  entries = []
  for index in sorted(used_overworld_sprite_packs()):
    address = tables.kCompSpritePtrs[index]
    decoded = read_sprite_pack(index)
    write_bytes(os.path.join(gfx_dir, "%03d.bin" % index), decoded)
    entries.append({
      "index": index,
      "address": hex(address),
      "decoded_length": len(decoded),
      "format": "snes-3bpp-decoded",
    })

  write_json(os.path.join(gfx_dir, "manifest.json"), {"entries": entries})
  manifest["files"]["sprite_graphics"] = {
    "decoded_pack": "gfx/sprite/%03d.bin",
    "manifest": "gfx/sprite/manifest.json",
  }


def used_overworld_sprite_packs():
  packs = {0, 1, 6, 7, 0x0b, 12, 70, *ITEM_ANIMATION_SPRITE_PACKS}
  for row in tables.kSpriteTilesets:
    for pack in row:
      if pack:
        packs.add(pack)
  return packs


def dump_sprite_palettes(manifest, out_dir):
  palette_dir = os.path.join(out_dir, "palettes")
  ensure_dir(palette_dir)
  palettes = [
    ("sprite_aux3", SPRITE_AUX3_PALETTE, SPRITE_AUX3_WORDS),
    ("sprite_misc", SPRITE_MISC_PALETTE, SPRITE_MISC_WORDS),
    ("sprite_main", SPRITE_MAIN_PALETTE, SPRITE_MAIN_WORDS),
    ("sprite_aux1", SPRITE_AUX1_PALETTE, SPRITE_AUX1_WORDS),
    ("sprite_sword", SPRITE_SWORD_PALETTE, SPRITE_SWORD_WORDS),
    ("sprite_shield", SPRITE_SHIELD_PALETTE, SPRITE_SHIELD_WORDS),
    ("sprite_armor", SPRITE_ARMOR_PALETTE, SPRITE_ARMOR_WORDS),
  ]
  files = manifest["files"].setdefault("palettes", {})
  for name, address, count in palettes:
    words = util.ROM.get_words(address, count)
    write_bytes(os.path.join(palette_dir, "%s.bin" % name), uint16le(words))
    write_json(os.path.join(palette_dir, "%s.json" % name), {
      "source_address": hex(address),
      "words": words,
    })
    files[name + "_bin"] = "palettes/%s.bin" % name
    files[name + "_json"] = "palettes/%s.json" % name


def normalize_sprite_sets(area_data):
  if not area_data:
    return {}
  light_sets = {
    "beginning": "Sprites.Beginning",
    "first": "Sprites.FirstPart",
    "second": "Sprites.SecondPart",
  }
  result = {}
  if "Sprites" in area_data:
    sprite_set = normalize_sprite_set(area_data["Sprites"])
    result["beginning"] = sprite_set
    result["first"] = sprite_set
    result["second"] = sprite_set
    return result
  for key, yaml_key in light_sets.items():
    if yaml_key in area_data:
      result[key] = normalize_sprite_set(area_data[yaml_key])
  return result


def read_sprite_pack(index):
  address = tables.kCompSpritePtrs[index]
  if index < 12:
    return bytes(util.ROM.get_bytes(address, SPRITE_PACK_BYTES))
  decoded = util.decomp(address, util.ROM.get_byte, False)
  if len(decoded) < SPRITE_PACK_BYTES:
    raise Exception("Sprite graphics pack %d decoded to %d bytes" % (
      index, len(decoded)))
  return bytes(decoded[:SPRITE_PACK_BYTES])


def normalize_sprite_set(sprite_set):
  info = sprite_set.get("info", {})
  return {
    "info": normalize_sprite_info(info),
    "sprites": [normalize_sprite(entry) for entry in sprite_set.get("sprites", [])],
  }


def normalize_sprite_info(info):
  if "gfx" not in info or "palette" not in info:
    return {}
  return {
    "gfx": info["gfx"],
    "palette": info["palette"],
  }


def normalize_sprite(entry):
  name = entry[2]
  sprite = {
    "x": entry[0],
    "y": entry[1],
    "type": tables.kSpriteNamesRev[name],
    "name": name,
  }
  if len(entry) > 3 and isinstance(entry[3], dict):
    sprite["custom"] = dict(entry[3])
  return sprite
