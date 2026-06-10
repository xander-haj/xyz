/*
 * ppu_grove_border_tile_data.h - Grove border tile table declarations.
 *
 * The data file owns the live Master Sword grove tile columns consumed by the
 * grove border renderer.
 */
#ifndef ZELDA3_SNES_PPU_GROVE_BORDER_TILE_DATA_H_
#define ZELDA3_SNES_PPU_GROVE_BORDER_TILE_DATA_H_

#include "src/types.h"

enum {
  /* Covers the grove's full vertical scroll range, not only the entry screen. */
  kMasterSwordGroveBorderRows = 68,
  /* Enough 8-pixel columns to cover the configured widescreen side padding. */
  kMasterSwordGroveBorderColumns = 12,
};

extern uint16 gMasterSwordGroveLeftBorderTiles[kMasterSwordGroveBorderRows]
                                               [kMasterSwordGroveBorderColumns];
extern uint16 gMasterSwordGroveRightBorderTiles[kMasterSwordGroveBorderRows]
                                                [kMasterSwordGroveBorderColumns];

#endif  // ZELDA3_SNES_PPU_GROVE_BORDER_TILE_DATA_H_
