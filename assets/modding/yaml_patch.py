"""Apply sparse overworld YAML metadata patches into generated files."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

import overworld_static_overlays

from .navigation_patch import is_navigation_operation, validate_navigation_tables
from .resolver import parse_int
from .schema import METADATA_SPRITE_PATHS, patch_operations, validate_metadata_operation_path
from .topology_patch import resize_overworld_area

HEADER_FIELD_LIMITS = {
    "gfx": 128,
    "palette": 128,
    "sign_text": 128,
}
HEADER_KEY_ALIASES = {
    "signText": "sign_text",
}
HEADER_SIZE_VALUES = {"small", "big", "wide", "tall"}
METADATA_AREA_LIMITS = {
    "items": 128,
    "sprites": 160,
}
METADATA_KINDS = {
    "metadata.header",
    "metadata.static-overlay",
    "metadata.travel",
    "metadata.entrance",
    "metadata.hole",
    "metadata.exit",
    "metadata.item",
    "metadata.sprite",
}
SPRITE_CONTEXT_AREA_LIMIT = 128
MISSING = object()


def copy_base_yaml(assets_dir: Path, generated_dir: Path) -> Path:
    """Copy extracted overworld YAML files into generated output.

    Parameters:
        assets_dir: Repository assets directory.
        generated_dir: Generated mod output directory.
    Returns:
        Generated overworld YAML directory.
    """
    source = assets_dir / "overworld"
    output = generated_dir / "overworld"
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    return output


def apply_metadata_patch(overworld_dir: Path, document: dict) -> list[dict]:
    """Apply sparse metadata patch operations.

    Parameters:
        overworld_dir: Generated overworld YAML directory.
        document: Parsed metadata patch document.
    Returns:
        Applied operation summaries.
    """
    applied = []
    touched_navigation = False
    for operation in patch_operations(document):
        if operation.get("kind") not in METADATA_KINDS:
            raise ValueError("Unsupported metadata operation kind %r." % operation.get("kind"))
        validate_metadata_operation_path(operation, "metadata patch")
        touched_navigation = touched_navigation or is_navigation_operation(operation)
        area = parse_int(operation.get("screen", operation.get("area")))
        path = overworld_dir / ("overworld-%d.yaml" % area)
        if not path.exists():
            raise ValueError("Missing overworld YAML for area %d." % area)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        old_size = data.get("Header", {}).get("size")
        apply_operation(data, area, operation)
        new_size = data.get("Header", {}).get("size")
        path.write_text(yaml.dump(data, default_flow_style=None, sort_keys=False), encoding="utf-8")
        if old_size != new_size:
            resize_overworld_area(overworld_dir, area, old_size, new_size)
        applied.append({"kind": operation["kind"], "area": area, "path": operation.get("path", [])})
    if touched_navigation:
        validate_navigation_tables(overworld_dir)
    return applied


def apply_operation(data, area: int, operation: dict) -> None:
    """Apply one metadata operation, validating compiler support boundaries."""
    path = normalize_path(operation.get("path", []))
    if operation.get("kind") == "metadata.special-exit":
        raise ValueError("special_exit payloads are edited through metadata.exit rows.")
    if operation.get("kind") == "metadata.static-overlay" and not path:
        path = ["Overlays"]
    value = operation.get("value")
    domain, limit = area_limited_domain(operation, path)
    if limit is not None and area >= limit:
        require_unchanged_unsupported_domain(data, area, path, operation, domain)
        return
    if is_static_overlay_operation(operation, path):
        apply_static_overlay_operation(data, area, path, value)
        return
    value = supported_sprite_context_value(data, area, path, value)
    if value is MISSING:
        return
    if not is_header_operation(operation, path):
        set_path(data, path, value)
        return
    apply_header_operation(data, area, path, value)


def normalize_path(path) -> list:
    """Normalize metadata patch paths before dispatching domain handlers."""
    if isinstance(path, list):
        return path
    if isinstance(path, tuple):
        return list(path)
    if isinstance(path, str):
        return [path]
    return []


def is_header_operation(operation: dict, path: list) -> bool:
    """Return true for full or nested Header metadata operations."""
    return operation.get("kind") == "metadata.header" or (path and path[0] == "Header")


def area_limited_domain(operation: dict, path: list) -> tuple[str | None, int | None]:
    """Return compiler-backed area limit for list metadata domains."""
    path_key = str(path[0]) if path else ""
    kind = operation.get("kind")
    if kind == "metadata.item" or path_key == "Items":
        return "Items", METADATA_AREA_LIMITS["items"]
    if kind == "metadata.sprite" or path_key in METADATA_SPRITE_PATHS:
        return "Sprites", METADATA_AREA_LIMITS["sprites"]
    return None, None


def is_static_overlay_operation(operation: dict, path: list) -> bool:
    """Return true for ZScream-style static overlay metadata operations."""
    path_key = str(path[0]) if path else ""
    return operation.get("kind") == "metadata.static-overlay" or path_key == "Overlays"


def apply_static_overlay_operation(data, area: int, path: list, value) -> None:
    """Apply and validate one Overlays metadata operation."""
    if not path or path[0] != "Overlays":
        raise ValueError("metadata.static-overlay path must start with Overlays.")
    rows = normalize_static_overlays(data, area, data.get("Overlays") or [])
    if len(path) == 1:
        data["Overlays"] = normalize_static_overlays(data, area, [] if value is None else value)
        return
    index = path_index(path[1], "Overlays")
    if index < 0 or index >= len(rows):
        raise ValueError("Overlays index %d is outside area %d." % (index, area))
    if len(path) == 2:
        rows[index] = value
    else:
        row = dict(normalize_static_overlays(data, area, [rows[index]])[0])
        if len(path) != 3:
            raise ValueError("Overlays rows only support x, y, and tile fields.")
        row[overlay_row_key(path[2])] = value
        rows[index] = row
    data["Overlays"] = normalize_static_overlays(data, area, rows)


def overlay_row_key(key) -> str:
    """Normalize overlay row field aliases."""
    key = str(key)
    if key == "tile_id":
        return "tile"
    if key not in {"x", "y", "tile"}:
        raise ValueError("Overlays rows only support x, y, and tile fields.")
    return key


def normalize_static_overlays(data, area: int, rows) -> list[dict]:
    """Validate static overlay rows against the 64x64 overlay tile-write target."""
    if not isinstance(rows, list):
        raise ValueError("Overlays metadata for area %d must be a list." % area)
    return overworld_static_overlays.normalize_static_overlay_rows(rows, area)


def path_index(value, label: str) -> int:
    """Parse a metadata path list index."""
    index = parse_int(value)
    if isinstance(index, bool):
        raise ValueError("%s index must be an integer, not boolean." % label)
    return index


def require_unchanged_unsupported_domain(data, area: int, path: list, operation: dict,
                                         domain: str) -> None:
    """Reject metadata writes outside the compiler-backed area range."""
    if not path:
        raise ValueError("%s metadata patch path cannot be empty." % domain)
    current = path_value(data, path)
    if current == operation.get("value"):
        return
    raise ValueError("%s metadata is not compiler-backed for area %d." % (domain, area))


def path_value(data, path: list):
    """Return the current value at path, or MISSING when absent."""
    current = data
    for key in path:
        try:
            current = current[key]
        except (KeyError, IndexError, TypeError):
            return MISSING
    return current


def supported_sprite_context_value(data, area: int, path: list, value):
    """Reject changed special-area sprite context while allowing placement edits."""
    if area < SPRITE_CONTEXT_AREA_LIMIT or not is_sprite_path(path):
        return value
    if is_sprite_info_path(path):
        if path_value(data, path) == value:
            return MISSING
        raise ValueError("Sprites.info metadata is not compiler-backed for area %d." % area)
    if not is_full_sprite_set_path(path) or not isinstance(value, dict):
        return value
    current_info = path_value(data, [*path, "info"])
    current_info = {} if current_info is MISSING else current_info
    if "info" not in value:
        cleaned = dict(value)
        cleaned["info"] = current_info
        return cleaned
    if value.get("info") != current_info:
        raise ValueError("Sprites.info metadata is not compiler-backed for area %d." % area)
    cleaned = dict(value)
    cleaned["info"] = current_info
    return cleaned


def is_sprite_path(path: list) -> bool:
    """Return true for any top-level Sprites metadata path."""
    return bool(path) and str(path[0]) in METADATA_SPRITE_PATHS


def is_sprite_info_path(path: list) -> bool:
    """Return true for nested Sprites.info metadata paths."""
    return is_sprite_path(path) and len(path) >= 2 and path[1] == "info"


def is_full_sprite_set_path(path: list) -> bool:
    """Return true for full Sprites or Sprites.Stage replacement paths."""
    return is_sprite_path(path) and len(path) == 1


def apply_header_operation(data, area: int, path: list, value) -> None:
    """Apply a Header operation without accepting unsupported changed fields."""
    if not path:
        raise ValueError("Metadata patch path cannot be empty.")
    if path[0] != "Header":
        raise ValueError("metadata.header path must start with Header.")
    header = data["Header"]
    if len(path) == 1:
        if not isinstance(value, dict):
            raise ValueError("metadata.header full Header value must be an object.")
        apply_full_header(header, area, value)
        return
    apply_header_path(header, area, path[1:], value)


def apply_full_header(header: dict, area: int, value: dict) -> None:
    """Apply a full Header replacement while preserving unsupported fields."""
    for raw_key, item in value.items():
        key = header_key(raw_key)
        if key == "size":
            set_header_size(header, area, item)
        elif key in HEADER_FIELD_LIMITS:
            set_header_field(header, area, key, item)
        elif key in ("music", "ambient"):
            apply_header_tags(header, area, key, item)
        else:
            header[key] = item


def apply_header_path(header: dict, area: int, path: list, value) -> None:
    """Apply a nested Header field edit with the same support validation."""
    key = header_key(path[0])
    if key == "size" and len(path) == 1:
        set_header_size(header, area, value)
        return
    if key in HEADER_FIELD_LIMITS and len(path) == 1:
        set_header_field(header, area, key, value)
        return
    if key in ("music", "ambient") and len(path) == 2:
        set_header_tag(header, area, key, path[1], value)
        return
    set_path({"Header": header}, ["Header", key, *path[1:]], value)


def set_header_field(header: dict, area: int, key: str, value) -> None:
    """Set one direct Header field only when the compiler writes that area."""
    if area < HEADER_FIELD_LIMITS[key]:
        header[key] = value
        return
    if header.get(key) != value:
        raise ValueError("Header.%s is not compiler-backed for area %d." % (key, area))


def set_header_size(header: dict, area: int, value) -> None:
    """Set Header.size after validating the generated topology enum."""
    if value not in HEADER_SIZE_VALUES:
        raise ValueError("Header.size for area %d must be small, big, wide, or tall." % area)
    header["size"] = value


def apply_header_tags(header: dict, area: int, key: str, value) -> None:
    """Apply Header music/ambient maps without adding unsupported stage tags."""
    if not isinstance(value, dict):
        raise ValueError("Header.%s value must be an object." % key)
    for tag, item in value.items():
        set_header_tag(header, area, key, tag, item)


def set_header_tag(header: dict, area: int, key: str, tag: str, value) -> None:
    """Set one music/ambient tag only when the area has that progression slot."""
    target = header.setdefault(key, {})
    if header_tag_backed(area, tag):
        target[tag] = value
        return
    if target.get(tag) != value:
        raise ValueError("Header.%s.%s is not compiler-backed for area %d." % (key, tag, area))


def header_tag_backed(area: int, tag: str) -> bool:
    """Return whether the local music tables compile this progression tag."""
    return area < 64 or tag == "agahnim"


def header_key(key) -> str:
    """Normalize browser camel-case Header keys to YAML keys."""
    return HEADER_KEY_ALIASES.get(str(key), str(key))


def set_path(data, path: list, value) -> None:
    """Set a nested YAML value by path.

    Parameters:
        data: Mutable YAML data.
        path: List of dict keys or list indexes.
        value: Value to write.
    Returns:
        None.
    """
    if not path:
        raise ValueError("Metadata patch path cannot be empty.")
    current = data
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
