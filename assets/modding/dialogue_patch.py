"""Apply dialogue.txt text patches into generated overworld mod assets."""

from __future__ import annotations

from pathlib import Path

from .resolver import parse_int
from .schema import DIALOGUE_MESSAGE_COUNT, patch_operations


# Dialogue source rows are "id: text" and ids must stay inside the compiled table.
DIALOGUE_SOURCE = "dialogue.txt"


def prepare_dialogue(assets_dir: Path, generated_dir: Path) -> dict:
    """Load base dialogue.txt into mutable generated-build state.

    Parameters:
        assets_dir: Repository assets directory containing dialogue.txt.
        generated_dir: Generated output root; accepted for builder symmetry.
    Returns:
        Mutable state with ordered records and an id lookup.
    """
    del generated_dir
    records = parse_dialogue_file(assets_dir / DIALOGUE_SOURCE)
    return {
        "records": records,
        "by_id": {record["id"]: record for record in records},
        "touched": False,
        "touched_by": {},
    }


def apply_dialogue_patch(state: dict, document: dict, report) -> list[dict]:
    """Apply dialogue.text operations into mutable dialogue state.

    Parameters:
        state: Mutable state from prepare_dialogue.
        document: Validated dialogue patch document.
        report: ConflictReport used for expectation and load-order conflicts.
    Returns:
        Applied operation summaries.
    """
    applied = []
    for operation in patch_operations(document):
        if operation.get("kind") != "dialogue.text":
            raise ValueError("Unsupported dialogue operation kind %r." % operation.get("kind"))
        dialogue_id = parse_dialogue_id(operation.get("id"))
        record = state["by_id"].get(dialogue_id)
        if record is None:
            raise ValueError("Dialogue id %d is not present in %s." % (dialogue_id, DIALOGUE_SOURCE))
        text = checked_text(operation.get("text"), "dialogue text")
        if not expectation_matches(record, operation, dialogue_id, report):
            continue
        if not claim_dialogue_id(state, operation, dialogue_id, report):
            continue
        record["text"] = text
        state["touched"] = True
        applied.append({"kind": "dialogue.text", "id": dialogue_id})
    return applied


def finalize_dialogue(generated_dir: Path, state: dict) -> None:
    """Write generated dialogue.txt when text patches changed any row.

    Parameters:
        generated_dir: Generated output root.
        state: Mutable dialogue patch state.
    Returns:
        None.
    """
    if not state.get("touched"):
        return
    lines = ["%d: %s" % (record["id"], record["text"]) for record in state["records"]]
    (generated_dir / DIALOGUE_SOURCE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_dialogue_file(path: Path) -> list[dict]:
    """Parse one dialogue.txt source file while preserving source order."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if ": " not in line:
            continue
        raw_id, text = line.split(": ", 1)
        records.append({"id": parse_dialogue_id(raw_id), "text": text})
    return records


def expectation_matches(record: dict, operation: dict, dialogue_id: int, report) -> bool:
    """Check optional optimistic-concurrency text before replacing a row."""
    if "expect" not in operation:
        return True
    expected = checked_text(operation.get("expect"), "dialogue expect")
    if record["text"] == expected:
        return True
    report.add(
        "dialogue-expect-failed",
        "Dialogue id %d no longer matches the expected base text." % dialogue_id,
        {"id": dialogue_id, "expected": expected, "actual": record["text"]},
    )
    return False


def claim_dialogue_id(state: dict, operation: dict, dialogue_id: int, report) -> bool:
    """Prevent silent load-order overwrites of the same dialogue id."""
    owner = state["touched_by"].get(dialogue_id)
    if owner is None or operation.get("override") is True:
        state["touched_by"][dialogue_id] = "dialogue.text"
        return True
    report.add(
        "dialogue-id-conflict",
        "Dialogue id %d was edited by more than one patch." % dialogue_id,
        {"id": dialogue_id, "first": owner, "overrideRequired": True},
    )
    return False


def parse_dialogue_id(value) -> int:
    """Parse and range-check one dialogue id."""
    if isinstance(value, bool):
        raise ValueError("Dialogue id must be an integer.")
    try:
        dialogue_id = parse_int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Dialogue id must be an integer.") from error
    if dialogue_id < 0 or dialogue_id >= DIALOGUE_MESSAGE_COUNT:
        raise ValueError("Dialogue id must be in 0..%d." % (DIALOGUE_MESSAGE_COUNT - 1))
    return dialogue_id


def checked_text(value, label: str) -> str:
    """Validate one dialogue.txt source row payload."""
    if not isinstance(value, str):
        raise ValueError("%s must be a string." % label)
    if "\n" in value or "\r" in value:
        raise ValueError("%s cannot contain literal newlines." % label)
    return value
