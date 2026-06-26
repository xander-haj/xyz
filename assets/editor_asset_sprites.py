# editor_asset_sprites.py -- Sprite catalog, placement, graphics, and behavior bindings.
#
# This module makes sprites addressable for editor UIs: every known sprite type
# gets a catalog record, and YAML placements from overworld areas and dungeon
# rooms are joined into a single placement index.

# Project-local helpers and source table extractors.
from editor_asset_common import (
  OVERWORLD_AREA_COUNT,
  asset_refs,
  code_ref,
  edit_status,
  load_yaml,
  overworld_sprite_stage_records,
  prefixed_hex_id,
  source_ref,
  sprite_name,
)
from dump_overworld_sprite_oam import dump_sprite_oam_tables
import tables


# Build every sprite-facing editor output.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   overworld_data: Payloads returned by editor_asset_overworld.
#   room_data: Payloads returned by editor_asset_rooms.
# Returns:
#   Dict of sprite output payloads.
def build_sprite_data(asset_lookup, overworld_data, room_data):
  placements = build_placement_index(overworld_data, room_data)
  return {
    'sprite_catalog': build_sprite_catalog(asset_lookup),
    'placement_index': placements,
    'oam_frames': build_oam_frames(),
    'graphics_requirements': build_graphics_requirements(placements, asset_lookup),
    'palette_requirements': build_palette_requirements(placements, room_data, asset_lookup),
    'behavior_bindings': build_behavior_bindings(asset_lookup),
  }


# Build the sprite type catalog from tables.py.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON sprite catalog payload.
def build_sprite_catalog(asset_lookup):
  entries = []
  for sprite_id, name in enumerate(tables.kSpriteNames):
    entries.append({
      'sprite': sprite_id,
      'name': name,
      'kind': 'overlord' if sprite_id >= 0x100 else 'standard',
      'init_flags3': tables.kSpriteInit_Flags3[sprite_id]
      if sprite_id < len(tables.kSpriteInit_Flags3) else None,
      'known_behavior_source': behavior_source_for_sprite(sprite_id),
    })
  return {
    'format': 'zelda3_editor_sprite_catalog',
    'sprites': entries,
    'sprite_tilesets': [
      {'set': index, 'packs': list(row)}
      for index, row in enumerate(tables.kSpriteTilesets)
    ],
    'compiled_assets': asset_refs(asset_lookup, [
      'kDungeonSprites', 'kDungeonSpriteOffs',
      'kOverworldSprites', 'kOverworldSpriteOffs',
    ]),
  }


# Build a combined source placement index.
# Parameters:
#   overworld_data: Payloads returned by editor_asset_overworld.
#   room_data: Payloads returned by editor_asset_rooms.
# Returns:
#   JSON placement index payload.
def build_placement_index(overworld_data, room_data):
  overworld = build_overworld_placements(overworld_data)
  rooms = build_room_placements(room_data)
  return {
    'format': 'zelda3_editor_sprite_placement_index',
    'overworld': overworld,
    'rooms': rooms,
    'all': overworld + rooms,
  }


# Build overworld sprite placement records from source YAML.
# Parameters:
#   overworld_data: Payloads returned by editor_asset_overworld.
# Returns:
#   List of placement records.
def build_overworld_placements(overworld_data):
  placements = []
  loaded_sources = {}
  for area in overworld_data['areas']['areas']:
    if area['area'] >= OVERWORLD_AREA_COUNT or not area['is_topology_head']:
      continue
    path = area['source_file']['path']
    if path not in loaded_sources:
      loaded_sources[path] = load_yaml(path)
    data = loaded_sources[path]
    for stage in overworld_sprite_stage_records(data):
      info = stage['info']
      for index, row in enumerate(stage['sprites']):
        sprite_id = prefixed_hex_id(row[2]) if len(row) > 2 else None
        placements.append({
          'scope': 'overworld',
          'area': area['area'],
          'source_area': area['source_area'],
          'stage': stage['stage'],
          'index': index,
          'x': row[0] if len(row) > 0 else None,
          'y': row[1] if len(row) > 1 else None,
          'type': sprite_id,
          'name': row[2] if len(row) > 2 else None,
          'canonical_name': sprite_name(sprite_id) if sprite_id is not None else None,
          'custom': row[3] if len(row) > 3 and isinstance(row[3], dict) else None,
          'graphics_set': info.get('gfx'),
          'palette_set': info.get('palette'),
          'source_file': area['source_file'],
        })
  return placements


# Build dungeon/indoor sprite placement records from room exports.
# Parameters:
#   room_data: Payloads returned by editor_asset_rooms.
# Returns:
#   List of placement records.
def build_room_placements(room_data):
  placements = []
  for room in room_data['rooms']['rooms']:
    for sprite in room['sprites']:
      record = dict(sprite)
      record.update({
        'scope': 'room',
        'source_file': room['source_file'],
        'room_header_palette': room['header'].get('palette'),
        'room_enemyblk': room['header'].get('enemyblk'),
      })
      placements.append(record)
  return placements


# Build OAM frame source tables by reusing the existing overworld dump extractor.
# Parameters: none.
# Returns:
#   JSON OAM payload.
def build_oam_frames():
  return {
    'format': 'zelda3_editor_sprite_oam_frames',
    'source_files': [
      source_ref('../src/sprite.c', 'c'),
      source_ref('../src/sprite_main.c', 'c'),
    ],
    'tables': dump_sprite_oam_tables(),
    'editability': edit_status(
      'code_backed',
      'Sprite OAM frames are C tables today; editor-safe writes require a compiler path.'),
  }


# Build graphics requirements from sprite placements.
# Parameters:
#   placements: Placement index payload.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON graphics requirements payload.
def build_graphics_requirements(placements, asset_lookup):
  requirements = {}
  for placement in placements['overworld']:
    key = placement.get('graphics_set')
    if key is None:
      continue
    requirements.setdefault(str(key), {'graphics_set': key, 'placements': []})
    requirements[str(key)]['placements'].append(placement_ref(placement))
  return {
    'format': 'zelda3_editor_sprite_graphics_requirements',
    'overworld_graphics_sets': list(requirements.values()),
    'sprite_tilesets': [{'set': index, 'packs': list(row)} for index, row in enumerate(tables.kSpriteTilesets)],
    'compiled_assets': asset_refs(asset_lookup, ['kOverworldSpriteGfx', 'kSprGfx']),
  }


# Build palette requirements from sprite placements and room headers.
# Parameters:
#   placements: Placement index payload.
#   room_data: Payloads returned by editor_asset_rooms.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON palette requirements payload.
def build_palette_requirements(placements, room_data, asset_lookup):
  overworld = {}
  for placement in placements['overworld']:
    key = placement.get('palette_set')
    if key is None:
      continue
    overworld.setdefault(str(key), {'palette_set': key, 'placements': []})
    overworld[str(key)]['placements'].append(placement_ref(placement))
  rooms = [
    {
      'room': room['room'],
      'palette': room['header'].get('palette'),
      'enemyblk': room['header'].get('enemyblk'),
      'sprite_count': len(room['sprites']),
    }
    for room in room_data['rooms']['rooms']
    if room['sprites']
  ]
  return {
    'format': 'zelda3_editor_sprite_palette_requirements',
    'overworld_palette_sets': list(overworld.values()),
    'room_palettes': rooms,
    'compiled_assets': asset_refs(asset_lookup, [
      'kOverworldSpritePalettes', 'kPalette_MainSpr',
      'kPalette_SpriteAux1', 'kPalette_SpriteAux3',
    ]),
  }


# Build behavior bindings for every sprite id.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON behavior binding payload.
def build_behavior_bindings(asset_lookup):
  return {
    'format': 'zelda3_editor_sprite_behavior_bindings',
    'bindings': [
      {
        'sprite': sprite_id,
        'name': name,
        'behavior_source': behavior_source_for_sprite(sprite_id),
        'editability': edit_status(
          'code_backed',
          'Sprite behavior is implemented in C and is not an editor-safe data table yet.'),
      }
      for sprite_id, name in enumerate(tables.kSpriteNames)
    ],
    'compiled_assets': asset_refs(asset_lookup, ['kEnemyDamageData']),
  }


# Build a small placement reference for requirement lists.
# Parameters:
#   placement: Full placement record.
# Returns:
#   Compact reference record.
def placement_ref(placement):
  if placement['scope'] == 'overworld':
    return {
      'scope': 'overworld',
      'area': placement['area'],
      'stage': placement['stage'],
      'index': placement['index'],
      'sprite': placement['type'],
    }
  return {
    'scope': 'room',
    'room': placement['room'],
    'index': placement['index'],
    'sprite': placement['type'],
  }


# Pick the current known code source for one sprite id.
# Parameters:
#   sprite_id: Sprite type id.
# Returns:
#   Source reference record.
def behavior_source_for_sprite(sprite_id):
  if sprite_id >= 0x100:
    return code_ref('../src/sprite.c', ['Overlord_Main'])
  return code_ref('../src/sprite_main.c', ['Sprite_Main'])
