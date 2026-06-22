"""Resize generated overworld YAML areas while preserving owned records."""

from __future__ import annotations

import copy
from pathlib import Path

import tables
import yaml

SIZE_OFFSETS = {
    "small": (0,),
    "big": (0, 1, 8, 9),
    "wide": (0, 1),
    "tall": (0, 8),
}
SIZE_VALUES = set(SIZE_OFFSETS)
GRID_STEP = 32
PIXEL_STEP = 512


def resize_overworld_area(overworld_dir: Path, area: int, old_size: str, new_size: str) -> None:
    """Resize one generated normal overworld area and move YAML records."""
    old_size = canonical_size(old_size)
    new_size = canonical_size(new_size)
    if area >= 128 or old_size == new_size:
        return
    validate_top_left(area, new_size)
    topology = build_current_topology(overworld_dir, {area: old_size})
    if topology["parents"].get(area) != area:
        raise ValueError("Header.size can only be changed on generated area head %d." % area)
    old_offsets = SIZE_OFFSETS[old_size]
    new_offsets = SIZE_OFFSETS[new_size]
    validate_absorbed_owners(area, old_offsets, new_offsets, topology)
    parent = read_area(overworld_dir, area)
    parent["Header"]["size"] = new_size
    split_parent_records(overworld_dir, area, parent, new_offsets, old_offsets)
    merge_new_children(overworld_dir, area, parent, old_offsets, new_offsets, topology)
    write_area(overworld_dir, area, parent)


def canonical_size(value: str) -> str:
    """Return the YAML size keyword accepted by the local compiler."""
    if value == "large":
        return "big"
    if value not in SIZE_VALUES:
        raise ValueError("Header.size must be small, big, wide, or tall.")
    return value


def validate_top_left(area: int, size: str) -> None:
    """Reject shapes that would cross the 8x8 normal-world grid."""
    x = area & 7
    y = (area & 63) >> 3
    if size in ("big", "wide") and x >= 7:
        raise ValueError("Header.size %s in area %d crosses the east world edge." % (size, area))
    if size in ("big", "tall") and y >= 7:
        raise ValueError("Header.size %s in area %d crosses the south world edge." % (size, area))


def build_current_topology(overworld_dir: Path, override_sizes: dict[int, str] | None = None) -> dict:
    """Return the generated normal-world ownership before a resize is applied."""
    override_sizes = override_sizes or {}
    parents: dict[int, int] = {}
    children: dict[int, list[int]] = {}
    sizes: dict[int, str] = {}
    for world_base in (0, 64):
        covered: dict[int, int] = {}
        for y in range(8):
            for x in range(8):
                area = world_base + y * 8 + x
                if area in covered:
                    continue
                path = area_path(overworld_dir, area)
                if not path.exists():
                    raise ValueError("Missing overworld YAML for generated area head %d." % area)
                data = read_area(overworld_dir, area)
                size = canonical_size(override_sizes.get(area, data.get("Header", {}).get("size")))
                validate_top_left(area, size)
                owned = []
                for offset in SIZE_OFFSETS[size]:
                    child = area + offset
                    if child in covered:
                        raise ValueError("Overworld area %d is covered by both %d and %d." % (
                            child, covered[child], area))
                    if offset and area_path(overworld_dir, child).exists():
                        raise ValueError(
                            "Overworld child area %d has YAML but is owned by parent area %d." % (
                                child, area))
                    covered[child] = area
                    parents[child] = area
                    sizes[child] = size
                    owned.append(child)
                children[area] = owned
    return {"children": children, "parents": parents, "sizes": sizes}


def validate_absorbed_owners(area: int, old_offsets: tuple[int, ...], new_offsets: tuple[int, ...],
                             topology: dict) -> None:
    """Reject expansions that would split another generated parent area."""
    old_children = {area + offset for offset in old_offsets}
    new_children = {area + offset for offset in new_offsets}
    checked = set()
    for child in sorted(new_children - old_children):
        owner = topology["parents"].get(child)
        if owner is None:
            raise ValueError("Overworld area %d has no generated parent before resize." % child)
        if owner == area or owner in checked:
            continue
        owned = set(topology["children"].get(owner, [owner]))
        if not owned <= new_children:
            outside = sorted(owned - new_children)
            raise ValueError(
                "Header.size for area %d would partially absorb parent area %d; outside=%s." % (
                    area, owner, outside))
        checked.add(owner)


def split_parent_records(overworld_dir: Path, area: int, parent: dict,
                         kept_offsets: tuple[int, ...], old_offsets: tuple[int, ...]) -> None:
    """Move records no longer owned by parent into generated child YAML files."""
    children: dict[int, dict] = {}
    for offset in old_offsets:
        if offset and offset not in kept_offsets:
            children[area + offset] = empty_area(parent, area + offset)
    split_grid_list(parent, "Entrances", kept_offsets, children, area, overworld_dir)
    split_grid_list(parent, "Holes", kept_offsets, children, area, overworld_dir)
    split_grid_list(parent, "Overlays", kept_offsets, children, area, overworld_dir)
    split_item_list(parent, kept_offsets, children, area, overworld_dir)
    split_destination_list(parent, "Travel", kept_offsets, children, area, overworld_dir)
    split_destination_list(parent, "Exits", kept_offsets, children, area, overworld_dir)
    for key in sprite_keys(parent):
        split_sprite_list(parent, key, kept_offsets, children, area, overworld_dir)
    for child_area, child_data in children.items():
        write_area(overworld_dir, child_area, child_data)


def merge_new_children(overworld_dir: Path, area: int, parent: dict, old_offsets: tuple[int, ...],
                       new_offsets: tuple[int, ...], topology: dict) -> None:
    """Merge newly owned child YAML records into the resized parent."""
    merged = set()
    for offset in new_offsets:
        if offset in old_offsets or offset == 0:
            continue
        child_area = area + offset
        owner = topology["parents"].get(child_area, child_area)
        if owner == area or owner in merged:
            continue
        owner_offset = owner - area
        path = area_path(overworld_dir, owner)
        if not path.exists():
            raise ValueError("Missing overworld YAML for absorbed parent area %d." % owner)
        child = read_area(overworld_dir, owner)
        merge_grid_list(parent, child, "Entrances", owner_offset)
        merge_grid_list(parent, child, "Holes", owner_offset)
        merge_grid_list(parent, child, "Overlays", owner_offset)
        merge_items(parent, child, owner_offset)
        merge_destination_list(parent, child, "Travel", owner_offset)
        merge_destination_list(parent, child, "Exits", owner_offset)
        for key in sprite_keys(child):
            ensure_sprite_set(parent, key, child[key])
            merge_sprite_rows(parent[key], child[key], owner_offset)
        path.unlink()
        merged.add(owner)


def split_grid_list(parent: dict, key: str, kept_offsets: tuple[int, ...], children: dict[int, dict],
                    area: int, overworld_dir: Path) -> None:
    """Split x/y grid records such as entrances and holes."""
    kept = []
    for row in parent.get(key, []):
        x, y = grid_row_xy(row)
        offset = grid_offset(x, y)
        if offset in kept_offsets:
            kept.append(row)
        else:
            child = child_data(children, overworld_dir, parent, area + offset)
            child.setdefault(key, []).append(adjust_grid_row_xy(row, offset, -GRID_STEP))
    parent[key] = kept


def split_item_list(parent: dict, kept_offsets: tuple[int, ...], children: dict[int, dict],
                    area: int, overworld_dir: Path) -> None:
    """Split [x, y, item] rows into child files when a parent shrinks."""
    kept = []
    for row in parent.get("Items", []):
        offset = grid_offset(row[0], row[1])
        if offset in kept_offsets:
            kept.append(row)
        else:
            child = child_data(children, overworld_dir, parent, area + offset)
            child.setdefault("Items", []).append(adjust_list_xy(row, offset, -GRID_STEP))
    parent["Items"] = kept


def split_sprite_list(parent: dict, key: str, kept_offsets: tuple[int, ...], children: dict[int, dict],
                      area: int, overworld_dir: Path) -> None:
    """Split one sprite-stage placement list without changing stage info."""
    kept = []
    for row in parent[key].get("sprites", []):
        offset = grid_offset(row[0], row[1])
        if offset in kept_offsets:
            kept.append(row)
        else:
            child = child_data(children, overworld_dir, parent, area + offset)
            ensure_sprite_set(child, key, parent[key])
            child[key]["sprites"].append(adjust_list_xy(row, offset, -GRID_STEP))
    parent[key]["sprites"] = kept


def split_destination_list(parent: dict, key: str, kept_offsets: tuple[int, ...],
                           children: dict[int, dict], area: int, overworld_dir: Path) -> None:
    """Split Travel/Exits pixel records into independent child areas."""
    kept = []
    for row in parent.get(key, []):
        xy = row.get("xy", [0, 0])
        offset = pixel_offset(xy[0], xy[1])
        if offset in kept_offsets:
            kept.append(row)
        else:
            child = child_data(children, overworld_dir, parent, area + offset)
            child.setdefault(key, []).append(adjust_destination(row, offset, -PIXEL_STEP, -GRID_STEP))
    parent[key] = kept


def merge_grid_list(parent: dict, child: dict, key: str, offset: int) -> None:
    """Move child x/y grid records into the parent coordinate space."""
    parent.setdefault(key, []).extend(adjust_grid_row_xy(row, offset, GRID_STEP) for row in child.get(key, []))


def merge_items(parent: dict, child: dict, offset: int) -> None:
    """Move child item rows into the parent coordinate space."""
    parent.setdefault("Items", []).extend(adjust_list_xy(row, offset, GRID_STEP) for row in child.get("Items", []))


def merge_sprite_rows(parent_set: dict, child_set: dict, offset: int) -> None:
    """Move child sprite rows into the parent coordinate space."""
    parent_set.setdefault("sprites", []).extend(
        adjust_list_xy(row, offset, GRID_STEP) for row in child_set.get("sprites", []))


def merge_destination_list(parent: dict, child: dict, key: str, offset: int) -> None:
    """Move child Travel/Exits pixel records into the parent coordinate space."""
    parent.setdefault(key, []).extend(
        adjust_destination(row, offset, PIXEL_STEP, GRID_STEP) for row in child.get(key, []))


def adjust_destination(row: dict, offset: int, pixel_step: int, grid_step: int) -> dict:
    """Adjust pixel-space fields and optional door grid coordinates."""
    moved = copy.deepcopy(row)
    for key in ("xy", "scroll_xy", "camera_xy"):
        if key in moved:
            moved[key] = adjust_pair(moved[key], offset, pixel_step)
    if isinstance(moved.get("door"), list) and len(moved["door"]) == 3:
        moved["door"] = [moved["door"][0], *adjust_pair(moved["door"][1:], offset, grid_step)]
    return moved


def adjust_dict_xy(row: dict, offset: int, step: int) -> dict:
    """Adjust dict rows with x/y fields."""
    moved = copy.deepcopy(row)
    moved["x"], moved["y"] = adjust_pair([moved.get("x", 0), moved.get("y", 0)], offset, step)
    return moved


def adjust_grid_row_xy(row, offset: int, step: int):
    """Adjust either dict x/y rows or list rows whose first two fields are x/y."""
    return adjust_dict_xy(row, offset, step) if isinstance(row, dict) else adjust_list_xy(row, offset, step)


def adjust_list_xy(row: list, offset: int, step: int) -> list:
    """Adjust list rows whose first two fields are x/y."""
    moved = copy.deepcopy(row)
    moved[0], moved[1] = adjust_pair(moved[:2], offset, step)
    return moved


def grid_row_xy(row) -> tuple[int, int]:
    """Read x/y from a dict grid row or a list row."""
    return (row.get("x", 0), row.get("y", 0)) if isinstance(row, dict) else (row[0], row[1])


def adjust_pair(pair: list, offset: int, step: int) -> list:
    """Add or subtract one child quadrant offset from a coordinate pair."""
    return [pair[0] + (step if offset & 1 else 0), pair[1] + (step if offset & 8 else 0)]


def grid_offset(x: int, y: int) -> int:
    """Return the 2x2 child offset for 16px-grid records."""
    return (1 if x >= GRID_STEP else 0) | (8 if y >= GRID_STEP else 0)


def pixel_offset(x: int, y: int) -> int:
    """Return the 2x2 child offset for pixel-space records."""
    return (1 if x >= PIXEL_STEP else 0) | (8 if y >= PIXEL_STEP else 0)


def child_data(children: dict[int, dict], overworld_dir: Path, parent: dict, area: int) -> dict:
    """Return an existing or newly synthesized child YAML record."""
    if area not in children:
        path = area_path(overworld_dir, area)
        children[area] = read_area(overworld_dir, area) if path.exists() else empty_area(parent, area)
    return children[area]


def empty_area(parent: dict, area: int) -> dict:
    """Create an independent child YAML shell using parent visual context."""
    data = {key: [] for key in ("Travel", "Entrances", "Holes", "Exits", "Items", "Overlays")}
    data["Header"] = copy.deepcopy(parent["Header"])
    data["Header"]["name"] = tables.kAreaNames[area]
    data["Header"]["size"] = "small"
    for key in sprite_keys(parent):
        data[key] = {"info": copy.deepcopy(parent[key].get("info", {})), "sprites": []}
    return data


def ensure_sprite_set(target: dict, key: str, source_set: dict) -> None:
    """Ensure a target area has a compatible sprite stage shell."""
    target.setdefault(key, {"info": copy.deepcopy(source_set.get("info", {})), "sprites": []})
    target[key].setdefault("sprites", [])


def sprite_keys(data: dict) -> list[str]:
    """Return top-level sprite-stage keys in YAML order."""
    return [key for key in data if key.startswith("Sprites")]


def read_area(overworld_dir: Path, area: int) -> dict:
    """Read one generated overworld YAML file."""
    return yaml.safe_load(area_path(overworld_dir, area).read_text(encoding="utf-8"))


def write_area(overworld_dir: Path, area: int, data: dict) -> None:
    """Write one generated overworld YAML file."""
    area_path(overworld_dir, area).write_text(
        yaml.dump(data, default_flow_style=None, sort_keys=False), encoding="utf-8")


def area_path(overworld_dir: Path, area: int) -> Path:
    """Return the generated YAML path for one area."""
    return overworld_dir / ("overworld-%d.yaml" % area)
