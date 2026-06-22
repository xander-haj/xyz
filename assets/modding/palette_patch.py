"""Apply palette recipe patches into generated local palette JSON/bin files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .resolver import parse_int, validate_u16
from .schema import patch_operations

PALETTE_FILES = {
    "overworld_bg_main": "overworld_bg_main",
    "overworld_bg_aux12": "overworld_bg_aux12",
    "overworld_bg_aux3": "overworld_bg_aux3",
}
PALETTE_WORD_COUNTS = {
    "overworld_bg_main": 210,
    "overworld_bg_aux12": 420,
    "overworld_bg_aux3": 98,
}


def prepare_palettes(assets_dir: Path, generated_dir: Path) -> dict[str, list[int]]:
    """Copy base overworld palette JSON/bin data into generated output.

    Parameters:
        assets_dir: Repository assets directory.
        generated_dir: Generated mod output directory.
    Returns:
        Dict keyed by palette table name.
    """
    result = {}
    source_dir = assets_dir / "overworld_dump" / "palettes"
    output_dir = generated_dir / "palettes"
    output_dir.mkdir(parents=True, exist_ok=True)
    for key, filename in PALETTE_FILES.items():
        source = source_dir / ("%s.json" % filename)
        if not source.exists():
            continue
        words = json.loads(source.read_text(encoding="utf-8"))["words"]
        result[key] = words
        write_palette(output_dir, filename, words)
    return result


def apply_palette_patch(palettes: dict[str, list[int]], document: dict, yaml_dir: Path | None = None) -> list[dict]:
    """Apply palette operations to generated palette/YAML state.

    Parameters:
        palettes: Mutable palette word tables.
        document: Parsed patch document.
        yaml_dir: Generated overworld YAML directory for assignment edits.
    Returns:
        List of applied summaries.
    """
    applied = []
    for operation in patch_operations(document):
        kind = operation.get("kind")
        if kind == "palette.color-edit":
            applied.append(apply_palette_word(palettes, operation))
        elif kind == "palette.assignment":
            applied.append(apply_palette_assignment(yaml_dir, operation))
        elif kind == "palette.descriptor":
            raise ValueError("palette.descriptor is not a supported patch operation.")
        else:
            raise ValueError("Unsupported palette operation kind %r." % kind)
    return applied


def apply_palette_word(palettes: dict[str, list[int]], operation: dict) -> dict:
    """Apply one palette table word edit.

    Parameters:
        palettes: Mutable palette word tables.
        operation: color-edit operation.
    Returns:
        Applied operation summary.
    """
    table = operation.get("table")
    if table not in palettes:
        raise ValueError("Unknown palette table %r" % table)
    index = parse_palette_int(operation.get("index"), "palette index")
    value = parse_palette_int(operation.get("color"), "BGR555 color")
    validate_u16(value, "BGR555 color")
    if not 0 <= index < len(palettes[table]):
        raise ValueError("Palette index %d outside %s." % (index, table))
    palettes[table][index] = value
    return {"kind": operation["kind"], "table": table, "index": index}


def apply_palette_assignment(yaml_dir: Path | None, operation: dict) -> dict:
    """Apply one overworld area palette assignment edit.

    Parameters:
        yaml_dir: Generated overworld YAML directory.
        operation: palette.assignment operation with area/screen and palette.
    Returns:
        Applied operation summary.
    """
    if yaml_dir is None:
        raise ValueError("Palette assignment requires generated overworld YAML.")
    area = parse_palette_int(operation.get("area", operation.get("screen")), "palette assignment area")
    if area < 0 or area >= 128:
        raise ValueError("Header.palette is not compiler-backed for area %d." % area)
    palette = parse_palette_int(operation.get("palette"), "Header.palette")
    if not 0 <= palette <= 0xFF:
        raise ValueError("Header.palette must be in 0..0xff.")
    path = yaml_dir / ("overworld-%d.yaml" % area)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["Header"]["palette"] = palette
    path.write_text(yaml.dump(data, default_flow_style=None, sort_keys=False), encoding="utf-8")
    return {"kind": operation["kind"], "area": area}


def finalize_palettes(generated_dir: Path, palettes: dict[str, list[int]]) -> None:
    """Write patched palettes back to generated output.

    Parameters:
        generated_dir: Generated mod output directory.
        palettes: Palette word tables.
    Returns:
        None.
    """
    output_dir = generated_dir / "palettes"
    for key, words in palettes.items():
        write_palette(output_dir, PALETTE_FILES[key], words)


def write_palette(output_dir: Path, name: str, words: list[int]) -> None:
    """Write one generated palette JSON and binary pair.

    Parameters:
        output_dir: Generated palette directory.
        name: Palette filename stem.
        words: SNES BGR555 values.
    Returns:
        None.
    """
    words = validate_palette_words(name, words)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ("%s.json" % name)).write_text(
        json.dumps({"source": "generated-overworld-mod", "words": words}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_dir / ("%s.bin" % name)).open("wb") as file:
        for word in words:
            file.write(int(word).to_bytes(2, "little"))


def parse_palette_int(value, label: str) -> int:
    """Parse one strict integer field from an overworld palette patch.

    Parameters:
        value: Candidate patch value.
        label: Diagnostic label.
    Returns:
        Parsed integer value.
    """
    if isinstance(value, bool):
        raise ValueError("%s must be an integer, not boolean." % label)
    try:
        return parse_int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("%s must be an integer value." % label) from error


def validate_palette_words(name: str, words: list[int]) -> list[int]:
    """Validate one generated overworld palette table before JSON/bin output.

    Parameters:
        name: Palette table name.
        words: Candidate BGR555 word list.
    Returns:
        Copied list of strict unsigned 16-bit integers.
    """
    expected_count = PALETTE_WORD_COUNTS.get(name)
    if expected_count is not None and len(words) != expected_count:
        raise ValueError("%s must contain exactly %d BGR555 words." % (name, expected_count))
    result = []
    for index, value in enumerate(words):
        if type(value) is not int:
            raise ValueError("%s[%d] must be an integer BGR555 word." % (name, index))
        validate_u16(value, "%s[%d]" % (name, index))
        result.append(value)
    return result
