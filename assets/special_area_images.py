# =============================================================================
# special_area_images.py -- Special overworld PNG renderer
#
# Renders the ROM's special overworld maps through the same data layers used by
# the engine: compressed map32 pages, map32->map16, map16->map8, loaded BG CHR,
# and overworld BG palettes. Output is the 256x192 playfield view under the HUD.
# =============================================================================

import os
import re
from ast import literal_eval

from PIL import Image, ImageChops

import sprite_sheets
import tables
import util

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOAD_GFX_C = os.path.join(PROJECT_ROOT, 'src', 'load_gfx.c')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'editing', 'special')

AREA_COUNT = 160
AREA_PIXEL_SIZE, SCREEN_PIXEL_SIZE = 512, 1024
VISIBLE_WIDTH, VISIBLE_HEIGHT, HUD_HEIGHT = 256, 192, 32
MAP32_COUNT = 2218
MAP16_GRID_SIZE = 32
MAP16_TO_MAP8_ADDR = 0x8F8000
MAP16_TO_MAP8_WORDS = 3752 * 4
SPECIAL_MAIN_TILE_THEME = 0x20
TRIFORCE_ROOM, TRIFORCE_AREAS = 0x189, (0x88, 0x93)
NAMED_AREA_ROOMS = {0x81: 0x182, 0x82: 0x182, 0x89: 0x182, 0x8a: 0x182, 0x94: 0x181, 0x97: 0x180}
OVERLAY_BASE_AREAS = {0x95: 0x03, 0x97: 0x00, 0x9c: 0x43, 0x9d: 0x00, 0x9e: 0x00, 0x9f: 0x00}
COOL_BACKGROUND_AREA, COOL_BACKGROUND_SCREEN = 0x96, 0x5b
CLOUD_ANIM_PACK = 0x59
SPECIAL_EXIT_ROOM_BASE, SPECIAL_EXIT_ROOM_LIMIT = 0x180, 0x190

OW_BG_MAIN_ADDR, OW_BG_AUX12_ADDR, OW_BG_AUX3_ADDR = 0x9BE6C8, 0x9BE86C, 0x9BE604

SP_EXIT_AUX_GFX_ADDR = 0x82E821
SP_EXIT_PAL_BG_ADDR = 0x82E831
SP_EXIT_TOP_ADDR = 0x82E6E1
SP_EXIT_LEFT_EDGE_ADDR = 0x82E7E1

EXIT_DATA_ROOM_ADDR = 0x82DD8A
EXIT_DATA_SCREEN_ADDR = 0x82DE28
EXIT_DATA_SCROLL_Y_ADDR = 0x82DF15
EXIT_DATA_SCROLL_X_ADDR = 0x82DFB3
EXIT_DATA_COUNT = 79
# Removes C block and line comments so initializer text can be parsed safely.
def _strip_c_comments(text):
  text = re.sub(r'/\*.*?\*/', '', text, flags = re.S)
  return re.sub(r'//.*', '', text)


# Finds the balanced brace initializer that follows a C symbol name.
def _find_initializer(text, name):
  pos = text.index(name)
  start = text.index('{', pos)
  depth = 0
  for i in range(start, len(text)):
    if text[i] == '{':
      depth += 1
    elif text[i] == '}':
      depth -= 1
      if depth == 0:
        return text[start:i + 1]
  raise ValueError('Could not find initializer for %s' % name)


# Loads a numeric C initializer from load_gfx.c as a Python list.
def _load_c_array(name):
  with open(LOAD_GFX_C, 'r') as f:
    init = _find_initializer(_strip_c_comments(f.read()), name)
  return literal_eval(init.replace('{', '[').replace('}', ']'))


# Loads the engine-side tileset and palette descriptor tables used here.
def _load_engine_tables():
  return {
    'main_tilesets': _load_c_array('kMainTilesets'),
    'aux_tilesets': _load_c_array('kAuxTilesets'),
    'ow_bg_pal_info': _load_c_array('kOwBgPalInfo'),
  }


# Copies a Palette_LoadMultiple-style block into a 256-entry SNES palette.
def _load_palette_block(palette, src, dst, x_ents, y_pals):
  width = x_ents + 1
  for row in range(y_pals + 1):
    palette[(dst >> 1) + row * 16:(dst >> 1) + row * 16 + width] = src[row * width:row * width + width]


# Copies a Palette_LoadSingle-style row into a 256-entry SNES palette.
def _load_palette_row(palette, src, dst, x_ents):
  width = x_ents + 1
  palette[dst >> 1:(dst >> 1) + width] = src[:width]


# Mirrors Palette_GetOwBgColor for the special-overworld backdrop slots.
def _get_backdrop_color(screen, room):
  if screen == COOL_BACKGROUND_SCREEN: return 0
  if screen < 0x80:
    return 0x2A32 if screen & 0x40 else 0x2669
  if room in (0x180, 0x182, 0x183): return 0x19C6
  return 0x2669


# Builds the BG palette visible after Overworld_LoadPalettes/Palette_SpecialOw.
def _build_palette(screen, bg_palette, room, ow_bg_pal_info, mode_override = None, aux2_override = None):
  palette = [0] * 256
  if mode_override is None:
    sc = screen & 0x3f
    mode = 2 if sc in (3, 5, 7) else 0
    mode += 1 if screen & 0x40 else 0
  else:
    mode = mode_override

  _load_palette_block(palette, util.get_words(OW_BG_MAIN_ADDR + mode * 35 * 2, 35), 0x42, 6, 4)

  aux1, aux2, aux3 = 3, 3, 0
  if bg_palette >= 0:
    d = ow_bg_pal_info[bg_palette * 3:bg_palette * 3 + 3]
    if d[0] >= 0: aux1 = d[0]
    if d[1] >= 0: aux2 = d[1]
    if d[2] >= 0: aux3 = d[2]
  if aux2_override is not None: aux2 = aux2_override
  _load_palette_block(palette, util.get_words(OW_BG_AUX12_ADDR + aux1 * 21 * 2, 21), 0x52, 6, 2)
  _load_palette_block(palette, util.get_words(OW_BG_AUX12_ADDR + aux2 * 21 * 2, 21), 0xB2, 6, 2)
  _load_palette_row(palette, util.get_words(OW_BG_AUX3_ADDR + aux3 * 7 * 2, 7), 0xE2, 6)
  backdrop = _get_backdrop_color(screen, room)
  palette[0] = backdrop
  palette[32] = backdrop
  return sprite_sheets.convert_snes_palette(palette)


# Decodes one compressed 3bpp BG pack into 64 4bpp 8x8 tiles.
def _decode_bg_pack(gfx_pack, high):
  data = util.decomp(tables.kCompBgPtrs[gfx_pack], util.get_byte, False)
  if len(data) < 64 * 24:
    raise ValueError('BG pack %d decoded to %d bytes' % (gfx_pack, len(data)))

  tiles = []
  for tile in range(64):
    offs = tile * 24
    pixels = [0] * 64
    for y in range(8):
      plane0 = data[offs + y * 2]
      plane1 = data[offs + y * 2 + 1]
      plane2 = data[offs + 16 + y]
      plane3 = (plane0 | plane1 | plane2) if high else 0
      for x in range(8):
        bit = 7 - x
        pixels[y * 8 + x] = ((plane0 >> bit) & 1) | (((plane1 >> bit) & 1) << 1) | (((plane2 >> bit) & 1) << 2) | (((plane3 >> bit) & 1) << 3)
    tiles.append(pixels)
  return tiles


# Builds the 512-tile BG CHR cache selected by InitializeTilesets.
def _build_tile_cache(main_gfx, aux_gfx, engine_tables, anim_pack = None):
  main = engine_tables['main_tilesets'][main_gfx]
  aux = engine_tables['aux_tilesets'][aux_gfx]
  packs = [main[0], main[1], main[2], aux[0] or main[3], aux[1] or main[4], aux[2] or main[5], aux[3] or main[6], main[7]]
  slots = [7, 6, 5, 4, 3, 2, 1, 0]
  pack_cache, tile_cache = {}, {}
  for group, gfx_pack in enumerate(packs):
    high = slots[group] in (7, 2, 3, 4) if main_gfx >= 0x20 else slots[group] >= 4
    key = (gfx_pack, high)
    if key not in pack_cache:
      pack_cache[key] = _decode_bg_pack(gfx_pack, high)
    for tile_index, pixels in enumerate(pack_cache[key]):
      tile_cache[group * 64 + tile_index] = pixels
  if anim_pack is not None:
    tile_cache.update((0x1c0 + i, pixels) for i, pixels in enumerate(_decode_bg_pack(anim_pack, False)[:32]))
  return tile_cache

# Decodes one 6-byte map32 definition record into four map16 ids.
def _decode_map32_record(addr):
  ov = [util.get_byte(addr + i) for i in range(6)]
  return [
    ov[0] | ((ov[4] >> 4) << 8),
    ov[1] | ((ov[4] & 0xf) << 8),
    ov[2] | ((ov[5] >> 4) << 8),
    ov[3] | ((ov[5] & 0xf) << 8),
  ]


# Builds the map32 id -> four map16 ids table used by the overworld loader.
def _build_map32_to_map16():
  result = []
  for i in range(MAP32_COUNT):
    groups = [
      _decode_map32_record(0x838000 + i * 6),
      _decode_map32_record(0x83B400 + i * 6),
      _decode_map32_record(0x848000 + i * 6),
      _decode_map32_record(0x84B400 + i * 6),
    ]
    for j in range(4):
      result.append((groups[0][j], groups[1][j], groups[2][j], groups[3][j]))
  return result


# Decodes one 512x512 overworld area page into a 32x32 map16 grid.
def _decode_area_map16(area, map32_to_map16):
  hi_addr = util.ROM.get_24(0x82F94D + area * 3)
  lo_addr = util.ROM.get_24(0x82FB2D + area * 3)
  hi = util.decomp(hi_addr, util.get_byte, True)
  lo = util.decomp(lo_addr, util.get_byte, True)
  if len(hi) < 256 or len(lo) < 256:
    raise ValueError('Area %d map32 data is incomplete' % area)

  grid = [[0] * MAP16_GRID_SIZE for _ in range(MAP16_GRID_SIZE)]
  for i in range(256):
    map32 = lo[i] | (hi[i] << 8)
    if map32 >= len(map32_to_map16):
      raise ValueError('Area %d references map32 id %d' % (area, map32))
    x = (i & 15) * 2
    y = (i >> 4) * 2
    q = map32_to_map16[map32]
    grid[y][x] = q[0]
    grid[y][x + 1] = q[1]
    grid[y + 1][x] = q[2]
    grid[y + 1][x + 1] = q[3]
  return grid


# Draws one 8x8 map tile into a paletted pixel buffer.
def _draw_map8_tile(pixels, width, x0, y0, tile_word, tile_cache):
  tile_id = tile_word & 0x1ff
  tile = tile_cache.get(tile_id)
  if tile is None:
    raise ValueError('Missing BG tile id %d' % tile_id)

  palette_base = ((tile_word >> 10) & 7) * 16
  hflip = tile_word & 0x4000
  vflip = tile_word & 0x8000
  for y in range(8):
    sy = 7 - y if vflip else y
    dst = (y0 + y) * width + x0
    for x in range(8):
      sx = 7 - x if hflip else x
      value = tile[sy * 8 + sx]
      pixels[dst + x] = 0 if value == 0 else palette_base + value


# Draws a 32x32 map16 grid to a 512x512 paletted pixel buffer.
def _draw_map16_grid(grid, map16_to_map8, tile_cache):
  pixels = bytearray(AREA_PIXEL_SIZE * AREA_PIXEL_SIZE)
  max_map16 = len(map16_to_map8) // 4
  for y, row in enumerate(grid):
    for x, map16 in enumerate(row):
      if map16 >= max_map16:
        raise ValueError('Map16 id %d is outside kMap16ToMap8' % map16)
      tiles = map16_to_map8[map16 * 4:map16 * 4 + 4]
      x0 = x * 16
      y0 = y * 16
      _draw_map8_tile(pixels, AREA_PIXEL_SIZE, x0, y0, tiles[0], tile_cache)
      _draw_map8_tile(pixels, AREA_PIXEL_SIZE, x0 + 8, y0, tiles[1], tile_cache)
      _draw_map8_tile(pixels, AREA_PIXEL_SIZE, x0, y0 + 8, tiles[2], tile_cache)
      _draw_map8_tile(pixels, AREA_PIXEL_SIZE, x0 + 8, y0 + 8, tiles[3], tile_cache)
  return pixels


# Renders a single 512x512 compressed overworld area page.
def _render_area_page(area, palette, tile_cache, map32_to_map16, map16_to_map8):
  img = Image.new('P', (AREA_PIXEL_SIZE, AREA_PIXEL_SIZE))
  img.putdata(_draw_map16_grid(_decode_area_map16(area, map32_to_map16), map16_to_map8, tile_cache))
  img.putpalette(palette)
  return img


# Renders the four-quadrant 1024x1024 screen buffer loaded by the engine.
def _render_screen_buffer(screen, palette, tile_cache, map32_to_map16, map16_to_map8):
  img = Image.new('P', (SCREEN_PIXEL_SIZE, SCREEN_PIXEL_SIZE))
  img.putpalette(palette)
  for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
    area = screen + dx + dy * 8
    if area < AREA_COUNT:
      img.paste(_render_area_page(area, palette, tile_cache, map32_to_map16, map16_to_map8), (dx * AREA_PIXEL_SIZE, dy * AREA_PIXEL_SIZE))
  return img


# Crops a source image with wraparound, matching the 1024px special screen mask.
def _crop_wrapped(img, left, top, width, height):
  result = Image.new(img.mode, (width, height)); result.putpalette(img.getpalette()) if img.mode == 'P' else None
  src_w, src_h = img.size
  y = 0
  while y < height:
    x = 0
    while x < width:
      sx = (left + x) % src_w
      sy = (top + y) % src_h
      w = min(width - x, src_w - sx)
      h = min(height - y, src_h - sy)
      result.paste(img.crop((sx, sy, sx + w, sy + h)), (x, y))
      x += w
    y += h
  return result


# Returns a filesystem-safe lowercase slug for an area name.
def _slug(name):
  label = name.split(':', 1)[-1].strip().lower()
  label = re.sub(r'[^a-z0-9]+', '-', label).strip('-')
  return label or 'special'


# Finds named SP area slots from tables.kAreaNames, skipping NA filler slots.
def _named_special_areas():
  for area, name in enumerate(tables.kAreaNames):
    if 0x80 <= area < 0xa0 and name.startswith('SP '):
      yield area, name


# Reads all engine exit records that target special-overworld rooms.
def _special_exit_records():
  records = []
  for i in range(EXIT_DATA_COUNT):
    room = util.get_word(EXIT_DATA_ROOM_ADDR + i * 2)
    if SPECIAL_EXIT_ROOM_BASE <= room < SPECIAL_EXIT_ROOM_LIMIT:
      screen = util.get_byte(EXIT_DATA_SCREEN_ADDR + i)
      records.append({'index': i, 'room': room, 'screen': screen, 'scroll_x': util.get_word(EXIT_DATA_SCROLL_X_ADDR + i * 2), 'scroll_y': util.get_word(EXIT_DATA_SCROLL_Y_ADDR + i * 2)})
  return records


# Reads special-exit graphics, palette, and screen-origin overrides.
def _special_context(slot):
  return {'aux_gfx': util.get_byte(SP_EXIT_AUX_GFX_ADDR + slot), 'pal_bg': util.get_byte(SP_EXIT_PAL_BG_ADDR + slot), 'top': util.get_word(SP_EXIT_TOP_ADDR + slot * 2), 'left_edge': util.get_word(SP_EXIT_LEFT_EDGE_ADDR + slot * 2)}


# Returns post-load tileset/palette overrides for hardcoded special scenes.
def _scene_profile(area, room, context):
  if room == TRIFORCE_ROOM or area in TRIFORCE_AREAS: return 36, 81, 14, 4
  if area == COOL_BACKGROUND_AREA:
    return 33, 59, util.get_byte(0x80FD1C + COOL_BACKGROUND_SCREEN), 1
  if area in OVERLAY_BASE_AREAS:
    base = OVERLAY_BASE_AREAS[area]; return 0x21 if base & 0x40 else 0x20, util.get_byte(0x80FC9C + base), util.get_byte(0x80FD1C + base), (2 if (base & 0x3f) in (3, 5, 7) else 0) + (1 if base & 0x40 else 0)
  return SPECIAL_MAIN_TILE_THEME, context['aux_gfx'], None, None


# Resolves named 2x2 SP quadrants back to their single runtime room context.
def _named_area_room(area, room_by_screen):
  return NAMED_AREA_ROOMS.get(area, room_by_screen.get(area))


# Renders one runtime special-exit viewport as a 256x192 PNG image.
def _render_exit_record(record, engine_tables, map32_to_map16, map16_to_map8):
  slot = (record['room'] & 0xff) - 0x80
  context = _special_context(slot)
  main_gfx, aux_gfx, pal_bg, mode = _scene_profile(record['screen'], record['room'], context)
  palette = _build_palette(record['screen'], pal_bg if pal_bg is not None else context['pal_bg'], record['room'], engine_tables['ow_bg_pal_info'], mode)
  tile_cache = _build_tile_cache(main_gfx, aux_gfx, engine_tables)
  screen = _render_screen_buffer(record['screen'], palette, tile_cache, map32_to_map16, map16_to_map8)
  if record['room'] == TRIFORCE_ROOM:
    overlay = Image.new('P', screen.size); overlay.putpalette(palette); overlay.paste(_render_area_page(TRIFORCE_AREAS[1], palette, tile_cache, map32_to_map16, map16_to_map8), (0, 0))
    screen = Image.composite(ImageChops.add(screen.convert('RGB'), overlay.convert('RGB'), 2.0), screen.convert('RGB'), overlay.point(lambda p: 255 if p else 0).convert('L'))
  local_x = record['scroll_x'] - context['left_edge']
  local_y = record['scroll_y'] + HUD_HEIGHT if record['room'] == TRIFORCE_ROOM else record['scroll_y'] + HUD_HEIGHT - context['top']
  return _crop_wrapped(screen, local_x, local_y, VISIBLE_WIDTH, VISIBLE_HEIGHT)


# Renders one named SP map slot as a 256x192 playfield crop.
def _render_named_area(area, room, engine_tables, map32_to_map16, map16_to_map8):
  slot = (room & 0xff) - 0x80 if room is not None else area & 0xf
  context = _special_context(slot)
  main_gfx, aux_gfx, pal_bg, mode = _scene_profile(area, room, context)
  bg_palette = pal_bg if pal_bg is not None else util.get_byte(0x80FD1C + area) if area < 136 else context['pal_bg']
  palette_screen, aux2 = (COOL_BACKGROUND_SCREEN, 3) if area == COOL_BACKGROUND_AREA else (area, None)
  palette = _build_palette(palette_screen, bg_palette, room, engine_tables['ow_bg_pal_info'], mode, aux2)
  tile_cache = _build_tile_cache(main_gfx, aux_gfx, engine_tables, CLOUD_ANIM_PACK if area == 0x95 else None)
  page = _render_area_page(area, palette, tile_cache, map32_to_map16, map16_to_map8)
  return page.crop((0, HUD_HEIGHT, VISIBLE_WIDTH, HUD_HEIGHT + VISIBLE_HEIGHT))


# Saves all special-overworld PNGs to editing/special and returns their paths.
def extract_special_area_images(output_dir = OUTPUT_DIR):
  os.makedirs(output_dir, exist_ok = True)
  engine_tables = _load_engine_tables()
  map32_to_map16 = _build_map32_to_map16()
  map16_to_map8 = util.get_words(MAP16_TO_MAP8_ADDR, MAP16_TO_MAP8_WORDS)
  paths = []

  exit_records = _special_exit_records()
  first_room_by_screen = {record['screen']: record['room'] for record in reversed(exit_records)}
  for record in exit_records:
    name = tables.kAreaNames[record['screen']]
    image = _render_exit_record(record, engine_tables, map32_to_map16, map16_to_map8)
    filename = 'room-0x%03x-area-%03d-%s.png' % (record['room'], record['screen'], _slug(name))
    path = os.path.join(output_dir, filename)
    image.save(path)
    paths.append(path)

  for area, name in _named_special_areas():
    image = _render_named_area(area, _named_area_room(area, first_room_by_screen), engine_tables, map32_to_map16, map16_to_map8)
    filename = 'area-%03d-%s.png' % (area, _slug(name))
    path = os.path.join(output_dir, filename)
    image.save(path)
    paths.append(path)

  return paths
