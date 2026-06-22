"""Reject unsupported grove-border recipes from overworld mod patches."""

from __future__ import annotations

from pathlib import Path

from .schema import patch_operations


def apply_grove_patch(generated_dir: Path, document: dict) -> list[dict]:
    """Reject grove border tile-table recipes until they feed runtime data.

    Parameters:
        generated_dir: Generated mod output directory.
        document: Parsed grove patch document.
    Returns:
        Empty list for legacy empty documents.
    """
    del generated_dir
    for operation in patch_operations(document):
        kind = operation.get("kind")
        if kind == "grove.border-tile-table":
            raise ValueError(
                "grove.border-tile-table is unsupported until it writes the live grove source table."
            )
        raise ValueError("Unsupported grove-border operation kind %r." % kind)
    return []
