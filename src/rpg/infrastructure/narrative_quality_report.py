"""Generate deterministic narrative quality report artifacts.

Usage examples:
    python -m rpg.infrastructure.narrative_quality_report
    python -m rpg.infrastructure.narrative_quality_report --profile strict --output artifacts/strict_report.json
    python -m rpg.infrastructure.narrative_quality_report --seeds 111,222,333 --script rest,rumour,travel,rest
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from rpg.application.services.narrative_quality_batch import (
    DEFAULT_SCRIPT,
    SCRIPT_PRESETS,
    generate_quality_report,
    read_quality_report_artifact,
    resolve_script,
    validate_quality_report_payload,
    write_quality_report_artifact,
)


def _parse_csv_list(value: str, *, allow_empty: bool = False) -> list[str]:
    parts = [item.strip() for item in str(value).split(",") if item.strip()]
    if not parts and not allow_empty:
        raise ValueError("Expected at least one comma-separated value")
    return parts


def _parse_seeds(value: str) -> list[int]:
    parts = _parse_csv_list(value)
    return [int(item) for item in parts]


def _parse_script(value: str | None) -> tuple[str, ...]:
    if value is None:
        return tuple(DEFAULT_SCRIPT)
    return tuple(_parse_csv_list(value))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic narrative batch quality validation and write a JSON artifact")
    parser.add_argument("--seeds", default="101,202,303", help="Comma-separated seed list")
    parser.add_argument("--script", default=None, help="Comma-separated action script; defaults to canonical 16-step script")
    parser.add_argument(
        "--script-name",
        default="",
        help=f"Named script profile ({', '.join(sorted(SCRIPT_PRESETS.keys()))})",
    )
    parser.add_argument("--profile", default="", help="Gate profile selector (strict, balanced, exploratory); empty uses env/default")
    parser.add_argument("--output", default="artifacts/narrative_quality_report.json", help="Output JSON artifact path")
    parser.add_argument("--compare-base", default="", help="Path to baseline report artifact for comparison mode")
    parser.add_argument("--compare-candidate", default="", help="Path to candidate report artifact for comparison mode")
    parser.add_argument("--print-json", action="store_true", help="Print report payload to stdout after writing artifact")
    return parser


def _semantic_band_counts(payload: dict) -> dict[str, int]:
    summaries = payload.get("summaries", []) if isinstance(payload, dict) else []
    counts = {"weak": 0, "fragile": 0, "stable": 0, "strong": 0}
    for row in summaries:
        if not isinstance(row, dict):
            continue
        band = str(row.get("semantic_arc_band", "")).strip().lower()
        if band in counts:
            counts[band] += 1
    return counts


def compare_report_artifacts(base_path: str | Path, candidate_path: str | Path) -> dict:
    base = load_report_artifact(base_path)
    candidate = load_report_artifact(candidate_path)

    base_gate = base.get("aggregate_gate", {}) if isinstance(base, dict) else {}
    candidate_gate = candidate.get("aggregate_gate", {}) if isinstance(candidate, dict) else {}

    base_blockers = set(str(item) for item in base_gate.get("blockers", ()) if str(item))
    candidate_blockers = set(str(item) for item in candidate_gate.get("blockers", ()) if str(item))

    base_pass_rate = float(base_gate.get("pass_rate", 0.0) or 0.0)
    candidate_pass_rate = float(candidate_gate.get("pass_rate", 0.0) or 0.0)
    band_base = _semantic_band_counts(base)
    band_candidate = _semantic_band_counts(candidate)

    return {
        "base_path": str(base_path),
        "candidate_path": str(candidate_path),
        "base_schema_version": str(base.get("schema", {}).get("version", "")),
        "candidate_schema_version": str(candidate.get("schema", {}).get("version", "")),
        "gate_verdict": {
            "base": str(base_gate.get("release_verdict", "unknown")),
            "candidate": str(candidate_gate.get("release_verdict", "unknown")),
            "changed": str(base_gate.get("release_verdict", "unknown")) != str(candidate_gate.get("release_verdict", "unknown")),
        },
        "pass_rate": {
            "base": round(base_pass_rate, 4),
            "candidate": round(candidate_pass_rate, 4),
            "delta": round(candidate_pass_rate - base_pass_rate, 4),
        },
        "blockers": {
            "base": tuple(sorted(base_blockers)),
            "candidate": tuple(sorted(candidate_blockers)),
            "added": tuple(sorted(candidate_blockers - base_blockers)),
            "removed": tuple(sorted(base_blockers - candidate_blockers)),
        },
        "semantic_band_counts": {
            "base": band_base,
            "candidate": band_candidate,
            "delta": {
                band: int(band_candidate.get(band, 0) - band_base.get(band, 0))
                for band in ("weak", "fragile", "stable", "strong")
            },
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    compare_base = str(args.compare_base or "").strip()
    compare_candidate = str(args.compare_candidate or "").strip()
    if compare_base or compare_candidate:
        if not (compare_base and compare_candidate):
            parser.error("Comparison mode requires both --compare-base and --compare-candidate.")
            return 2
        if args.script is not None or str(args.script_name or "").strip() or str(args.profile or "").strip() or str(args.seeds or "").strip() != "101,202,303":
            parser.error("Comparison mode does not accept generation options (--seeds/--script/--script-name/--profile).")
            return 2
        comparison = compare_report_artifacts(compare_base, compare_candidate)
        print(json.dumps(comparison, indent=2, sort_keys=True, default=list))
        return 0

    try:
        seeds = _parse_seeds(args.seeds)
        parsed_script = _parse_script(args.script) if args.script is not None else None
        script = resolve_script(script=parsed_script, script_name=str(args.script_name or ""))
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    report = generate_quality_report(seeds=seeds, script=script, profile=str(args.profile or ""))
    validate_quality_report_payload(report)
    artifact_path = write_quality_report_artifact(args.output, report)

    gate = report.get("aggregate_gate", {}) if isinstance(report, dict) else {}
    verdict = str(gate.get("release_verdict", "unknown"))
    profile = str(report.get("profile", "balanced"))
    pass_rate = gate.get("pass_rate", 0)

    print(f"Narrative quality report generated: {artifact_path}")
    print(f"Profile={profile} Verdict={verdict} PassRate={pass_rate}")
    if args.print_json:
        print(json.dumps(report, indent=2, sort_keys=True, default=list))

    return 0


def load_report_artifact(path: str | Path) -> dict:
    return read_quality_report_artifact(path)


if __name__ == "__main__":
    raise SystemExit(main())
