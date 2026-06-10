/*
 * ppu_grove_border_tiles.h - Master Sword grove widescreen border fill API.
 *
 * ppu.c calls this module when the grove needs authored BG2 tile columns
 * instead of the generic two-tile repeat used by structured rooms.
 */
#ifndef ZELDA3_SNES_PPU_GROVE_BORDER_TILES_H_
#define ZELDA3_SNES_PPU_GROVE_BORDER_TILES_H_

#include "ppu.h"

/*
 * Fill grove-only widescreen side borders from authored BG2 tile words.
 * The missing side widths are accepted for the shared PPU fill hook, but this
 * path intentionally overwrites each complete side-border band.
 */
void PpuFillGroveTileColumnWidescreenBorders(Ppu *ppu, uint32 *dst, int full_width,
                                             int missing_left, int missing_right, uint y);

/*
 * Reset grove-only runtime state when the renderer leaves grove mode.
 * The table-driven path currently has no persistent state, but keeps this hook
 * available for the PPU mode transition code.
 */
void PpuResetGroveTileColumnWidescreenBorders(void);

#endif  // ZELDA3_SNES_PPU_GROVE_BORDER_TILES_H_
