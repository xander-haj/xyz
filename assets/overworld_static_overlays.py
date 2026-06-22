"""ZScream-style static overworld overlay tile writes."""

from __future__ import annotations

from functools import lru_cache

SCREEN_COUNT = 160
VANILLA_SCREEN_COUNT = 128
OVERLAY_POINTERS_PC = 0x077664
OVERLAY_EXPANDED_MARKER_PC = 0x077676
OVERLAY_EXPANDED_PTRS_PC = 0x077677
OVERLAY_BANK = 0x8E0000


def normalize_static_overlay_rows(rows, area: int, max_x: int = 63, max_y: int = 63) -> list[dict]:
  """Return validated static overlay rows in canonical dict form."""
  result = []
  for index, row in enumerate(rows or []):
    x, y, tile = overlay_row_values(row)
    if x < 0 or x > max_x or y < 0 or y > max_y:
      raise ValueError("Overworld overlay row %d in area %d is outside %d,%d." % (
        index, area, max_x, max_y))
    if tile < 0 or tile > 0xffff:
      raise ValueError("Overworld overlay tile in area %d must be 0..0xffff." % area)
    result.append({"x": x, "y": y, "tile": tile})
  return result


def overlay_row_values(row) -> tuple[int, int, int]:
  """Read x/y/tile from either YAML-list or YAML-dict overlay row shapes."""
  if isinstance(row, dict):
    return (
      overlay_int(row.get("x", 0), "x"),
      overlay_int(row.get("y", 0), "y"),
      overlay_int(row.get("tile", row.get("tile_id", 0)), "tile"),
    )
  if isinstance(row, (list, tuple)) and len(row) >= 3:
    return overlay_int(row[0], "x"), overlay_int(row[1], "y"), overlay_int(row[2], "tile")
  raise ValueError("Overworld overlay rows must be {x, y, tile} or [x, y, tile].")


def overlay_int(value, label: str) -> int:
  """Parse one strict integer field from an overlay tile-write row."""
  if isinstance(value, bool):
    raise ValueError("Overworld overlay %s must be an integer, not boolean." % label)
  if isinstance(value, int):
    return value
  if isinstance(value, str):
    return int(value, 0)
  raise ValueError("Overworld overlay %s must be an integer." % label)


@lru_cache(maxsize=1)
def rom_static_overlay_infos() -> dict[int, list[dict]]:
  """Parse vanilla or ZScream-expanded static overlay streams from util.ROM."""
  import util
  return read_rom_static_overlays(util.ROM)


def read_rom_static_overlays(rom) -> dict[int, list[dict]]:
  """Read static overlay ASM streams with the opcode model used by ZScream."""
  expanded = rom.get_byte(pc_to_snes(OVERLAY_EXPANDED_MARKER_PC)) == 0x6b
  count = SCREEN_COUNT if expanded else VANILLA_SCREEN_COUNT
  result = {}
  for area in range(count):
    start = expanded_overlay_pointer(rom, area) if expanded else vanilla_overlay_pointer(rom, area)
    rows = parse_overlay_stream(rom, start)
    if rows:
      result[area] = rows
  return result


def vanilla_overlay_pointer(rom, area: int) -> int:
  """Resolve the original 16-bit overlay pointer in bank 0x8e."""
  ptr = rom.get_word(pc_to_snes(OVERLAY_POINTERS_PC + area * 2))
  return OVERLAY_BANK | ptr


def expanded_overlay_pointer(rom, area: int) -> int:
  """Resolve the ZScream ASM v3 overlay pointer table when installed."""
  table = pc_to_snes(OVERLAY_EXPANDED_PTRS_PC + area * 3)
  return rom.get_byte(table) | rom.get_byte(table + 1) << 8 | rom.get_byte(table + 2) << 16


def parse_overlay_stream(rom, address: int) -> list[dict]:
  """Decode one static overlay stream into x/y/tile records."""
  rows = []
  a = 0
  x = 0
  seen = set()
  while True:
    if address in seen:
      break
    seen.add(address)
    opcode = rom.get_byte(address)
    if opcode in (0x60, 0x6b, 0xff):
      break
    if opcode == 0xa9:
      a = rom.get_word(address + 1)
      address += 3
    elif opcode == 0xa2:
      x = rom.get_word(address + 1)
      address += 3
    elif opcode == 0x8d:
      rows.append(tile_write(rom.get_word(address + 1), a, 0))
      address += 3
    elif opcode == 0x9d:
      rows.append(tile_write(rom.get_word(address + 1), a, x))
      address += 3
    elif opcode == 0x8f:
      rows.append(tile_write(rom.get_word(address + 1), a, x))
      address += 4
    elif opcode == 0x1a:
      a = (a + 1) & 0xffff
      address += 1
    elif opcode == 0x4c:
      address = OVERLAY_BANK | rom.get_word(address + 1)
    else:
      break
  return rows


def tile_write(address: int, tile: int, x_offset: int) -> dict:
  """Convert a ZScream STA target into a 64-column map16 coordinate."""
  pos = (address & 0x1fff) + x_offset
  index = pos // 2
  return {"x": index % 64, "y": index // 64, "tile": tile & 0xffff}


def pc_to_snes(pc: int) -> int:
  """Convert a LoROM PC offset into the SNES address convention used by util."""
  bank = pc // 0x8000
  return 0x800000 | bank << 16 | 0x8000 | (pc % 0x8000)
