# editor_assets.py -- Editor-facing indexes over the compiled Zelda 3 asset dump.
#
# This module turns the faithful dat dump into helper JSON files that an editor
# can consume without hardcoding every runtime asset index. It does not replace
# source YAML; it adds grouped runtime tables, palette previews, and decode hints.

# Standard library imports for JSON output, safe directory refresh, and filesystem
# path handling.
import json
import shutil
from pathlib import Path

# Domain builders create the complete editor-readable database.
from editor_asset_allocators import build_allocator_data
from editor_asset_behavior import build_behavior_data
from editor_asset_dialogue import build_dialogue_data
from editor_asset_foundation import build_constraints
from editor_asset_foundation import build_provenance
from editor_asset_foundation import build_source_index
from editor_asset_graphics import build_graphics_data
from editor_asset_navigation import build_navigation_data
from editor_asset_overworld import build_overworld_data
from editor_asset_rooms import build_room_data
from editor_asset_sprites import build_sprite_data
from editor_asset_tiles import build_tile_data
from editor_asset_validation import build_validation_data

# Project-local helper builders keep this orchestration module below the project
# line-count ceiling.
from editor_asset_records import build_dungeon_rooms
from editor_asset_records import build_entrances
from editor_asset_records import build_overworld_navigation
from editor_asset_records import values_for_asset

# The editor helper format is versioned separately from the raw dat dump format.
EDITOR_FORMAT_VERSION = 1

# Editor helper outputs live under assets/dat-dump/editor.
EDITOR_DIR_NAME = 'editor'

# Runtime dump root used by restool.py after it changes cwd to assets/.
DAT_DUMP_DIR_NAME = 'dat-dump'

# Element sizes for flat runtime array payloads.
TYPE_SIZES = {
  'uint8': 1,
  'int8': 1,
  'uint16': 2,
  'int16': 2,
}

# Palette-style assets contain little-endian SNES BGR555 color words.
PALETTE_ASSETS = {
  'kPalette_DungBgMain',
  'kPalette_MainSpr',
  'kPalette_ArmorAndGloves',
  'kPalette_Sword',
  'kPalette_Shield',
  'kPalette_SpriteAux3',
  'kPalette_MiscSprite_Indoors',
  'kPalette_SpriteAux1',
  'kPalette_OverworldBgMain',
  'kPalette_OverworldBgAux12',
  'kPalette_OverworldBgAux3',
  'kPalette_PalaceMapBg',
  'kPalette_PalaceMapSpr',
  'kHudPalData',
  'kOverworldMapPaletteData',
}


# Write all editor-facing helper outputs next to the dat dump manifest.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   dump_manifest: Manifest returned by dat_dump.write_assets_to_directory().
#   args: Optional restool args, used for generated overworld/mod source roots.
#   output_dir: Runtime dump root, normally "dat-dump".
# Returns:
#   Root editor index dictionary written to editor_index.json.
def write_editor_assets(assets, dump_manifest, args=None, output_dir=DAT_DUMP_DIR_NAME):
  root = Path(output_dir)
  editor_dir = root / EDITOR_DIR_NAME
  reset_editor_directory(editor_dir)

  asset_lookup = build_asset_lookup(dump_manifest)
  outputs = {}

  def emit(key, rel_path, data):
    outputs[key] = write_json(root / rel_path, data, root)

  palettes = build_palettes(assets, asset_lookup)
  overworld_data = build_overworld_data(asset_lookup, args)
  room_data = build_room_data(assets, asset_lookup)
  navigation_data = build_navigation_data(assets, asset_lookup, overworld_data, room_data)
  allocator_data = build_allocator_data(overworld_data, room_data, navigation_data)
  tile_data = build_tile_data(assets, asset_lookup, args)
  graphics_data = build_graphics_data(assets, asset_lookup, palettes)
  sprite_data = build_sprite_data(asset_lookup, overworld_data, room_data)
  dialogue_data = build_dialogue_data(asset_lookup, overworld_data, room_data, sprite_data)
  behavior_data = build_behavior_data(assets, asset_lookup, sprite_data)
  validation_data = build_validation_data(
    overworld_data, room_data, navigation_data, tile_data, sprite_data, dialogue_data)

  emit('source_index', 'editor/source_index.json', build_source_index(asset_lookup))
  emit('constraints', 'editor/constraints.json', build_constraints())
  emit('typed_arrays', 'editor/typed_arrays.json', build_typed_arrays(assets, asset_lookup))
  emit('packed_assets', 'editor/packed_assets.json', build_packed_assets(dump_manifest))
  emit('palettes', 'editor/palettes.json', palettes)
  emit('entrances', 'editor/entrances.json', build_entrances(assets))
  emit('overworld_navigation', 'editor/overworld_navigation.json', build_overworld_navigation(assets))
  emit('dungeon_rooms', 'editor/dungeon_rooms.json', build_dungeon_rooms(assets, asset_lookup))

  emit('overworld/areas', 'editor/overworld/areas.json', overworld_data['areas'])
  emit('overworld/source_areas', 'editor/overworld/source_areas.json', overworld_data['source_areas'])
  emit('world/topology', 'editor/world/topology.json', overworld_data['topology'])
  emit('world/area_grid', 'editor/world/area_grid.json', overworld_data['area_grid'])
  emit('world/area_references', 'editor/world/area_references.json', overworld_data['area_references'])
  emit('world/remap_rules', 'editor/world/remap_rules.json', overworld_data['remap_rules'])
  emit('rooms/rooms', 'editor/rooms/rooms.json', room_data['rooms'])
  emit('rooms/default_rooms', 'editor/rooms/default_rooms.json', room_data['default_rooms'])
  emit('rooms/overlay_rooms', 'editor/rooms/overlay_rooms.json', room_data['overlay_rooms'])
  emit('navigation/world_graph', 'editor/navigation/world_graph.json', navigation_data['world_graph'])
  emit('navigation/entrance_graph', 'editor/navigation/entrance_graph.json', navigation_data['entrance_graph'])
  emit('navigation/exit_graph', 'editor/navigation/exit_graph.json', navigation_data['exit_graph'])
  emit('navigation/travel_graph', 'editor/navigation/travel_graph.json', navigation_data['travel_graph'])

  for key in ('rooms', 'entrances', 'starting_points', 'overworld_entrances',
              'fall_holes', 'exits', 'special_exits', 'overworld_areas'):
    emit('allocators/%s' % key, 'editor/allocators/%s.json' % key, allocator_data[key])

  for key in ('chr_tiles', 'map8_tiles', 'map16_tiles', 'map32_tiles',
              'tile_usage', 'collision_attributes', 'palette_usage'):
    emit('tiles/%s' % key, 'editor/tiles/%s.json' % key, tile_data[key])

  emit('graphics/bg_graphics', 'editor/graphics/bg_graphics.json', graphics_data['bg_graphics'])
  emit('graphics/sprite_graphics', 'editor/graphics/sprite_graphics.json', graphics_data['sprite_graphics'])
  emit('palettes/bg_palette_groups', 'editor/palettes/bg_palette_groups.json',
       graphics_data['bg_palette_groups'])
  emit('palettes/sprite_palette_groups', 'editor/palettes/sprite_palette_groups.json',
       graphics_data['sprite_palette_groups'])
  emit('palettes/palette_sources', 'editor/palettes/palette_sources.json',
       graphics_data['palette_sources'])

  for key in ('sprite_catalog', 'placement_index', 'oam_frames',
              'graphics_requirements', 'palette_requirements', 'behavior_bindings'):
    emit('sprites/%s' % key, 'editor/sprites/%s.json' % key, sprite_data[key])

  for key in ('dialogue_strings', 'sign_bindings', 'room_message_bindings',
              'npc_dialogue_bindings', 'usage_index'):
    emit('dialogue/%s' % key, 'editor/dialogue/%s.json' % key, dialogue_data[key])

  for key in ('enemy_behavior', 'projectiles', 'damage_tables', 'animation_bindings'):
    emit('behavior/%s' % key, 'editor/behavior/%s.json' % key, behavior_data[key])

  emit('player/link_animations', 'editor/player/link_animations.json',
       behavior_data['link_animations'])
  emit('validation', 'editor/validation.json', validation_data)
  emit('provenance', 'editor/provenance.json', build_provenance(outputs))

  index = build_editor_index(dump_manifest, outputs)
  write_json(root / 'editor_index.json', index, root)
  print('Wrote editor asset helpers to %s' % editor_dir)
  return index


# Replace only the owned editor helper directory.
# Parameters:
#   editor_dir: Path to assets/dat-dump/editor.
# Returns:
#   None.
def reset_editor_directory(editor_dir):
  if editor_dir.name != EDITOR_DIR_NAME:
    raise ValueError('Refusing to clean unexpected editor directory: %s' % editor_dir)
  if editor_dir.exists():
    # Avoid following symlinks so the refresh cannot delete files outside the dump.
    if editor_dir.is_symlink():
      raise ValueError('Refusing to replace symlinked editor directory: %s' % editor_dir)
    if not editor_dir.is_dir():
      raise ValueError('Editor asset path exists and is not a directory: %s' % editor_dir)
    shutil.rmtree(editor_dir)
  editor_dir.mkdir(parents=True)


# Build a name-keyed lookup from the raw dat dump manifest.
# Parameters:
#   dump_manifest: Root dat dump manifest dictionary.
# Returns:
#   Dict mapping asset name to manifest asset record.
def build_asset_lookup(dump_manifest):
  return {asset['name']: asset for asset in dump_manifest['assets']}


# Create the root editor index that points at all helper files.
# Parameters:
#   dump_manifest: Root dat dump manifest dictionary.
#   outputs: Mapping of helper section name to relative output path.
# Returns:
#   JSON-serializable editor index.
def build_editor_index(dump_manifest, outputs):
  return {
    'format': 'zelda3_editor_assets',
    'format_version': EDITOR_FORMAT_VERSION,
    'dat_dump_manifest': 'manifest.json',
    'asset_count': dump_manifest['asset_count'],
    'outputs': outputs,
    'notes': [
      'These files group runtime assets for editor loading.',
      'Editable semantic sources still live in extracted YAML where available.',
      'Code-backed behavior is marked explicitly instead of pretending it is data-editable.',
    ],
  }


# Build metadata for flat typed arrays without copying full payloads into JSON.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Name-keyed dat dump manifest lookup.
# Returns:
#   List of typed array metadata records.
def build_typed_arrays(assets, asset_lookup):
  records = []
  # Preserve runtime order so editor code can compare against asset indexes.
  for name, (asset_type, data) in assets.items():
    if asset_type == 'packed':
      continue
    element_size = TYPE_SIZES[asset_type]
    records.append({
      'name': name,
      'index': asset_lookup[name]['index'],
      'type': asset_type,
      'element_size': element_size,
      'element_count': len(data) // element_size,
      'byte_order': 'little' if element_size > 1 else 'not_applicable',
      'data_file': asset_lookup[name]['data_file'],
    })
  return records


# Build packed asset records with family-level decode hints.
# Parameters:
#   dump_manifest: Root dat dump manifest dictionary.
# Returns:
#   List of packed asset metadata records.
def build_packed_assets(dump_manifest):
  records = []
  # Packed assets already have split entries in the raw dump; this layer adds
  # editor-oriented interpretation hints beside those file paths.
  for asset in dump_manifest['assets']:
    if asset['type'] != 'packed':
      continue
    record = {
      'name': asset['name'],
      'index': asset['index'],
      'entry_count': asset['entry_count'],
      'packed_file': asset['packed_file'],
      'entries_directory': asset['entries_directory'],
      'family': packed_family(asset['name']),
      'entries': [],
    }
    for entry in asset['entries']:
      entry_record = dict(entry)
      entry_record['decode_hint'] = packed_entry_decode_hint(asset['name'], entry)
      record['entries'].append(entry_record)
    records.append(record)
  return records


# Classify a packed asset into an editor-facing family.
# Parameters:
#   name: Runtime asset name.
# Returns:
#   Family identifier string.
def packed_family(name):
  families = {
    'kSprGfx': 'sprite_graphics',
    'kBgGfx': 'background_graphics',
    'kDialogue': 'dialogue',
    'kDialogueFont': 'dialogue_font',
    'kDialogueMap': 'dialogue_language_map',
    'kDungMap_FloorLayout': 'dungeon_map_floor_layout',
    'kDungMap_Tiles': 'dungeon_map_tiles',
    'kOverworld_Hibytes_Comp': 'overworld_map32_high_streams',
    'kOverworld_Lobytes_Comp': 'overworld_map32_low_streams',
  }
  return families.get(name, 'packed_runtime_array')


# Give an editor a concrete first decoder to try for one packed entry.
# Parameters:
#   name: Runtime packed asset name.
#   entry: Per-entry manifest record containing index and size.
# Returns:
#   Decode hint string.
def packed_entry_decode_hint(name, entry):
  if name == 'kSprGfx':
    # Vanilla sprite sheets 0-11 are fixed raw 4bpp tiles; later sheets are
    # normally SNES-LZ streams unless the user compiled from PNGs.
    return 'raw_snes_4bpp_tiles' if entry['index'] < 12 else 'snes_lz_or_png_encoded_tiles'
  if name == 'kBgGfx':
    return 'snes_lz_or_generated_bg_tiles'
  if name in ('kOverworld_Hibytes_Comp', 'kOverworld_Lobytes_Comp'):
    return 'snes_lz_or_store_wrapped_map32_stream'
  if name.startswith('kDialogue'):
    return 'dialogue_nested_packed_runtime_data'
  return 'raw_packed_entry'


# Decode palette assets into SNES words and RGB preview colors.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Name-keyed dat dump manifest lookup.
# Returns:
#   Dict keyed by palette asset name.
def build_palettes(assets, asset_lookup):
  palettes = {}
  for name in sorted(PALETTE_ASSETS):
    if name not in assets:
      continue
    words = values_for_asset(assets, name)
    palettes[name] = {
      'index': asset_lookup[name]['index'],
      'data_file': asset_lookup[name]['data_file'],
      'color_count': len(words),
      'colors': [snes_color_record(index, word) for index, word in enumerate(words)],
    }
  return palettes


# Convert one SNES BGR555 color word into an editor preview record.
# Parameters:
#   index: Color index within the asset.
#   word: 15-bit SNES BGR color value.
# Returns:
#   JSON color record with raw word, RGB channels, and hex string.
def snes_color_record(index, word):
  red = scale_5bit_channel(word & 0x1f)
  green = scale_5bit_channel((word >> 5) & 0x1f)
  blue = scale_5bit_channel((word >> 10) & 0x1f)
  return {
    'index': index,
    'snes_bgr555': word,
    'rgb': [red, green, blue],
    'hex': '#%02x%02x%02x' % (red, green, blue),
  }


# Expand a 5-bit SNES color channel to an 8-bit preview channel.
# Parameters:
#   value: Integer 0..31.
# Returns:
#   Integer 0..255.
def scale_5bit_channel(value):
  return (value * 255 + 15) // 31


# Write deterministic JSON and return the dump-root-relative path.
# Parameters:
#   path: Output path.
#   data: JSON-serializable value.
#   root: Optional dump root for relative path calculation.
# Returns:
#   Path string relative to the dump root.
def write_json(path, data, root=None):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf8')
  relative_root = root if root is not None else path.parents[1]
  return path.relative_to(relative_root).as_posix()
