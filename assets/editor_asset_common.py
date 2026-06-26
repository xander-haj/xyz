# editor_asset_common.py -- Shared helpers for editor asset database builders.
#
# The editor export modules all need the same small set of source references,
# runtime asset references, YAML loading, and name decoding helpers. Keeping that
# here prevents each domain exporter from inventing a slightly different schema.

# Standard library imports for JSON/YAML source loading and path handling.
import json
import re
from pathlib import Path

# Project-local lookup tables provide canonical game names and reverse maps.
import tables
import yaml

# Source counts used by both compiler tables and editor-facing allocators.
OVERWORLD_AREA_COUNT = 160
NORMAL_OVERWORLD_AREA_COUNT = 128
DUNGEON_ROOM_COUNT = 320
DEFAULT_ROOM_COUNT = 8
OVERLAY_ROOM_COUNT = 19

# Overworld sprite YAML can be either one shared Sprites block or three stage
# blocks. The runtime stores the three stages in this order.
OVERWORLD_SPRITE_STAGES = (
  ('beginning', 'Sprites.Beginning', 0),
  ('first', 'Sprites.FirstPart', 1),
  ('second', 'Sprites.SecondPart', 2),
)


# Load one YAML file and normalize empty files to an empty dictionary.
# Parameters:
#   path: Path to a YAML source file relative to assets/.
# Returns:
#   Parsed YAML value or {} when the file is empty.
def load_yaml(path):
  with Path(path).open('r', encoding='utf8') as file:
    data = yaml.safe_load(file)
  return data if data is not None else {}


# Load one optional JSON file.
# Parameters:
#   path: Path to the JSON file.
# Returns:
#   Parsed JSON value, or None when the file does not exist.
def load_json_if_exists(path):
  path = Path(path)
  if not path.exists():
    return None
  with path.open('r', encoding='utf8') as file:
    return json.load(file)


# Convert a local path to the relative slash style used in editor JSON.
# Parameters:
#   path: Path-like source.
# Returns:
#   POSIX-style relative path string.
def relative_path(path):
  return Path(path).as_posix()


# Build a compact source-file reference.
# Parameters:
#   path: Source path relative to assets/ or project root as documented.
#   kind: Data kind such as yaml, json, text, c, or png.
# Returns:
#   JSON source reference.
def source_ref(path, kind):
  return {'path': relative_path(path), 'kind': kind}


# Build a compact compiler reference.
# Parameters:
#   function_name: compile_resources function that owns the transformation.
#   compiled_assets: Runtime asset names written by that compiler function.
# Returns:
#   JSON compiler reference.
def compiler_ref(function_name, compiled_assets):
  return {
    'path': 'compile_resources.py',
    'function': function_name,
    'compiled_assets': list(compiled_assets),
  }


# Build a compact C source reference for code-backed systems.
# Parameters:
#   path: Project path to the C source or header file.
#   symbols: Optional symbol names worth opening first.
# Returns:
#   JSON source reference.
def code_ref(path, symbols=None):
  record = source_ref(path, 'c')
  if symbols:
    record['symbols'] = list(symbols)
  return record


# Build a compact runtime asset reference from the dat dump manifest.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
#   name: Runtime asset name.
# Returns:
#   JSON asset reference with missing status when absent.
def asset_ref(asset_lookup, name):
  record = asset_lookup.get(name)
  if record is None:
    return {'name': name, 'status': 'missing'}
  result = {
    'name': name,
    'status': 'present',
    'index': record['index'],
    'type': record['type'],
    'size': record['size'],
    'directory': record.get('directory'),
  }
  for key in ('data_file', 'packed_file', 'entries_directory', 'entry_count'):
    if key in record:
      result[key] = record[key]
  return result


# Build runtime asset references for a list of names.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
#   names: Runtime asset names.
# Returns:
#   List of compact runtime asset references.
def asset_refs(asset_lookup, names):
  return [asset_ref(asset_lookup, name) for name in names]


# Return a known area name where the tables module has one.
# Parameters:
#   area: Overworld area id.
# Returns:
#   Friendly area name or None.
def area_name(area):
  return tables.kAreaNames[area] if area < len(tables.kAreaNames) else None


# Return a known entrance name where the tables module has one.
# Parameters:
#   entrance: Entrance id.
# Returns:
#   Friendly entrance name or None.
def entrance_name(entrance):
  return tables.kEntranceNames[entrance] if entrance < len(tables.kEntranceNames) else None


# Return a known sprite name where the tables module has one.
# Parameters:
#   sprite_id: Sprite type id.
# Returns:
#   Friendly sprite name or None.
def sprite_name(sprite_id):
  return tables.kSpriteNames[sprite_id] if sprite_id < len(tables.kSpriteNames) else None


# Parse the numeric prefix used by YAML names such as E8-FakeSword.
# Parameters:
#   value: YAML value, usually a string with a hex prefix.
# Returns:
#   Integer id, or None when no numeric prefix is present.
def prefixed_hex_id(value):
  if isinstance(value, int):
    return value
  if not isinstance(value, str):
    return None
  match = re.match(r'^([0-9A-Fa-f]+)(?:[.-]|$)', value)
  if not match:
    return None
  return int(match.group(1), 16)


# Normalize overworld sprite stage blocks from one area YAML.
# Parameters:
#   area_data: Parsed overworld YAML object.
# Returns:
#   List of stage records with stage name, slot, source key, info, and sprites.
def overworld_sprite_stage_records(area_data):
  if 'Sprites' in area_data:
    shared = area_data.get('Sprites') or {}
    return [
      sprite_stage_record(stage, yaml_key, slot, shared)
      for stage, yaml_key, slot in OVERWORLD_SPRITE_STAGES
    ]
  return [
    sprite_stage_record(stage, yaml_key, slot, area_data.get(yaml_key) or {})
    for stage, yaml_key, slot in OVERWORLD_SPRITE_STAGES
  ]


# Normalize one overworld sprite stage block.
# Parameters:
#   stage: Editor stage id.
#   yaml_key: Source YAML key.
#   slot: Runtime stage slot.
#   sprite_set: Parsed YAML sprite set.
# Returns:
#   Stage record with info and sprite rows.
def sprite_stage_record(stage, yaml_key, slot, sprite_set):
  return {
    'stage': stage,
    'stage_slot': slot,
    'source_key': yaml_key,
    'info': dict(sprite_set.get('info') or {}),
    'sprites': list(sprite_set.get('sprites') or []),
  }


# Normalize one generic editability record.
# Parameters:
#   status: One of yaml_backed, compiler_backed, code_backed, or requires_engine_work.
#   reason: Human-readable reason for the current status.
# Returns:
#   JSON editability record.
def edit_status(status, reason):
  return {'status': status, 'reason': reason}
