# editor_asset_overworld_sources.py -- Editable overworld source rows for editor exports.
#
# The high-level area summary is useful for browsing, but editor tools also need
# the actual YAML-backed rows they can inspect, move, and eventually write. This
# module reuses the existing overworld dump normalizers so dat-dump records match
# the schema already consumed by the browser editor.

# Standard library imports for copying parsed YAML without mutating compiler data.
from copy import deepcopy

# Existing overworld dump helpers define the editor-facing row shapes.
from dump_overworld_interactions import normalize_interactions
from dump_overworld_metadata import (
  build_hole_slot_metadata,
  normalize_header_metadata,
  normalize_navigation_metadata,
)
from dump_overworld_special import normalize_special_exits
from dump_overworld_sprites import normalize_sprite_sets
import overworld_static_overlays

# Shared editor-export constants and source helpers.
from editor_asset_common import (
  OVERWORLD_AREA_COUNT,
  edit_status,
  overworld_sprite_stage_records,
  source_ref,
)


# Build source-backed area records for every overworld area id.
# Parameters:
#   area_data: Parsed overworld YAML keyed by source area id.
#   area_sources: Source file paths keyed by source area id.
#   topology: Parent/child topology returned by editor_asset_overworld.
# Returns:
#   JSON payload with one record per area id.
def build_source_area_data(area_data, area_sources, topology):
  hole_slots = build_hole_slot_metadata(area_data)
  return {
    'format': 'zelda3_editor_overworld_source_areas',
    'area_count': OVERWORLD_AREA_COUNT,
    'areas': [
      build_source_area_record(area, area_data, area_sources, topology, hole_slots)
      for area in range(OVERWORLD_AREA_COUNT)
    ],
  }


# Build one source-area record, including inherited child-area ownership.
# Parameters:
#   area: Area id being described.
#   area_data: Parsed overworld YAML keyed by source area id.
#   area_sources: Source file paths keyed by source area id.
#   topology: Parent/child topology returned by editor_asset_overworld.
#   hole_slots: Fixed fall-hole slots keyed by (source_area, row_index).
# Returns:
#   JSON record with raw and normalized editable source sections.
def build_source_area_record(area, area_data, area_sources, topology, hole_slots):
  parent = topology['parents'][area]
  source_area = area if area in area_data else parent
  data = area_data.get(source_area) or {}
  source_path = area_sources.get(source_area)
  return {
    'area': area,
    'source_area': source_area,
    'source_file': source_ref(source_path, 'yaml') if source_path else None,
    'source_status': 'direct' if source_area == area else 'inherited',
    'topology_parent': parent,
    'topology_children': topology['children'].get(source_area, [source_area]),
    'header': normalize_header_metadata(data.get('Header') or {}),
    'sections': source_sections(data),
    'navigation': normalize_navigation_metadata(data, hole_slots_for_area(hole_slots, source_area)),
    'interactions': normalize_interactions(source_area, data),
    'special_exits': normalize_special_exits(data.get('Exits', [])),
    'sprite_sets': normalize_sprite_sets(data),
    'sprite_sources': source_sprite_stages(data),
    'static_overlays': overworld_static_overlays.normalize_static_overlay_rows(
      data.get('Overlays', []), source_area),
    'editability': source_editability(area, source_area),
  }


# Return an editability record that tells child areas where edits must be made.
# Parameters:
#   area: Area id being described.
#   source_area: YAML-owning source area id.
# Returns:
#   Standard editability status record.
def source_editability(area, source_area):
  if area == source_area:
    return edit_status('yaml_backed', 'This area has direct overworld YAML source rows.')
  return edit_status(
    'yaml_backed',
    'This child area inherits source rows from topology parent %d.' % source_area)


# Extract raw editable YAML sections without sharing mutable objects.
# Parameters:
#   data: Parsed overworld YAML for one source area.
# Returns:
#   Dict of raw source sections used by editor writeback tools.
def source_sections(data):
  return {
    'travel': deepcopy(data.get('Travel') or []),
    'entrances': deepcopy(data.get('Entrances') or []),
    'holes': deepcopy(data.get('Holes') or []),
    'exits': deepcopy(data.get('Exits') or []),
    'items': deepcopy(data.get('Items') or []),
    'overlays': deepcopy(data.get('Overlays') or []),
  }


# Build raw per-stage sprite source rows with stage metadata preserved.
# Parameters:
#   data: Parsed overworld YAML for one source area.
# Returns:
#   List of sprite stage source records.
def source_sprite_stages(data):
  return [
    {
      'stage': stage['stage'],
      'stage_slot': stage['stage_slot'],
      'source_key': stage['source_key'],
      'info': deepcopy(stage['info']),
      'sprites': deepcopy(stage['sprites']),
    }
    for stage in overworld_sprite_stage_records(data)
  ]


# Select fixed fall-hole slot metadata for one source area.
# Parameters:
#   hole_slots: Dict keyed by (source_area, row_index).
#   source_area: YAML-owning area id.
# Returns:
#   Dict keyed by row index for normalize_navigation_metadata.
def hole_slots_for_area(hole_slots, source_area):
  return {
    row_index: slot
    for (slot_area, row_index), slot in hole_slots.items()
    if slot_area == source_area
  }
