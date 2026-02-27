"""Validate data/world dialogue tree content.

Usage examples:
    python -m rpg.infrastructure.dialogue_content_validator
    python -m rpg.infrastructure.dialogue_content_validator --path data/world/dialogue_trees.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from rpg.application.services.dialogue_service import DialogueService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate dialogue tree JSON schema and requirements")
    parser.add_argument(
        "--path",
        default=DialogueService._DIALOGUE_CONTENT_FILE,
        help="Path to dialogue tree JSON file",
    )
    return parser


def validate_dialogue_file(path: str | Path) -> list[str]:
    source = Path(path)
    if not source.exists():
        return [f"File not found: {source}"]

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    return DialogueService.validate_dialogue_content(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    errors = validate_dialogue_file(args.path)
    if errors:
        print(f"Dialogue content invalid ({len(errors)} errors):")
        for message in errors:
            print(f"- {message}")
        return 1

    print("Dialogue content valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
