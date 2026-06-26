# editor_asset_npc_dialogue.py -- Source-backed overworld NPC dialogue bindings.
#
# The game does not store a single placement-to-dialogue table. Overworld NPC
# handlers choose messages in C based on sprite type, area, and game state. This
# exporter records those source-backed message sets so editor UI can truthfully
# expose text for the selected placement without guessing from sprite names.

# Project-local helpers keep editor JSON source references consistent.
from editor_asset_common import code_ref, edit_status


# The text compiler and messaging runtime currently support 398 US messages.
DIALOGUE_MESSAGE_CAPACITY = 398

# Source files whose handlers were traced for these message bindings.
SOURCE_SPRITE_MAIN = code_ref('../src/sprite_main.c')
SOURCE_MESSAGING = code_ref('../src/messaging.c')

# Text edits are compiler-backed, while choosing when to show a message remains
# sprite-handler logic in C.
TEXT_EDITABILITY = edit_status(
  'compiler_backed',
  'Edit dialogue text through dialogue.text patches; message selection remains source-code behavior.')

# Static source-handler message sets keyed by overworld sprite type. Dynamic
# handlers with area-dependent messages are resolved in messages_for_placement.
MESSAGE_RULES = {
  0x16: ('Sprite_16_Elder_bounce', [0x16, 0x17, 0x18, 0x1b]),
  0x28: ('Sprite_28_DarkWorldHintNPC', [0xfe, 0xff, 0x100, 0x101, 0x102, 0x103, 0x149]),
  0x29: ('Sprite_HumanMulti_1', [0xa1, 0xa2, 0xa3, 0xa4, 0x171, 0x172]),
  0x2a: ('Sprite_SweepingLady', [0xa5]),
  0x2b: ('Sprite_2B_Hobo', [0xd7]),
  0x2c: ('Sprite_Lumberjacks', [0x12c, 0x12d, 0x12e]),
  0x2f: ('Sprite_MazeGameLady', [0xcc, 0xd0]),
  0x30: ('Sprite_MazeGameGuy', [0xcb, 0xcd, 0xce, 0xcf, 0xd0]),
  0x31: ('Sprite_FortuneTeller', [
    0xea, 0xeb, 0xec, 0xed, 0xee, 0xef, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5,
    0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xfb, 0xfc, 0xfd,
  ]),
  0x32: ('Sprite_QuarrelBros', [0x12f, 0x130, 0x131]),
  0x34: ('Sprite_YoungSnitchLady', [0x2f]),
  0x35: ('Sprite_InnKeeper', [0x182, 0x183]),
  0x36: ('Sprite_Witch', [0x4a, 0x4b, 0x4c]),
  0x39: ('Sprite_39_Locksmith', [0x107, 0x109, 0x10a, 0x10b, 0x10c]),
  0x3a: ('Sprite_3A_MagicBat', [0x110, 0x111]),
  0x3c: ('Sprite_TroughBoy', [0x147, 0x148]),
  0x3d: ('Sprite_OldSnitchLady', [0x2f]),
  0x3f: ('Sprite_TutorialGuardOrBarrier', [
    0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0xb2, 0xb3,
  ]),
  0x52: ('Sprite_52_KingZora', [0x142, 0x143, 0x144, 0x145, 0x146]),
  0x72: ('Sprite_72_FairyPond', [
    0x89, 0x94, 0x95, 0x96, 0x97, 0x98, 0x14c, 0x14e, 0x150, 0x151,
    0x152, 0x153, 0x154,
  ]),
  0x74: ('Sprite_RunningMan', [0xa6]),
  0x75: ('Sprite_BottleVendor', [0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6]),
  0x78: ('Sprite_78_MrsSahasrahla', [0x2b, 0x2c, 0x2d, 0x2e]),
  0xad: ('Sprite_AD_OldMan', [0x9c, 0x9e, 0x9f, 0xa0]),
  0xb4: ('Sprite_B4_PurpleChest', [0x116]),
  0xb5: ('Sprite_B5_BombShop', [0x117, 0x118, 0x119, 0x11a, 0x16e, 0x17c]),
  0xb6: ('Sprite_B6_Kiki', [0x11b, 0x11c, 0x11d, 0x11e, 0x11f, 0x120]),
  0xb7: ('Sprite_B7_BlindMaiden', [0x122]),
  0xb9: ('Sprite_B9_BullyAndPinkBall', [0x15b, 0x15c, 0x15d, 0x15e]),
  0xbb: ('Sprite_BB_Shopkeeper', [
    0x15f, 0x160, 0x161, 0x163, 0x164, 0x165, 0x16d, 0x17c, 0x17e,
    0x17f, 0x180, 0x181,
  ]),
  0xbc: ('Sprite_BC_Drunkard', [0x175]),
  0xc0: ('Sprite_C0_Catfish', [0x12a, 0x12b]),
  0xd5: ('Sprite_D5_DigGameGuy', [0x187, 0x188, 0x189, 0x18a, 0x18b, 0x18c]),
  0xe8: ('Sprite_E8_FakeSword', [0x6f]),
}


# Build source-backed NPC dialogue bindings for overworld sprite placements.
# Parameters:
#   sprite_data: Payloads returned by editor_asset_sprites.
# Returns:
#   JSON NPC dialogue binding payload.
def build_npc_dialogue_bindings(sprite_data):
  placement_index = sprite_data.get('placement_index', sprite_data)
  overworld = placement_index.get('overworld', [])
  bindings = []
  for placement in overworld:
    messages = messages_for_placement(placement)
    if not messages:
      continue
    bindings.append(binding_record(placement, messages))
  return {
    'format': 'zelda3_editor_npc_dialogue_bindings',
    'bindings': bindings,
    'placement_index': 'editor/sprites/placement_index.json',
    'source_files': [SOURCE_SPRITE_MAIN, SOURCE_MESSAGING],
    'sprite_placement_count': len(placement_index.get('all', [])),
    'overworld_placement_count': len(overworld),
    'dialogue_placement_count': len(bindings),
    'message_capacity': DIALOGUE_MESSAGE_CAPACITY,
    'editability': edit_status(
      'compiler_backed',
      'NPC dialogue text is dialogue.txt data; placement message choices are source-code handlers.'),
  }


# Return the traced message set for one overworld placement.
# Parameters:
#   placement: One placement row from editor/sprites/placement_index.json.
# Returns:
#   List of message records, or [] when the sprite has no NPC dialogue binding.
def messages_for_placement(placement):
  sprite_type = placement.get('type')
  if sprite_type == 0x1a:
    return smithy_messages(placement)
  if sprite_type == 0x25:
    return talking_tree_messages(placement)
  if sprite_type == 0x2e:
    return flute_kid_messages(placement)
  if sprite_type == 0xb3:
    return pedestal_messages(placement)
  if sprite_type == 0xf2:
    return medallion_tablet_messages(placement)
  rule = MESSAGE_RULES.get(sprite_type)
  return message_list(rule[1], rule[0]) if rule else []


# Convert a traced list of message ids into editor binding message records.
# Parameters:
#   ids: Dialogue ids seen in source.
#   handler: Source handler that owns the ids.
# Returns:
#   Deduplicated message record list.
def message_list(ids, handler):
  records = []
  seen = set()
  for dialogue_id in ids:
    if dialogue_id in seen:
      continue
    seen.add(dialogue_id)
    records.append(message_record(dialogue_id, handler))
  return records


# Build one message record with source and text-edit metadata.
# Parameters:
#   dialogue_id: Numeric dialogue.txt id.
#   handler: Source handler that uses the id.
#   trigger: Optional state/branch label.
# Returns:
#   JSON message record.
def message_record(dialogue_id, handler, trigger='source handler branch'):
  return {
    'dialogue_id': dialogue_id,
    'trigger': trigger,
    'handler': handler,
    'source_file': code_ref('../src/sprite_main.c', [handler]),
    'editability': TEXT_EDITABILITY,
  }


# Talking trees choose their first message by X parity and later messages by area.
# Parameters:
#   placement: Live tree placement.
# Returns:
#   Source-backed greeting plus area-specific follow-up message records.
def talking_tree_messages(placement):
  x = placement.get('x') or 0
  first_id = 0x7d if x % 2 == 0 else 0x82
  messages = [message_record(first_id, 'TalkingTree_Mouth', 'first touch x-parity branch')]
  area = placement_area(placement)
  follow_up_by_area = {0x58: 0x7e, 0x5d: 0x7f, 0x72: 0x80, 0x6b: 0x81}
  if area in follow_up_by_area:
    messages.append(message_record(follow_up_by_area[area], 'TalkingTree_Mouth', 'subsequent touch area branch'))
  return messages


# Flute Kid only has overworld dialogue in the Dark World stump form.
# Parameters:
#   placement: Flute Kid placement.
# Returns:
#   Dark World stump messages, or [] for the Light World silent flute boy.
def flute_kid_messages(placement):
  if placement_area(placement) < 64:
    return []
  return message_list([0xe5, 0xe6, 0xe7, 0xe8, 0xe9], 'Sprite_FluteKid_Stumpy')


# Smithy type 0x1a is the Dark World frog outdoors and smithy family elsewhere.
# Parameters:
#   placement: Smithy-family placement.
# Returns:
#   Area-appropriate smithy message set.
def smithy_messages(placement):
  if placement_area(placement) >= 64:
    return message_list([0xe1], 'Smithy_Frog')
  return message_list([0xd8, 0xd9, 0xda, 0xdb, 0xdc, 0xdd, 0xde, 0xdf, 0xe0, 0xe2, 0xe3, 0xe4],
                      'Smithy_Main')


# Pedestal plaque messages differ between Desert Palace and the Lost Woods.
# Parameters:
#   placement: Pedestal or inscription placement.
# Returns:
#   Source-backed plain/book reading messages.
def pedestal_messages(placement):
  if placement_area(placement) == 0x30:
    return message_list([0xbc, 0xbd], 'Sprite_B3_PedestalPlaque')
  return message_list([0xb6, 0xb7], 'Sprite_B3_PedestalPlaque')


# Medallion tablet messages differ by tablet screen: area 3 is Ether, area 48 is Bombos.
# Parameters:
#   placement: Medallion tablet placement.
# Returns:
#   Source-backed cannot-read and successful tablet messages.
def medallion_tablet_messages(placement):
  if placement_area(placement) == 0x30:
    return message_list([0x10d, 0x10f], 'BombosTablet')
  return message_list([0x10d, 0x10e], 'EtherTablet')


# Build the per-placement binding row consumed by editor UI.
# Parameters:
#   placement: Overworld placement row.
#   messages: Source-backed message rows.
# Returns:
#   JSON binding record.
def binding_record(placement, messages):
  return {
    'scope': 'overworld',
    'area': placement.get('area'),
    'source_area': placement.get('source_area'),
    'stage': placement.get('stage'),
    'index': placement.get('index'),
    'sprite': placement.get('type'),
    'name': placement.get('canonical_name') or placement.get('name'),
    'x': placement.get('x'),
    'y': placement.get('y'),
    'source_file': placement.get('source_file'),
    'binding_status': 'source_code_message_set',
    'message_ids': [message['dialogue_id'] for message in messages],
    'messages': messages,
    'editability': TEXT_EDITABILITY,
  }


# Prefer source_area because large-area child placements compile through the parent screen.
# Parameters:
#   placement: Overworld placement row.
# Returns:
#   Numeric source area when present, otherwise the visual area.
def placement_area(placement):
  return placement.get('source_area', placement.get('area', 0))
