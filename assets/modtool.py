#!/usr/bin/env python3
"""CLI for validating and building data-only overworld mod packages."""

from __future__ import annotations

import argparse
import json

from modding.overworld_builder import build_mods, list_mods, validate_mods


def parse_args() -> argparse.Namespace:
    """Parse modtool CLI arguments.

    Parameters: none.
    Returns:
        argparse namespace.
    """
    parser = argparse.ArgumentParser(description="Overworld mod package tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List mods under mods/overworld.")
    validate = sub.add_parser("validate", help="Validate one or more mod packages.")
    validate.add_argument("mods", nargs="+")
    build = sub.add_parser("build", help="Build generated local assets for mod packages.")
    build.add_argument("mods", nargs="+")
    return parser.parse_args()


def main() -> None:
    """Run the selected modtool command.

    Parameters: none.
    Returns:
        None.
    """
    args = parse_args()
    if args.command == "list":
        result = {"mods": list_mods()}
    elif args.command == "validate":
        result = {"ok": True, "mods": [entry["manifest"] for entry in validate_mods(args.mods)]}
    else:
        result = build_mods(args.mods)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
