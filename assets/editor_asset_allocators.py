# editor_asset_allocators.py -- Slot allocator views for editor planning.
#
# Many Zelda 3 systems are fixed-slot tables. These records make slot ownership
# explicit so an editor can allocate safely inside current bounds and can also
# tell the user when a request needs compiler/runtime expansion first.

# Project-local source helpers and friendly names.
from editor_asset_common import (
  DUNGEON_ROOM_COUNT,
  OVERWORLD_AREA_COUNT,
  area_name,
  edit_status,
  entrance_name,
)


# Build every allocator payload required by the editor database.
# Parameters:
#   overworld_data: Payloads returned by editor_asset_overworld.
#   room_data: Payloads returned by editor_asset_rooms.
#   navigation_data: Payloads returned by editor_asset_navigation.
# Returns:
#   Dict keyed by allocator output id.
def build_allocator_data(overworld_data, room_data, navigation_data):
  rooms = room_data['rooms']['rooms']
  areas = overworld_data['areas']['areas']
  runtime_nav = navigation_data['runtime_navigation']
  entrance_tables = navigation_data['runtime_entrances']
  return {
    'rooms': range_allocator('zelda3_editor_room_allocator', DUNGEON_ROOM_COUNT, used_room_slots(rooms),
                             room_owner, 'requires_engine_work'),
    'entrances': range_allocator('zelda3_editor_entrance_allocator', 133, used_entrance_slots(rooms),
                                 entrance_owner, 'requires_engine_work'),
    'starting_points': range_allocator('zelda3_editor_starting_point_allocator', 7,
                                       used_starting_point_slots(rooms),
                                       starting_point_owner, 'requires_engine_work'),
    'overworld_entrances': range_allocator('zelda3_editor_overworld_entrance_allocator', 129,
                                           used_nav_slots(runtime_nav['entrances']),
                                           overworld_entrance_owner, 'requires_engine_work'),
    'fall_holes': range_allocator('zelda3_editor_fall_hole_allocator', 19,
                                  used_nav_slots(runtime_nav['fall_holes']),
                                  fall_hole_owner, 'requires_engine_work'),
    'exits': range_allocator('zelda3_editor_exit_allocator', 79,
                             {row['index']: row for row in runtime_nav['exits']},
                             exit_owner, 'requires_engine_work'),
    'special_exits': range_allocator('zelda3_editor_special_exit_allocator', 16,
                                     {row['slot']: row for row in runtime_nav['special_exits']},
                                     special_exit_owner, 'requires_engine_work'),
    'overworld_areas': range_allocator('zelda3_editor_overworld_area_allocator',
                                       OVERWORLD_AREA_COUNT,
                                       {area['area']: area for area in areas},
                                       overworld_area_owner, 'requires_engine_work'),
    'runtime_entrance_tables': entrance_tables,
  }


# Build one fixed-range allocator.
# Parameters:
#   format_name: JSON format tag.
#   capacity: Number of fixed slots.
#   used: Dict keyed by slot id with owner source records.
#   owner_builder: Function that converts a used record to owner JSON.
#   expansion_status: Status for allocations beyond capacity.
# Returns:
#   JSON allocator payload.
def range_allocator(format_name, capacity, used, owner_builder, expansion_status):
  slots = []
  for slot in range(capacity):
    owner = used.get(slot)
    slots.append({
      'slot': slot,
      'status': 'used' if owner is not None else 'free',
      'owner': owner_builder(slot, owner) if owner is not None else None,
    })
  return {
    'format': format_name,
    'capacity': capacity,
    'used_count': sum(1 for slot in slots if slot['status'] == 'used'),
    'free_count': sum(1 for slot in slots if slot['status'] == 'free'),
    'slots': slots,
    'editability': edit_status('compiler_backed', 'Existing slots are compiler-backed fixed tables.'),
    'beyond_capacity': edit_status(expansion_status, 'Adding slots beyond this capacity needs compiler/runtime work.'),
  }


# Build used room slot records.
# Parameters:
#   rooms: Full room records.
# Returns:
#   Dict keyed by room id.
def used_room_slots(rooms):
  return {room['room']: room for room in rooms}


# Build used entrance slot records from room YAML.
# Parameters:
#   rooms: Full room records.
# Returns:
#   Dict keyed by entrance slot.
def used_entrance_slots(rooms):
  used = {}
  for room in rooms:
    for entrance in room.get('entrances') or []:
      slot = entrance.get('entrance_index')
      if slot is not None:
        used[slot] = {'room': room['room'], 'entrance': entrance}
  return used


# Build used starting point slot records from room YAML.
# Parameters:
#   rooms: Full room records.
# Returns:
#   Dict keyed by starting point slot.
def used_starting_point_slots(rooms):
  used = {}
  for room in rooms:
    for point in room.get('starting_points') or []:
      slot = point.get('starting_point_index')
      if slot is not None:
        used[slot] = {'room': room['room'], 'starting_point': point}
  return used


# Build used slot records from navigation rows that have deletion sentinels.
# Parameters:
#   rows: Runtime navigation rows.
# Returns:
#   Dict keyed by slot index.
def used_nav_slots(rows):
  return {
    row['index']: row
    for row in rows
    if not row.get('deleted')
  }


# Build a room slot owner record.
# Parameters:
#   slot: Slot id.
#   owner: Room record.
# Returns:
#   JSON owner record.
def room_owner(slot, owner):
  return {'room': slot, 'source_file': owner['source_file']}


# Build an entrance slot owner record.
# Parameters:
#   slot: Slot id.
#   owner: Entrance owner record.
# Returns:
#   JSON owner record.
def entrance_owner(slot, owner):
  return {
    'entrance_id': slot,
    'entrance_name': entrance_name(slot),
    'room': owner['room'],
    'source': owner['entrance'],
  }


# Build a starting point owner record.
# Parameters:
#   slot: Slot id.
#   owner: Starting point owner record.
# Returns:
#   JSON owner record.
def starting_point_owner(slot, owner):
  return {'starting_point': slot, 'room': owner['room'], 'source': owner['starting_point']}


# Build an overworld entrance owner record.
# Parameters:
#   slot: Slot id.
#   owner: Runtime overworld entrance record.
# Returns:
#   JSON owner record.
def overworld_entrance_owner(slot, owner):
  return {
    'slot': slot,
    'area': owner['area'],
    'area_name': area_name(owner['area']),
    'entrance_id': owner['entrance_id'],
    'position': owner['pos'],
  }


# Build a fall-hole owner record.
# Parameters:
#   slot: Slot id.
#   owner: Runtime fall-hole record.
# Returns:
#   JSON owner record.
def fall_hole_owner(slot, owner):
  return {
    'slot': slot,
    'area': owner['area'],
    'area_name': area_name(owner['area']),
    'entrance_id': owner['entrance_id'],
    'position': owner['pos'],
  }


# Build an exit owner record.
# Parameters:
#   slot: Slot id.
#   owner: Runtime exit record.
# Returns:
#   JSON owner record.
def exit_owner(slot, owner):
  return {
    'slot': slot,
    'room': owner['room'],
    'area': owner['screen_index'],
    'area_name': area_name(owner['screen_index']),
  }


# Build a special-exit owner record.
# Parameters:
#   slot: Slot id.
#   owner: Runtime special-exit record.
# Returns:
#   JSON owner record.
def special_exit_owner(slot, owner):
  return {'slot': slot, 'room': owner['room'], 'dir': owner['dir']}


# Build an overworld area owner record.
# Parameters:
#   slot: Area id.
#   owner: Area record.
# Returns:
#   JSON owner record.
def overworld_area_owner(slot, owner):
  return {
    'area': slot,
    'name': owner['name'],
    'world': owner['world'],
    'source_file': owner['source_file'],
    'topology_parent': owner['topology_parent'],
  }
