"""Build generated local overworld assets from instruction-only mod recipes."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .chr_patch import apply_chr_patch, finalize_chr_packs, prepare_chr_packs
from .conflict_report import ConflictReport
from .dialogue_patch import apply_dialogue_patch, finalize_dialogue, prepare_dialogue
from .grove_patch import apply_grove_patch
from .gravestone_patch import apply_gravestone_patch, finalize_gravestones, prepare_gravestones
from .palette_patch import apply_palette_patch, finalize_palettes, prepare_palettes
from .paths import ASSETS_DIR, generated_dir_for, mod_dir_from_arg, validate_mod_id
from .schema import load_json, validate_manifest, validate_patch_document, write_json
from .terrain_patch import apply_terrain_patch, copy_base_maps
from .tile_patch import apply_tile_patch, finalize_tile_sources, prepare_tile_sources
from .yaml_patch import apply_metadata_patch, copy_base_yaml


def list_mods() -> list[dict]:
    """List overworld mod directories after manifest and patch validation.

    Parameters: none.
    Returns:
        List of mod summaries.
    """
    root = ASSETS_DIR.parent / "mods" / "overworld"
    if not root.exists():
        return []
    mods = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not (child / "mod.json").exists():
            continue
        try:
            manifest = validate_manifest(child)
            validate_patch_files(child, manifest)
            mods.append({"id": manifest["id"], "name": manifest["name"], "path": str(child)})
        except (OSError, ValueError, json.JSONDecodeError) as error:
            mods.append({"id": child.name, "name": child.name, "path": str(child), "error": str(error)})
    return mods


def validate_patch_files(mod_dir: Path, manifest: dict) -> None:
    """Validate every patch file listed by a mod manifest."""
    for patch_path in manifest.get("patches", []):
        validate_patch_document(load_json(mod_dir / patch_path), patch_path)


def validate_mods(values: list[str]) -> list[dict]:
    """Validate one or more mod packages.

    Parameters:
        values: Mod ids or paths.
    Returns:
        Parsed manifests.
    """
    manifests = []
    for value in values:
        mod_dir = mod_dir_from_arg(value)
        manifest = validate_manifest(mod_dir)
        validate_patch_files(mod_dir, manifest)
        manifests.append({"dir": mod_dir, "manifest": manifest})
    return manifests


def build_mods(values: list[str]) -> dict:
    """Build generated local assets for one or more ordered mods.

    Parameters:
        values: Mod ids or paths in load order.
    Returns:
        Build summary with generated paths and conflict report.
    """
    entries = validate_mods(values)
    mod_ids = [validate_mod_id(entry["manifest"]["id"]) for entry in entries]
    generated_dir = generated_dir_for(mod_ids)
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)

    report = ConflictReport()
    summaries = []
    map_dir = copy_base_maps(ASSETS_DIR / "overworld_maps", generated_dir)
    yaml_dir = copy_base_yaml(ASSETS_DIR, generated_dir)
    tile_state = prepare_tile_sources(ASSETS_DIR, generated_dir)
    palettes = prepare_palettes(ASSETS_DIR, generated_dir)
    chr_packs = prepare_chr_packs(ASSETS_DIR, generated_dir)
    gravestones = prepare_gravestones(generated_dir)
    dialogue = prepare_dialogue(ASSETS_DIR, generated_dir)
    terrain_touched = {}

    for entry in entries:
        summaries.extend(apply_mod(entry["dir"], entry["manifest"], generated_dir, map_dir,
                                   yaml_dir, tile_state, palettes, chr_packs, gravestones, dialogue, report,
                                   terrain_touched))
    report.raise_if_needed()
    finalize_tile_sources(generated_dir, tile_state)
    finalize_palettes(generated_dir, palettes)
    finalize_chr_packs(generated_dir, chr_packs)
    finalize_gravestones(generated_dir, gravestones)
    finalize_dialogue(generated_dir, dialogue)
    summary = build_summary(mod_ids, generated_dir, summaries, report)
    write_json(generated_dir / "source_patch_summary.json", summary)
    return summary


def apply_mod(mod_dir: Path, manifest: dict, generated_dir: Path, map_dir: Path, yaml_dir: Path,
              tile_state: dict, palettes: dict, chr_packs: dict, gravestones: dict, dialogue: dict,
              report: ConflictReport, terrain_touched: dict) -> list[dict]:
    """Apply every patch listed by one manifest.

    Parameters are resolved mod/build state and a conflict report.
    Returns:
        Applied patch summaries.
    """
    documents = []
    for patch_path in manifest.get("patches", []):
        document = validate_patch_document(load_json(mod_dir / patch_path), patch_path)
        documents.append((patch_path, document))
    summaries = []
    for patch_path, document in sorted(documents, key=lambda item: document_phase(item[1])):
        summaries.extend(apply_document(mod_dir, patch_path, document, generated_dir, map_dir,
                                        yaml_dir, tile_state, palettes, chr_packs, gravestones, dialogue, report,
                                        terrain_touched))
    return summaries


def document_phase(document: dict) -> int:
    """Return the build phase for a patch document.

    Parameters:
        document: Parsed patch document.
    Returns:
        Numeric phase; lower phases apply first.
    """
    format_value = document["format"]
    if "definitions" in format_value or "map8-words" in format_value or "tile-attributes" in format_value:
        return 0
    if "terrain-patch" in format_value:
        return 1
    return 2


def apply_document(mod_dir: Path, patch_path: str, document: dict, generated_dir: Path, map_dir: Path,
                   yaml_dir: Path, tile_state: dict, palettes: dict, chr_packs: dict,
                   gravestones: dict, dialogue: dict, report: ConflictReport,
                   terrain_touched: dict) -> list[dict]:
    """Dispatch one patch document to the matching layer handler.

    Parameters are the patch source and mutable generated build state.
    Returns:
        Applied operation summaries.
    """
    format_value = document["format"]
    applied = []
    if format_value.endswith("terrain-patch-v1"):
        applied = apply_terrain_patch(
            map_dir, document, report, tile_state.get("map32_allocator"), terrain_touched)
    elif ("map32-definitions" in format_value or "map16-definitions" in format_value or
          "map8-words" in format_value or "tile-attributes" in format_value):
        applied = apply_tile_patch(tile_state, document, report)
    elif "chr-recipes" in format_value:
        applied = apply_chr_patch(chr_packs, ASSETS_DIR, document)
    elif "palettes" in format_value:
        applied = apply_palette_patch(palettes, document, yaml_dir)
    elif "metadata" in format_value:
        applied = apply_metadata_patch(yaml_dir, document)
    elif "gravestones" in format_value:
        applied = apply_gravestone_patch(gravestones, document)
    elif "dialogue" in format_value:
        applied = apply_dialogue_patch(dialogue, document, report)
    elif "grove-border" in format_value:
        applied = apply_grove_patch(generated_dir, document)
    return [{"mod": mod_dir.name, "patch": patch_path, **item} for item in applied]


def build_summary(mod_ids: list[str], generated_dir: Path, applied: list[dict], report: ConflictReport) -> dict:
    """Create a deterministic generated build summary.

    Parameters:
        mod_ids: Ordered mod ids.
        generated_dir: Generated output directory.
        applied: Applied operation summaries.
        report: ConflictReport for this build.
    Returns:
        JSON-serializable build summary.
    """
    return {
        "format": "zelda3-overworld-generated-summary-v1",
        "mods": mod_ids,
        "generated": {
            "root": str(generated_dir),
            "overworld_maps": str(generated_dir / "overworld_maps"),
            "overworld": str(generated_dir / "overworld"),
            "map32_to_map16": str(generated_dir / "map32_to_map16.txt"),
            "dialogue": str(generated_dir / "dialogue.txt"),
            "gravestones": str(generated_dir / "tables" / "overworld_gravestones.json"),
        },
        "baseHashes": base_hashes(),
        "applied": applied,
        "conflictReport": report.to_json(),
    }


def base_hashes() -> dict[str, str]:
    """Hash key local extracted files used as mod bases.

    Parameters: none.
    Returns:
        Dict of relative paths to sha256 values.
    """
    hashes = {}
    for relative in ["map32_to_map16.txt", "overworld_maps/000.json", "overworld_maps/128.json"]:
        path = ASSETS_DIR / relative
        if path.exists():
            hashes[relative] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes
