"""
Read and validate overworld map8 tile-type data for viewer dumps.
"""


def read_generated_map8_tile_attributes(generated_root, read_generated_words, rom):
  """Read the generated 512-byte tile-type table or fall back to ROM bytes.

  Parameters:
    generated_root: Optional generated mod output root.
    read_generated_words: Local dump helper for generated JSON word tables.
    rom: ROM accessor used for the vanilla fallback table.
  Returns:
    A strict 512-byte list of tile-type integers.
  """
  words = read_generated_words(
    generated_root, ("tables", "map8_tile_attributes.json"),
    [rom.get_byte(0x8E9459 + i) for i in range(512)])
  return validate_generated_map8_tile_attributes(words)


def validate_generated_map8_tile_attributes(words):
  """Validate ZScream's fixed 512-entry map8 tile-type byte table.

  Parameters:
    words: Candidate map8 tile-type list.
  Returns:
    A copied list of byte-sized integer values.
  """
  if len(words) != 512:
    raise ValueError("map8_tile_attributes must contain exactly 512 bytes.")
  result = []
  for index, value in enumerate(words):
    if type(value) is not int:
      raise ValueError("map8_tile_attributes[%d] must be an integer byte." % index)
    if not 0 <= value <= 0xFF:
      raise ValueError("map8_tile_attributes[%d] is outside 0x00..0xFF." % index)
    result.append(value)
  return result
