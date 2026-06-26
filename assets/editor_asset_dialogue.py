# editor_asset_dialogue.py -- Dialogue strings and binding indexes for editors.
#
# Text itself is source-backed by dialogue.txt. Sign text and room telepathy
# messages have explicit YAML fields. NPC dialogue uses source-backed handler
# rules exported by editor_asset_npc_dialogue.

# Project-local helpers.
from editor_asset_common import asset_refs, edit_status, source_ref
from editor_asset_npc_dialogue import build_npc_dialogue_bindings


# Build every dialogue-facing editor output.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   overworld_data: Payloads returned by editor_asset_overworld.
#   room_data: Payloads returned by editor_asset_rooms.
#   sprite_data: Payloads returned by editor_asset_sprites.
# Returns:
#   Dict of dialogue output payloads.
def build_dialogue_data(asset_lookup, overworld_data, room_data, sprite_data):
  strings = parse_dialogue_strings('dialogue.txt')
  sign_bindings = build_sign_bindings(overworld_data)
  room_bindings = build_room_message_bindings(room_data)
  npc_bindings = build_npc_dialogue_bindings(sprite_data)
  return {
    'dialogue_strings': {
      'format': 'zelda3_editor_dialogue_strings',
      'source_file': source_ref('dialogue.txt', 'text'),
      'strings': strings,
      'compiled_assets': asset_refs(asset_lookup, ['kDialogue', 'kDialogueFont', 'kDialogueMap']),
      'editability': edit_status(
        'compiler_backed',
        'Text is source-backed by dialogue.txt and compiled by print_dialogue.'),
    },
    'sign_bindings': sign_bindings,
    'room_message_bindings': room_bindings,
    'npc_dialogue_bindings': npc_bindings,
    'usage_index': build_usage_index(strings, sign_bindings, room_bindings, npc_bindings),
  }


# Parse the base dialogue text file.
# Parameters:
#   path: Dialogue source path relative to assets/.
# Returns:
#   List of dialogue string records.
def parse_dialogue_strings(path):
  records = []
  with open(path, 'r', encoding='utf8') as file:
    for line in file.read().splitlines():
      if ':' not in line:
        continue
      raw_id, text = line.split(':', 1)
      records.append({
        'id': int(raw_id),
        'text': text[1:] if text.startswith(' ') else text,
      })
  return records


# Build overworld sign text bindings from Header.sign_text.
# Parameters:
#   overworld_data: Payloads returned by editor_asset_overworld.
# Returns:
#   JSON sign binding payload.
def build_sign_bindings(overworld_data):
  bindings = []
  for area in overworld_data['areas']['areas']:
    sign_text = area['header'].get('sign_text')
    if sign_text is None:
      continue
    bindings.append({
      'area': area['area'],
      'source_area': area['source_area'],
      'dialogue_id': sign_text,
      'binding_status': 'none' if sign_text == -1 else 'dialogue',
      'source_file': area['source_file'],
      'editability': edit_status('yaml_backed', 'Edit Header.sign_text in overworld YAML.'),
    })
  return {'format': 'zelda3_editor_sign_bindings', 'bindings': bindings}


# Build room message bindings from Header.tele_msg.
# Parameters:
#   room_data: Payloads returned by editor_asset_rooms.
# Returns:
#   JSON room message binding payload.
def build_room_message_bindings(room_data):
  bindings = []
  for room in room_data['rooms']['rooms']:
    tele_msg = room['header'].get('tele_msg')
    if tele_msg is None:
      continue
    bindings.append({
      'room': room['room'],
      'dialogue_id': tele_msg,
      'compiled_tele_msg': room['compiled_offsets'].get('tele_msg'),
      'source_file': room['source_file'],
      'editability': edit_status('yaml_backed', 'Edit Header.tele_msg in dungeon room YAML.'),
    })
  return {'format': 'zelda3_editor_room_message_bindings', 'bindings': bindings}


# Build a reverse usage index keyed by dialogue id.
# Parameters:
#   strings: Dialogue string records.
#   sign_bindings: Sign binding payload.
#   room_bindings: Room message binding payload.
#   npc_bindings: NPC dialogue binding payload.
# Returns:
#   JSON dialogue usage index.
def build_usage_index(strings, sign_bindings, room_bindings, npc_bindings):
  usage = {record['id']: [] for record in strings}
  for binding in sign_bindings['bindings']:
    usage.setdefault(binding['dialogue_id'], []).append({
      'kind': 'overworld_sign',
      'area': binding['area'],
      'source_file': binding['source_file'],
    })
  for binding in room_bindings['bindings']:
    usage.setdefault(binding['dialogue_id'], []).append({
      'kind': 'room_message',
      'room': binding['room'],
      'source_file': binding['source_file'],
    })
  for binding in npc_bindings['bindings']:
    for message in binding.get('messages', []):
      usage.setdefault(message['dialogue_id'], []).append({
        'kind': 'overworld_npc',
        'area': binding['area'],
        'stage': binding['stage'],
        'index': binding['index'],
        'sprite': binding['sprite'],
        'handler': message['handler'],
        'source_file': message['source_file'],
      })
  return {
    'format': 'zelda3_editor_dialogue_usage_index',
    'usage': [
      {'dialogue_id': dialogue_id, 'users': users}
      for dialogue_id, users in sorted(usage.items())
    ],
    'npc_dialogue_status': npc_bindings['editability'],
  }
