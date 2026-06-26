# editor_asset_behavior.py -- Enemy, projectile, damage, and animation bindings.
#
# Most behavior in this codebase is still C logic, not editable data. This
# module exports the data-backed pieces that exist now and marks code-backed
# systems explicitly so future editor work can create real compiler paths.

# Project-local helpers and runtime array decoding.
from editor_asset_common import asset_ref, asset_refs, code_ref, edit_status, source_ref
from editor_asset_records import values_for_asset
import tables


# Build behavior and player-animation payloads.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   sprite_data: Payloads returned by editor_asset_sprites.
# Returns:
#   Dict of behavior and player output payloads.
def build_behavior_data(assets, asset_lookup, sprite_data):
  placement_counts = placement_counts_by_sprite(sprite_data)
  return {
    'enemy_behavior': build_enemy_behavior(asset_lookup, placement_counts),
    'projectiles': build_projectiles(asset_lookup),
    'damage_tables': build_damage_tables(assets, asset_lookup),
    'animation_bindings': build_animation_bindings(asset_lookup),
    'link_animations': build_link_animations(asset_lookup),
  }


# Count source placements by sprite id.
# Parameters:
#   sprite_data: Payloads returned by editor_asset_sprites.
# Returns:
#   Dict keyed by sprite id.
def placement_counts_by_sprite(sprite_data):
  counts = {}
  for placement in sprite_data['placement_index']['all']:
    sprite_id = placement.get('type')
    if sprite_id is not None:
      counts[sprite_id] = counts.get(sprite_id, 0) + 1
  return counts


# Build enemy behavior catalog records.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
#   placement_counts: Dict keyed by sprite id.
# Returns:
#   JSON enemy behavior payload.
def build_enemy_behavior(asset_lookup, placement_counts):
  records = []
  for sprite_id, name in enumerate(tables.kSpriteNames):
    records.append({
      'sprite': sprite_id,
      'name': name,
      'placement_count': placement_counts.get(sprite_id, 0),
      'init_flags3': tables.kSpriteInit_Flags3[sprite_id]
      if sprite_id < len(tables.kSpriteInit_Flags3) else None,
      'behavior_source': behavior_source(sprite_id),
      'editability': edit_status(
        'code_backed',
        'AI decisions, attacks, and movement are implemented in C behavior code today.'),
    })
  return {
    'format': 'zelda3_editor_enemy_behavior',
    'sprites': records,
    'known_data_tables': [
      'kSpriteInit_Flags3 from tables.py',
      'kEnemyDamageData from compiled assets',
    ],
    'compiled_assets': asset_refs(asset_lookup, ['kEnemyDamageData']),
  }


# Build projectile and ancilla source bindings.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON projectile payload.
def build_projectiles(asset_lookup):
  return {
    'format': 'zelda3_editor_projectiles',
    'source_files': [
      code_ref('../src/ancilla.c'),
      code_ref('../src/ancilla.h'),
      code_ref('../src/player.c'),
      code_ref('../src/sprite.c'),
      code_ref('../src/sprite_main.c'),
    ],
    'records': [],
    'editability': edit_status(
      'requires_engine_work',
      'Projectile definitions are not exported as a data table yet; they are spawned by C logic.'),
    'required_next_step': (
      'Extract ancilla/projectile type definitions, spawn parameters, graphics, and damage '
      'into compiler-backed records before UI editing.'),
    'compiled_assets': asset_refs(asset_lookup, ['kSprGfx']),
  }


# Build raw enemy damage table payload.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON damage table payload.
def build_damage_tables(assets, asset_lookup):
  values = values_for_asset(assets, 'kEnemyDamageData') if 'kEnemyDamageData' in assets else []
  return {
    'format': 'zelda3_editor_damage_tables',
    'source_rom_address': '0x83e800',
    'asset': asset_ref(asset_lookup, 'kEnemyDamageData'),
    'byte_count': len(values),
    'bytes': values,
    'layout_status': 'raw_decompressed_table',
    'editability': edit_status(
      'compiler_backed',
      'The compiler emits this table, but named weapon/enemy row metadata still needs extraction.'),
  }


# Build animation source bindings for sprite and enemy animation work.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON animation binding payload.
def build_animation_bindings(asset_lookup):
  return {
    'format': 'zelda3_editor_animation_bindings',
    'sprite_oam_frames': 'editor/sprites/oam_frames.json',
    'source_files': [
      code_ref('../src/sprite.c'),
      code_ref('../src/sprite_main.c'),
      code_ref('../src/player_oam.c'),
    ],
    'editability': edit_status(
      'code_backed',
      'Animation frame selection is currently C table/logic backed.'),
    'compiled_assets': asset_refs(asset_lookup, ['kSprGfx', 'kLinkGraphics']),
  }


# Build Link animation and graphics source bindings.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON Link animation payload.
def build_link_animations(asset_lookup):
  return {
    'format': 'zelda3_editor_link_animations',
    'graphics_asset': asset_ref(asset_lookup, 'kLinkGraphics'),
    'graphics_source': source_ref('linksprite.png', 'png'),
    'logic_sources': [
      code_ref('../src/player.c', [
        'kPlayerHandlers',
        'kLinkSpinGraphicsByDir',
        'kLinkSpinDelays',
      ]),
      code_ref('../src/player_oam.c', [
        'kLinkDmaGraphicsIndices',
        'kLinkSpriteBodys',
        'LinkOam_Main',
      ]),
    ],
    'editability': edit_status(
      'requires_engine_work',
      'The sheet is compiler-backed, but adding new Link animation states needs player/OAM table work.'),
    'required_next_step': (
      'Extract Link pose categories, DMA indices, body OAM descriptors, and state transitions '
      'into compiler-backed animation records.'),
  }


# Pick the current known behavior source for one sprite id.
# Parameters:
#   sprite_id: Sprite type id.
# Returns:
#   Source reference record.
def behavior_source(sprite_id):
  if sprite_id >= 0x100:
    return code_ref('../src/sprite.c', ['Overlord_Main'])
  return code_ref('../src/sprite_main.c', ['Sprite_Main'])
