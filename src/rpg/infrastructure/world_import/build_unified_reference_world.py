"""Build a unified reference-world artifact from CSV snapshots.

Usage:
    python -m rpg.infrastructure.world_import.build_unified_reference_world
    python -m rpg.infrastructure.world_import.build_unified_reference_world --output data/reference_world/unified_reference_world.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from rpg.infrastructure.world_import.reference_dataset_loader import load_reference_world_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build unified reference world JSON artifact")
    parser.add_argument(
        "--reference-dir",
        default="data/reference_world",
        help="Directory containing Pres*.csv reference snapshots",
    )
    parser.add_argument(
        "--output",
        default="data/reference_world/unified_reference_world.json",
        help="Output JSON file path",
    )
    return parser


def build_payload(reference_dir: Path) -> dict[str, object]:
    dataset = load_reference_world_dataset(reference_dir)
    model = asdict(dataset)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_dir": str(reference_dir),
        "counts": {
            "source_files": len(model.get("source_files", {})),
            "states": len(model.get("states_by_slug", {})),
            "province_groups": len(model.get("provinces_by_state_slug", {})),
            "military_states": len(model.get("military_by_state_slug", {})),
            "relations_states": len(model.get("relations_matrix", {})),
            "biome_rows": len(model.get("biome_rows", [])),
            "biome_severity_entries": len(model.get("biome_severity_index", {})),
            "burg_rows": len(model.get("burg_rows", [])),
            "marker_rows": len(model.get("marker_rows", [])),
            "religion_rows": len(model.get("religion_rows", [])),
            "river_rows": len(model.get("river_rows", [])),
            "route_rows": len(model.get("route_rows", [])),
        },
        "dataset": model,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    reference_dir = Path(args.reference_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = build_payload(reference_dir)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    counts = dict(payload.get("counts", {}) or {})
    print(f"Unified reference world written to {output}")
    print(
        "Counts: "
        f"files={counts.get('source_files', 0)} "
        f"states={counts.get('states', 0)} "
        f"province_groups={counts.get('province_groups', 0)} "
        f"military={counts.get('military_states', 0)} "
        f"relations={counts.get('relations_states', 0)} "
        f"biomes={counts.get('biome_rows', 0)} "
        f"burgs={counts.get('burg_rows', 0)} "
        f"markers={counts.get('marker_rows', 0)} "
        f"religions={counts.get('religion_rows', 0)} "
        f"rivers={counts.get('river_rows', 0)} "
        f"routes={counts.get('route_rows', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
