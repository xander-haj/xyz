# editor_asset_overworld.py -- Overworld area records for editor exports.
#
# This module exposes the YAML-backed overworld area model, including topology,
# source map32 grids, inherited child areas, and the rules an editor must obey
# before attempting expansion or row insertion.

# Standard library imports for path handling.
from pathlib import Path

# Project-local constants, source helpers, and lookup tables.
from editor_asset_common import (
  NORMAL_OVERWORLD_AREA_COUNT,
  OVERWORLD_AREA_COUNT,
  asset_refs,
  area_name,
  edit_status,
  load_json_if_exists,
  load_yaml,
  overworld_sprite_stage_records,
  source_ref,
)
from editor_asset_overworld_sources import build_source_area_data
import overworld_map32

# Topology constants mirror compile_resources.py and the runtime table shape.
OW_AREA_TOPOLOGY_STRIDE = 192
OW_AREA_SIZE_CODES = {'small': 0, 'big': 1, 'large': 1, 'wide': 2, 'tall': 3}
OW_AREA_SIZE_NAMES = {0: 'small', 1: 'big', 2: 'wide', 3: 'tall'}
OW_AREA_SIZE_OFFSETS = {
  'small': (0,),
  'big': (0, 1, 8, 9),
  'wide': (0, 1),
  'tall': (0, 8),
}


# Build every overworld-facing editor output.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   args: Optional restool args, used when mod-generated roots are active.
# Returns:
#   Dict containing areas, topology, grid, references, and remap rules.
def build_overworld_data(asset_lookup, args=None):
  area_sources = load_area_sources(args)
  area_data = {area: load_yaml(path) for area, path in area_sources.items()}
  topology = build_topology(area_data)
  map32_root = map32_source_root(args)
  areas = [
    build_area_record(area, area_data, area_sources, topology, map32_root, asset_lookup)
    for area in range(OVERWORLD_AREA_COUNT)
  ]
  return {
    'areas': {
      'format': 'zelda3_editor_overworld_areas',
      'area_count': OVERWORLD_AREA_COUNT,
      'areas': areas,
    },
    'source_areas': build_source_area_data(area_data, area_sources, topology),
    'topology': build_topology_record(topology),
    'area_grid': build_area_grid(),
    'area_references': build_area_references(areas),
    'remap_rules': build_remap_rules(),
    'raw_topology': topology,
  }


# Locate the overworld YAML source file for every existing source area.
# Parameters:
#   args: Optional restool args with overworld_generated_root.
# Returns:
#   Dict mapping area id to source Path.
def load_area_sources(args):
  result = {}
  raw_generated_root = getattr(args, 'overworld_generated_root', None) if args else None
  generated_root = Path(raw_generated_root) if raw_generated_root else None
  for area in range(OVERWORLD_AREA_COUNT):
    generated = generated_root / 'overworld' / ('overworld-%d.yaml' % area) if generated_root else None
    base = Path('overworld') / ('overworld-%d.yaml' % area)
    if generated is not None and generated.exists():
      result[area] = generated
    elif base.exists():
      result[area] = base
  return result


# Select the map32 source root that compile_resources would prefer.
# Parameters:
#   args: Optional restool args with overworld_source_root.
# Returns:
#   Path to editable map32 JSON files.
def map32_source_root(args):
  source_root = getattr(args, 'overworld_source_root', None) if args else None
  return Path(source_root or overworld_map32.DEFAULT_SOURCE_DIR)


# Build the same parent/child topology compile_resources writes to runtime assets.
# Parameters:
#   area_data: Dict of parsed YAML by source area id.
# Returns:
#   Dict with parents, sizes, children, and heads.
def build_topology(area_data):
  parents = list(range(OW_AREA_TOPOLOGY_STRIDE))
  sizes = [0] * OW_AREA_TOPOLOGY_STRIDE
  children = {area: [area] for area in range(OVERWORLD_AREA_COUNT)}

  for world_base in (0, 64):
    covered = {}
    for y in range(8):
      for x in range(8):
        area = world_base + y * 8 + x
        if area in covered:
          continue
        data = area_data.get(area)
        if data is None:
          raise ValueError('Missing overworld YAML for generated area head %d.' % area)
        size = canonical_size(data.get('Header', {}).get('size'), area)
        validate_topology_fit(area, x, y, size)
        owned = []
        for offset in OW_AREA_SIZE_OFFSETS[size]:
          child = area + offset
          if child in covered:
            raise ValueError('Overworld area %d is covered twice.' % child)
          covered[child] = area
          parents[child] = area
          sizes[child] = OW_AREA_SIZE_CODES[size]
          owned.append(child)
        children[area] = owned

  for area in range(NORMAL_OVERWORLD_AREA_COUNT, OVERWORLD_AREA_COUNT):
    data = area_data.get(area)
    if data is None:
      raise ValueError('Missing overworld YAML for special area %d.' % area)
    size = canonical_size(data.get('Header', {}).get('size'), area)
    parents[area] = area
    sizes[area] = OW_AREA_SIZE_CODES[size]
    children[area] = [area]

  return {
    'parents': parents,
    'sizes': sizes,
    'children': children,
    'heads': [area for area in range(OVERWORLD_AREA_COUNT) if parents[area] == area],
  }


# Normalize one Header.size value to the canonical spelling.
# Parameters:
#   value: YAML Header.size value.
#   area: Area id used for diagnostics.
# Returns:
#   Canonical size string.
def canonical_size(value, area):
  if value not in OW_AREA_SIZE_CODES:
    raise ValueError('Overworld Header.size in area %d must be small, big, wide, or tall.' % area)
  return OW_AREA_SIZE_NAMES[OW_AREA_SIZE_CODES[value]]


# Validate that a parent area shape fits inside the 8x8 world grid.
# Parameters:
#   area: Parent area id.
#   x: Grid x coordinate.
#   y: Grid y coordinate.
#   size: Canonical size string.
# Returns:
#   None.
def validate_topology_fit(area, x, y, size):
  if size in ('big', 'wide') and x >= 7:
    raise ValueError('Overworld Header.size %s in area %d crosses the east edge.' % (size, area))
  if size in ('big', 'tall') and y >= 7:
    raise ValueError('Overworld Header.size %s in area %d crosses the south edge.' % (size, area))


# Build one editor area record, including child inheritance.
# Parameters:
#   area: Overworld area id.
#   area_data: Parsed YAML by source area id.
#   area_sources: Source path by source area id.
#   topology: Parent/child topology.
#   map32_root: Path to editable map32 sources.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON area record.
def build_area_record(area, area_data, area_sources, topology, map32_root, asset_lookup):
  parent = topology['parents'][area]
  is_head = parent == area
  source_area = area if area in area_data else parent
  data = area_data[source_area]
  header = dict(data.get('Header') or {})
  header['size'] = canonical_size(header.get('size'), source_area)
  map32_path = map32_root / ('%03d.json' % area)
  map32_payload = load_json_if_exists(map32_path)
  record = {
    'area': area,
    'name': area_name(area),
    'world': world_name(area),
    'grid': grid_position(area),
    'is_topology_head': is_head,
    'topology_parent': parent,
    'topology_children': topology['children'].get(area, [area]),
    'topology_size': OW_AREA_SIZE_NAMES[topology['sizes'][area]],
    'source_area': source_area,
    'source_file': source_ref(area_sources[source_area], 'yaml'),
    'map32_source_file': source_ref(map32_path, 'json') if map32_path.exists() else None,
    'map32_source_status': map32_status(map32_payload),
    'header': header,
    'sections': section_counts(data),
    'sprite_stages': summarize_sprite_stages(data),
    'compiled_assets': asset_refs(asset_lookup, [
      'kOverworld_Hibytes_Comp', 'kOverworld_Lobytes_Comp',
      'kOverworldMapIsSmall', 'kOverworldAuxTileThemeIndexes',
      'kOverworldBgPalettes', 'kOverworld_SignText',
    ]),
  }
  if is_head:
    record['editability'] = edit_status('yaml_backed', 'This area has direct overworld YAML.')
  else:
    record['editability'] = edit_status(
      'yaml_backed',
      'This child area inherits from topology parent %d; edit the parent YAML.' % parent)
  return record


# Classify the world range an area id belongs to.
# Parameters:
#   area: Overworld area id.
# Returns:
#   World label string.
def world_name(area):
  if area < 64:
    return 'light_world'
  if area < NORMAL_OVERWORLD_AREA_COUNT:
    return 'dark_world'
  return 'special'


# Compute the fixed 8x8 grid coordinate for normal areas.
# Parameters:
#   area: Overworld area id.
# Returns:
#   Grid coordinate record or None for special areas.
def grid_position(area):
  if area >= NORMAL_OVERWORLD_AREA_COUNT:
    return None
  local = area & 63
  return {'x': local % 8, 'y': local // 8}


# Summarize whether one map32 source JSON is present and schema-shaped.
# Parameters:
#   payload: Parsed map32 JSON or None.
# Returns:
#   Status record.
def map32_status(payload):
  if payload is None:
    return {'status': 'missing', 'format': None}
  return {
    'status': 'present',
    'format': payload.get('format'),
    'width': payload.get('width'),
    'height': payload.get('height'),
  }


# Count source sections that matter to editor navigation and placement tools.
# Parameters:
#   data: Parsed overworld YAML.
# Returns:
#   Dict of section counts.
def section_counts(data):
  return {
    'travel': len(data.get('Travel') or []),
    'entrances': len(data.get('Entrances') or []),
    'holes': len(data.get('Holes') or []),
    'exits': len(data.get('Exits') or []),
    'items': len(data.get('Items') or []),
    'overlays': len(data.get('Overlays') or []),
  }


# Build per-stage sprite counts and graphics requirements.
# Parameters:
#   data: Parsed overworld YAML.
# Returns:
#   List of sprite stage summaries.
def summarize_sprite_stages(data):
  records = []
  for stage in overworld_sprite_stage_records(data):
    records.append({
      'stage': stage['stage'],
      'source_key': stage['source_key'],
      'stage_slot': stage['stage_slot'],
      'info': stage['info'],
      'sprite_count': len(stage['sprites']),
    })
  return records


# Build the topology JSON output.
# Parameters:
#   topology: Parent/child topology.
# Returns:
#   JSON topology record.
def build_topology_record(topology):
  return {
    'format': 'zelda3_editor_world_topology',
    'parents': topology['parents'][:OVERWORLD_AREA_COUNT],
    'sizes': [
      {'area': area, 'code': topology['sizes'][area], 'name': OW_AREA_SIZE_NAMES[topology['sizes'][area]]}
      for area in range(OVERWORLD_AREA_COUNT)
    ],
    'heads': topology['heads'],
    'children': {str(area): children for area, children in sorted(topology['children'].items())},
  }


# Build fixed world-grid rows for editor map browsers.
# Parameters: none.
# Returns:
#   JSON world grid record.
def build_area_grid():
  return {
    'format': 'zelda3_editor_area_grid',
    'worlds': [
      {'world': 'light_world', 'base_area': 0, 'width': 8, 'height': 8, 'rows': grid_rows(0, 8)},
      {'world': 'dark_world', 'base_area': 64, 'width': 8, 'height': 8, 'rows': grid_rows(64, 8)},
      {'world': 'special', 'base_area': 128, 'width': 8, 'height': 4, 'rows': grid_rows(128, 4)},
    ],
  }


# Build row-major area ids for a grid section.
# Parameters:
#   base: First area id in the section.
#   height: Number of 8-wide rows.
# Returns:
#   Nested list of area ids.
def grid_rows(base, height):
  return [[base + y * 8 + x for x in range(8)] for y in range(height)]


# Build a compact area-reference index.
# Parameters:
#   areas: Full area records.
# Returns:
#   JSON area reference table.
def build_area_references(areas):
  return {
    'format': 'zelda3_editor_area_references',
    'areas': [
      {
        'area': area['area'],
        'name': area['name'],
        'world': area['world'],
        'source_file': area['source_file'],
        'map32_source_file': area['map32_source_file'],
        'topology_parent': area['topology_parent'],
      }
      for area in areas
    ],
  }


# Build explicit future remap rules for expansion work.
# Parameters: none.
# Returns:
#   JSON remap rule documentation.
def build_remap_rules():
  return {
    'format': 'zelda3_editor_world_remap_rules',
    'current_area_range': [0, OVERWORLD_AREA_COUNT - 1],
    'row_insert_requires': [
      'renumber affected overworld YAML files',
      'renumber map32 source files',
      'rewrite area references in entrances, holes, exits, travel, sprites, and signs',
      'extend compiler topology constants',
      'extend runtime area index assumptions in C code',
    ],
    'new_outer_map_square_status': 'requires_engine_work',
  }
