# editor_asset_graphics.py -- Graphics and palette grouping for editor exports.
#
# Graphics assets mix raw tile data, packed compressed streams, PNG-derived Link
# graphics, and palette words. This module labels each source honestly so editor
# code knows which data is immediately decodable and which needs a graphics
# decoder or compiler write path.

# Project-local reference helpers.
from editor_asset_common import asset_ref, asset_refs, edit_status, source_ref

# Palette groups are deliberately explicit so UI code can present meaningful tabs.
BG_PALETTE_ASSETS = (
  'kPalette_DungBgMain',
  'kPalette_OverworldBgMain',
  'kPalette_OverworldBgAux12',
  'kPalette_OverworldBgAux3',
  'kPalette_PalaceMapBg',
  'kHudPalData',
  'kOverworldMapPaletteData',
)
SPRITE_PALETTE_ASSETS = (
  'kPalette_MainSpr',
  'kPalette_ArmorAndGloves',
  'kPalette_Sword',
  'kPalette_Shield',
  'kPalette_SpriteAux3',
  'kPalette_MiscSprite_Indoors',
  'kPalette_SpriteAux1',
  'kPalette_PalaceMapSpr',
)


# Build every graphics and palette payload.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name from the dump manifest.
#   palettes: Palette preview payload from editor_assets.build_palettes.
# Returns:
#   Dict of graphics and palette output payloads.
def build_graphics_data(assets, asset_lookup, palettes):
  return {
    'bg_graphics': build_bg_graphics(assets, asset_lookup),
    'sprite_graphics': build_sprite_graphics(assets, asset_lookup),
    'bg_palette_groups': build_palette_group(
      'zelda3_editor_bg_palette_groups', BG_PALETTE_ASSETS, palettes, asset_lookup),
    'sprite_palette_groups': build_palette_group(
      'zelda3_editor_sprite_palette_groups', SPRITE_PALETTE_ASSETS, palettes, asset_lookup),
    'palette_sources': build_palette_sources(palettes, asset_lookup),
  }


# Build background graphics source records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON background graphics payload.
def build_bg_graphics(assets, asset_lookup):
  return {
    'format': 'zelda3_editor_bg_graphics',
    'sources': [
      packed_graphics_source(asset_lookup, 'kBgGfx', 'background_graphics', 'snes_lz_or_generated_bg_tiles'),
      flat_graphics_source(assets, asset_lookup, 'kOverworldMapGfx', 'raw_snes_4bpp_tiles', 32),
      flat_graphics_source(assets, asset_lookup, 'kLightOverworldTilemap', 'raw_tilemap_bytes', 2),
      flat_graphics_source(assets, asset_lookup, 'kDarkOverworldTilemap', 'raw_tilemap_bytes', 2),
    ] + [
      flat_graphics_source(assets, asset_lookup, 'kBgTilemap_%d' % index, 'dma_tilemap_stream', 1)
      for index in range(6)
    ],
    'editability': edit_status(
      'compiler_backed',
      'Raw graphics can be decoded directly; compressed BG sheets need a decoder/compiler write path.'),
  }


# Build sprite graphics source records.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON sprite graphics payload.
def build_sprite_graphics(assets, asset_lookup):
  return {
    'format': 'zelda3_editor_sprite_graphics',
    'sources': [
      packed_graphics_source(asset_lookup, 'kSprGfx', 'sprite_graphics', 'raw_4bpp_or_snes_lz_tiles'),
      flat_graphics_source(assets, asset_lookup, 'kLinkGraphics', 'raw_snes_4bpp_tiles', 32),
    ],
    'source_files': [
      source_ref('linksprite.png', 'png'),
      source_ref('sprites/sprites_*.png', 'png_optional'),
    ],
    'editability': edit_status(
      'compiler_backed',
      'Link graphics are PNG-backed; general sprite sheets still need per-pack editor write support.'),
  }


# Build one packed graphics source record.
# Parameters:
#   asset_lookup: Dict keyed by runtime asset name.
#   asset_name: Runtime packed asset name.
#   family: Editor family id.
#   decode_hint: Family-level decode hint.
# Returns:
#   JSON graphics source record.
def packed_graphics_source(asset_lookup, asset_name, family, decode_hint):
  ref = asset_ref(asset_lookup, asset_name)
  return {
    'asset': ref,
    'family': family,
    'encoding': 'runtime_packed',
    'entry_count': ref.get('entry_count'),
    'decode_hint': decode_hint,
  }


# Build one flat graphics source record.
# Parameters:
#   assets: Ordered compile_resources.assets mapping.
#   asset_lookup: Dict keyed by runtime asset name.
#   asset_name: Runtime asset name.
#   encoding: Editor-visible encoding label.
#   bytes_per_unit: Unit byte size for tile/count estimates.
# Returns:
#   JSON graphics source record.
def flat_graphics_source(assets, asset_lookup, asset_name, encoding, bytes_per_unit):
  ref = asset_ref(asset_lookup, asset_name)
  size = len(assets[asset_name][1]) if asset_name in assets else None
  return {
    'asset': ref,
    'encoding': encoding,
    'unit_count': size // bytes_per_unit if size is not None and bytes_per_unit else None,
  }


# Build grouped palette previews.
# Parameters:
#   format_name: JSON format tag.
#   names: Runtime palette asset names.
#   palettes: Palette preview payload keyed by asset name.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON palette group payload.
def build_palette_group(format_name, names, palettes, asset_lookup):
  groups = []
  for name in names:
    if name not in palettes:
      continue
    groups.append({
      'name': name,
      'asset': asset_ref(asset_lookup, name),
      'color_count': palettes[name]['color_count'],
      'colors': palettes[name]['colors'],
    })
  return {'format': format_name, 'groups': groups}


# Build compact palette source records.
# Parameters:
#   palettes: Palette preview payload keyed by asset name.
#   asset_lookup: Dict keyed by runtime asset name.
# Returns:
#   JSON palette source payload.
def build_palette_sources(palettes, asset_lookup):
  return {
    'format': 'zelda3_editor_palette_sources',
    'palette_format': 'snes_bgr555',
    'sources': [
      {
        'name': name,
        'asset': asset_ref(asset_lookup, name),
        'color_count': payload['color_count'],
      }
      for name, payload in sorted(palettes.items())
    ],
    'compiled_assets': asset_refs(asset_lookup, sorted(palettes.keys())),
  }
