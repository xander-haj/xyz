"""Shared map32 grid serializers for editable overworld terrain sources.

This module is the narrow bridge between ROM-compressed overworld map streams
and the JSON grid files that future overworld editing tools can modify. The
shared helpers keep extraction, compilation, and viewer dumping on the same
validation rules so the editable source path cannot silently drift.
"""

from __future__ import annotations

import json
import os
from typing import Any

import util

# The format tag lets builders reject stale or unrelated JSON terrain files.
FORMAT = "zelda3-overworld-map32-grid-v1"

# Zelda 3 has 160 overworld map32 streams: 128 normal areas plus 32 Special slots.
SCREEN_COUNT = 160

# Each overworld area stores a 16x16 grid of 32x32-pixel map32 ids.
GRID_WIDTH = 16
GRID_HEIGHT = 16
CELL_COUNT = GRID_WIDTH * GRID_HEIGHT

# These ROM pointer tables locate the split high-byte and low-byte map32 streams.
ROM_HIGH_POINTER_TABLE = 0x82F94D
ROM_LOW_POINTER_TABLE = 0x82FB2D

# The default extracted source directory is relative to assets/, matching restool.py.
DEFAULT_SOURCE_DIR = "overworld_maps"


def validate_screen(screen: int) -> None:
  """Validate one overworld screen id.

  Parameters:
    screen: Candidate screen index from a caller or JSON file.
  Returns:
    None.
  Raises:
    ValueError: If the screen is outside the 0..159 overworld stream range.
  """
  if not 0 <= screen < SCREEN_COUNT:
    raise ValueError("overworld screen %r is outside 0..%d" % (screen, SCREEN_COUNT - 1))


def source_path(source_dir: str, screen: int) -> str:
  """Build the canonical JSON path for one extracted map32 source file.

  Parameters:
    source_dir: Directory containing three-digit screen JSON files.
    screen: Overworld screen index.
  Returns:
    Relative or absolute path to the requested JSON source file.
  """
  validate_screen(screen)
  return os.path.join(source_dir, "%03d.json" % screen)


def has_any_source_files(source_dir: str = DEFAULT_SOURCE_DIR) -> bool:
  """Check whether a map32 source directory appears to contain editable grids.

  Parameters:
    source_dir: Directory to inspect for JSON source files.
  Returns:
    True when at least one `.json` source file is present, otherwise False.
  """
  if not os.path.isdir(source_dir):
    return False
  return any(name.endswith(".json") for name in os.listdir(source_dir))


def load_all_map32_sources(source_dir: str = DEFAULT_SOURCE_DIR) -> list[list[int]]:
  """Load every overworld map32 grid from an editable source directory.

  Parameters:
    source_dir: Directory that must contain 000.json through 159.json.
  Returns:
    A list of 160 flat 256-entry map32 id arrays, indexed by screen id.
  Raises:
    FileNotFoundError: If the directory or any required screen file is missing.
    ValueError: If any JSON file has the wrong format, dimensions, or values.
  """
  if not os.path.isdir(source_dir):
    raise FileNotFoundError("overworld map32 source directory is missing: %s" % source_dir)
  return [load_map32_source(source_dir, screen) for screen in range(SCREEN_COUNT)]


def load_map32_source(source_dir: str, screen: int) -> list[int]:
  """Load and validate one JSON map32 grid.

  Parameters:
    source_dir: Directory containing extracted terrain JSON files.
    screen: Overworld screen index to load.
  Returns:
    Flat 256-entry list of 16-bit map32 ids in row-major order.
  Raises:
    FileNotFoundError: If the requested JSON file is absent.
    ValueError: If the JSON schema or grid values are invalid.
  """
  path = source_path(source_dir, screen)
  with open(path, "r") as file:
    data = json.load(file)
  return decode_source_payload(data, screen, path)


def decode_source_payload(data: dict[str, Any], expected_screen: int, path: str) -> list[int]:
  """Validate and flatten one parsed map32 source JSON object.

  Parameters:
    data: Parsed JSON object.
    expected_screen: Screen id implied by the file name or caller.
    path: File path used only for diagnostic messages.
  Returns:
    Flat 256-entry list of map32 ids.
  Raises:
    ValueError: If the payload does not match the source schema.
  """
  if data.get("format") != FORMAT:
    raise ValueError("%s has unsupported map32 format %r" % (path, data.get("format")))
  if data.get("screen") != expected_screen:
    raise ValueError("%s declares screen %r, expected %d" % (path, data.get("screen"), expected_screen))
  if data.get("width") != GRID_WIDTH or data.get("height") != GRID_HEIGHT:
    raise ValueError("%s must be a %dx%d map32 grid" % (path, GRID_WIDTH, GRID_HEIGHT))
  return flatten_grid(data.get("map32"), expected_screen, path)


def flatten_grid(rows: Any, screen: int, path: str = "<memory>") -> list[int]:
  """Flatten a 16x16 JSON grid while validating every cell.

  Parameters:
    rows: Candidate nested list from JSON or an in-memory editor.
    screen: Screen id used for error messages.
    path: Source label used for error messages.
  Returns:
    Flat 256-entry row-major list of map32 ids.
  Raises:
    ValueError: If the value is not a 16-row grid of valid 16-bit integers.
  """
  if not isinstance(rows, list) or len(rows) != GRID_HEIGHT:
    raise ValueError("%s screen %d must contain %d map32 rows" % (path, screen, GRID_HEIGHT))
  words: list[int] = []
  for y, row in enumerate(rows):
    if not isinstance(row, list) or len(row) != GRID_WIDTH:
      raise ValueError("%s screen %d row %d must contain %d cells" % (path, screen, y, GRID_WIDTH))
    for x, value in enumerate(row):
      if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError("%s screen %d cell %d,%d has invalid map32 id %r" % (
          path, screen, x, y, value))
      words.append(value)
  return words


def validate_words(words: list[int], screen: int | None = None) -> list[int]:
  """Validate a flat 256-entry map32 word list.

  Parameters:
    words: Candidate row-major list of map32 ids.
    screen: Optional screen id used in diagnostics.
  Returns:
    The original word list when valid.
  Raises:
    ValueError: If the list length or any value is invalid.
  """
  label = "screen %d" % screen if screen is not None else "map32 grid"
  if len(words) != CELL_COUNT:
    raise ValueError("%s must contain %d map32 ids" % (label, CELL_COUNT))
  for index, value in enumerate(words):
    if type(value) is not int or not 0 <= value <= 0xFFFF:
      raise ValueError("%s cell %d has invalid map32 id %r" % (label, index, value))
  return words


def words_to_grid(words: list[int], screen: int | None = None) -> list[list[int]]:
  """Convert a flat map32 word list into the persisted 16x16 grid shape.

  Parameters:
    words: Flat row-major map32 id list.
    screen: Optional screen id used in validation diagnostics.
  Returns:
    Nested list with 16 rows of 16 map32 ids each.
  """
  validate_words(words, screen)
  return [words[y * GRID_WIDTH:(y + 1) * GRID_WIDTH] for y in range(GRID_HEIGHT)]


def read_rom_stream(pointer_table: int, screen: int, rom, offset_is_be: bool = True) -> dict[str, Any]:
  """Read and decompress one ROM-backed overworld map32 byte stream.

  Parameters:
    pointer_table: SNES pointer table for either high-byte or low-byte streams.
    screen: Overworld screen index.
    rom: Loaded ROM object from util.load_rom.
    offset_is_be: Backreference byte order expected by util.decomp.
  Returns:
    Dict containing the source address, compressed bytes, decoded bytes, and lengths.
  Raises:
    ValueError: If the decoded stream is shorter than one 16x16 screen.
  """
  validate_screen(screen)
  address = rom.get_24(pointer_table + screen * 3)
  decoded, compressed_length = util.decomp(address, rom.get_byte, offset_is_be, True)
  if len(decoded) < CELL_COUNT:
    raise ValueError("ROM overworld screen %d decoded to only %d bytes" % (screen, len(decoded)))
  return {
    "address": address,
    "compressed_length": compressed_length,
    "compressed": bytes(rom.get_bytes(address, compressed_length)),
    "decoded": bytes(decoded[:CELL_COUNT]),
  }


def decode_rom_words(screen: int, rom) -> tuple[list[int], dict[str, Any], dict[str, Any]]:
  """Decode one ROM screen into map32 ids plus high/low source metadata.

  Parameters:
    screen: Overworld screen index.
    rom: Loaded ROM object from util.load_rom.
  Returns:
    Tuple of flat map32 words, high-byte stream metadata, and low-byte stream metadata.
  """
  high = read_rom_stream(ROM_HIGH_POINTER_TABLE, screen, rom, True)
  low = read_rom_stream(ROM_LOW_POINTER_TABLE, screen, rom, True)
  words = [low["decoded"][index] | (high["decoded"][index] << 8) for index in range(CELL_COUNT)]
  return words, high, low


def write_grid_file(output_dir: str, screen: int, words: list[int], source: str, extra: dict[str, Any]) -> str:
  """Write one validated map32 word list as an editable JSON grid.

  Parameters:
    output_dir: Destination directory for three-digit screen JSON files.
    screen: Overworld screen index.
    words: Flat 256-entry map32 id list.
    source: Human-readable source label stored in the JSON.
    extra: Additional metadata to merge into the top-level payload.
  Returns:
    Path written by the function.
  Side effects:
    Creates the output directory and writes one JSON file.
  """
  validate_screen(screen)
  payload = {
    "format": FORMAT,
    "screen": screen,
    "source": source,
    "width": GRID_WIDTH,
    "height": GRID_HEIGHT,
    "map32": words_to_grid(words, screen),
  }
  payload.update(extra)
  os.makedirs(output_dir, exist_ok=True)
  path = source_path(output_dir, screen)
  with open(path, "w") as file:
    json.dump(payload, file, indent=2)
    file.write("\n")
  return path


def write_base_maps_from_rom(output_dir: str, rom) -> list[str]:
  """Extract all ROM-backed overworld map32 streams into editable JSON grids.

  Parameters:
    output_dir: Destination directory, normally assets/overworld_maps.
    rom: Loaded ROM object from util.load_rom.
  Returns:
    List of JSON paths written, one per overworld screen.
  Side effects:
    Creates or overwrites 160 local extracted JSON files.
  """
  paths = []
  for screen in range(SCREEN_COUNT):
    words, high, low = decode_rom_words(screen, rom)
    paths.append(write_grid_file(output_dir, screen, words, "extracted-from-rom", {
      "source_addresses": {
        "high": hex(high["address"]),
        "low": hex(low["address"]),
      },
    }))
  return paths


def split_words(words: list[int], screen: int | None = None) -> tuple[list[int], list[int]]:
  """Split 16-bit map32 ids into the high-byte and low-byte streams the engine expects.

  Parameters:
    words: Flat row-major map32 id list.
    screen: Optional screen id used in validation diagnostics.
  Returns:
    Tuple of high-byte list and low-byte list, each 256 entries long.
  """
  validate_words(words, screen)
  high = [(value >> 8) & 0xFF for value in words]
  low = [value & 0xFF for value in words]
  return high, low


def compress_store(values: list[int]) -> bytes:
  """Encode bytes as a deterministic literal-only Zelda 3 LZ stream.

  Parameters:
    values: Byte values to store in compressed-stream form.
  Returns:
    Valid LZ stream bytes using only literal chunks and the 0xFF terminator.
  """
  encoded = bytearray()
  index = 0
  while index < len(values):
    chunk = values[index:index + 1024]
    encoded.append(0xE0 | ((len(chunk) - 1) >> 8))
    encoded.append((len(chunk) - 1) & 0xFF)
    encoded.extend(chunk)
    index += len(chunk)
  encoded.append(0xFF)
  return bytes(encoded)


def encode_word_streams(words: list[int], screen: int | None = None) -> tuple[bytes, bytes]:
  """Encode one map32 grid into high-byte and low-byte compressed streams.

  Parameters:
    words: Flat 256-entry map32 id list.
    screen: Optional screen id used in validation diagnostics.
  Returns:
    Tuple of compressed high-byte stream bytes and compressed low-byte stream bytes.
  """
  high, low = split_words(words, screen)
  return compress_store(high), compress_store(low)
