"""
Dump source-backed sprite-sheet preview metadata for the overworld editor.

The editor needs enough data to identify and draw enemy sprite families without
guessing per-enemy OAM. This module reuses the same fixed-up entries consumed by
sprite_sheets.py so the browser can compose compact previews from decoded CHR.
"""

import copy
import re

import sprite_sheet_info
import sprite_sheets


FORMAT = "zelda3-sprite-sheet-previews-v1"
CONTEXT_NAMES = {
  0: "overworld",
  1: "dark-world",
  2: "dungeon",
  3: "raw-sheet",
}


def dump_sprite_sheet_previews():
  """
  Build compact preview metadata from sprite_sheet_info.py entries.

  Parameters: none.
  Returns:
    A JSON-serializable envelope with grouped sprite preview definitions.
  """
  groups = {}
  order = []
  for entry in fixed_entries():
    sprite_type = parse_sprite_type(entry.name)
    if sprite_type is None:
      continue
    key = (sprite_type, entry.name, entry.dungeon_or_ow)
    if key not in groups:
      groups[key] = []
      order.append(key)
    groups[key].append(entry)

  previews = []
  for key in order:
    preview = build_preview(key, groups[key])
    if preview:
      previews.append(preview)
  return {"format": FORMAT, "previews": previews}


def fixed_entries():
  """
  Return sprite-sheet entries with sprite_sheets.py derived fields available.

  Parameters: none.
  Returns:
    Entry-like objects with resolved tileset and palette fields.
  """
  entries = sprite_sheet_info.entries
  if all(hasattr(entry, "pal_idx") for entry in entries):
    return entries

  fixed = [copy.copy(entry) for entry in entries]
  previous = None
  for entry in fixed:
    sprite_sheets.fixup_sprite_set_entry(entry, previous)
    previous = entry
  return fixed


def parse_sprite_type(name):
  """
  Parse the hex sprite id from a sprite_sheet_info entry name.

  Parameters:
    name: Entry display name, usually beginning with two hex digits.
  Returns:
    Integer sprite type, or None for synthetic XX sheet entries.
  """
  match = re.match(r"^([0-9a-fA-F]{2})", name)
  return int(match.group(1), 16) if match else None


def build_preview(key, entries):
  """
  Build one grouped preview from all matching source-sheet sections.

  Parameters:
    key: Tuple of sprite type, display name, and context id.
    entries: Fixed sprite-sheet entries belonging to this preview.
  Returns:
    A JSON-ready preview object, or None if no source tiles are used.
  """
  sprite_type, name, context = key
  sections = []
  y = 0
  max_width = 0
  for section_entries in group_section_entries(entries):
    section = build_section(section_entries)
    if not section:
      continue
    section["y"] = y
    sections.append(section)
    max_width = max(max_width, section["width"])
    y += section["height"] + 1

  if not sections:
    return None
  for section in sections:
    section["x"] = (max_width - section["width"]) // 2
  return {
    "type": sprite_type,
    "name": name,
    "context": CONTEXT_NAMES.get(context, "unknown"),
    "dark_world_variant": "(DW)" in name or context == 1,
    "width": max_width,
    "height": y - 1,
    "sections": sections,
  }


def group_section_entries(entries):
  """
  Group palette-split entries that occupy the same source sheet slot.

  Parameters:
    entries: Fixed sprite-sheet entries belonging to one preview.
  Returns:
    Ordered lists of entries that should be composited together.
  """
  groups = {}
  order = []
  for entry in entries:
    key = (entry.tileset, entry.ss_idx)
    if key not in groups:
      groups[key] = []
      order.append(key)
    groups[key].append(entry)
  return [groups[key] for key in order]


def build_section(entries):
  """
  Convert fixed same-slot entries into one tile placement section.

  Parameters:
    entries: Fixed sprite-sheet entries sharing tileset and slot.
  Returns:
    A section object containing source tile coordinates and palette layers.
  """
  used = []
  for entry in entries:
    used.extend(used_tiles(entry.matrix))
  if not used:
    return None

  min_col = min(col for col, row in used)
  max_col = max(col for col, row in used)
  min_row = min(row for col, row in used)
  max_row = max(row for col, row in used)
  first = entries[0]
  return {
    "tileset": first.tileset,
    "slot": first.ss_idx,
    "x": 0,
    "width": (max_col - min_col + 1) * 8,
    "height": (max_row - min_row + 1) * 8,
    "layers": [build_layer(entry, min_col, min_row) for entry in entries],
  }


def build_layer(entry, min_col, min_row):
  """
  Build one palette layer inside a composited source-sheet section.

  Parameters:
    entry: Fixed sprite-sheet entry for one palette.
    min_col/min_row: Section crop origin in tile coordinates.
  Returns:
    Layer metadata with palette words and relative tile placements.
  """
  return {
    "palette_words": list(sprite_sheets.get_palette_subset(entry.pal_idx, entry.pal_subidx)),
    "palette_index": entry.pal_idx,
    "palette_subindex": entry.pal_subidx,
    "tiles": [
      {
        "x": (col - min_col) * 8,
        "y": (row - min_row) * 8,
        "tile": row * 16 + col,
      }
      for col, row in used_tiles(entry.matrix)
    ],
  }


def used_tiles(matrix):
  """
  Locate all occupied 8x8 tiles in a sprite_sheet_info matrix.

  Parameters:
    matrix: Four-row by sixteen-column tile-use grid.
  Returns:
    List of (column, row) tuples for non-empty tile slots.
  """
  result = []
  for row, values in enumerate(matrix):
    for col, value in enumerate(values):
      if value != ".":
        result.append((col, row))
  return result
