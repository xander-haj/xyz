"""Validation for data-only overworld mod manifests and patch files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import safe_join, validate_mod_id
from .zscream_parity import assert_zscream_parity_contract, known_zscream_patch_kinds

MOD_FORMAT = "zelda3-overworld-mod-v1"
PATCH_FORMATS = {
    "terrain": "zelda3-overworld-terrain-patch-v1",
    "map32-definitions": "zelda3-overworld-map32-definitions-v1",
    "map16-definitions": "zelda3-overworld-map16-definitions-v1",
    "map8-words": "zelda3-overworld-map8-words-v1",
    "tile-attributes": "zelda3-overworld-tile-attributes-v1",
    "chr-recipes": "zelda3-overworld-chr-recipes-v1",
    "palettes": "zelda3-overworld-palettes-v1",
    "metadata": "zelda3-overworld-metadata-v1",
    "gravestones": "zelda3-overworld-gravestones-v1",
    "grove-border": "zelda3-overworld-grove-border-v1",
}
KNOWN_PATCH_KINDS = known_zscream_patch_kinds()
PATCH_OPERATION_KEYS = ("patches", "definitions", "edits", "recipes")
PATCH_FORMAT_KINDS = {
    PATCH_FORMATS["terrain"]: {"terrain.map32-placement"},
    PATCH_FORMATS["map32-definitions"]: {"tile.map32-definition"},
    PATCH_FORMATS["map16-definitions"]: {"tile.map16-definition"},
    PATCH_FORMATS["map8-words"]: {"tile.map8-word"},
    PATCH_FORMATS["tile-attributes"]: {"tile.map8-attribute"},
    PATCH_FORMATS["chr-recipes"]: {"chr.tile-recipe"},
    PATCH_FORMATS["palettes"]: {"palette.color-edit", "palette.assignment"},
    PATCH_FORMATS["metadata"]: {
        "metadata.header",
        "metadata.static-overlay",
        "metadata.travel",
        "metadata.entrance",
        "metadata.hole",
        "metadata.exit",
        "metadata.item",
        "metadata.sprite",
    },
    PATCH_FORMATS["gravestones"]: {"gravestone.record"},
    PATCH_FORMATS["grove-border"]: set(),
}
PATCH_FORMAT_COLLECTIONS = {
    PATCH_FORMATS["terrain"]: "patches",
    PATCH_FORMATS["map32-definitions"]: "definitions",
    PATCH_FORMATS["map16-definitions"]: "definitions",
    PATCH_FORMATS["map8-words"]: "edits",
    PATCH_FORMATS["tile-attributes"]: "edits",
    PATCH_FORMATS["chr-recipes"]: "recipes",
    PATCH_FORMATS["palettes"]: "patches",
    PATCH_FORMATS["metadata"]: "patches",
    PATCH_FORMATS["gravestones"]: "patches",
    PATCH_FORMATS["grove-border"]: "patches",
}
METADATA_KIND_PATHS = {
    "metadata.header": "Header",
    "metadata.travel": "Travel",
    "metadata.entrance": "Entrances",
    "metadata.hole": "Holes",
    "metadata.exit": "Exits",
    "metadata.item": "Items",
}
METADATA_SPRITE_PATHS = {
    "Sprites",
    "Sprites.Beginning",
    "Sprites.FirstPart",
    "Sprites.SecondPart",
}


def load_json(path: Path) -> Any:
    """Load one JSON file.

    Parameters:
        path: JSON file path.
    Returns:
        Parsed JSON value.
    """
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    """Write one stable, reviewed JSON file.

    Parameters:
        path: Destination file.
        data: JSON-serializable data.
    Returns:
        None.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)
        file.write("\n")


def validate_manifest(mod_dir: Path) -> dict:
    """Validate and return a mod manifest.

    Parameters:
        mod_dir: Directory containing mod.json.
    Returns:
        Parsed manifest dict.
    Raises:
        ValueError: If the manifest can execute code, escape paths, or has bad fields.
    """
    manifest_path = mod_dir / "mod.json"
    if not manifest_path.exists():
        raise ValueError("Missing mod.json in %s" % mod_dir)
    manifest = load_json(manifest_path)
    require_object(manifest, "mod manifest")
    if manifest.get("format") != MOD_FORMAT:
        raise ValueError("Unsupported mod format %r" % manifest.get("format"))
    validate_mod_id(manifest.get("id"))
    for key in ["name", "version", "author"]:
        require_string(manifest.get(key), key)
    target = manifest.get("target", {})
    require_object(target, "target")
    if target.get("requiresExtractedAssets") is not True:
        raise ValueError("Overworld mods must require local extracted assets.")
    patches = manifest.get("patches", [])
    require_list(patches, "patches")
    for patch in patches:
        require_string(patch, "patch path")
        safe_join(mod_dir, patch)
        if Path(patch).suffix != ".json":
            raise ValueError("Patch path must end in .json: %s" % patch)
    return manifest


def validate_patch_document(data: Any, label: str = "patch") -> dict:
    """Validate a patch document envelope and operation kinds.

    Parameters:
        data: Parsed patch JSON.
        label: File or route label used in diagnostics.
    Returns:
        Parsed patch dict when valid.
    """
    assert_zscream_parity_contract()
    require_object(data, label)
    format_value = data.get("format")
    if format_value not in PATCH_FORMATS.values():
        raise ValueError("%s has unsupported format %r" % (label, format_value))
    allowed_kinds = PATCH_FORMAT_KINDS[format_value]
    operations = patch_operations(data)
    for operation in operations:
        require_object(operation, "%s operation" % label)
        kind = operation.get("kind")
        if kind not in KNOWN_PATCH_KINDS:
            raise ValueError("%s has unknown operation kind %r" % (label, kind))
        if kind not in allowed_kinds:
            raise ValueError("%s has operation kind %r outside format %r" % (label, kind, format_value))
        validate_operation_shape(format_value, operation, label)
    return data


def validate_operation_shape(format_value: str, operation: dict, label: str) -> None:
    """Validate operation fields whose meaning depends on the patch format."""
    if format_value == PATCH_FORMATS["metadata"]:
        validate_metadata_operation_path(operation, label)


def validate_metadata_operation_path(operation: dict, label: str = "metadata patch") -> None:
    """Require metadata operation kinds to own the top-level YAML path they edit."""
    kind = operation.get("kind")
    key = metadata_path_key(operation.get("path", []))
    if kind == "metadata.static-overlay" and not key:
        return
    if not key:
        raise ValueError("%s operation %r must include a metadata path." % (label, kind))
    if kind == "metadata.static-overlay":
        expected = "Overlays"
    elif kind == "metadata.sprite":
        if key not in METADATA_SPRITE_PATHS:
            raise ValueError("%s operation %r cannot edit metadata path %r." % (label, kind, key))
        return
    else:
        expected = METADATA_KIND_PATHS.get(kind)
    if expected is not None and key != expected:
        raise ValueError("%s operation %r cannot edit metadata path %r." % (label, kind, key))


def metadata_path_key(path) -> str:
    """Return the top-level YAML key from a JSON patch path."""
    if isinstance(path, list):
        return str(path[0]) if path else ""
    if isinstance(path, str):
        return path
    return ""


def patch_operations(data: dict) -> list:
    """Return the operation list from any supported patch envelope.

    Parameters:
        data: Parsed patch document.
    Returns:
        List of patch operation dicts.
    """
    expected_key = PATCH_FORMAT_COLLECTIONS.get(data.get("format"))
    present_keys = [key for key in PATCH_OPERATION_KEYS if key in data]
    if expected_key is not None:
        unexpected = [key for key in present_keys if key != expected_key]
        if unexpected:
            raise ValueError("Patch format %r cannot use collection(s) %s." % (data.get("format"), unexpected))
        if expected_key not in data:
            raise ValueError("Patch format %r must use collection %r." % (data.get("format"), expected_key))
        require_list(data[expected_key], expected_key)
        return data[expected_key]
    for key in PATCH_OPERATION_KEYS:
        if key in data:
            require_list(data[key], key)
            return data[key]
    return []


def require_object(value: Any, label: str) -> None:
    """Require a JSON object.

    Parameters:
        value: Candidate value.
        label: Diagnostic label.
    Returns:
        None.
    """
    if not isinstance(value, dict):
        raise ValueError("%s must be an object." % label)


def require_list(value: Any, label: str) -> None:
    """Require a JSON list.

    Parameters:
        value: Candidate value.
        label: Diagnostic label.
    Returns:
        None.
    """
    if not isinstance(value, list):
        raise ValueError("%s must be a list." % label)


def require_string(value: Any, label: str) -> None:
    """Require a non-empty JSON string.

    Parameters:
        value: Candidate value.
        label: Diagnostic label.
    Returns:
        None.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string." % label)
