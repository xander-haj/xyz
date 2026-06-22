"""Apply copyright-safe CHR tile recipes to generated BG graphics packs."""

from __future__ import annotations

from pathlib import Path

import overworld_map32

from .resolver import parse_int
from .schema import patch_operations

TILE_BYTES = 24
TILE_PIXELS = 8


def prepare_chr_packs(assets_dir: Path, generated_dir: Path) -> dict[int, bytearray]:
    """Load base compressed BG packs from the viewer dump when present.

    Parameters:
        assets_dir: Repository assets directory.
        generated_dir: Generated mod output directory.
    Returns:
        Mutable decompressed pack data keyed by pack id.
    """
    output = generated_dir / "gfx" / "bg"
    output.mkdir(parents=True, exist_ok=True)
    return {}


def apply_chr_patch(packs: dict[int, bytearray], assets_dir: Path, document: dict) -> list[dict]:
    """Apply CHR tile recipes by mutating decoded local pack data.

    Parameters:
        packs: Mutable decoded pack cache.
        assets_dir: Repository assets directory containing overworld_dump.
        document: Parsed CHR patch document.
    Returns:
        Applied recipe summaries.
    """
    applied = []
    for recipe in patch_operations(document):
        if recipe.get("kind") != "chr.tile-recipe":
            raise ValueError("Unsupported CHR operation kind %r." % recipe.get("kind"))
        source = recipe.get("source", {})
        target = recipe.get("target", source)
        source_pack = parse_chr_int(source.get("pack"), "source pack")
        source_tile = parse_chr_int(source.get("tile"), "source tile")
        target_pack = parse_chr_int(target.get("pack", source_pack), "target pack")
        target_tile = parse_chr_int(target.get("tile", source_tile), "target tile")
        validate_nonnegative(source_pack, "source pack")
        validate_nonnegative(source_tile, "source tile")
        validate_nonnegative(target_pack, "target pack")
        validate_nonnegative(target_tile, "target tile")
        source_pixels = read_tile(load_pack(packs, assets_dir, source_pack), source_tile)
        apply_pixel_ops(source_pixels, recipe.get("ops", []))
        write_tile(load_pack(packs, assets_dir, target_pack), target_tile, source_pixels)
        applied.append({"kind": recipe["kind"], "pack": target_pack, "tile": target_tile})
    return applied


def finalize_chr_packs(generated_dir: Path, packs: dict[int, bytearray]) -> None:
    """Write changed BG packs as valid literal LZ streams.

    Parameters:
        generated_dir: Generated mod output directory.
        packs: Mutable decompressed pack cache.
    Returns:
        None.
    """
    output = generated_dir / "gfx" / "bg"
    output.mkdir(parents=True, exist_ok=True)
    for pack, decoded in packs.items():
        (output / ("%03d.bin" % pack)).write_bytes(overworld_map32.compress_store(list(decoded)))


def load_pack(packs: dict[int, bytearray], assets_dir: Path, pack: int) -> bytearray:
    """Load and decompress one BG graphics pack from the base dump.

    Parameters:
        packs: Mutable decoded pack cache.
        assets_dir: Repository assets directory.
        pack: BG graphics pack id.
    Returns:
        Mutable decompressed 3bpp pack bytes.
    """
    if pack not in packs:
        path = assets_dir / "overworld_dump" / "gfx" / "bg" / ("%03d.bin" % pack)
        if not path.exists():
            raise ValueError("Missing BG graphics pack %03d in overworld_dump." % pack)
        packs[pack] = bytearray(decompress_lz(path.read_bytes()))
    return packs[pack]


def decompress_lz(data: bytes) -> bytes:
    """Decode a Zelda 3 LZ stream from a bytes object.

    Parameters:
        data: Compressed stream.
    Returns:
        Decompressed bytes.
    """
    dst = bytearray()
    index = 0
    while index < len(data):
        cmd = data[index]
        index += 1
        if cmd == 0xFF:
            return bytes(dst)
        if (cmd & 0xE0) != 0xE0:
            length = (cmd & 0x1F) + 1
            mode = cmd & 0xE0
        else:
            length = data[index] + ((cmd & 3) << 8) + 1
            index += 1
            mode = (cmd << 3) & 0xE0
        index = apply_lz_command(data, index, dst, mode, length)
    return bytes(dst)


def apply_lz_command(data: bytes, index: int, dst: bytearray, mode: int, length: int) -> int:
    """Apply one Zelda 3 LZ command.

    Parameters are compressed bytes, current index, output buffer, mode, and length.
    Returns:
        Next compressed index.
    """
    if mode == 0x00:
        dst.extend(data[index:index + length])
        return index + length
    if mode == 0x20:
        dst.extend([data[index]] * length)
        return index + 1
    if mode == 0x40:
        first, second = data[index], data[index + 1]
        dst.extend(first if (n & 1) == 0 else second for n in range(length))
        return index + 2
    if mode == 0x60:
        value = data[index]
        dst.extend((value + n) & 0xFF for n in range(length))
        return index + 1
    if mode & 0x80:
        offset = data[index] | (data[index + 1] << 8)
        dst.extend(dst[offset + n] for n in range(length))
        return index + 2
    raise ValueError("Unknown LZ command mode %r" % mode)


def read_tile(pack: bytearray, tile: int) -> list[list[int]]:
    """Decode one 8x8 3bpp tile to palette indexes.

    Parameters:
        pack: Decompressed pack bytes.
        tile: Tile index in the pack.
    Returns:
        8x8 matrix of palette indexes 0..7.
    """
    offset = tile * TILE_BYTES
    if offset + TILE_BYTES > len(pack):
        raise ValueError("CHR tile %d outside decoded pack." % tile)
    rows = []
    for y in range(TILE_PIXELS):
        lo = pack[offset + y * 2]
        hi = pack[offset + y * 2 + 1]
        plane = pack[offset + 16 + y]
        row = []
        for x in range(TILE_PIXELS):
            bit = 7 - x
            row.append(((lo >> bit) & 1) | (((hi >> bit) & 1) << 1) | (((plane >> bit) & 1) << 2))
        rows.append(row)
    return rows


def write_tile(pack: bytearray, tile: int, pixels: list[list[int]]) -> None:
    """Encode one 8x8 3bpp tile back into a decoded pack.

    Parameters:
        pack: Decompressed pack bytes.
        tile: Tile index.
        pixels: 8x8 palette-index matrix.
    Returns:
        None.
    """
    offset = tile * TILE_BYTES
    if offset + TILE_BYTES > len(pack):
        raise ValueError("CHR tile %d outside decoded pack." % tile)
    for y, row in enumerate(pixels):
        lo = hi = plane = 0
        for x, value in enumerate(row):
            if not 0 <= value <= 7:
                raise ValueError("CHR palette index must be 0..7.")
            bit = 7 - x
            lo |= (value & 1) << bit
            hi |= ((value >> 1) & 1) << bit
            plane |= ((value >> 2) & 1) << bit
        pack[offset + y * 2] = lo
        pack[offset + y * 2 + 1] = hi
        pack[offset + 16 + y] = plane


def apply_pixel_ops(pixels: list[list[int]], ops: list[dict]) -> None:
    """Apply supported pixel operations to an 8x8 tile matrix.

    Parameters:
        pixels: Mutable 8x8 palette-index matrix.
        ops: List of setPixel/hline/vline/fillRect operations.
    Returns:
        None.
    """
    for op in ops:
        name = op.get("op")
        color = parse_chr_int(op.get("paletteIndex"), "CHR palette index")
        if name == "setPixel":
            x = parse_chr_int(op.get("x"), "CHR x")
            y = parse_chr_int(op.get("y"), "CHR y")
            set_pixel(pixels, x, y, color)
        elif name == "hline":
            x = parse_chr_int(op.get("x"), "CHR x")
            y = parse_chr_int(op.get("y"), "CHR y")
            length = parse_chr_extent(op.get("length"), "CHR hline length")
            for dx in range(length):
                set_pixel(pixels, x + dx, y, color)
        elif name == "vline":
            x = parse_chr_int(op.get("x"), "CHR x")
            y = parse_chr_int(op.get("y"), "CHR y")
            length = parse_chr_extent(op.get("length"), "CHR vline length")
            for dy in range(length):
                set_pixel(pixels, x, y + dy, color)
        elif name == "fillRect":
            x = parse_chr_int(op.get("x"), "CHR x")
            y = parse_chr_int(op.get("y"), "CHR y")
            width = parse_chr_extent(op.get("width"), "CHR fillRect width")
            height = parse_chr_extent(op.get("height"), "CHR fillRect height")
            for dy in range(height):
                for dx in range(width):
                    set_pixel(pixels, x + dx, y + dy, color)
        else:
            raise ValueError("Unknown CHR op %r" % name)


def parse_chr_int(value, label: str) -> int:
    """Parse one strict integer field from a CHR tile recipe.

    Parameters:
        value: Candidate recipe value.
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


def parse_chr_extent(value, label: str) -> int:
    """Parse one positive pixel-count field from a CHR tile recipe.

    Parameters:
        value: Candidate length, width, or height.
        label: Diagnostic label.
    Returns:
        Positive integer extent.
    """
    extent = parse_chr_int(value, label)
    if extent <= 0:
        raise ValueError("%s must be positive." % label)
    return extent


def validate_nonnegative(value: int, label: str) -> None:
    """Reject negative pack and tile indexes before Python can index from the end.

    Parameters:
        value: Candidate index.
        label: Diagnostic label.
    Returns:
        None.
    """
    if value < 0:
        raise ValueError("%s must be nonnegative." % label)


def set_pixel(pixels: list[list[int]], x: int, y: int, color: int) -> None:
    """Set one bounded CHR pixel.

    Parameters are tile matrix, x/y coordinates, and palette index.
    Returns:
        None.
    """
    if not 0 <= x < TILE_PIXELS or not 0 <= y < TILE_PIXELS:
        raise ValueError("CHR pixel coordinate is outside 8x8.")
    if not 0 <= color <= 7:
        raise ValueError("CHR palette index must be 0..7.")
    pixels[y][x] = color
