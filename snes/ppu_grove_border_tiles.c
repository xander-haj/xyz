/*
 * ppu_grove_border_tiles.c - Master Sword grove widescreen border renderer.
 *
 * The Master Sword grove uses authored BG2 tile words for its side border
 * columns. Opaque pixels draw from the editable arrays; transparent pixels
 * fall through to the backdrop/color-math path instead of copying temporary
 * capture-time edge tiles.
 */

#include "ppu_grove_border_tiles.h"
#include "ppu_grove_border_tile_data.h"

enum {
  kGroveBg1Layer = 0,
  kGroveBg2Layer = 1,
  kGroveBg2MathLayer = 1,
  kGroveBackdropMathLayer = 5,
};

/*
 * Reset runtime-only grove state when leaving grove fill mode.
 * The table-driven path has no persistent state, but ppu.c calls this through
 * the same mode transition hook used by older grove fill implementations.
 */
void PpuResetGroveTileColumnWidescreenBorders(void) {
}

/*
 * Snap a signed screen coordinate to the first pixel in its mosaic block.
 * The normal PPU mosaic helper is private to ppu.c, so the grove renderer
 * keeps the same floor-style modulo rule for negative widescreen columns.
 */
static int PpuGetGroveMosaicBlockStart(Ppu *ppu, int coord) {
  int size = ppu->mosaicSize;
  if (size <= 1)
    return coord;
  int remainder = coord % size;
  if (remainder < 0)
    remainder += size;
  return coord - remainder;
}

/*
 * Resolve one authored 4bpp BG tile pixel from a tile word.
 * Returns zero for transparent pixels so the caller can resolve the SNES
 * backdrop instead of copying old temporary edge-fill pixels.
 */
static uint8 PpuGetGroveBorderTilePixel(Ppu *ppu, uint layer, uint16 tile, uint bg_x,
                                        uint bg_y) {
  BgLayer *bglayer = &ppu->bgLayer[layer];
  uint tile_row = (tile & 0x8000) ? 7 - (bg_y & 7) : (bg_y & 7);
  uint tile_col = (tile & 0x4000) ? (bg_x & 7) : 7 - (bg_x & 7);
  uint tile_base = bglayer->tileAdr + (tile & 0x3ff) * 16 + tile_row;
  uint32 bits = ppu->vram[tile_base & 0x7fff] | ppu->vram[(tile_base + 8) & 0x7fff] << 16;
  uint8 pixel = (bits >> tile_col) & 1 |
                ((bits >> (7 + tile_col)) & 2) |
                ((bits >> (14 + tile_col)) & 4) |
                ((bits >> (21 + tile_col)) & 8);
  return pixel ? ((tile & 0x1c00) >> 6) + pixel : 0;
}

/*
 * Sample the Lost Woods BG1 overlay at an extended screen coordinate.
 * The grove has no real BG2 side-space, but BG1 fog/canopy data is still a
 * normal overlay tilemap and can be sampled directly for color math.
 */
static uint8 PpuGetGroveBorderBg1SubscreenPixel(Ppu *ppu, int screen_x, uint y) {
  BgLayer *bglayer = &ppu->bgLayer[kGroveBg1Layer];
  int sample_x = screen_x;
  uint sample_y = y;
  if (ppu->mosaicEnabled & (1 << kGroveBg1Layer)) {
    sample_x = PpuGetGroveMosaicBlockStart(ppu, sample_x);
    sample_y = (uint)PpuGetGroveMosaicBlockStart(ppu, (int)sample_y);
  }

  uint bg_x = (uint)(sample_x + bglayer->hScroll);
  uint bg_y = sample_y + bglayer->vScroll;
  uint16 tilemap_adr = bglayer->tilemapAdr + (((bg_y >> 3) & 0x1f) << 5) +
                       ((bg_x >> 3) & 0x1f);
  if ((bg_x & 0x100) && bglayer->tilemapWider)
    tilemap_adr += 0x400;
  if ((bg_y & 0x100) && bglayer->tilemapHigher)
    tilemap_adr += bglayer->tilemapWider ? 0x800 : 0x400;

  uint16 tile = ppu->vram[tilemap_adr & 0x7fff];
  return PpuGetGroveBorderTilePixel(ppu, kGroveBg1Layer, tile, bg_x, bg_y);
}

/*
 * Return the subscreen pixel used for grove color math.
 * Native columns can reuse the already-built sub buffer. Side-border columns
 * sample BG1 by coordinate when the grove's known fog overlay owns the
 * subscreen, keeping the custom BG2 border and fog in the same coordinate
 * space instead of inheriting old edge strips.
 */
static uint8 PpuGetGroveBorderSubscreenPixel(Ppu *ppu, int screen_x, uint y) {
  if ((screen_x < 0 || screen_x >= 256) &&
      ppu->mode == 1 && ppu->screenEnabled[1] == (1 << kGroveBg1Layer) &&
      !(ppu->screenWindowed[1] & (1 << kGroveBg1Layer)))
    return PpuGetGroveBorderBg1SubscreenPixel(ppu, screen_x, y);

  int buffer_x = screen_x + ppu->extraLeftRight;
  if (screen_x >= -ppu->extraLeftCur && screen_x < 256 + ppu->extraRightCur &&
      (unsigned)buffer_x < kPpuXPixels)
    return ppu->bgBuffers[1].data[buffer_x] & 0xff;

  if (ppu->mode == 1 && ppu->screenEnabled[1] == (1 << kGroveBg1Layer) &&
      !(ppu->screenWindowed[1] & (1 << kGroveBg1Layer)))
    return PpuGetGroveBorderBg1SubscreenPixel(ppu, screen_x, y);

  return 0;
}

/*
 * Apply the current PPU brightness and color math to one synthetic main-screen
 * pixel. Opaque table pixels use BG2's math bit; transparent table pixels use
 * the backdrop path, matching how a normal transparent BG2 tile would compose.
 */
static uint32 PpuResolveGroveBorderColor(Ppu *ppu, uint8 pixel, uint8 math_layer,
                                         int screen_x, uint y) {
  uint32 color = ppu->cgram[pixel];
  uint32 r = color & 0x1f;
  uint32 g = (color >> 5) & 0x1f;
  uint32 b = (color >> 10) & 0x1f;
  uint32 fixed_color = ppu->fixedColorR | ppu->fixedColorG << 5 | ppu->fixedColorB << 10;
  uint8 *color_map = ppu->brightnessMult;

  if (ppu->preventMathMode != 3 && (ppu->mathEnabled & (1 << math_layer))) {
    uint32 color2;
    if (ppu->addSubscreen) {
      uint8 sub_pixel = PpuGetGroveBorderSubscreenPixel(ppu, screen_x, y);
      color2 = sub_pixel ? ppu->cgram[sub_pixel] : fixed_color;
      if (sub_pixel)
        color_map = ppu->halfColor ? ppu->brightnessMultHalf : ppu->brightnessMult;
    } else {
      color2 = fixed_color;
      color_map = ppu->halfColor ? ppu->brightnessMultHalf : ppu->brightnessMult;
    }

    uint32 r2 = color2 & 0x1f;
    uint32 g2 = (color2 >> 5) & 0x1f;
    uint32 b2 = (color2 >> 10) & 0x1f;
    if (ppu->subtractColor) {
      r = (r >= r2) ? r - r2 : 0;
      g = (g >= g2) ? g - g2 : 0;
      b = (b >= b2) ? b - b2 : 0;
    } else {
      r += r2;
      g += g2;
      b += b2;
    }
  }

  return color_map[b] | color_map[g] << 8 | color_map[r] << 16;
}

/*
 * Convert the absolute BG2 scroll row used by the normal renderer into the
 * editable table row. Values outside the captured strip clamp to the nearest
 * row so bottom overscan and transition edges still respond to table edits.
 */
static int PpuGetGroveBorderTableRow(Ppu *ppu, uint y) {
  uint bg_y = y + ppu->bgLayer[kGroveBg2Layer].vScroll;
  return IntMin(bg_y >> 3, kMasterSwordGroveBorderRows - 1);
}

/*
 * Fill the Master Sword grove's widescreen-only side borders from the editable
 * BG2 tile-word tables. This path deliberately does not copy or preserve 4:3
 * edge tiles; the data arrays are the source of truth for every synthetic
 * border column.
 *
 * The right table is anchored to the native 4:3 edge: column 0 touches the
 * native screen's right edge and columns increase outward to the right. The
 * left table is authored in screen order: column 0 is the far-left side of the
 * border and the final column touches the native screen's left edge.
 */
void PpuFillGroveTileColumnWidescreenBorders(Ppu *ppu, uint32 *dst, int full_width,
                                             int missing_left, int missing_right, uint y) {
  (void)missing_left;
  (void)missing_right;

  int row = PpuGetGroveBorderTableRow(ppu, y);
  uint bg_y = y + ppu->bgLayer[kGroveBg2Layer].vScroll;
  int table_width = kMasterSwordGroveBorderColumns * 8;
  int side_width = IntMin(ppu->extraLeftRight, table_width);

  if (side_width > 0) {
    int left_start = ppu->extraLeftRight - side_width;
    for (int x = left_start; x < ppu->extraLeftRight; x++) {
      int table_x = table_width - side_width + x - left_start;
      int screen_x = x - ppu->extraLeftRight;
      int column = table_x >> 3;
      uint16 tile = gMasterSwordGroveLeftBorderTiles[row][column];
      uint8 pixel = PpuGetGroveBorderTilePixel(ppu, kGroveBg2Layer, tile, table_x, bg_y);
      uint8 math_layer = pixel ? kGroveBg2MathLayer : kGroveBackdropMathLayer;
      dst[x] = PpuResolveGroveBorderColor(ppu, pixel, math_layer, screen_x, y);
    }
  }

  if (side_width > 0) {
    int right_start = ppu->extraLeftRight + 256;
    int right_end = IntMin(right_start + side_width, full_width);
    for (int x = right_start; x < right_end; x++) {
      int distance = x - right_start;
      int screen_x = x - ppu->extraLeftRight;
      int column = distance >> 3;
      uint16 tile = gMasterSwordGroveRightBorderTiles[row][column];
      uint8 pixel = PpuGetGroveBorderTilePixel(ppu, kGroveBg2Layer, tile, distance, bg_y);
      uint8 math_layer = pixel ? kGroveBg2MathLayer : kGroveBackdropMathLayer;
      dst[x] = PpuResolveGroveBorderColor(ppu, pixel, math_layer, screen_x, y);
    }
  }
}
