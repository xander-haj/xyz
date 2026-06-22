"""
Extract source-backed sprite OAM draw tables for the overworld viewer.
"""

import os

from dump_overworld_support import extract_array, parse_matrix, parse_numbers, read_text


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPRITE_MAIN_C = os.path.join(PROJECT_ROOT, "src", "sprite_main.c")
SPRITE_C = os.path.join(PROJECT_ROOT, "src", "sprite.c")

SOLDIER_TABLES = {
  "gfx": "kSoldier_Gfx",
  "draw1_char": "kSoldier_Draw1_Char",
  "draw1_flags": "kSoldier_Draw1_Flags",
  "draw1_yd": "kSoldier_Draw1_Yd",
  "draw2_xd": "kSoldier_Draw2_Xd",
  "draw2_yd": "kSoldier_Draw2_Yd",
  "draw2_char": "kSoldier_Draw2_Char",
  "draw2_flags": "kSoldier_Draw2_Flags",
  "draw2_big": "kSoldier_Draw2_Big",
  "draw2_oam_idx": "kSoldier_Draw2_OamIdx",
  "draw3_xd": "kSoldier_Draw3_Xd",
  "draw3_yd": "kSoldier_Draw3_Yd",
  "draw3_char": "kSoldier_Draw3_Char",
  "draw3_flags": "kSoldier_Draw3_Flags",
  "draw3_oam_idx": "kSoldier_Draw3_OamIdx",
}

COMMON_TABLES = {
  "single_large_base": "kSprite_PrepAndDrawSingleLarge_Tab1",
  "single_large_tiles": "kSprite_PrepAndDrawSingleLarge_Tab2",
  "absorbable_mode": "kAbsorbable_Tab1",
  "absorbable_number": "kAbsorbable_Tab2",
  "numbered_x": "kNumberedAbsorbable_X",
  "numbered_y": "kNumberedAbsorbable_Y",
  "numbered_char": "kNumberedAbsorbable_Char",
  "numbered_size": "kNumberedAbsorbable_Ext",
}

STATIC_RECIPES = {
  0x51: [{"symbol": "kArmos_Dmd", "start": 0, "count": 2}],
  0x57: [{"symbol": "kDesertBarrier_Dmd", "start": 0, "count": 4}],
  0xad: [{"symbol": "kOldMountainMan_Dmd1", "start": 0, "count": 2}],
  0xb5: [{"symbol": "kBombShopEntity_Dmd", "start": 0, "count": 1}],
  0xbb: [{"symbol": "kShopkeeper_Dmd", "start": 0, "count": 2}],
  0xbc: [{"symbol": "kDrinkingGuy_Dmd", "start": 0, "count": 3}],
  0xc4: [{"symbol": "kBully_Dmd", "start": 0, "count": 2}],
  0xc8: [{"symbol": "kBigFaerie_Dmd", "start": 0, "count": 4}],
  0xd2: [
    {"symbol": "kFish_Dmd", "start": 0, "count": 2, "x": 4},
    {"symbol": "kFish_Dmd2", "start": 0, "count": 3, "x": 4},
  ],
  0xd3: [{"symbol": "kStal_Dmd", "start": 0, "count": 1}],
  0xd4: [{"symbol": "kLandmine_Dmd", "start": 0, "count": 2}],
  0xe9: [{"symbol": "kShopkeeper_Dmd", "start": 0, "count": 2}],
  0xed: [{"symbol": "kSomariaPlatform_Dmd", "start": 12, "count": 4}],
}

DMD_RECIPES = {
  0x01: [{"symbol": "kVulture_Dmd", "start": 0, "count": 2}],
  0x0e: [{"symbol": "kSnapDragon_Dmd", "start": 0, "count": 4}],
  0x11: [{"symbol": "kHinox_Dmd", "start": 0, "count": 4}],
  0x12: [{"symbol": "kMoblin_Dmd", "start": 0, "count": 4}],
  0x1a: [{"symbol": "kSmithyFrog_Dmd", "start": 0, "count": 1}],
  0x22: [{"symbol": "kRopa_Dmd", "start": 0, "count": 3}],
  0x25: [{"symbol": "kTalkingTree_Dmd", "start": 4, "count": 4}],
  0x28: [{"symbol": "kStoryTeller_Dmd", "start": 0, "count": 1}],
  0x2a: [{"symbol": "kSweepingLadyDmd", "start": 0, "count": 2}],
  0x2b: [{"symbol": "kHobo_Dmd", "start": 0, "count": 4}],
  0x2c: [{"symbol": "kLumberJacks_Dmd", "start": 0, "count": 11}],
  0x2e: [{"symbol": "kFluteBoy_Dmd", "start": 0, "count": 4}],
  0x2f: [{"symbol": "kLadyDmd", "start": 0, "count": 2}],
  0x30: [{"symbol": "kMazeGameGuy_Dmd", "start": 0, "count": 2}],
  0x32: [{"symbol": "kQuarrelBros_Dmd", "start": 0, "count": 2}],
  0x34: [{"symbol": "kYoungSnitchLady_Dmd", "start": 0, "count": 2}],
  0x35: [{"symbol": "kInnKeeper_Dmd", "start": 0, "count": 2}],
  0x39: [{"symbol": "kMiddleAgedMan_Dmd", "start": 0, "count": 2}],
  0x3c: [{"symbol": "kTroughBoy_Dmd", "start": 0, "count": 2}],
  0x3d: [{"symbol": "kLadyDmd", "start": 0, "count": 2}],
  0x40: [{"symbol": "kEvilBarrier_Dmd", "start": 0, "count": 9, "y": 8}],
  0x51: [{"symbol": "kArmos_Dmd", "start": 0, "count": 2}],
  0x57: [{"symbol": "kDesertBarrier_Dmd", "start": 0, "count": 4}],
  0x74: [{"symbol": "kRunningMan_Dmd", "start": 8, "count": 2}],
  0x75: [{"symbol": "kBottleVendor_Dmd", "start": 0, "count": 2}],
  0x78: [{"symbol": "kElderWife_Dmd", "start": 0, "count": 2}],
  0x9e: [{"symbol": "kFluteBoyOstrich_Dmd", "start": 0, "count": 4}],
  0xa8: [{"symbol": "kBomber_Dmd", "start": 0, "count": 2}],
  0xa9: [{"symbol": "kBomber_Dmd", "start": 0, "count": 2}],
  0xaa: [{"symbol": "kPikit_Dmd", "start": 0, "count": 2}],
  0xad: [{"symbol": "kOldMountainMan_Dmd1", "start": 0, "count": 2}],
  0xb5: [{"symbol": "kBombShopEntity_Dmd", "start": 0, "count": 1}],
  0xb6: [{"symbol": "kKiki_Dmd1", "start": 0, "count": 2}],
  0xb9: [{"symbol": "kBully_Dmd", "start": 0, "count": 2}],
  0xbb: [{"symbol": "kShopkeeper_Dmd", "start": 0, "count": 2}],
  0xbc: [{"symbol": "kDrinkingGuy_Dmd", "start": 0, "count": 3}],
  0xc0: [{"symbol": "kGreatCatfish_Dmd", "start": 0, "count": 4}],
  0xc4: [{"symbol": "kThief_Dmd", "start": 0, "count": 2}],
  0xc8: [{"symbol": "kBigFaerie_Dmd", "start": 0, "count": 4}],
  0xc9: [{"symbol": "kTektite_Dmd", "start": 0, "count": 2}],
  0xd0: [{"symbol": "kLynel_Dmd", "start": 0, "count": 3}],
  0xd2: [{"symbol": "kFish_Dmd", "start": 0, "count": 2},
         {"symbol": "kFish_Dmd2", "start": 0, "count": 3}],
  0xd3: [{"symbol": "kStal_Dmd", "start": 0, "count": 2}],
  0xd4: [{"symbol": "kLandmine_Dmd", "start": 0, "count": 2}],
  0xd5: [{"symbol": "kDiggingGameGuy_Dmd", "start": 0, "count": 3}],
  0xe8: [{"symbol": "kFakeSword_Dmd", "start": 0, "count": 2}],
  0xe9: [{"symbol": "kShopkeeper_Dmd", "start": 0, "count": 2}],
  0xed: [{"symbol": "kSomariaPlatform_Dmd", "start": 12, "count": 4}],
  0xf2: [{"symbol": "kMedallionTablet_Dmd", "start": 0, "count": 4}],
}

CUSTOM_ARRAY_TABLES = [
  "kBuzzBlob_DrawX",
  "kBuzzBlob_DrawY",
  "kBuzzBlob_DrawChar",
  "kBuzzBlob_DrawFlags",
  "kBuzzBlob_DrawExt",
  "kCoveredRupeeCrab_DrawY",
  "kCoveredRupeeCrab_DrawChar",
  "kCoveredRupeeCrab_DrawFlags",
  "kCrab_Draw_X",
  "kCrab_Draw_Char",
  "kCrab_Draw_Flags",
  "kGerudoMan_Draw_X",
  "kGerudoMan_Draw_Y",
  "kGerudoMan_Draw_Char",
  "kGerudoMan_Draw_Flags",
  "kGerudoMan_Draw_Big",
  "kMasterSword_Draw_X",
  "kMasterSword_Draw_Y",
  "kMasterSword_Draw_Char",
  "kOctoballoon_Draw_X",
  "kOctoballoon_Draw_Y",
  "kOctoballoon_Draw_Char",
  "kOctoballoon_Draw_Flags",
  "kRecruit_Draw_X",
  "kRecruit_Draw_Char",
  "kRecruit_Draw_Flags",
  "kToppo_Draw_X",
  "kToppo_Draw_Y",
  "kToppo_Draw_Char",
  "kToppo_Draw_Flags",
  "kToppo_Draw_Big",
  "kTutorialSoldier_X",
  "kTutorialSoldier_Y",
  "kTutorialSoldier_Char",
  "kTutorialSoldier_Flags",
  "kTutorialSoldier_Big",
  "kWalkingZora_Draw_Char",
  "kWalkingZora_Draw_Flags",
  "kWalkingZora_Draw_Char2",
  "kWalkingZora_Draw_Flags2",
  "kZora_Draw_X",
  "kZora_Draw_Y",
  "kZora_Draw_Char",
  "kZora_Draw_Flags",
  "kZora_Draw_Big",
  "kZoraKing_Draw_X0",
  "kZoraKing_Draw_Y0",
  "kZoraKing_Draw_Char0",
  "kZoraKing_Draw_Flags0",
]

CUSTOM_ROW_TABLES = [
  "kWitch_DrawDataA",
  "kWitch_DrawDataB",
  "kWitch_DrawDataC",
]


def dump_sprite_oam_tables():
  sprite_main = read_text(SPRITE_MAIN_C)
  sprite_common = read_text(SPRITE_C)
  return {
    "soldier": {
      key: parse_numbers(extract_array(sprite_main, name))
      for key, name in SOLDIER_TABLES.items()
    },
    "common": {
      key: parse_numbers(extract_array(sprite_common, name))
      for key, name in COMMON_TABLES.items()
    },
    "arrays": dump_number_arrays(sprite_main, CUSTOM_ARRAY_TABLES),
    "dmd": dump_static_recipes(sprite_main, DMD_RECIPES),
    "rows": dump_row_arrays(sprite_main, CUSTOM_ROW_TABLES),
    "static": dump_static_recipes(sprite_main, STATIC_RECIPES),
  }


def dump_number_arrays(source, names):
  return {
    name: parse_numbers(extract_array(source, name))
    for name in names
  }


def dump_row_arrays(source, names):
  return {
    name: parse_matrix(extract_array(source, name))
    for name in names
  }


def dump_static_recipes(source, recipes):
  return {
    "%d" % sprite_type: build_static_recipe(source, parts)
    for sprite_type, parts in recipes.items()
  }


def build_static_recipe(source, parts):
  entries = []
  for part in parts:
    rows = parse_matrix(extract_array(source, part["symbol"]))
    for row in rows[part["start"]:part["start"] + part["count"]]:
      entries.append({
        "x": row[0] + part.get("x", 0),
        "y": row[1] + part.get("y", 0),
        "char_flags": row[2],
        "size": row[3],
        "source": part["symbol"],
      })
  return entries
