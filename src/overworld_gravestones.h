#pragma once

#include "types.h"

enum {
  kOverworldGravestoneCount = 15,
  kOverworldGravestoneStairsIndex = 0x0d,
  kOverworldGravestoneHoleIndex = 0x0e,
};

extern const uint16 kOverworldGravestoneX[kOverworldGravestoneCount];
extern const uint16 kOverworldGravestoneY[kOverworldGravestoneCount];
extern const uint16 kOverworldGravestoneTilemapPos[kOverworldGravestoneCount];
extern const uint8 kOverworldGravestoneCounter[kOverworldGravestoneCount];
