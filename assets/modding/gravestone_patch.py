"""Apply fixed-index overworld gravestone table patches."""

from __future__ import annotations

from pathlib import Path

from dump_overworld_gravestones import dump_gravestone_records
from dump_overworld_support import read_text

from .paths import PROJECT_ROOT
from .resolver import parse_int
from .schema import patch_operations, write_json

GRAVESTONE_SOURCE = PROJECT_ROOT / "src" / "overworld_gravestones.c"
GRAVESTONE_COORD_MAX = 4088
GRAVESTONE_AREA_MAX = 0x3F
GRAVESTONE_LOCAL_COORD_MAX = 0x3FF
GRAVESTONE_U16_MAX = 0xFFFF


def prepare_gravestones(generated_dir: Path) -> dict:
    """Load base gravestone records from the runtime source table."""
    del generated_dir
    data = dump_gravestone_records(read_text(GRAVESTONE_SOURCE))
    return {"records": data["records"], "touched": False}


def apply_gravestone_patch(state: dict, document: dict) -> list[dict]:
    """Apply fixed-index gravestone record replacements."""
    applied = []
    records = state["records"]
    seen = set()
    for operation in patch_operations(document):
        if operation.get("kind") != "gravestone.record":
            raise ValueError("Unsupported gravestone operation kind %r." % operation.get("kind"))
        index = parse_gravestone_int(operation.get("index"), "gravestone index")
        if index in seen:
            raise ValueError("Duplicate gravestone record patch for index %d." % index)
        if index < 0 or index >= len(records):
            raise ValueError("Gravestone index %d is out of range." % index)
        records[index] = patched_record(records[index], patch_value(operation, index))
        seen.add(index)
        state["touched"] = True
        applied.append({"kind": "gravestone.record", "index": index})
    return applied


def finalize_gravestones(generated_dir: Path, state: dict) -> None:
    """Write generated gravestone tables when a mod changed them."""
    if not state.get("touched"):
        return
    table_dir = generated_dir / "tables"
    records = [json_record(record) for record in state["records"]]
    write_json(table_dir / "overworld_gravestones.json", {
        "format": "zelda3-overworld-gravestones-generated-v1",
        "records": records,
    })


def patched_record(before: dict, value: dict) -> dict:
    """Return a normalized replacement record."""
    record = dict(before)
    x = clamp_coord(parse_gravestone_int(value.get("x", record["x"]), "gravestone x"))
    y = clamp_coord(parse_gravestone_int(value.get("y", record["y"]), "gravestone y"))
    area = parse_area(value.get("area", area_from_world(x, y)))
    tilemap_pos = value.get("tilemapPos", value.get("tilemap_pos"))
    record.update({
        "area": area,
        "x": x,
        "y": y,
    })
    record["local_x"] = x - (area & 7) * 512
    record["local_y"] = y - (area >> 3) * 512
    validate_local_position(record)
    expected_tilemap = tilemap_from_record(record)
    record["tilemap_pos"] = (
        parse_tilemap_pos(tilemap_pos, expected_tilemap, record["index"])
        if tilemap_pos is not None else expected_tilemap
    )
    word = record["tilemap_pos"] >> 1
    record["tilemap_grid_x"] = word & 0x3f
    record["tilemap_grid_y"] = word >> 6
    record["trigger_x"] = record["x"]
    record["trigger_y"] = record["y"] + 16
    return record


def patch_value(operation: dict, index: int) -> dict:
    if "value" not in operation or operation["value"] is None:
        return {}
    value = operation["value"]
    if not isinstance(value, dict):
        raise ValueError("Gravestone record %d value must be an object." % index)
    return value


def parse_gravestone_int(value, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError("%s must be an integer." % label)
    try:
        return parse_int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("%s must be an integer." % label) from error


def parse_area(value) -> int:
    area = parse_gravestone_int(value, "gravestone area")
    if area < 0 or area > GRAVESTONE_AREA_MAX:
        raise ValueError("Gravestone area must be in 0..0x%02x." % GRAVESTONE_AREA_MAX)
    return area


def parse_tilemap_pos(value, expected: int, index: int) -> int:
    tilemap_pos = parse_gravestone_int(value, "gravestone tilemap_pos")
    validate_tilemap_pos(tilemap_pos)
    if tilemap_pos != expected:
        raise ValueError(
            "Gravestone %d tilemap_pos 0x%04x does not match x/y/area; expected 0x%04x." % (
                index, tilemap_pos, expected))
    return tilemap_pos


def validate_local_position(record: dict) -> None:
    if record["local_x"] < 0 or record["local_x"] > GRAVESTONE_LOCAL_COORD_MAX:
        raise ValueError("Gravestone %d x is outside area 0x%02x." % (
            record["index"], record["area"]))
    if record["local_y"] < 0 or record["local_y"] > GRAVESTONE_LOCAL_COORD_MAX:
        raise ValueError("Gravestone %d y is outside area 0x%02x." % (
            record["index"], record["area"]))


def validate_tilemap_pos(value: int) -> None:
    if value < 0 or value > GRAVESTONE_U16_MAX:
        raise ValueError("Gravestone tilemap_pos must be in 0..0xffff.")
    if value & 1:
        raise ValueError("Gravestone tilemap_pos must be even.")


def json_record(record: dict) -> dict:
    """Keep only fields consumed by compile/dump preview paths."""
    return {
        "area": record["area"],
        "index": record["index"],
        "special": record.get("special"),
        "tilemap_pos": record["tilemap_pos"],
        "x": record["x"],
        "y": record["y"],
    }


def tilemap_from_record(record: dict) -> int:
    """Match ZScream's tilemap calculation for a grave's parent map."""
    xx = (record["x"] - (record["area"] & 7) * 512) // 16
    yy = (record["y"] - (record["area"] >> 3) * 512) // 16
    return ((yy << 6) | (xx & 0x3f)) << 1


def area_from_world(x: int, y: int) -> int:
    """Return the 8-column overworld area containing an absolute point."""
    return (y // 512) * 8 + (x // 512)


def clamp_coord(value: int) -> int:
    """Match ZScream's drag coordinate clamp."""
    return max(0, min(GRAVESTONE_COORD_MAX, value))
