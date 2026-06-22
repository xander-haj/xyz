"""Apply map32, map16, and map8 tile-table recipes."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .resolver import IdAllocator, parse_int, parse_tile_word, resolve_quadrant
from .schema import patch_operations, write_json

LINE_RE = re.compile(r"^\s*(\d+)\s*:\s*(.*)$")


def prepare_tile_sources(assets_dir: Path, generated_dir: Path) -> dict:
    """Copy base tile-definition sources into generated output.

    Parameters:
        assets_dir: Repository assets directory.
        generated_dir: Generated mod output directory.
    Returns:
        Dict containing map32 entries and map16-to-map8 words.
    """
    map32_path = assets_dir / "map32_to_map16.txt"
    map16_path = assets_dir / "overworld_dump" / "tables" / "map16_to_map8.json"
    if not map32_path.exists():
        raise ValueError("Missing extracted map32_to_map16.txt.")
    if not map16_path.exists():
        raise ValueError("Missing overworld_dump/tables/map16_to_map8.json.")
    entries = read_map32_to_map16(map32_path)
    words = read_map16_to_map8(map16_path)
    attributes = read_map8_attributes(assets_dir / "overworld_dump" / "tables" / "source_tables.json")
    shutil.copy2(map32_path, generated_dir / "map32_to_map16.txt")
    write_map16_to_map8(generated_dir / "tables", words)
    if attributes is not None:
        write_map8_attributes(generated_dir / "tables", attributes)
    return {"map32": entries, "map16": words, "map8_attrs": attributes}


def apply_tile_patch(state: dict, document: dict, report) -> list[dict]:
    """Apply tile table patch documents to in-memory generated state.

    Parameters:
        state: Dict from prepare_tile_sources.
        document: Parsed patch JSON.
        report: ConflictReport receiving duplicate id failures.
    Returns:
        Applied operation summaries.
    """
    map32_alloc = state.setdefault("map32_allocator", IdAllocator(len(state["map32"])))
    map16_alloc = state.setdefault("map16_allocator", IdAllocator(len(state["map16"]) // 4))
    applied = []
    for operation in patch_operations(document):
        kind = operation.get("kind")
        if is_duplicate_mod_id(state, kind, operation.get("id"), report):
            continue
        if kind == "tile.map32-definition":
            apply_map32_definition(state["map32"], map32_alloc, map16_alloc, operation)
        elif kind == "tile.map16-definition":
            apply_map16_definition(state["map16"], map16_alloc, operation)
        elif kind == "tile.map8-word":
            apply_map8_word(state["map16"], map16_alloc, operation)
        elif kind == "tile.map8-attribute":
            apply_map8_attribute(state.get("map8_attrs"), operation)
        else:
            raise ValueError("Unsupported tile operation kind %r." % kind)
        applied.append({"kind": kind, "id": operation.get("id") or operation.get("target")})
    return applied


def is_duplicate_mod_id(state: dict, kind: str, ref, report) -> bool:
    """Record and reject duplicate mod ids within one generated build.

    Parameters:
        state: Mutable tile state shared across mods.
        kind: Patch operation kind.
        ref: Candidate id reference.
        report: ConflictReport receiving duplicate id failures.
    Returns:
        True when the id is a duplicate and should be skipped.
    """
    if not isinstance(ref, str) or not ref.startswith("mod:"):
        return False
    key = (kind, ref)
    defined = state.setdefault("defined_mod_ids", set())
    if key in defined:
        report.add("duplicate-mod-id", "Two mods define the same mod id.", {"kind": kind, "id": ref})
        return True
    defined.add(key)
    return False


def finalize_tile_sources(generated_dir: Path, state: dict) -> None:
    """Write patched tile tables to generated output.

    Parameters:
        generated_dir: Generated mod output directory.
        state: Mutable tile state from prepare_tile_sources.
    Returns:
        None.
    """
    entries = list(state["map32"])
    while len(entries) % 4:
        entries.append(entries[-1][:])
    write_map32_to_map16(generated_dir / "map32_to_map16.txt", entries)
    write_map16_to_map8(generated_dir / "tables", state["map16"])
    if state.get("map8_attrs") is not None:
        write_map8_attributes(generated_dir / "tables", state["map8_attrs"])


def apply_map32_definition(entries: list[list[int]], map32_alloc: IdAllocator,
                           map16_alloc: IdAllocator, operation: dict) -> None:
    """Apply one map32 definition recipe.

    Parameters are generated table state and one patch operation.
    Returns:
        None.
    """
    index = (
        map32_alloc.define(operation["id"])
        if str(operation.get("id", "")).startswith("mod:")
        else int(operation["id"])
    )
    base = [0, 0, 0, 0]
    if operation.get("from") is not None:
        base_index = map32_alloc.resolve(operation["from"])
        base = entries[base_index][:]
    ensure_entry(entries, index, base)
    changes = operation.get("setMap16", {})
    for label, value in changes.items():
        entries[index][resolve_quadrant(label)] = map16_alloc.resolve(value)


def apply_map16_definition(words: list[int], map16_alloc: IdAllocator, operation: dict) -> None:
    """Apply one map16 definition recipe.

    Parameters are generated map16 words, allocator, and patch operation.
    Returns:
        None.
    """
    index = (
        map16_alloc.define(operation["id"])
        if str(operation.get("id", "")).startswith("mod:")
        else int(operation["id"])
    )
    base = [0, 0, 0, 0]
    if operation.get("from") is not None:
        base_index = map16_alloc.resolve(operation["from"])
        base = words[base_index * 4:base_index * 4 + 4]
    ensure_map16(words, index, base)
    for label, value in operation.get("setMap8", {}).items():
        words[index * 4 + resolve_quadrant(label)] = parse_tile_word({"word": value})


def apply_map8_word(words: list[int], map16_alloc: IdAllocator, operation: dict) -> None:
    """Apply one map8 tile-word edit inside a map16 definition.

    Parameters are generated map16 words, allocator, and patch operation.
    Returns:
        None.
    """
    target = operation.get("target", {})
    map16 = map16_alloc.resolve(target.get("map16"))
    slot = resolve_quadrant(target.get("slot", "tl"))
    ensure_map16(words, map16, [0, 0, 0, 0])
    current = words[map16 * 4 + slot]
    words[map16 * 4 + slot] = parse_tile_word(operation.get("set", operation), current)


def apply_map8_attribute(attributes: list[int] | None, operation: dict) -> None:
    """Apply one overworld map8-to-tile-type edit.

    Parameters:
        attributes: Mutable 512-byte map8 attribute table.
        operation: Patch operation with target index and type/attribute value.
    Returns:
        None.
    """
    if attributes is None:
        raise ValueError("Missing overworld_dump/tables/source_tables.json map8_tile_attributes.")
    target = operation.get("target", {})
    index_value = target.get("index", operation.get("index", target.get("tile", operation.get("tile"))))
    index = parse_map8_attribute_int(index_value, "map8 attribute index")
    value = parse_attribute_value(operation)
    validate_range(index, 0, 0x1FF, "map8 attribute index")
    validate_range(value, 0, 0xFF, "map8 tile attribute")
    attributes[index] = value


def read_map32_to_map16(path: Path) -> list[list[int]]:
    """Read extracted map32-to-map16 text into a direct table.

    Parameters:
        path: map32_to_map16.txt path.
    Returns:
        List indexed by map32 id, each value containing four map16 ids.
    """
    entries: dict[int, list[int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LINE_RE.match(line)
        if match:
            entries[int(match.group(1))] = [int(part.strip()) for part in match.group(2).split(",")]
    return [entries[index] for index in range(max(entries) + 1)]


def write_map32_to_map16(path: Path, entries: list[list[int]]) -> None:
    """Write a direct map32-to-map16 table in the existing text format.

    Parameters:
        path: Destination map32_to_map16.txt path.
        entries: List of four-map16 entries.
    Returns:
        None.
    """
    with path.open("w", encoding="utf-8") as file:
        for index, values in enumerate(entries):
            file.write("%5d: %4d, %4d, %4d, %4d\n" % (index, values[0], values[1], values[2], values[3]))


def read_map16_to_map8(path: Path) -> list[int]:
    """Read map16-to-map8 words from the viewer dump JSON.

    Parameters:
        path: map16_to_map8.json path.
    Returns:
        Flat word list.
    """
    return json.loads(path.read_text(encoding="utf-8"))["words"]


def read_map8_attributes(path: Path) -> list[int] | None:
    """Read the dumped 512-byte map8 tile attribute table when available.

    Parameters:
        path: source_tables.json path from the local overworld dump.
    Returns:
        Flat byte list, or None for older dumps that do not expose the table.
    """
    if not path.exists():
        return None
    attributes = json.loads(path.read_text(encoding="utf-8")).get("map8_tile_attributes")
    if attributes is None:
        return None
    if len(attributes) != 512:
        raise ValueError("map8_tile_attributes must contain exactly 512 bytes.")
    return [checked_byte(value, "map8 tile attribute") for value in attributes]


def write_map16_to_map8(directory: Path, words: list[int]) -> None:
    """Write generated map16-to-map8 JSON and binary files.

    Parameters:
        directory: Generated tables directory.
        words: Flat uint16 word list.
    Returns:
        None.
    """
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "map16_to_map8.json", {"source": "generated-overworld-mod", "words": words})
    with (directory / "map16_to_map8.bin").open("wb") as file:
        for word in words:
            file.write(int(word).to_bytes(2, "little"))


def write_map8_attributes(directory: Path, attributes: list[int]) -> None:
    """Write generated map8 tile attributes for compiler and preview consumers.

    Parameters:
        directory: Generated tables directory.
        attributes: Flat 512-byte attribute table.
    Returns:
        None.
    """
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "map8_tile_attributes.json", {
        "source": "generated-overworld-mod",
        "words": attributes,
    })
    with (directory / "map8_tile_attributes.bin").open("wb") as file:
        file.write(bytes(checked_byte(value, "map8 tile attribute") for value in attributes))


def ensure_entry(entries: list[list[int]], index: int, fill: list[int]) -> None:
    """Grow a map32 table to include one index.

    Parameters are the table, target index, and fill value.
    Returns:
        None.
    """
    while len(entries) <= index:
        entries.append(fill[:])


def ensure_map16(words: list[int], index: int, fill: list[int]) -> None:
    """Grow a map16 word table to include one index.

    Parameters are the flat word table, target map16 id, and fill four words.
    Returns:
        None.
    """
    while len(words) < index * 4 + 4:
        words.extend(fill[:])


def parse_attribute_value(operation: dict) -> int:
    """Resolve the new tile type byte from supported patch spellings.

    Parameters:
        operation: Patch operation containing `set`, `attribute`, or `type`.
    Returns:
        Parsed tile attribute byte.
    """
    set_value = operation.get("set")
    if isinstance(set_value, dict):
        value = set_value.get("attribute", set_value.get("type"))
    elif set_value is not None:
        value = set_value
    else:
        value = operation.get("attribute", operation.get("type"))
    return parse_map8_attribute_int(value, "map8 tile attribute")


def parse_map8_attribute_int(value, label: str) -> int:
    """Parse one strict integer field from a map8 tile attribute edit.

    Parameters:
        value: Candidate JSON value from a patch operation.
        label: Diagnostic field label.
    Returns:
        Parsed integer value.
    """
    if isinstance(value, bool):
        raise ValueError("%s must be an integer, not boolean." % label)
    try:
        return parse_int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("%s must be an integer value." % label) from error


def validate_range(value: int, minimum: int, maximum: int, label: str) -> None:
    """Validate one parsed integer field.

    Parameters:
        value: Candidate value.
        minimum: Inclusive lower bound.
        maximum: Inclusive upper bound.
        label: Diagnostic label.
    Returns:
        None.
    """
    if not minimum <= value <= maximum:
        raise ValueError("%s is outside 0x%X..0x%X." % (label, minimum, maximum))


def checked_byte(value: int, label: str) -> int:
    """Validate and return one byte-sized table value.

    Parameters:
        value: Candidate byte.
        label: Diagnostic label.
    Returns:
        The original value when valid.
    """
    if type(value) is not int:
        raise ValueError("%s must be an integer byte." % label)
    validate_range(value, 0, 0xFF, label)
    return int(value)
