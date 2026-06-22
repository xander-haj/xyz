"""Reference resolution and id allocation for overworld mod recipes."""

from __future__ import annotations


QUADRANT_INDEX = {"tl": 0, "tr": 1, "bl": 2, "br": 3, 0: 0, 1: 1, 2: 2, 3: 3}


class IdAllocator:
    """Allocates numeric ids for `mod:` references without colliding with base ids."""

    def __init__(self, first_id: int) -> None:
        """Create an allocator.

        Parameters:
            first_id: First generated id after the local base table.
        Returns:
            IdAllocator instance.
        """
        self.next_id = first_id
        self.ids: dict[str, int] = {}

    def define(self, ref: str) -> int:
        """Define or return one mod id.

        Parameters:
            ref: `mod:name` reference.
        Returns:
            Numeric generated id.
        """
        name = parse_mod_ref(ref)
        if name not in self.ids:
            self.ids[name] = self.next_id
            self.next_id += 1
        return self.ids[name]

    def resolve(self, value) -> int:
        """Resolve a base/mod/int reference.

        Parameters:
            value: Integer, `base:0x...`, or already-defined `mod:name`.
        Returns:
            Numeric id.
        """
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.startswith("base:"):
            return parse_int(value[5:])
        if isinstance(value, str) and value.startswith("mod:"):
            name = parse_mod_ref(value)
            if name not in self.ids:
                raise ValueError("Unresolved mod reference %s" % value)
            return self.ids[name]
        raise ValueError("Unsupported tile reference %r" % value)


def parse_mod_ref(ref: str) -> str:
    """Validate and return the symbolic part of a mod reference.

    Parameters:
        ref: Reference string beginning with `mod:`.
    Returns:
        Symbolic id after the prefix.
    """
    if not isinstance(ref, str) or not ref.startswith("mod:") or len(ref) <= 4:
        raise ValueError("Expected mod reference, got %r" % ref)
    name = ref[4:]
    if any(char in name for char in "/\\:") or name.startswith("."):
        raise ValueError("Unsafe mod reference %r" % ref)
    return name


def parse_int(value) -> int:
    """Parse an integer or hexadecimal string.

    Parameters:
        value: Integer or string accepted by int(..., 0).
    Returns:
        Parsed integer.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError("Expected integer value, got %r" % value)


def resolve_quadrant(value) -> int:
    """Resolve a quadrant label to the 0..3 map16/map8 slot index.

    Parameters:
        value: One of tl/tr/bl/br or numeric 0..3.
    Returns:
        Integer slot index.
    """
    if value not in QUADRANT_INDEX:
        raise ValueError("Unknown quadrant %r" % value)
    return QUADRANT_INDEX[value]


def parse_tile_word(fields: dict, current: int = 0) -> int:
    """Build a SNES BG tile word from a patch object.

    Parameters:
        fields: Dict containing either `word` or individual tile-word fields.
        current: Existing word used for omitted fields.
    Returns:
        16-bit tile word.
    """
    if "word" in fields:
        word = parse_tile_word_int(fields["word"], "tile word")
        validate_u16(word, "tile word")
        return word
    tile = parse_tile_word_int(fields.get("tile", current & 0x03FF), "CHR tile id")
    palette = parse_tile_word_int(fields.get("palette", (current >> 10) & 7), "palette row")
    priority = parse_tile_word_bool(fields, "priority", bool(current & 0x2000))
    h_flip = parse_tile_word_bool(fields, "hFlip", bool(current & 0x4000))
    v_flip = parse_tile_word_bool(fields, "vFlip", bool(current & 0x8000))
    if not 0 <= tile <= 0x03FF:
        raise ValueError("CHR tile id is outside 0..0x3ff.")
    if not 0 <= palette <= 7:
        raise ValueError("Palette row is outside 0..7.")
    return tile | (palette << 10) | (priority << 13) | (h_flip << 14) | (v_flip << 15)


def parse_tile_word_int(value, label: str) -> int:
    """Parse one strict integer field from a SNES BG tile-word edit.

    Parameters:
        value: Candidate tile-word field value.
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


def parse_tile_word_bool(fields: dict, key: str, default: bool) -> bool:
    """Read one explicit boolean bit flag from a SNES BG tile-word edit.

    Parameters:
        fields: Tile-word patch fields.
        key: Flag key to read.
        default: Current bit value used when the key is omitted.
    Returns:
        Boolean flag value.
    """
    if key not in fields:
        return default
    if not isinstance(fields[key], bool):
        raise ValueError("%s must be boolean." % key)
    return fields[key]


def validate_u16(value: int, label: str) -> None:
    """Validate one unsigned 16-bit value.

    Parameters:
        value: Candidate integer.
        label: Diagnostic label.
    Returns:
        None.
    """
    if not 0 <= value <= 0xFFFF:
        raise ValueError("%s must be in 0..0xffff." % label)
