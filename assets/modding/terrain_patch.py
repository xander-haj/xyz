"""Apply sparse map32 placement patches to editable overworld grid JSON files."""

from __future__ import annotations

import shutil
from pathlib import Path

import overworld_map32

from .resolver import parse_int
from .schema import patch_operations

MISSING = object()


def copy_base_maps(base_dir: Path, generated_dir: Path) -> Path:
    """Copy local extracted map32 grids into a generated mod workspace.

    Parameters:
        base_dir: Directory containing base 000.json through 159.json.
        generated_dir: Root generated mod output directory.
    Returns:
        Generated overworld_maps directory path.
    """
    output = generated_dir / "overworld_maps"
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(base_dir, output)
    return output


def apply_terrain_patch(source_dir: Path, document: dict, report, map32_allocator=None, touched=None) -> list[dict]:
    """Apply terrain.map32-placement operations to generated map32 grids.

    Parameters:
        source_dir: Generated overworld_maps directory.
        document: Parsed terrain patch document.
        report: ConflictReport receiving duplicate/expect failures.
        map32_allocator: Optional allocator for previously defined mod: map32 ids.
        touched: Optional build-wide terrain write tracker.
    Returns:
        List of applied operation summaries.
    """
    applied = []
    if touched is None:
        touched = {}
    for operation in patch_operations(document):
        if operation.get("kind") != "terrain.map32-placement":
            raise ValueError("Unsupported terrain operation kind %r." % operation.get("kind"))
        screen = parse_terrain_int(operation.get("screen"), "terrain screen")
        overworld_map32.validate_screen(screen)
        words = overworld_map32.load_map32_source(str(source_dir), screen)
        for edit in operation.get("set", []):
            apply_cell_edit(words, screen, edit, touched, report, map32_allocator)
        overworld_map32.write_grid_file(str(source_dir), screen, words, "generated-from-overworld-mod", {})
        applied.append({"kind": operation["kind"], "screen": screen, "count": len(operation.get("set", []))})
    return applied


def apply_cell_edit(words: list[int], screen: int, edit: dict, touched: dict, report, map32_allocator) -> None:
    """Apply one guarded map32 cell edit.

    Parameters:
        words: Mutable flat map32 grid.
        screen: Screen being edited.
        edit: Patch cell edit.
        touched: Build-wide terrain write tracker.
        report: ConflictReport receiving failures.
        map32_allocator: Optional allocator for mod: tile references.
    Returns:
        None.
    """
    x = parse_terrain_int(edit.get("x"), "terrain x")
    y = parse_terrain_int(edit.get("y"), "terrain y")
    if not 0 <= x < overworld_map32.GRID_WIDTH or not 0 <= y < overworld_map32.GRID_HEIGHT:
        raise ValueError("Terrain edit coordinate %d,%d is outside 16x16." % (x, y))
    key = (screen, x, y)
    if key in touched and not edit.get("override"):
        report.add("terrain-cell-conflict", "Multiple mods set the same terrain cell.", {"cell": key})
        return
    index = y * overworld_map32.GRID_WIDTH + x
    expected = edit.get("expect", MISSING)
    if expected is not MISSING and words[index] != parse_reference(expected):
        report.add("terrain-expect-failed", "Terrain edit expected a different base value.", {
            "screen": screen,
            "x": x,
            "y": y,
            "expected": expected,
            "actual": words[index],
        })
        return
    words[index] = parse_reference(edit.get("map32", edit.get("set")), map32_allocator)
    touched[key] = edit


def parse_reference(value, map32_allocator=None) -> int:
    """Parse a currently numeric terrain reference.

    Parameters:
        value: Integer, base: hex reference, or defined mod: reference.
        map32_allocator: Optional allocator for mod references.
    Returns:
        Numeric map32 id.
    """
    if isinstance(value, str) and value.startswith("base:"):
        return validate_map32_id(parse_terrain_int(value[5:], "terrain map32 reference"))
    if isinstance(value, str) and value.startswith("mod:"):
        if map32_allocator is None:
            raise ValueError("Mod map32 ids must be defined before terrain placement.")
        return validate_map32_id(map32_allocator.resolve(value))
    return validate_map32_id(parse_terrain_int(value, "terrain map32 reference"))


def parse_terrain_int(value, label: str) -> int:
    """Parse one strict terrain patch integer field.

    Parameters:
        value: Candidate integer or base-0 string.
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


def validate_map32_id(value: int) -> int:
    """Validate one unsigned 16-bit map32 tile id.

    Parameters:
        value: Candidate map32 id.
    Returns:
        The validated id.
    """
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError("Terrain map32 reference must be in 0..0xffff.")
    return value
