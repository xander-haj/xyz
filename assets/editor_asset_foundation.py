# editor_asset_foundation.py -- Root metadata for the editor asset database.
#
# These builders describe where data comes from, which outputs were written,
# and what hard limits the current compiler/runtime still enforce. The editor
# should use these files before deciding whether a record is safe to edit.

# Project-local helpers produce consistent source and asset references.
from editor_asset_common import (
  DEFAULT_ROOM_COUNT,
  DUNGEON_ROOM_COUNT,
  NORMAL_OVERWORLD_AREA_COUNT,
  OVERLAY_ROOM_COUNT,
  OVERWORLD_AREA_COUNT,
  asset_refs,
  code_ref,
  compiler_ref,
  source_ref,
)


# Build the root source index for every data family the editor database exposes.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
# Returns:
#   JSON source index.
def build_source_index(asset_lookup):
  return {
    'format': 'zelda3_editor_source_index',
    'sources': {
      'overworld_areas': {
        'pattern': 'overworld/overworld-%d.yaml',
        'count': OVERWORLD_AREA_COUNT,
        'kind': 'yaml',
      },
      'overworld_map32': {
        'pattern': 'overworld_maps/%03d.json',
        'count': OVERWORLD_AREA_COUNT,
        'kind': 'json',
      },
      'rooms': {
        'pattern': 'dungeon/dungeon-%d.yaml',
        'count': DUNGEON_ROOM_COUNT,
        'kind': 'yaml',
      },
      'room_templates': {
        'files': [
          source_ref('dungeon/default_rooms.yaml', 'yaml'),
          source_ref('dungeon/overlay_rooms.yaml', 'yaml'),
        ],
      },
      'tiles': {
        'files': [
          source_ref('map32_to_map16.txt', 'text'),
          source_ref('overworld_dump/tables/map16_to_map8.json', 'json_optional'),
        ],
      },
      'dialogue': {'files': [source_ref('dialogue.txt', 'text')]},
      'link_graphics': {'files': [source_ref('linksprite.png', 'png')]},
      'behavior_code': {
        'files': [
          code_ref('../src/sprite.c', ['Sprite_Main']),
          code_ref('../src/sprite_main.c'),
          code_ref('../src/ancilla.c'),
          code_ref('../src/player.c', ['kPlayerHandlers']),
          code_ref('../src/player_oam.c'),
        ],
      },
      'lookup_tables': {'files': [source_ref('tables.py', 'python')]},
    },
    'compiled_runtime_assets': {
      'room_core': asset_refs(asset_lookup, [
        'kDungeonRoom', 'kDungeonRoomOffs', 'kDungeonRoomDoorOffs',
        'kDungeonRoomHeaders', 'kDungeonRoomHeadersOffs',
      ]),
      'overworld_core': asset_refs(asset_lookup, [
        'kOverworld_Hibytes_Comp', 'kOverworld_Lobytes_Comp',
        'kOverworldMapIsSmall', 'kOverworldAuxTileThemeIndexes',
      ]),
      'navigation': asset_refs(asset_lookup, [
        'kEntranceData_rooms', 'kStartingPoint_rooms',
        'kOverworld_Entrance_Area', 'kFallHole_Area', 'kExitDataRooms',
      ]),
      'tiles': asset_refs(asset_lookup, [
        'kMap32ToMap16_0', 'kMap32ToMap16_1', 'kMap32ToMap16_2',
        'kMap32ToMap16_3', 'kMap16ToMap8', 'kMap8DataToTileAttr',
      ]),
      'sprites_and_behavior': asset_refs(asset_lookup, [
        'kDungeonSprites', 'kOverworldSprites', 'kSprGfx',
        'kEnemyDamageData', 'kLinkGraphics',
      ]),
      'dialogue': asset_refs(asset_lookup, ['kDialogue', 'kDialogueFont', 'kDialogueMap']),
    },
  }


# Build provenance metadata that connects editor files to compiler paths.
# Parameters:
#   outputs: Mapping of output key to dump-root-relative path.
# Returns:
#   JSON provenance dictionary.
def build_provenance(outputs):
  return {
    'format': 'zelda3_editor_provenance',
    'outputs': dict(sorted(outputs.items())),
    'compiler_paths': {
      'overworld': compiler_ref('print_overworld_tables', [
        'kOverworldMapIsSmall', 'kOverworldAuxTileThemeIndexes',
        'kOverworldBgPalettes', 'kOverworld_SignText',
      ]),
      'overworld_terrain': compiler_ref('print_overworld', [
        'kOverworld_Hibytes_Comp', 'kOverworld_Lobytes_Comp',
      ]),
      'rooms': compiler_ref('print_dungeon_rooms', [
        'kDungeonRoom', 'kDungeonRoomOffs', 'kDungeonRoomHeaders',
        'kEntranceData_rooms', 'kStartingPoint_rooms',
      ]),
      'sprites': compiler_ref('print_dungeon_sprites / print_overworld_tables', [
        'kDungeonSprites', 'kDungeonSpriteOffs',
        'kOverworldSprites', 'kOverworldSpriteOffs',
      ]),
      'tiles': compiler_ref('print_map32_to_map16 / print_misc', [
        'kMap32ToMap16_0', 'kMap32ToMap16_1', 'kMap32ToMap16_2',
        'kMap32ToMap16_3', 'kMap16ToMap8', 'kMap8DataToTileAttr',
      ]),
      'dialogue': compiler_ref('print_dialogue', ['kDialogue', 'kDialogueFont', 'kDialogueMap']),
      'behavior': compiler_ref('print_enemy_damage_data', ['kEnemyDamageData']),
      'link': compiler_ref('print_link_graphics', ['kLinkGraphics']),
    },
  }


# Build editor constraints and capacity limits exposed to UI tooling.
# Parameters: none.
# Returns:
#   JSON constraints dictionary.
def build_constraints():
  return {
    'format': 'zelda3_editor_constraints',
    'overworld': {
      'area_count': OVERWORLD_AREA_COUNT,
      'normal_area_count': NORMAL_OVERWORLD_AREA_COUNT,
      'special_area_count': OVERWORLD_AREA_COUNT - NORMAL_OVERWORLD_AREA_COUNT,
      'grid_width': 16,
      'grid_height': 16,
      'expansion_status': 'requires_compiler_and_runtime_work',
      'notes': [
        'Adding new map squares beyond 159 is not a data-only edit yet.',
        'Row insertion must update topology, navigation, terrain streams, and runtime area indexing together.',
      ],
    },
    'rooms': {
      'room_count': DUNGEON_ROOM_COUNT,
      'default_room_count': DEFAULT_ROOM_COUNT,
      'overlay_room_count': OVERLAY_ROOM_COUNT,
      'expansion_status': 'requires_compiler_and_runtime_work',
    },
    'navigation_slots': {
      'entrances': 133,
      'starting_points': 7,
      'overworld_entrances': 129,
      'fall_holes': 19,
      'exits': 79,
      'special_exits': 16,
      'travel': 17,
    },
    'tiles': {
      'map32_grid': '16x16 per overworld area',
      'map32_to_map16_quadrants': ['top_left', 'top_right', 'bottom_left', 'bottom_right'],
      'map16_to_map8_quadrants': ['top_left', 'top_right', 'bottom_left', 'bottom_right'],
      'palette_format': 'snes_bgr555',
      'map8_attr_status': 'compiler_backed',
    },
    'editability_levels': {
      'yaml_backed': 'Editor can write source YAML/JSON and rely on the compiler.',
      'compiler_backed': 'Compiler emits data, but source authoring path may need UI/schema work.',
      'code_backed': 'Behavior is implemented in C code, not an editor-safe data table.',
      'requires_engine_work': 'The runtime and compiler must be extended before safe editing.',
    },
  }
