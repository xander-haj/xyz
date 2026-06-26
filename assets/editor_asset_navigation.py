# editor_asset_navigation.py -- Editor navigation graphs over runtime transitions.
#
# Runtime navigation is stored as several structure-of-arrays tables. This module
# builds graph-shaped records so the editor can trace area, room, entrance, exit,
# fall-hole, and travel relationships without hardcoding every table.

# Project-local grouped runtime records and lookup helpers.
from editor_asset_common import asset_refs, area_name, entrance_name
from editor_asset_records import build_entrances, build_overworld_navigation


# Build every navigation graph payload.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   overworld_data: Payloads returned by editor_asset_overworld.
#   room_data: Payloads returned by editor_asset_rooms.
# Returns:
#   Dict of navigation graph payloads.
def build_navigation_data(assets, asset_lookup, overworld_data, room_data):
  entrance_tables = build_entrances(assets)
  overworld_nav = build_overworld_navigation(assets)
  areas = overworld_data['areas']['areas']
  rooms = room_data['rooms']['rooms']
  return {
    'world_graph': build_world_graph(areas, overworld_nav, asset_lookup),
    'entrance_graph': build_entrance_graph(entrance_tables, overworld_nav, rooms, asset_lookup),
    'exit_graph': build_exit_graph(overworld_nav, rooms, asset_lookup),
    'travel_graph': build_travel_graph(overworld_nav, asset_lookup),
    'runtime_navigation': overworld_nav,
    'runtime_entrances': entrance_tables,
  }


# Build an area graph with grid edges and transition summaries.
# Parameters:
#   areas: Full area records.
#   overworld_nav: Grouped overworld navigation tables.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON world graph.
def build_world_graph(areas, overworld_nav, asset_lookup):
  nodes = [
    {
      'id': area['area'],
      'name': area['name'],
      'world': area['world'],
      'topology_parent': area['topology_parent'],
      'is_topology_head': area['is_topology_head'],
    }
    for area in areas
  ]
  return {
    'format': 'zelda3_editor_world_graph',
    'nodes': nodes,
    'edges': build_grid_edges(areas),
    'transition_counts': {
      'overworld_entrances': len(overworld_nav['entrances']),
      'fall_holes': len(overworld_nav['fall_holes']),
      'exits': len(overworld_nav['exits']),
      'special_exits': len(overworld_nav['special_exits']),
      'travel': len(overworld_nav['travel']),
    },
    'compiled_assets': asset_refs(asset_lookup, [
      'kOverworld_Entrance_Area', 'kFallHole_Area', 'kExitData_ScreenIndex',
      'kBirdTravel_ScreenIndex', 'kWhirlpoolAreas',
    ]),
  }


# Build fixed grid-neighbor edges for normal overworld areas.
# Parameters:
#   areas: Full area records.
# Returns:
#   List of graph edge records.
def build_grid_edges(areas):
  area_by_id = {area['area']: area for area in areas}
  edges = []
  for area in areas:
    grid = area['grid']
    if grid is None:
      continue
    for direction, dx, dy in (
        ('west', -1, 0), ('east', 1, 0), ('north', 0, -1), ('south', 0, 1)):
      nx = grid['x'] + dx
      ny = grid['y'] + dy
      if nx < 0 or nx >= 8 or ny < 0 or ny >= 8:
        continue
      neighbor = (0 if area['world'] == 'light_world' else 64) + ny * 8 + nx
      if neighbor in area_by_id:
        edges.append({'from_area': area['area'], 'to_area': neighbor, 'kind': 'grid', 'direction': direction})
  return edges


# Build overworld-to-room entrance and fall-hole graph edges.
# Parameters:
#   entrance_tables: Grouped entrance/starting-point runtime records.
#   overworld_nav: Grouped overworld navigation tables.
#   rooms: Full room records.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON entrance graph.
def build_entrance_graph(entrance_tables, overworld_nav, rooms, asset_lookup):
  entrances = {row['index']: row for row in entrance_tables['entrances']}
  room_set = {room['room'] for room in rooms}
  edges = []
  for source_kind, rows in (
      ('overworld_entrance', overworld_nav['entrances']),
      ('fall_hole', overworld_nav['fall_holes'])):
    for row in rows:
      if row.get('deleted'):
        continue
      entrance = entrances.get(row['entrance_id'])
      edges.append({
        'kind': source_kind,
        'slot': row['index'],
        'from_area': row['area'],
        'from_area_name': area_name(row['area']),
        'entrance_id': row['entrance_id'],
        'entrance_name': entrance_name(row['entrance_id']),
        'to_room': entrance['room'] if entrance else None,
        'to_room_exists': entrance is not None and entrance['room'] in room_set,
        'position': row['pos'],
      })
  return {
    'format': 'zelda3_editor_entrance_graph',
    'edges': edges,
    'entrances': entrance_tables['entrances'],
    'starting_points': entrance_tables['starting_points'],
    'compiled_assets': asset_refs(asset_lookup, [
      'kEntranceData_rooms', 'kStartingPoint_rooms',
      'kOverworld_Entrance_Area', 'kOverworld_Entrance_Id',
      'kFallHole_Area', 'kFallHole_Entrances',
    ]),
  }


# Build room-to-overworld exit graph edges.
# Parameters:
#   overworld_nav: Grouped overworld navigation tables.
#   rooms: Full room records.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON exit graph.
def build_exit_graph(overworld_nav, rooms, asset_lookup):
  room_set = {room['room'] for room in rooms}
  edges = []
  for row in overworld_nav['exits']:
    room_kind = exit_room_reference_kind(row['room'])
    room_exists = row['room'] in room_set
    edges.append({
      'kind': 'exit',
      'slot': row['index'],
      'from_room': row['room'],
      'from_room_exists': room_exists,
      'from_room_reference_kind': room_kind,
      'from_room_validation_status': exit_room_validation_status(room_kind, room_exists),
      'to_area': row['screen_index'],
      'to_area_name': area_name(row['screen_index']),
      'player_xy': row['player_xy'],
      'scroll_xy': row['scroll_xy'],
      'camera_xy': row['camera_xy'],
      'normal_door': row['normal_door'],
      'fancy_door': row['fancy_door'],
    })
  return {
    'format': 'zelda3_editor_exit_graph',
    'edges': edges,
    'special_exits': overworld_nav['special_exits'],
    'compiled_assets': asset_refs(asset_lookup, [
      'kExitDataRooms', 'kExitData_ScreenIndex', 'kExitData_XCoord',
      'kExitData_YCoord', 'kSpExit_Top', 'kSpExit_Dir',
    ]),
  }


# Classify exit room values before validation treats them as dungeon room ids.
# Parameters:
#   room: Raw room value from kExitDataRooms.
# Returns:
#   Reference-kind string used by validation and editor labels.
def exit_room_reference_kind(room):
  if room is None:
    return 'none'
  if room == 0xffff:
    return 'sentinel_no_room'
  if 0x180 <= room <= 0x18f:
    return 'special_exit_room'
  if room >= 0x1000:
    return 'engine_extended_exit'
  return 'normal_room'


# Return whether an exit room reference is valid, missing, or intentionally non-room.
# Parameters:
#   room_kind: Classification returned by exit_room_reference_kind.
#   room_exists: Whether the room id exists in the normal room table.
# Returns:
#   Validation status string for the graph edge.
def exit_room_validation_status(room_kind, room_exists):
  if room_kind != 'normal_room':
    return 'non_room_reference'
  return 'ok' if room_exists else 'missing_room'


# Build bird and whirlpool travel graph records.
# Parameters:
#   overworld_nav: Grouped overworld navigation tables.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON travel graph.
def build_travel_graph(overworld_nav, asset_lookup):
  edges = []
  for row in overworld_nav['travel']:
    edge = {
      'kind': row['kind'],
      'slot': row['index'],
      'to_area': row['screen_index'],
      'to_area_name': area_name(row['screen_index']),
      'link_xy': row['link_xy'],
      'scroll_xy': row['scroll_xy'],
      'camera_xy': row['camera_xy'],
      'map16_load_src_off': row['map16_load_src_off'],
    }
    if row['kind'] == 'whirlpool':
      source_area = row.get('whirlpool_source_area')
      edge['from_area'] = source_area
      edge['from_area_name'] = area_name(source_area) if source_area is not None else None
    edges.append(edge)
  return {
    'format': 'zelda3_editor_travel_graph',
    'edges': edges,
    'compiled_assets': asset_refs(asset_lookup, [
      'kBirdTravel_ScreenIndex', 'kBirdTravel_LinkXCoord',
      'kBirdTravel_LinkYCoord', 'kWhirlpoolAreas',
    ]),
  }
