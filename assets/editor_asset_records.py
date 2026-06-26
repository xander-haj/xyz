# editor_asset_records.py -- Group runtime asset arrays into editor records.
#
# The compiled asset file stores many tables as separate parallel arrays because
# that is efficient for the C runtime. This module joins those arrays back into
# record-shaped JSON objects that are easier for editor code to consume.

# Standard library import for decoding signed and little-endian runtime arrays.
import struct

# Project-local lookup tables provide friendly names for music and palace IDs.
import tables


# Group entrance and starting-point structure-of-arrays into records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   Dict with entrance and starting-point record lists.
def build_entrances(assets):
  return {
    'entrances': build_entrance_records(assets, 'kEntranceData_', 133, False),
    'starting_points': build_entrance_records(assets, 'kStartingPoint_', 7, True),
  }


# Build one grouped entrance-like record list from parallel runtime arrays.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   prefix: kEntranceData_ or kStartingPoint_.
#   count: Number of records to build.
#   include_starting_point_link: Whether to include associated entrance index.
# Returns:
#   List of grouped entrance records.
def build_entrance_records(assets, prefix, count, include_starting_point_link):
  rooms = values_for_asset(assets, prefix + 'rooms')
  relative = values_for_asset(assets, prefix + 'relativeCoords')
  records = []
  for index in range(count):
    starting_bg = value_at(assets, prefix + 'startingBg', index)
    record = {
      'index': index,
      'room': rooms[index],
      'relative_coords': relative[index * 8:index * 8 + 8],
      'scroll_xy': [value_at(assets, prefix + 'scrollX', index),
                    value_at(assets, prefix + 'scrollY', index)],
      'player_xy': [value_at(assets, prefix + 'playerX', index),
                    value_at(assets, prefix + 'playerY', index)],
      'camera_xy': [value_at(assets, prefix + 'cameraX', index),
                    value_at(assets, prefix + 'cameraY', index)],
      'blockset': value_at(assets, prefix + 'blockset', index),
      'floor': value_at(assets, prefix + 'floor', index),
      'palace': palace_record(value_at(assets, prefix + 'palace', index)),
      'doorway_orientation': value_at(assets, prefix + 'doorwayOrientation', index),
      'starting_bg': starting_bg_record(starting_bg),
      'quadrants': quadrant_record(value_at(assets, prefix + 'quadrant1', index),
                                   value_at(assets, prefix + 'quadrant2', index)),
      'door': entrance_door_record(value_at(assets, prefix + 'doorSettings', index)),
      'music': music_record(value_at(assets, prefix + 'musicTrack', index)),
    }
    if include_starting_point_link:
      record['associated_entrance_index'] = value_at(assets, prefix + 'entrance', index)
    records.append(record)
  return records


# Decode the packed starting-BG byte used by entrance records.
# Parameters:
#   value: Raw startingBg byte.
# Returns:
#   Dict with raw byte, plane, and ladder level.
def starting_bg_record(value):
  return {'raw': value, 'plane': value & 0xf, 'ladder_level': value >> 4}


# Convert encoded palace data back into a raw/name pair.
# Parameters:
#   value: Encoded palace byte from kEntranceData_palace or kStartingPoint_palace.
# Returns:
#   Dict with raw value and best known name.
def palace_record(value):
  if value == -1:
    return {'raw': value, 'name': tables.kPalaceNames[0]}
  palace_index = value // 2 + 1
  name = tables.kPalaceNames[palace_index] if palace_index < len(tables.kPalaceNames) else None
  return {'raw': value, 'name': name}


# Convert music track ID to a friendly name where available.
# Parameters:
#   value: Music track byte.
# Returns:
#   Dict with raw value and name.
def music_record(value):
  return {'raw': value, 'name': tables.kMusicNames.get(value)}


# Decode entrance quadrant fields into named scroll layout values.
# Parameters:
#   quadrant1: Encoded scroll width/height byte.
#   quadrant2: Encoded starting quadrant byte.
# Returns:
#   Dict containing raw and decoded quadrant information.
def quadrant_record(quadrant1, quadrant2):
  quadrant_names = {0: 'upper_left', 2: 'lower_left', 16: 'upper_right', 18: 'lower_right'}
  return {
    'raw': [quadrant1, quadrant2],
    'x': 'double_x' if quadrant1 & 0x20 else 'single_x',
    'y': 'double_y' if quadrant1 & 0x02 else 'single_y',
    'start': quadrant_names.get(quadrant2),
  }


# Decode a house-exit door setting used by entrance data.
# Parameters:
#   value: Encoded uint16 door setting.
# Returns:
#   Door record with type and tile coordinates when present.
def entrance_door_record(value):
  if value == 0:
    return {'raw': value, 'type': 'none'}
  if value == 0xffff:
    return {'raw': value, 'type': 'none_0xffff'}
  return {
    'raw': value,
    'type': 'bombable' if value & 0x8000 else 'wooden',
    'x': (value & 0x7e) >> 1,
    'y': (value & 0x3f80) >> 7,
  }


# Group overworld navigation and transition tables into editor records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   Dict of overworld navigation record lists.
def build_overworld_navigation(assets):
  return {
    'travel': build_travel_records(assets),
    'entrances': build_overworld_entrance_records(assets),
    'fall_holes': build_fall_hole_records(assets),
    'exits': build_exit_records(assets),
    'special_exits': build_special_exit_records(assets),
  }


# Build bird and whirlpool travel records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of travel records.
def build_travel_records(assets):
  records = []
  for index in range(17):
    record = {
      'index': index,
      'kind': 'bird' if index < 9 else 'whirlpool',
      'screen_index': value_at(assets, 'kBirdTravel_ScreenIndex', index),
      'map16_load_src_off': value_at(assets, 'kBirdTravel_Map16LoadSrcOff', index),
      'scroll_xy': [value_at(assets, 'kBirdTravel_ScrollX', index),
                    value_at(assets, 'kBirdTravel_ScrollY', index)],
      'link_xy': [value_at(assets, 'kBirdTravel_LinkXCoord', index),
                  value_at(assets, 'kBirdTravel_LinkYCoord', index)],
      'camera_xy': [value_at(assets, 'kBirdTravel_CameraXScroll', index),
                    value_at(assets, 'kBirdTravel_CameraYScroll', index)],
      'unknown': [value_at(assets, 'kBirdTravel_Unk1', index),
                  value_at(assets, 'kBirdTravel_Unk3', index)],
    }
    if index >= 9:
      record['whirlpool_source_area'] = value_at(assets, 'kWhirlpoolAreas', index - 9)
    records.append(record)
  return records


# Build overworld-to-interior entrance records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of overworld entrance records.
def build_overworld_entrance_records(assets):
  records = []
  for index in range(129):
    pos = value_at(assets, 'kOverworld_Entrance_Pos', index)
    records.append({
      'index': index,
      'area': value_at(assets, 'kOverworld_Entrance_Area', index),
      'pos': tile_pos_record(pos),
      'entrance_id': value_at(assets, 'kOverworld_Entrance_Id', index),
      'deleted': pos == 0xffff,
    })
  return records


# Build overworld fall-hole records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of fall-hole records.
def build_fall_hole_records(assets):
  records = []
  for index in range(19):
    pos = value_at(assets, 'kFallHole_Pos', index)
    decoded = tile_pos_record(pos)
    if decoded['x'] is not None:
      decoded['y'] += 8
    records.append({
      'index': index,
      'area': value_at(assets, 'kFallHole_Area', index),
      'pos': decoded,
      'entrance_id': value_at(assets, 'kFallHole_Entrances', index),
      'deleted': pos == 0xfbff,
    })
  return records


# Build dungeon-to-overworld exit records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of exit records.
def build_exit_records(assets):
  records = []
  for index in range(79):
    records.append({
      'index': index,
      'screen_index': value_at(assets, 'kExitData_ScreenIndex', index),
      'room': value_at(assets, 'kExitDataRooms', index),
      'map16_load_src_off': value_at(assets, 'kExitData_Map16LoadSrcOff', index),
      'scroll_xy': [value_at(assets, 'kExitData_ScrollX', index),
                    value_at(assets, 'kExitData_ScrollY', index)],
      'player_xy': [value_at(assets, 'kExitData_XCoord', index),
                    value_at(assets, 'kExitData_YCoord', index)],
      'camera_xy': [value_at(assets, 'kExitData_CameraXScroll', index),
                    value_at(assets, 'kExitData_CameraYScroll', index)],
      'normal_door': exit_door_record(value_at(assets, 'kExitData_NormalDoor', index), False),
      'fancy_door': exit_door_record(value_at(assets, 'kExitData_FancyDoor', index), True),
      'unknown': [value_at(assets, 'kExitData_Unk1', index),
                  value_at(assets, 'kExitData_Unk3', index)],
    })
  return records


# Build special exit override records for rooms 0x180..0x18f.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
# Returns:
#   List of special exit records.
def build_special_exit_records(assets):
  records = []
  for index in range(16):
    records.append({
      'slot': index,
      'room': 0x180 + index,
      'bounds': special_exit_bounds(assets, index),
      'gfx': special_exit_gfx(assets, index),
      'dir': value_at(assets, 'kSpExit_Dir', index),
      'unknown': [value_at(assets, 'kSpExit_Tab4', index),
                  value_at(assets, 'kSpExit_Tab5', index),
                  value_at(assets, 'kSpExit_Tab6', index),
                  value_at(assets, 'kSpExit_Tab7', index)],
    })
  return records


# Build the boundary section of one special exit record.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   index: Special exit slot.
# Returns:
#   Dict of scroll boundary fields.
def special_exit_bounds(assets, index):
  return {
    'top': value_at(assets, 'kSpExit_Top', index),
    'bottom': value_at(assets, 'kSpExit_Bottom', index),
    'left': value_at(assets, 'kSpExit_Left', index),
    'right': value_at(assets, 'kSpExit_Right', index),
    'left_edge_of_map': value_at(assets, 'kSpExit_LeftEdgeOfMap', index),
  }


# Build the graphics section of one special exit record.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   index: Special exit slot.
# Returns:
#   Dict of graphics and palette override fields.
def special_exit_gfx(assets, index):
  return {
    'sprite': value_at(assets, 'kSpExit_SprGfx', index),
    'aux': value_at(assets, 'kSpExit_AuxGfx', index),
    'pal_bg': value_at(assets, 'kSpExit_PalBg', index),
    'pal_spr': value_at(assets, 'kSpExit_PalSpr', index),
  }


# Decode an overworld tile-position word into x/y fields.
# Parameters:
#   value: Packed tile position or deletion sentinel.
# Returns:
#   Dict with raw value and decoded coordinates where possible.
def tile_pos_record(value):
  if value in (0xffff, 0xfbff):
    return {'raw': value, 'x': None, 'y': None}
  return {'raw': value, 'x': (value >> 1) & 0x3f, 'y': (value >> 7) & 0x3f}


# Decode an overworld exit door word.
# Parameters:
#   value: Encoded door word.
#   fancy: True for palace/sanctuary door table, false for wooden/bombable table.
# Returns:
#   Door record with type and tile coordinates when present.
def exit_door_record(value, fancy):
  if value == 0:
    return {'raw': value, 'type': 'none'}
  if fancy:
    door_type = 'palace' if value & 0x8000 else 'sanctuary'
  else:
    door_type = 'bombable' if value & 0x8000 else 'wooden'
  return {'raw': value, 'type': door_type, 'x': (value & 0x7e) >> 1, 'y': (value & 0x3f80) >> 7}


# Build dungeon room offset metadata for interior/dungeon editor loading.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Name-keyed dat dump manifest lookup.
# Returns:
#   Dict describing room stream and offset tables.
def build_dungeon_rooms(assets, asset_lookup):
  room_offsets = values_for_asset(assets, 'kDungeonRoomOffs')
  door_offsets = values_for_asset(assets, 'kDungeonRoomDoorOffs')
  header_offsets = values_for_asset(assets, 'kDungeonRoomHeadersOffs')
  rooms = []
  for room in range(len(room_offsets)):
    rooms.append({
      'room': room,
      'room_data_offset': room_offsets[room],
      'door_data_offset': door_offsets[room],
      'header_offset': header_offsets[room],
    })
  return {
    'room_stream': asset_file_record(asset_lookup, 'kDungeonRoom'),
    'door_offset_table': asset_file_record(asset_lookup, 'kDungeonRoomDoorOffs'),
    'header_stream': asset_file_record(asset_lookup, 'kDungeonRoomHeaders'),
    'rooms': rooms,
  }


# Create a compact file-reference record for one dat dump asset.
# Parameters:
#   asset_lookup: Name-keyed dat dump manifest lookup.
#   name: Runtime asset name.
# Returns:
#   Dict with index, name, and data file.
def asset_file_record(asset_lookup, name):
  record = asset_lookup[name]
  return {'index': record['index'], 'name': name, 'data_file': record.get('data_file')}


# Decode a flat typed runtime asset into Python values.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   name: Runtime asset name.
# Returns:
#   List of integer values.
def values_for_asset(assets, name):
  asset_type, data = assets[name]
  if asset_type == 'uint8':
    return list(data)
  if asset_type == 'int8':
    return list(struct.unpack('%db' % len(data), data))
  if asset_type == 'uint16':
    return list(struct.unpack('<%dH' % (len(data) // 2), data))
  if asset_type == 'int16':
    return list(struct.unpack('<%dh' % (len(data) // 2), data))
  raise ValueError('Cannot decode non-flat asset %s of type %s.' % (name, asset_type))


# Read one value from a flat typed runtime asset.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   name: Runtime asset name.
#   index: Element index.
# Returns:
#   Integer element value.
def value_at(assets, name, index):
  return values_for_asset(assets, name)[index]
