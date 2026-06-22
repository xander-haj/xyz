"""Safe path helpers for overworld mod packages and generated outputs."""

from __future__ import annotations

import re
from pathlib import Path

# All modding paths are rooted in the repository that contains assets/.
ASSETS_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ASSETS_DIR.parent
MODS_ROOT = PROJECT_ROOT / "mods" / "overworld"
GENERATED_ROOT = ASSETS_DIR / "generated" / "overworld_mods"
MOD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_mod_id(mod_id: str) -> str:
    """Validate a portable overworld mod id.

    Parameters:
        mod_id: Candidate package id from a manifest, URL, or CLI argument.
    Returns:
        The original id when it is valid.
    Raises:
        ValueError: If the id could escape paths or is not stable for sharing.
    """
    if not isinstance(mod_id, str) or not MOD_ID_RE.fullmatch(mod_id):
        raise ValueError("Mod id must be lowercase letters, digits, underscores, or hyphens.")
    return mod_id


def safe_join(root: Path, *parts: str) -> Path:
    """Join path pieces while preventing traversal outside the root.

    Parameters:
        root: Directory that must contain the final path.
        parts: Relative path pieces supplied by manifests or API routes.
    Returns:
        Resolved path inside root.
    Raises:
        ValueError: If the path is absolute or escapes root.
    """
    root_resolved = root.resolve()
    candidate = root_resolved
    for part in parts:
        if Path(part).is_absolute():
            raise ValueError("Absolute paths are not allowed in overworld mods.")
        candidate = candidate / part
    resolved = candidate.resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise ValueError("Path escapes allowed overworld mod root: %s" % candidate)
    return resolved


def mod_dir_from_arg(value: str) -> Path:
    """Resolve a CLI mod id or path to a mod package directory.

    Parameters:
        value: Existing directory path or package id under mods/overworld.
    Returns:
        Resolved mod directory path.
    """
    direct = Path(value)
    if direct.exists():
        return direct.resolve()
    return safe_join(MODS_ROOT, validate_mod_id(value))


def generated_id(mod_ids: list[str]) -> str:
    """Create the deterministic generated-output id for one or more mods.

    Parameters:
        mod_ids: Ordered mod ids used by the builder.
    Returns:
        Hyphen-joined id suitable for assets/generated/overworld_mods.
    """
    if not mod_ids:
        raise ValueError("At least one mod id is required.")
    return "__".join(validate_mod_id(mod_id) for mod_id in mod_ids)


def generated_dir_for(mod_ids: list[str]) -> Path:
    """Return the generated local output directory for an ordered mod list.

    Parameters:
        mod_ids: Ordered mod ids used by the builder.
    Returns:
        Path under assets/generated/overworld_mods.
    """
    return safe_join(GENERATED_ROOT, generated_id(mod_ids))
