"""Map32 stream dumping helpers for the overworld viewer dump.

The viewer consumes explicit map32 words, decoded JSON, and high/low compressed
stream artifacts. This module keeps that terrain-specific dump path separate
from the broader palette, graphics, metadata, and source-table dump code.
"""

import os

from dump_overworld_support import ensure_dir, uint16le, write_bytes, write_json
import overworld_map32
import util

# Re-exported constants keep dump_overworld.py's manifest values tied to the serializer.
SCREEN_COUNT = overworld_map32.SCREEN_COUNT
MAP32_COUNT = overworld_map32.CELL_COUNT
HI_PTR_TABLE = overworld_map32.ROM_HIGH_POINTER_TABLE
LO_PTR_TABLE = overworld_map32.ROM_LOW_POINTER_TABLE


def dump_map32_streams(manifest, out_dir, source_dir=None):
  """Write all map32 stream files required by the browser viewer.

  Parameters:
    manifest: Mutable dump manifest that receives the map32 file patterns.
    out_dir: Root overworld dump directory.
    source_dir: Optional generated overworld_maps directory.
  Returns:
    None.
  Side effects:
    Writes compressed stream files, decoded JSON, little-endian word binaries,
    and map32 stream metadata under the dump directory.
  """
  hi_dir = os.path.join(out_dir, "map32", "high_compressed")
  lo_dir = os.path.join(out_dir, "map32", "low_compressed")
  decoded_dir = os.path.join(out_dir, "map32", "decoded")
  words_dir = os.path.join(out_dir, "map32", "words")
  for path in [hi_dir, lo_dir, decoded_dir, words_dir]:
    ensure_dir(path)

  # A partial source directory should fail through load_all_map32_sources instead
  # of silently mixing edited JSON screens with ROM-backed screens.
  source_maps = None
  candidate_dir = source_dir or overworld_map32.DEFAULT_SOURCE_DIR
  if overworld_map32.has_any_source_files(candidate_dir):
    source_maps = overworld_map32.load_all_map32_sources(candidate_dir)

  stream_meta = []
  for screen in range(SCREEN_COUNT):
    hi, lo, map32, source, source_file = build_stream_records(screen, source_maps, candidate_dir)
    validate_decoded_lengths(screen, hi, lo)
    write_stream_files(hi_dir, lo_dir, decoded_dir, words_dir, screen, hi, lo, map32, source, source_file)
    stream_meta.append(stream_metadata(screen, hi, lo, source, source_file))

  manifest["files"]["map32_streams"] = {
    "high_compressed": "map32/high_compressed/%03d.bin",
    "low_compressed": "map32/low_compressed/%03d.bin",
    "decoded_json": "map32/decoded/%03d.json",
    "map32_words_le": "map32/words/%03d.bin",
    "source": "overworld_maps/%03d.json" if source_maps is not None else "rom_pointer_tables",
    "metadata": stream_meta,
  }


def build_stream_records(screen, source_maps, source_dir):
  """Build high/low stream records from either editable JSON or the ROM fallback.

  Parameters:
    screen: Overworld screen index being dumped.
    source_maps: Optional list of already-loaded editable map32 word grids.
    source_dir: Directory used to load editable map32 JSON grids.
  Returns:
    Tuple of high stream record, low stream record, map32 words, source label,
    and source file path.
  """
  if source_maps is None:
    hi = read_compressed_stream(HI_PTR_TABLE, screen, True)
    lo = read_compressed_stream(LO_PTR_TABLE, screen, True)
    map32 = [lo["decoded"][index] | (hi["decoded"][index] << 8) for index in range(MAP32_COUNT)]
    return hi, lo, map32, "rom", None

  map32 = source_maps[screen]
  high_decoded, low_decoded = overworld_map32.split_words(map32, screen)
  high_compressed, low_compressed = overworld_map32.encode_word_streams(map32, screen)
  hi_rom = read_compressed_stream(HI_PTR_TABLE, screen, True)
  lo_rom = read_compressed_stream(LO_PTR_TABLE, screen, True)
  source_file = overworld_map32.source_path(source_dir, screen)
  return (
    source_backed_stream_record(hi_rom, high_compressed, high_decoded),
    source_backed_stream_record(lo_rom, low_compressed, low_decoded),
    map32,
    "overworld_maps",
    source_file,
  )


def source_backed_stream_record(rom_record, compressed, decoded):
  """Merge generated editable-source bytes with ROM provenance metadata.

  Parameters:
    rom_record: ROM-backed stream metadata for the same screen and byte plane.
    compressed: Generated compressed stream bytes from the editable JSON grid.
    decoded: Generated decoded byte values from the editable JSON grid.
  Returns:
    Dict shaped like a ROM stream record with an extra ROM compressed-length field.
  """
  return {
    "address": rom_record["address"],
    "compressed_length": len(compressed),
    "compressed": compressed,
    "decoded": bytes(decoded),
    "rom_compressed_length": rom_record["compressed_length"],
  }


def validate_decoded_lengths(screen, hi, lo):
  """Validate that both decoded byte planes cover a complete 16x16 map32 screen.

  Parameters:
    screen: Overworld screen index used for diagnostics.
    hi: High-byte stream record.
    lo: Low-byte stream record.
  Returns:
    None.
  Raises:
    Exception: If either byte plane is too short for 256 map32 cells.
  """
  if len(hi["decoded"]) < MAP32_COUNT or len(lo["decoded"]) < MAP32_COUNT:
    raise Exception("Overworld screen %d decoded to %d/%d bytes" % (
      screen, len(hi["decoded"]), len(lo["decoded"])))


def write_stream_files(hi_dir, lo_dir, decoded_dir, words_dir, screen, hi, lo, map32, source, source_file):
  """Write all dump artifacts for one map32 screen.

  Parameters:
    hi_dir: Directory for high-byte compressed stream files.
    lo_dir: Directory for low-byte compressed stream files.
    decoded_dir: Directory for decoded JSON records.
    words_dir: Directory for little-endian map32 word binaries.
    screen: Overworld screen index being written.
    hi: High-byte stream record.
    lo: Low-byte stream record.
    map32: Flat 256-entry map32 word list.
    source: Source label stored in decoded JSON.
    source_file: Optional editable JSON source path.
  Returns:
    None.
  Side effects:
    Writes four per-screen dump files.
  """
  write_bytes(os.path.join(hi_dir, "%03d.bin" % screen), hi["compressed"])
  write_bytes(os.path.join(lo_dir, "%03d.bin" % screen), lo["compressed"])
  write_bytes(os.path.join(words_dir, "%03d.bin" % screen), uint16le(map32))
  write_json(os.path.join(decoded_dir, "%03d.json" % screen), {
    "screen": screen,
    "high_address": hex(hi["address"]),
    "low_address": hex(lo["address"]),
    "high_compressed_length": hi["compressed_length"],
    "low_compressed_length": lo["compressed_length"],
    "high_decoded_length": len(hi["decoded"]),
    "low_decoded_length": len(lo["decoded"]),
    "source": source,
    "source_file": source_file,
    "high": list(hi["decoded"][:MAP32_COUNT]),
    "low": list(lo["decoded"][:MAP32_COUNT]),
    "map32": map32,
  })


def stream_metadata(screen, hi, lo, source, source_file):
  """Create the manifest metadata entry for one map32 stream.

  Parameters:
    screen: Overworld screen index.
    hi: High-byte stream record.
    lo: Low-byte stream record.
    source: Source label stored in the manifest.
    source_file: Optional editable JSON source path.
  Returns:
    Dict describing the stream addresses, lengths, and source path.
  """
  metadata = {
    "screen": screen,
    "high_address": hex(hi["address"]),
    "low_address": hex(lo["address"]),
    "high_compressed_length": hi["compressed_length"],
    "low_compressed_length": lo["compressed_length"],
    "high_decoded_length": len(hi["decoded"]),
    "low_decoded_length": len(lo["decoded"]),
    "source": source,
    "source_file": source_file,
  }
  if "rom_compressed_length" in hi:
    metadata["high_rom_compressed_length"] = hi["rom_compressed_length"]
    metadata["low_rom_compressed_length"] = lo["rom_compressed_length"]
  return metadata


def read_compressed_stream(pointer_table, screen, offset_is_be):
  """Read one ROM-compressed high-byte or low-byte map32 stream.

  Parameters:
    pointer_table: SNES pointer table for the requested byte plane.
    screen: Overworld screen index.
    offset_is_be: Backreference byte order for the Zelda 3 LZ decoder.
  Returns:
    Dict containing address, compressed bytes, decoded bytes, and length.
  """
  return overworld_map32.read_rom_stream(pointer_table, screen, util.ROM, offset_is_be)
