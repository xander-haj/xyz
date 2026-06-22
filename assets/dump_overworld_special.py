"""
Special-overworld metadata helpers for the explicit viewer dump.
"""


def normalize_special_exits(exits):
  """Return special-exit records with their parent exit scroll data preserved.

  Parameters:
    exits: YAML exit records from one overworld area.
  Returns:
    List of special-exit dictionaries ready for area_metadata.json.
  """
  records = []
  for exit_info in exits:
    if "special_exit" not in exit_info:
      continue
    special = dict(exit_info["special_exit"])
    # The PNG-accurate browser view needs the regular exit scroll fields as
    # well as the nested kSpExit fields, because the viewport crop comes from
    # both tables.
    for key in ["index", "room", "xy", "scroll_xy", "camera_xy", "load_xy", "unk"]:
      if key in exit_info:
        special[key] = exit_info[key]
    records.append(special)
  return records
