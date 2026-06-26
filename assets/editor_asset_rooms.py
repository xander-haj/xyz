# editor_asset_rooms.py -- Dungeon and indoor room records for editor exports.
#
# Room YAML is already the closest thing this project has to a semantic indoor
# editor model. This module exports that model directly, with compiled offsets
# attached so a UI can compare source records with runtime table positions.

# Standard library imports for path handling and sprite subcode parsing.
import re
from pathlib import Path

# Project-local helpers and runtime array decoding.
from editor_asset_common import (
  DEFAULT_ROOM_COUNT,
  DUNGEON_ROOM_COUNT,
  OVERLAY_ROOM_COUNT,
  asset_refs,
  edit_status,
  load_yaml,
  prefixed_hex_id,
  source_ref,
  sprite_name,
)
from editor_asset_records import values_for_asset


# Build every room-facing editor output.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
# Returns:
#   Dict containing room, default-room, and overlay-room JSON payloads.
def build_room_data(assets, asset_lookup):
  rooms = [build_room_record(room, load_room(room), assets, asset_lookup)
           for room in range(DUNGEON_ROOM_COUNT)]
  return {
    'rooms': {
      'format': 'zelda3_editor_rooms',
      'room_count': DUNGEON_ROOM_COUNT,
      'rooms': rooms,
      'compiled_assets': asset_refs(asset_lookup, [
        'kDungeonRoom', 'kDungeonRoomOffs', 'kDungeonRoomDoorOffs',
        'kDungeonRoomHeaders', 'kDungeonRoomHeadersOffs',
        'kDungeonRoomChests', 'kDungeonRoomTeleMsg', 'kDungeonPitsHurtPlayer',
      ]),
    },
    'default_rooms': build_template_rooms(
      'zelda3_editor_default_rooms',
      'dungeon/default_rooms.yaml',
      'Default',
      DEFAULT_ROOM_COUNT,
      assets,
      asset_lookup,
      'kDungeonRoomDefault',
      'kDungeonRoomDefaultOffs'),
    'overlay_rooms': build_template_rooms(
      'zelda3_editor_overlay_rooms',
      'dungeon/overlay_rooms.yaml',
      'Overlay',
      OVERLAY_ROOM_COUNT,
      assets,
      asset_lookup,
      'kDungeonRoomOverlay',
      'kDungeonRoomOverlayOffs'),
  }


# Load one room YAML file.
# Parameters:
#   room: Room id 0..319.
# Returns:
#   Parsed room YAML.
def load_room(room):
  return load_yaml(Path('dungeon') / ('dungeon-%d.yaml' % room))


# Build one room record with source data and runtime offsets.
# Parameters:
#   room: Room id.
#   data: Parsed room YAML.
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON room record.
def build_room_record(room, data, assets, asset_lookup):
  offsets = room_offsets(room, assets)
  return {
    'room': room,
    'source_file': source_ref(Path('dungeon') / ('dungeon-%d.yaml' % room), 'yaml'),
    'editability': edit_status('yaml_backed', 'Room source is editable YAML compiled by print_dungeon_rooms.'),
    'header': dict(data.get('Header') or {}),
    'sprites': [normalize_dungeon_sprite(room, index, row)
                for index, row in enumerate(data.get('Sprites') or [])],
    'secrets': [normalize_xy_name(row) for row in data.get('Secrets') or []],
    'chests': list(data.get('Chests') or []),
    'entrances': list(data.get('Entrances') or []),
    'starting_points': list(data.get('StartingPoints') or []),
    'layers': build_layers(data),
    'compiled_offsets': offsets,
    'compiled_assets': asset_refs(asset_lookup, [
      'kDungeonRoom', 'kDungeonRoomOffs', 'kDungeonRoomDoorOffs',
      'kDungeonRoomHeaders', 'kDungeonRoomHeadersOffs',
      'kDungeonSprites', 'kDungeonSpriteOffs', 'kDungeonSecrets',
    ]),
  }


# Build per-room runtime offsets when the compiled assets are present.
# Parameters:
#   room: Room id.
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   Dict of runtime offsets and small tables.
def room_offsets(room, assets):
  return {
    'room_data_offset': asset_value(assets, 'kDungeonRoomOffs', room),
    'door_data_offset': asset_value(assets, 'kDungeonRoomDoorOffs', room),
    'header_offset': asset_value(assets, 'kDungeonRoomHeadersOffs', room),
    'sprite_offset': asset_value(assets, 'kDungeonSpriteOffs', room),
    'tele_msg': asset_value(assets, 'kDungeonRoomTeleMsg', room),
    'pits_hurt_player': bool(asset_value(assets, 'kDungeonPitsHurtPlayer', room)),
  }


# Safely read one flat runtime value.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   name: Runtime asset name.
#   index: Element index.
# Returns:
#   Integer value or None when unavailable.
def asset_value(assets, name, index):
  if name not in assets:
    return None
  values = values_for_asset(assets, name)
  return values[index] if index < len(values) else None


# Normalize one dungeon sprite placement.
# Parameters:
#   room: Room id.
#   index: Row index inside the room.
#   row: YAML sprite row.
# Returns:
#   JSON sprite placement record.
def normalize_dungeon_sprite(room, index, row):
  sprite_id = prefixed_hex_id(row[3]) if len(row) > 3 else None
  return {
    'room': room,
    'index': index,
    'x': row[0] if len(row) > 0 else None,
    'y': row[1] if len(row) > 1 else None,
    'floor': row[2] if len(row) > 2 else None,
    'type': sprite_id,
    'name': row[3] if len(row) > 3 else None,
    'canonical_name': sprite_name(sprite_id) if sprite_id is not None else None,
    'subcode': sprite_subcode(row[3]) if len(row) > 3 else None,
    'drop': row[4] if len(row) > 4 else None,
  }


# Parse optional sprite subcode syntax such as 4A.1-Name.
# Parameters:
#   name: YAML sprite name.
# Returns:
#   Integer subcode or None.
def sprite_subcode(name):
  match = re.match(r'^[0-9A-Fa-f]{2}\.(\d+)-', str(name))
  return int(match.group(1)) if match else None


# Normalize [x, y, name] rows used by room secrets.
# Parameters:
#   row: YAML row.
# Returns:
#   JSON row with decoded type id.
def normalize_xy_name(row):
  return {
    'x': row[0] if len(row) > 0 else None,
    'y': row[1] if len(row) > 1 else None,
    'type': prefixed_hex_id(row[2]) if len(row) > 2 else None,
    'name': row[2] if len(row) > 2 else None,
  }


# Build room layer records, including door sublayers.
# Parameters:
#   data: Parsed room YAML.
# Returns:
#   Dict keyed by layer id.
def build_layers(data):
  layers = {}
  for layer in ('Layer1', 'Layer2', 'Layer3'):
    objects = list(data.get(layer) or [])
    doors = list(data.get(layer + '.doors') or [])
    layers[layer] = {
      'object_count': len(objects),
      'door_count': len(doors),
      'objects': objects,
      'doors': doors,
    }
  return layers


# Build default or overlay room template records.
# Parameters:
#   format_name: JSON format tag.
#   source_path: YAML path relative to assets/.
#   key_prefix: Default or Overlay.
#   count: Template count.
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
#   asset_name: Runtime template stream asset.
#   offset_asset_name: Runtime template offset asset.
# Returns:
#   JSON template room payload.
def build_template_rooms(format_name, source_path, key_prefix, count, assets,
                         asset_lookup, asset_name, offset_asset_name):
  data = load_yaml(source_path)
  offsets = values_for_asset(assets, offset_asset_name) if offset_asset_name in assets else []
  templates = []
  for index in range(count):
    key = '%s%d' % (key_prefix, index)
    objects = list(data.get(key) or [])
    templates.append({
      'index': index,
      'source_key': key,
      'source_file': source_ref(source_path, 'yaml'),
      'object_count': len(objects),
      'objects': objects,
      'compiled_offset': offsets[index] if index < len(offsets) else None,
      'editability': edit_status('yaml_backed', 'Template source is editable YAML.'),
    })
  return {
    'format': format_name,
    'template_count': count,
    'templates': templates,
    'compiled_assets': asset_refs(asset_lookup, [asset_name, offset_asset_name]),
  }
