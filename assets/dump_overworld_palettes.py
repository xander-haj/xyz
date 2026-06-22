"""
Dump and validate overworld background palette tables for the editor preview.
"""

import os

import util
from dump_overworld_support import ensure_dir, uint16le, write_bytes, write_json

OW_BG_MAIN_PALETTE = 0x9BE6C8
OW_BG_MAIN_WORDS = 210
OW_BG_AUX12_PALETTE = 0x9BE86C
OW_BG_AUX12_WORDS = 420
OW_BG_AUX3_PALETTE = 0x9BE604
OW_BG_AUX3_WORDS = 98

PALETTES = [
  ("overworld_bg_main", OW_BG_MAIN_PALETTE, OW_BG_MAIN_WORDS),
  ("overworld_bg_aux12", OW_BG_AUX12_PALETTE, OW_BG_AUX12_WORDS),
  ("overworld_bg_aux3", OW_BG_AUX3_PALETTE, OW_BG_AUX3_WORDS),
]


def dump_palettes(manifest, out_dir, generated_root, read_generated_words):
  """Write palette preview files from generated data or ROM fallback words.

  Parameters:
    manifest: Mutable dump manifest.
    out_dir: Overworld dump output directory.
    generated_root: Optional generated mod output root.
    read_generated_words: Helper that reads generated JSON word files.
  Returns:
    None.
  """
  palette_dir = os.path.join(out_dir, "palettes")
  ensure_dir(palette_dir)
  files = {}
  for name, address, count in PALETTES:
    words = read_palette_words(generated_root, read_generated_words, name, address, count)
    write_bytes(os.path.join(palette_dir, "%s.bin" % name), uint16le(words))
    write_json(os.path.join(palette_dir, "%s.json" % name), {
      "source_address": hex(address),
      "words": words,
    })
    files[name + "_bin"] = "palettes/%s.bin" % name
    files[name + "_json"] = "palettes/%s.json" % name
  manifest["files"]["palettes"] = files


def read_palette_words(generated_root, read_generated_words, name, address, count):
  """Read one fixed-length BGR555 palette word table.

  Parameters are generated source context plus ROM fallback address/count.
  Returns:
    Validated unsigned 16-bit words.
  """
  words = read_generated_words(generated_root, ("palettes", "%s.json" % name),
                               util.ROM.get_words(address, count))
  return validate_palette_words(name, words, count)


def validate_palette_words(name, words, count):
  """Validate one generated overworld palette table against its ROM-sized shape.

  Parameters are the table name, candidate words, and exact expected word count.
  Returns:
    A copied list of unsigned 16-bit integer words.
  """
  if len(words) != count:
    raise ValueError("%s must contain exactly %d BGR555 words." % (name, count))
  result = []
  for index, value in enumerate(words):
    if type(value) is not int:
      raise ValueError("%s[%d] must be an integer BGR555 word." % (name, index))
    if not 0 <= value <= 0xFFFF:
      raise ValueError("%s[%d] is outside 0x0000..0xFFFF." % (name, index))
    result.append(value)
  return result
