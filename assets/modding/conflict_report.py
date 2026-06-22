"""Conflict collection for deterministic overworld mod builds."""

from __future__ import annotations


class ConflictReport:
    """Tracks builder conflicts without hiding the first failure.

    The builder records every conflict it can prove, then raises once a phase
    completes. This gives the editor enough detail to show actionable errors.
    """

    def __init__(self) -> None:
        """Create an empty conflict report.

        Parameters: none.
        Returns: ConflictReport instance.
        """
        self.conflicts: list[dict] = []

    def add(self, kind: str, message: str, detail: dict | None = None) -> None:
        """Append one conflict.

        Parameters:
            kind: Machine-readable conflict category.
            message: Human-readable explanation.
            detail: Optional structured context for editor display.
        Returns:
            None.
        """
        self.conflicts.append({"kind": kind, "message": message, "detail": detail or {}})

    def has_conflicts(self) -> bool:
        """Return whether any conflicts have been recorded.

        Parameters: none.
        Returns:
            True if at least one conflict exists.
        """
        return bool(self.conflicts)

    def raise_if_needed(self) -> None:
        """Raise ValueError if the report contains conflicts.

        Parameters: none.
        Returns:
            None.
        Raises:
            ValueError: When one or more conflicts were recorded.
        """
        if self.conflicts:
            raise ValueError("Overworld mod conflicts: %s" % self.conflicts)

    def to_json(self) -> dict:
        """Return a JSON-serializable conflict report.

        Parameters: none.
        Returns:
            Dict containing the conflict list.
        """
        return {"conflicts": self.conflicts, "ok": not self.conflicts}
