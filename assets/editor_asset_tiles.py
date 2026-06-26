# editor_asset_tiles.py -- Tile indirection and usage exports for editors.
#
# Zelda 3 overworld terrain is a chain: map32 cells point at four map16 tiles,
# map16 tiles point at four map8 tile words, and map8 words point at CHR tile
# pixels plus palette/flip/priority bits. This module exposes each layer.

# Standard library imports for path handling and usage counters.
from collections import Counter
from pathlib import Path

# Project-local helpers and runtime array decoding.
from editor_asset_common import asset_refs, load_json_if_exists, source_ref
from editor_asset_records import values_for_asset
import overworld_map32

# Quadrant names shared by map32->map16 and map16->map8 records.
QUADRANTS = ('top_left', 'top_right', 'bottom_left', 'bottom_right')


# Build every tile-facing editor output.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   args: Optional restool args, used when mod-generated roots are active.
# Returns:
#   Dict of tile output payloads.
def build_tile_data(assets, asset_lookup, args=None):
  map32_entries, map32_source = load_map32_to_map16(args)
  map16_entries = build_map16_entries(assets)
  map8_entries = build_map8_entries(map16_entries, assets)
  usage = build_tile_usage(map32_entries, map16_entries, args)
  return {
    'chr_tiles': build_chr_tiles(assets, asset_lookup),
    'map8_tiles': {
      'format': 'zelda3_editor_map8_tiles',
      'tiles': map8_entries,
      'compiled_assets': asset_refs(asset_lookup, ['kMap16ToMap8', 'kMap8DataToTileAttr']),
    },
    'map16_tiles': {
      'format': 'zelda3_editor_map16_tiles',
      'tiles': map16_entries,
      'compiled_assets': asset_refs(asset_lookup, ['kMap16ToMap8']),
    },
    'map32_tiles': {
      'format': 'zelda3_editor_map32_tiles',
      'source_file': source_ref(map32_source, 'text'),
      'tiles': map32_entries,
      'compiled_assets': asset_refs(asset_lookup, [
        'kMap32ToMap16_0', 'kMap32ToMap16_1',
        'kMap32ToMap16_2', 'kMap32ToMap16_3',
      ]),
    },
    'tile_usage': usage,
    'collision_attributes': build_collision_attributes(assets, asset_lookup),
    'palette_usage': build_palette_usage(map8_entries, map16_entries),
  }


# Load map32-to-map16 source rows from the same file compile_resources prefers.
# Parameters:
#   args: Optional restool args with overworld_generated_root.
# Returns:
#   Tuple of editor entries and source path.
def load_map32_to_map16(args):
  raw_generated_root = getattr(args, 'overworld_generated_root', None) if args else None
  generated_root = Path(raw_generated_root) if raw_generated_root else None
  generated = generated_root / 'map32_to_map16.txt' if generated_root else None
  source = generated if generated is not None and generated.exists() else Path('map32_to_map16.txt')
  entries = []
  with source.open('r', encoding='utf8') as file:
    for line in file:
      stripped = line.strip()
      if not stripped:
        continue
      raw_index, raw_values = stripped.split(':', 1)
      values = [int(value) for value in raw_values.split(',')]
      entries.append({
        'map32': int(raw_index),
        'map16': dict(zip(QUADRANTS, values)),
      })
  return entries, source


# Build map16 records from the compiled kMap16ToMap8 table.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of map16 records.
def build_map16_entries(assets):
  if 'kMap16ToMap8' not in assets:
    return []
  words = values_for_asset(assets, 'kMap16ToMap8')
  entries = []
  for index in range(len(words) // 4):
    group = words[index * 4:index * 4 + 4]
    entries.append({
      'map16': index,
      'map8_words': dict(zip(QUADRANTS, group)),
      'map8_tiles': {
        quadrant: decode_map8_word(word)
        for quadrant, word in zip(QUADRANTS, group)
      },
    })
  return entries


# Build unique map8 word records used by map16 tiles.
# Parameters:
#   map16_entries: List of map16 records.
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of unique map8 records.
def build_map8_entries(map16_entries, assets):
  attrs = values_for_asset(assets, 'kMap8DataToTileAttr') if 'kMap8DataToTileAttr' in assets else []
  counts = Counter()
  for entry in map16_entries:
    for word in entry['map8_words'].values():
      counts[word] += 1
  records = []
  for word, count in sorted(counts.items()):
    decoded = decode_map8_word(word)
    tile_id = decoded['tile_id']
    decoded['word'] = word
    decoded['used_by_map16_count'] = count
    decoded['collision_attr'] = attrs[tile_id] if tile_id < len(attrs) else None
    records.append(decoded)
  return records


# Decode one SNES BG tile word.
# Parameters:
#   word: 16-bit map8 tile word.
# Returns:
#   Dict with tile id, palette, priority, and flip flags.
def decode_map8_word(word):
  return {
    'tile_id': word & 0x03ff,
    'palette': (word >> 10) & 0x07,
    'priority': bool(word & 0x2000),
    'h_flip': bool(word & 0x4000),
    'v_flip': bool(word & 0x8000),
  }


# Build CHR tile pixel records for raw 4bpp assets available in the dump.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
# Returns:
#   JSON CHR tile payload.
def build_chr_tiles(assets, asset_lookup):
  sources = []
  tiles = []
  if 'kOverworldMapGfx' in assets:
    _asset_type, data = assets['kOverworldMapGfx']
    sources.append({
      'asset': 'kOverworldMapGfx',
      'encoding': 'raw_snes_4bpp_tiles',
      'tile_count': len(data) // 32,
    })
    for index in range(len(data) // 32):
      tiles.append({
        'source_asset': 'kOverworldMapGfx',
        'tile': index,
        'pixels': decode_4bpp_tile(data[index * 32:index * 32 + 32]),
      })
  return {
    'format': 'zelda3_editor_chr_tiles',
    'sources': sources,
    'tiles': tiles,
    'notes': [
      'This file decodes raw 4bpp CHR assets that are already flat runtime data.',
      'Compressed BG graphics remain referenced in editor/graphics/bg_graphics.json.',
    ],
    'compiled_assets': asset_refs(asset_lookup, ['kOverworldMapGfx', 'kBgGfx']),
  }


# Decode one 8x8 SNES 4bpp tile to palette-index pixels.
# Parameters:
#   tile: 32-byte SNES 4bpp tile.
# Returns:
#   8x8 nested list of palette indices 0..15.
def decode_4bpp_tile(tile):
  rows = []
  for y in range(8):
    row = []
    plane01 = y * 2
    plane23 = y * 2 + 16
    for x in range(8):
      bit = 7 - x
      value = ((tile[plane01] >> bit) & 1)
      value |= ((tile[plane01 + 1] >> bit) & 1) << 1
      value |= ((tile[plane23] >> bit) & 1) << 2
      value |= ((tile[plane23 + 1] >> bit) & 1) << 3
      row.append(value)
    rows.append(row)
  return rows


# Build source-grid tile usage counts.
# Parameters:
#   map32_entries: List of map32 records.
#   map16_entries: List of map16 records.
#   args: Optional restool args with overworld_source_root.
# Returns:
#   JSON tile usage payload.
def build_tile_usage(map32_entries, map16_entries, args):
  map32_counts = Counter()
  source_root = Path(getattr(args, 'overworld_source_root', None) or overworld_map32.DEFAULT_SOURCE_DIR)
  for screen in range(overworld_map32.SCREEN_COUNT):
    payload = load_json_if_exists(source_root / ('%03d.json' % screen))
    if not payload:
      continue
    for row in payload.get('map32') or []:
      for value in row:
        map32_counts[value] += 1
  map32_lookup = {entry['map32']: entry for entry in map32_entries}
  map16_counts = Counter()
  for map32, count in map32_counts.items():
    entry = map32_lookup.get(map32)
    if not entry:
      continue
    for map16 in entry['map16'].values():
      map16_counts[map16] += count
  map16_lookup = {entry['map16']: entry for entry in map16_entries}
  map8_counts = Counter()
  for map16, count in map16_counts.items():
    entry = map16_lookup.get(map16)
    if not entry:
      continue
    for word in entry['map8_words'].values():
      map8_counts[word] += count
  return {
    'format': 'zelda3_editor_tile_usage',
    'source_root': source_ref(source_root, 'json_directory'),
    'map32': counter_records(map32_counts, 'map32'),
    'map16': counter_records(map16_counts, 'map16'),
    'map8_words': counter_records(map8_counts, 'word'),
  }


# Convert a Counter to sorted JSON records.
# Parameters:
#   counter: Counter keyed by tile id.
#   key_name: JSON key name for the tile id.
# Returns:
#   List of count records.
def counter_records(counter, key_name):
  return [{key_name: key, 'use_count': count} for key, count in sorted(counter.items())]


# Build map8 collision attribute records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON collision attribute payload.
def build_collision_attributes(assets, asset_lookup):
  attrs = values_for_asset(assets, 'kMap8DataToTileAttr') if 'kMap8DataToTileAttr' in assets else []
  return {
    'format': 'zelda3_editor_collision_attributes',
    'attributes': [
      {'map8_tile_id': index, 'attribute': value}
      for index, value in enumerate(attrs)
    ],
    'compiled_assets': asset_refs(asset_lookup, ['kMap8DataToTileAttr', 'kSomeTileAttr']),
  }


# Build palette-use summaries from map8 words.
# Parameters:
#   map8_entries: Unique map8 records.
#   map16_entries: List of map16 records.
# Returns:
#   JSON palette usage payload.
def build_palette_usage(map8_entries, map16_entries):
  palette_counts = Counter()
  for entry in map8_entries:
    palette_counts[entry['palette']] += entry['used_by_map16_count']
  map16_palettes = []
  for entry in map16_entries:
    palettes = sorted({tile['palette'] for tile in entry['map8_tiles'].values()})
    map16_palettes.append({'map16': entry['map16'], 'palettes': palettes})
  return {
    'format': 'zelda3_editor_palette_usage',
    'map8_palette_counts': counter_records(palette_counts, 'palette'),
    'map16_palettes': map16_palettes,
  }
