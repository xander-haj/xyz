# editor_asset_validation.py -- Self-checks for the editor asset database.
#
# These checks do not replace compiler validation. They give the editor a quick
# machine-readable summary of missing optional sources and cross-reference issues
# after an editor asset dump is produced.


# Build validation payload for the generated editor data.
# Parameters:
#   overworld_data: Payloads returned by editor_asset_overworld.
#   room_data: Payloads returned by editor_asset_rooms.
#   navigation_data: Payloads returned by editor_asset_navigation.
#   tile_data: Payloads returned by editor_asset_tiles.
#   sprite_data: Payloads returned by editor_asset_sprites.
#   dialogue_data: Payloads returned by editor_asset_dialogue.
# Returns:
#   JSON validation payload.
def build_validation_data(overworld_data, room_data, navigation_data,
                          tile_data, sprite_data, dialogue_data):
  issues = []
  issues.extend(validate_map32_sources(overworld_data))
  issues.extend(validate_navigation(navigation_data))
  issues.extend(validate_dialogue(dialogue_data))
  issues.extend(validate_sprites(sprite_data))
  issues.extend(validate_tiles(tile_data))
  return {
    'format': 'zelda3_editor_validation',
    'issue_count': len(issues),
    'issues': issues,
    'summary': summarize_issues(issues),
  }


# Validate presence of editable map32 source grids.
# Parameters:
#   overworld_data: Payloads returned by editor_asset_overworld.
# Returns:
#   List of validation issues.
def validate_map32_sources(overworld_data):
  missing = [
    area['area']
    for area in overworld_data['areas']['areas']
    if area['map32_source_status']['status'] != 'present'
  ]
  if not missing:
    return []
  return [{
    'severity': 'warning',
    'code': 'missing_map32_sources',
    'message': 'Some areas do not have editable overworld_maps JSON sources.',
    'areas': missing,
  }]


# Validate graph links that should point at existing room ids.
# Parameters:
#   navigation_data: Payloads returned by editor_asset_navigation.
# Returns:
#   List of validation issues.
def validate_navigation(navigation_data):
  issues = []
  bad_entrances = [
    edge for edge in navigation_data['entrance_graph']['edges']
    if edge['to_room'] is not None and not edge['to_room_exists']
  ]
  if bad_entrances:
    issues.append({
      'severity': 'error',
      'code': 'entrance_points_to_missing_room',
      'message': 'One or more entrance graph edges point to rooms outside the room table.',
      'edges': bad_entrances,
    })
  bad_exits = [
    edge for edge in navigation_data['exit_graph']['edges']
    if exit_edge_missing_normal_room(edge)
  ]
  if bad_exits:
    issues.append({
      'severity': 'error',
      'code': 'exit_from_missing_room',
      'message': 'One or more exit graph edges start from rooms outside the room table.',
      'edges': bad_exits,
    })
  return issues


# Return true only for exit edges that should name an existing normal room.
# Parameters:
#   edge: Exit graph edge from editor_asset_navigation.
# Returns:
#   Boolean indicating a real missing-room validation error.
def exit_edge_missing_normal_room(edge):
  room = edge.get('from_room')
  if room is None:
    return False
  kind = edge.get('from_room_reference_kind') or classify_exit_room_reference(room)
  return kind == 'normal_room' and not edge.get('from_room_exists')


# Classify older exit graph edges that do not yet carry reference metadata.
# Parameters:
#   room: Raw kExitDataRooms value.
# Returns:
#   Reference-kind string matching editor_asset_navigation.
def classify_exit_room_reference(room):
  if room == 0xffff:
    return 'sentinel_no_room'
  if 0x180 <= room <= 0x18f:
    return 'special_exit_room'
  if room >= 0x1000:
    return 'engine_extended_exit'
  return 'normal_room'


# Validate dialogue references against dialogue.txt ids.
# Parameters:
#   dialogue_data: Payloads returned by editor_asset_dialogue.
# Returns:
#   List of validation issues.
def validate_dialogue(dialogue_data):
  known_ids = {record['id'] for record in dialogue_data['dialogue_strings']['strings']}
  missing = []
  for usage in dialogue_data['usage_index']['usage']:
    if usage['dialogue_id'] == -1:
      continue
    if usage['users'] and usage['dialogue_id'] not in known_ids:
      missing.append(usage)
  if not missing:
    return []
  return [{
    'severity': 'error',
    'code': 'dialogue_reference_missing',
    'message': 'A sign or room message references a dialogue id missing from dialogue.txt.',
    'references': missing,
  }]


# Validate sprite placement ids.
# Parameters:
#   sprite_data: Payloads returned by editor_asset_sprites.
# Returns:
#   List of validation issues.
def validate_sprites(sprite_data):
  undecoded = [
    placement for placement in sprite_data['placement_index']['all']
    if placement.get('type') is None
  ]
  if not undecoded:
    return []
  return [{
    'severity': 'error',
    'code': 'sprite_type_not_decoded',
    'message': 'A sprite placement did not decode to a numeric sprite id.',
    'placements': undecoded,
  }]


# Validate tile source coverage.
# Parameters:
#   tile_data: Payloads returned by editor_asset_tiles.
# Returns:
#   List of validation issues.
def validate_tiles(tile_data):
  issues = []
  if not tile_data['map32_tiles']['tiles']:
    issues.append({
      'severity': 'error',
      'code': 'missing_map32_to_map16',
      'message': 'No map32-to-map16 records were exported.',
    })
  if not tile_data['map16_tiles']['tiles']:
    issues.append({
      'severity': 'error',
      'code': 'missing_map16_to_map8',
      'message': 'No map16-to-map8 records were exported.',
    })
  if not tile_data['chr_tiles']['tiles']:
    issues.append({
      'severity': 'warning',
      'code': 'no_raw_chr_tiles_decoded',
      'message': 'No raw 4bpp CHR tiles were decoded for pixel-level editor previews.',
    })
  return issues


# Summarize issue counts by severity.
# Parameters:
#   issues: Validation issue records.
# Returns:
#   Dict keyed by severity.
def summarize_issues(issues):
  summary = {}
  for issue in issues:
    severity = issue.get('severity', 'info')
    summary[severity] = summary.get(severity, 0) + 1
  return summary
