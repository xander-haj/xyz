# dat_dump.py -- Directory emitter for compiled Zelda 3 runtime assets.
#
# This module writes the finished compile_resources.assets dictionary into a
# stable folder tree for editor tooling. It intentionally preserves the runtime
# payload bytes instead of trying to semantically decode every asset family.

# Standard library imports for JSON metadata, safe directory replacement, binary
# offset parsing, and filesystem path handling.
import json
import shutil
import struct
from pathlib import Path

# The dump format version lets editor loaders reject future incompatible layouts.
DUMP_FORMAT_VERSION = 1

# The legacy nodat output folder name is fixed so cleanup can be tightly scoped.
DUMP_DIR_NAME = 'dat dump'

# Editor-facing dumps use a shell-friendly hyphenated directory.
EDITOR_DUMP_DIR_NAME = 'dat-dump'

# compile_resources marks packed indexed containers with this type string.
PACKED_ASSET_TYPE = 'packed'

# Packed arrays add 8192 to the stored trailer count when their offset table uses
# 32-bit entries instead of 16-bit entries.
PACKED_LARGE_SENTINEL = 8192


# Write all compiled assets into a clean directory tree.
# Parameters:
#   assets: Ordered mapping of asset name to (type, raw bytes), matching
#           compile_resources.assets after print_all() has populated it.
#   output_dir: Destination directory, normally assets/dat dump or
#               assets/dat-dump because
#               restool.py changes the working directory to assets/.
# Returns:
#   Manifest dictionary that was written to manifest.json.
def write_assets_to_directory(assets, output_dir=DUMP_DIR_NAME):
  root = Path(output_dir)
  reset_output_directory(root)

  manifest = {
    'format': 'zelda3_dat_dump',
    'format_version': DUMP_FORMAT_VERSION,
    'asset_count': len(assets),
    'notes': [
      'Payload bytes match compile_resources.assets after compilation.',
      'Packed assets are split into indexed entries for tooling convenience.',
      'Internal SNES-LZ, dialogue, and graphics encodings are preserved here.',
    ],
    'assets': [],
  }

  # Keep the same insertion order as zelda3_assets.dat so index-based runtime
  # references remain visible to editor tooling.
  for index, (name, (asset_type, data)) in enumerate(assets.items()):
    asset_record = write_asset_directory(root, index, name, asset_type, data)
    manifest['assets'].append(asset_record)

  write_json(root / 'manifest.json', manifest)
  print('Wrote %d compiled assets to %s' % (len(assets), root))
  return manifest


# Replace only the owned dat dump directory before writing a fresh export.
# Parameters:
#   root: Path object for the dump directory.
# Returns:
#   None.
def reset_output_directory(root):
  # Cleanup is intentionally limited to owned dump folder names so a bad caller
  # cannot point this writer at an arbitrary project directory.
  if root.name not in (DUMP_DIR_NAME, EDITOR_DUMP_DIR_NAME):
    raise ValueError('Refusing to clean unexpected dat dump directory: %s' % root)
  # Existing dump contents are replaced so stale assets cannot survive between
  # editor data refreshes.
  if root.exists():
    # A symlink at the dump path could redirect cleanup outside assets/, so fail
    # instead of following it.
    if root.is_symlink():
      raise ValueError('Refusing to replace symlinked dat dump directory: %s' % root)
    if not root.is_dir():
      raise ValueError('Dat dump path exists and is not a directory: %s' % root)
    shutil.rmtree(root)
  root.mkdir(parents=True)


# Write one asset directory and its per-asset manifest.
# Parameters:
#   root: Root dump directory.
#   index: Runtime asset index.
#   name: Runtime asset name such as kDungeonRoom.
#   asset_type: compile_resources type tag.
#   data: Raw compiled payload bytes.
# Returns:
#   Metadata record for the root manifest.
def write_asset_directory(root, index, name, asset_type, data):
  asset_dir = root / asset_directory_name(index, name)
  asset_dir.mkdir()

  record = {
    'index': index,
    'name': name,
    'type': asset_type,
    'size': len(data),
    'directory': relative_dump_path(root, asset_dir),
  }

  # Packed assets use the runtime offset-table container, while typed assets are
  # already flat payloads and can be written directly.
  if asset_type == PACKED_ASSET_TYPE:
    write_packed_asset(root, asset_dir, record, data)
  else:
    data_file = asset_dir / 'data.bin'
    data_file.write_bytes(data)
    record['data_file'] = relative_dump_path(root, data_file)
    record['payload_encoding'] = 'raw_%s' % asset_type

  asset_manifest = asset_dir / 'asset.json'
  record['manifest_file'] = relative_dump_path(root, asset_manifest)
  write_json(asset_manifest, record)
  return record


# Write a packed asset as both the original packed blob and split indexed entries.
# Parameters:
#   root: Root dump directory.
#   asset_dir: Directory for this asset.
#   record: Mutable metadata record to enrich.
#   data: Raw packed payload bytes.
# Returns:
#   None.
def write_packed_asset(root, asset_dir, record, data):
  packed_file = asset_dir / 'packed.bin'
  packed_file.write_bytes(data)

  unpacked = unpack_packed_blob(data)
  entries_dir = asset_dir / 'entries'
  entries_dir.mkdir()
  entry_records = []

  # Split the runtime packed container into one file per entry while preserving
  # each entry's internal encoding.
  for entry_index, entry_data in enumerate(unpacked['entries']):
    entry_file = entries_dir / ('%04d.bin' % entry_index)
    entry_file.write_bytes(entry_data)
    entry_records.append({
      'index': entry_index,
      'size': len(entry_data),
      'file': relative_dump_path(root, entry_file),
    })

  record.update({
    'payload_encoding': 'runtime_packed',
    'packed_file': relative_dump_path(root, packed_file),
    'packed_mode': unpacked['mode'],
    'packed_offset_width': unpacked['offset_width'],
    'entry_count': len(unpacked['entries']),
    'entries_directory': relative_dump_path(root, entries_dir),
    'entries': entry_records,
  })


# Decode the offset table that compile_resources.pack_arrays writes.
# Parameters:
#   data: Raw packed bytes from one packed asset.
# Returns:
#   Dict containing mode metadata and a list of entry byte strings.
def unpack_packed_blob(data):
  # compile_resources.pack_arrays([]) emits an empty blob, which represents an
  # empty indexed container rather than a malformed one.
  if not data:
    return {
      'mode': 'empty',
      'offset_width': 0,
      'entries': [],
    }
  # Non-empty packed blobs must include the 16-bit count trailer consumed by
  # FindIndexInMemblk().
  if len(data) < 2:
    raise ValueError('Packed asset is too small to contain an entry trailer.')

  trailer = read_le16(data, len(data) - 2)
  data_end = len(data) - 2
  # Trailer values below the sentinel use compact 16-bit offsets; values at or
  # above it encode 32-bit mode by subtracting the sentinel first.
  if trailer < PACKED_LARGE_SENTINEL:
    mode = 'u16_offsets'
    offset_width = 2
    offset_count = trailer
  else:
    mode = 'u32_offsets'
    offset_width = 4
    offset_count = trailer - PACKED_LARGE_SENTINEL

  table_size = offset_count * offset_width
  # The offset table lives before the entry data; if it crosses the trailer
  # boundary, the packed blob is corrupt and should not be dumped as valid data.
  if table_size > data_end:
    raise ValueError('Packed asset offset table extends beyond the payload.')

  offsets = read_offset_table(data, offset_count, offset_width)
  validate_offsets(offsets, data_end - table_size)

  entries = []
  # The trailer stores count-1, so there is one more entry than table offsets.
  for entry_index in range(offset_count + 1):
    entry_start = table_size if entry_index == 0 else table_size + offsets[entry_index - 1]
    entry_end = data_end if entry_index == offset_count else table_size + offsets[entry_index]
    entries.append(data[entry_start:entry_end])

  return {
    'mode': mode,
    'offset_width': offset_width,
    'entries': entries,
  }


# Read the cumulative offsets that separate packed entries.
# Parameters:
#   data: Packed asset bytes.
#   offset_count: Number of offset entries stored before the data region.
#   offset_width: Either 2 or 4 bytes.
# Returns:
#   List of cumulative offsets from the start of the data region.
def read_offset_table(data, offset_count, offset_width):
  offsets = []
  # Offsets are stored contiguously at the start of the packed blob.
  for offset_index in range(offset_count):
    byte_index = offset_index * offset_width
    if offset_width == 2:
      offsets.append(read_le16(data, byte_index))
    else:
      offsets.append(read_le32(data, byte_index))
  return offsets


# Validate that packed offsets are monotonic and point inside the data region.
# Parameters:
#   offsets: Cumulative offsets from the packed table.
#   data_region_size: Byte size of the concatenated entry data.
# Returns:
#   None.
def validate_offsets(offsets, data_region_size):
  previous = 0
  # Each offset is the end of one entry relative to the data region base.
  for offset in offsets:
    if offset < previous:
      raise ValueError('Packed asset offsets are not monotonic.')
    if offset > data_region_size:
      raise ValueError('Packed asset offset extends beyond the data region.')
    previous = offset


# Produce a stable, index-prefixed directory name for one asset.
# Parameters:
#   index: Runtime asset index.
#   name: Asset name from compile_resources.
# Returns:
#   Filesystem-safe directory name.
def asset_directory_name(index, name):
  safe_name = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in name)
  return '%03d_%s' % (index, safe_name)


# Convert a path inside the dump root to a slash-separated manifest path.
# Parameters:
#   root: Dump root path.
#   path: File or directory below root.
# Returns:
#   Relative POSIX-style path string for JSON manifests.
def relative_dump_path(root, path):
  return path.relative_to(root).as_posix()


# Write deterministic JSON with a trailing newline.
# Parameters:
#   path: Output JSON path.
#   data: JSON-serializable value.
# Returns:
#   None.
def write_json(path, data):
  path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf8')


# Read a little-endian 16-bit value from a bytes object.
# Parameters:
#   data: Source bytes.
#   offset: Byte offset to read from.
# Returns:
#   Unsigned 16-bit integer.
def read_le16(data, offset):
  return struct.unpack_from('<H', data, offset)[0]


# Read a little-endian 32-bit value from a bytes object.
# Parameters:
#   data: Source bytes.
#   offset: Byte offset to read from.
# Returns:
#   Unsigned 32-bit integer.
def read_le32(data, offset):
  return struct.unpack_from('<I', data, offset)[0]
