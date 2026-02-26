from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.seed_policy import derive_seed
from rpg.application.services.story_director import register_story_director_handlers
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository


QUALITY_PROFILES = {
    "strict": {
        "min_pass_rate": 0.8,
        "max_warn_count": 0,
        "max_fail_count": 0,
    },
    "balanced": {
        "min_pass_rate": 0.66,
        "max_warn_count": 1,
        "max_fail_count": 0,
    },
    "exploratory": {
        "min_pass_rate": 0.5,
        "max_warn_count": 2,
        "max_fail_count": 1,
    },
}

TARGET_SEMANTIC_SCORE_MIN = 55
TARGET_TENSION_MIN = 45
TARGET_TENSION_MAX = 75
TARGET_MAX_ACTIVE_SEEDS = 1
TARGET_MIN_MAJOR_EVENTS = 1
TARGET_MIN_PASS_RATE = 0.66
TARGET_MAX_WARN_COUNT = 1
TARGET_MAX_FAIL_COUNT = 0

DEFAULT_SCRIPT = (
    "rest",
    "rumour",
    "travel",
    "rest",
    "social",
    "travel",
    "rest",
    "rumour",
    "explore",
    "social",
    "rest",
    "travel",
    "rest",
    "travel",
    "rumour",
    "rest",
)

SCRIPT_PRESETS: dict[str, tuple[str, ...]] = {
    "baseline": tuple(DEFAULT_SCRIPT),
    "exploration_heavy": (
        "rest",
        "travel",
        "explore",
        "rest",
        "explore",
        "travel",
        "rumour",
        "explore",
        "social",
        "rest",
        "travel",
        "explore",
        "rumour",
        "social",
        "rest",
        "explore",
    ),
}

REPORT_SCHEMA_NAME = "narrative_quality_report"
REPORT_SCHEMA_VERSION = "1.0"
SUPPORTED_REPORT_SCHEMA_VERSIONS = {REPORT_SCHEMA_VERSION}

SESSION_REPORT_ENABLED_ENV = "RPG_NARRATIVE_SESSION_REPORT_ENABLED"
SESSION_REPORT_OUTPUT_ENV = "RPG_NARRATIVE_SESSION_REPORT_OUTPUT"
SESSION_REPORT_PROFILE_ENV = "RPG_NARRATIVE_SESSION_REPORT_PROFILE"
SESSION_REPORT_SEED_COUNT_ENV = "RPG_NARRATIVE_SESSION_REPORT_SEED_COUNT"
DEFAULT_SESSION_REPORT_OUTPUT = "artifacts/narrative_quality_session_report.json"


def _safe_float(raw_value, fallback: float) -> float:
    try:
        return float(raw_value)
    except Exception:
        return float(fallback)


def _safe_int(raw_value, fallback: int) -> int:
    try:
        return int(raw_value)
    except Exception:
        return int(fallback)


def resolve_script(
    *,
    script: Sequence[str] | None = None,
    script_name: str | None = None,
) -> tuple[str, ...]:
    normalized_name = str(script_name or "").strip().lower()
    if script is not None and normalized_name:
        raise ValueError("Provide either --script or --script-name, not both.")

    if normalized_name:
        preset = SCRIPT_PRESETS.get(normalized_name)
        if preset is None:
            allowed = ", ".join(sorted(SCRIPT_PRESETS.keys()))
            raise ValueError(f"Unknown script profile '{normalized_name}'. Choose one of: {allowed}.")
        return tuple(preset)

    if script is None:
        return tuple(DEFAULT_SCRIPT)

    resolved = tuple(str(action).strip() for action in script if str(action).strip())
    if not resolved:
        raise ValueError("Script cannot be empty.")
    return resolved


def quality_targets() -> dict:
    return {
        "semantic_min": _safe_int(os.getenv("RPG_NARRATIVE_GATE_TARGET_SEMANTIC_MIN"), TARGET_SEMANTIC_SCORE_MIN),
        "tension_min": _safe_int(os.getenv("RPG_NARRATIVE_GATE_TARGET_TENSION_MIN"), TARGET_TENSION_MIN),
        "tension_max": _safe_int(os.getenv("RPG_NARRATIVE_GATE_TARGET_TENSION_MAX"), TARGET_TENSION_MAX),
        "max_active_seeds": _safe_int(
            os.getenv("RPG_NARRATIVE_GATE_TARGET_MAX_ACTIVE_SEEDS"),
            TARGET_MAX_ACTIVE_SEEDS,
        ),
        "min_major_events": _safe_int(
            os.getenv("RPG_NARRATIVE_GATE_TARGET_MIN_MAJOR_EVENTS"),
            TARGET_MIN_MAJOR_EVENTS,
        ),
    }


def _quality_profiles_from_file() -> dict[str, dict[str, float | int]]:
    path = os.getenv("RPG_NARRATIVE_GATE_PROFILE_FILE", "").strip()
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return {}

    source = payload.get("profiles", payload) if isinstance(payload, dict) else {}
    if not isinstance(source, dict):
        return {}

    normalized: dict[str, dict[str, float | int]] = {}
    for profile_name, values in source.items():
        if not isinstance(values, dict):
            continue
        key = str(profile_name).strip().lower()
        if not key:
            continue
        normalized[key] = {
            "min_pass_rate": _safe_float(values.get("min_pass_rate"), TARGET_MIN_PASS_RATE),
            "max_warn_count": _safe_int(values.get("max_warn_count"), TARGET_MAX_WARN_COUNT),
            "max_fail_count": _safe_int(values.get("max_fail_count"), TARGET_MAX_FAIL_COUNT),
        }
    return normalized


def resolved_quality_profiles() -> dict[str, dict[str, float | int]]:
    profiles = {
        key: {
            "min_pass_rate": float(value["min_pass_rate"]),
            "max_warn_count": int(value["max_warn_count"]),
            "max_fail_count": int(value["max_fail_count"]),
        }
        for key, value in QUALITY_PROFILES.items()
    }

    from_file = _quality_profiles_from_file()
    for key, value in from_file.items():
        profiles[key] = {
            "min_pass_rate": _safe_float(
                value.get("min_pass_rate"),
                profiles.get("balanced", {}).get("min_pass_rate", TARGET_MIN_PASS_RATE),
            ),
            "max_warn_count": _safe_int(
                value.get("max_warn_count"),
                profiles.get("balanced", {}).get("max_warn_count", TARGET_MAX_WARN_COUNT),
            ),
            "max_fail_count": _safe_int(
                value.get("max_fail_count"),
                profiles.get("balanced", {}).get("max_fail_count", TARGET_MAX_FAIL_COUNT),
            ),
        }

    for profile_name in list(profiles.keys()):
        upper = profile_name.upper()
        min_pass_raw = os.getenv(f"RPG_NARRATIVE_GATE_{upper}_MIN_PASS_RATE")
        max_warn_raw = os.getenv(f"RPG_NARRATIVE_GATE_{upper}_MAX_WARN_COUNT")
        max_fail_raw = os.getenv(f"RPG_NARRATIVE_GATE_{upper}_MAX_FAIL_COUNT")
        if min_pass_raw is not None:
            profiles[profile_name]["min_pass_rate"] = _safe_float(min_pass_raw, profiles[profile_name]["min_pass_rate"])
        if max_warn_raw is not None:
            profiles[profile_name]["max_warn_count"] = _safe_int(max_warn_raw, profiles[profile_name]["max_warn_count"])
        if max_fail_raw is not None:
            profiles[profile_name]["max_fail_count"] = _safe_int(max_fail_raw, profiles[profile_name]["max_fail_count"])
    return profiles


def semantic_arc_score(*, summary: dict) -> tuple[int, str]:
    tension = int(summary.get("tension_level", 0))
    resolved = int(summary.get("story_seed_resolved", 0))
    active = int(summary.get("story_seed_active", 0))
    major_events = int(summary.get("major_event_count", 0))
    injection_count = int(summary.get("injection_count", 0))
    injection_kinds = tuple(summary.get("injection_kinds", ()))
    unique_categories = len({str(kind) for kind in injection_kinds if str(kind)})

    score = 0
    score += min(25, resolved * 12)
    score += min(20, major_events * 8)
    score += min(15, max(0, injection_count - 1) * 3)
    score += min(15, unique_categories * 7)

    if 40 <= tension <= 75:
        score += 15
    elif 25 <= tension <= 90:
        score += 8

    if active == 0:
        score += 10
    elif active == 1:
        score += 5
    else:
        score -= min(10, (active - 1) * 4)

    score = max(0, min(100, int(score)))
    if score >= 75:
        band = "strong"
    elif score >= 50:
        band = "stable"
    elif score >= 30:
        band = "fragile"
    else:
        band = "weak"
    return score, band


def quality_alerts(*, summary: dict) -> tuple[str, ...]:
    alerts: list[str] = []
    targets = quality_targets()
    semantic_score = int(summary.get("semantic_arc_score", 0))
    tension = int(summary.get("tension_level", 0))
    active = int(summary.get("story_seed_active", 0))
    major_events = int(summary.get("major_event_count", 0))

    if semantic_score < int(targets["semantic_min"]):
        alerts.append("semantic_below_target")
    if tension < int(targets["tension_min"]):
        alerts.append("tension_under_target")
    if tension > int(targets["tension_max"]):
        alerts.append("tension_over_target")
    if active > int(targets["max_active_seeds"]):
        alerts.append("too_many_active_seeds")
    if major_events < int(targets["min_major_events"]):
        alerts.append("low_event_density")
    return tuple(alerts)


def quality_status(*, alerts: tuple[str, ...]) -> str:
    if not alerts:
        return "pass"
    if "semantic_below_target" in alerts and "low_event_density" in alerts:
        return "fail"
    return "warn"


def quality_profile_thresholds(profile: str) -> dict:
    default_profile = str(os.getenv("RPG_NARRATIVE_GATE_DEFAULT_PROFILE", "balanced")).strip().lower() or "balanced"
    key = str(profile or default_profile).strip().lower()
    profiles = resolved_quality_profiles()
    thresholds = profiles.get(key)
    if thresholds is None:
        key = "balanced"
        thresholds = profiles.get(key, QUALITY_PROFILES[key])
    return {
        "profile": key,
        "min_pass_rate": float(thresholds["min_pass_rate"]),
        "max_warn_count": int(thresholds["max_warn_count"]),
        "max_fail_count": int(thresholds["max_fail_count"]),
    }


def batch_quality_gate(summaries: list[dict], profile: str = "balanced") -> dict:
    thresholds = quality_profile_thresholds(profile)
    total = len(summaries)
    pass_count = sum(1 for row in summaries if str(row.get("quality_status", "")) == "pass")
    warn_count = sum(1 for row in summaries if str(row.get("quality_status", "")) == "warn")
    fail_count = sum(1 for row in summaries if str(row.get("quality_status", "")) == "fail")
    pass_rate = (pass_count / total) if total > 0 else 0.0

    blockers: list[str] = []
    if fail_count > thresholds["max_fail_count"]:
        blockers.append("too_many_failures")
    if pass_rate < thresholds["min_pass_rate"]:
        blockers.append("pass_rate_below_target")
    if warn_count > thresholds["max_warn_count"]:
        blockers.append("too_many_warnings")

    verdict = "go" if not blockers else "hold"
    return {
        "profile": thresholds["profile"],
        "total": int(total),
        "pass_count": int(pass_count),
        "warn_count": int(warn_count),
        "fail_count": int(fail_count),
        "pass_rate": round(float(pass_rate), 4),
        "target_min_pass_rate": float(thresholds["min_pass_rate"]),
        "target_max_warn_count": int(thresholds["max_warn_count"]),
        "target_max_fail_count": int(thresholds["max_fail_count"]),
        "blockers": tuple(blockers),
        "release_verdict": verdict,
    }


def build_simulation_service(seed: int) -> tuple[GameService, int]:
    event_bus = EventBus()
    world_repo = InMemoryWorldRepository(seed=seed)
    world = world_repo.load_default()
    world.threat_level = 7
    world_repo.save(world)

    character = Character(id=901, name="BatchHero", location_id=1)
    character.attributes["charisma"] = 14
    character.attributes["wisdom"] = 14
    character_repo = InMemoryCharacterRepository({character.id: character})

    entities = [
        Entity(id=1, name="Wolf", level=1, hp=6, faction_id="wild"),
        Entity(id=2, name="Bandit", level=2, hp=8, faction_id="wardens"),
        Entity(id=3, name="Ghoul", level=2, hp=9, faction_id="undead"),
    ]
    entity_repo = InMemoryEntityRepository(entities)
    entity_repo.set_location_entities(2, [1, 2, 3])

    location_repo = InMemoryLocationRepository(
        {
            1: Location(id=1, name="Town Square", tags=["town"], factions=["wardens"]),
            2: Location(id=2, name="North Wilds", tags=["wilderness"], factions=["wild"]),
        }
    )

    faction_repo = InMemoryFactionRepository()
    progression = WorldProgression(world_repo, entity_repo, event_bus)
    register_story_director_handlers(event_bus=event_bus, world_repo=world_repo, cadence_turns=2)

    service = GameService(
        character_repo=character_repo,
        entity_repo=entity_repo,
        location_repo=location_repo,
        world_repo=world_repo,
        progression=progression,
        faction_repo=faction_repo,
    )
    return service, character.id


def simulate_arc(seed: int, script: Sequence[str] = DEFAULT_SCRIPT) -> dict:
    service, character_id = build_simulation_service(seed)
    rumour_ids: list[str] = []

    for action in script:
        if action == "rest":
            service.rest_intent(character_id)
        elif action == "travel":
            service.travel_intent(character_id)
        elif action == "social":
            service.submit_social_approach_intent(character_id, "broker_silas", "Friendly")
        elif action == "rumour":
            board = service.get_rumour_board_intent(character_id)
            rumour_ids = [item.rumour_id for item in board.items]
        elif action == "explore":
            service.explore(character_id)
        else:
            raise ValueError(f"Unknown simulation action: {action}")

    world = service._require_world()
    narrative = world.flags.get("narrative", {}) if isinstance(world.flags, dict) else {}
    injections = narrative.get("injections", []) if isinstance(narrative, dict) else []
    story_seeds = narrative.get("story_seeds", []) if isinstance(narrative, dict) else []
    major_events = narrative.get("major_events", []) if isinstance(narrative, dict) else []

    resolved = 0
    active = 0
    for row in story_seeds:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", ""))
        if status == "resolved":
            resolved += 1
        if status in {"active", "simmering", "escalated", "critical"}:
            active += 1

    summary = {
        "seed": int(seed),
        "script_len": len(script),
        "final_turn": int(getattr(world, "current_turn", 0)),
        "threat_level": int(getattr(world, "threat_level", 0)),
        "tension_level": int(narrative.get("tension_level", 0)) if isinstance(narrative, dict) else 0,
        "injection_count": len([row for row in injections if isinstance(row, dict)]),
        "injection_kinds": tuple(
            str(row.get("kind", "")) for row in injections if isinstance(row, dict)
        ),
        "story_seed_total": len([row for row in story_seeds if isinstance(row, dict)]),
        "story_seed_resolved": int(resolved),
        "story_seed_active": int(active),
        "major_event_count": len([row for row in major_events if isinstance(row, dict)]),
        "rumour_signature": tuple(rumour_ids),
    }
    semantic_score, semantic_band = semantic_arc_score(summary=summary)
    summary["semantic_arc_score"] = int(semantic_score)
    summary["semantic_arc_band"] = semantic_band
    alerts = quality_alerts(summary=summary)
    summary["quality_alerts"] = alerts
    summary["quality_status"] = quality_status(alerts=alerts)
    return summary


def run_batch(seeds: Sequence[int], script: Sequence[str] = DEFAULT_SCRIPT) -> list[dict]:
    return [simulate_arc(int(seed), script) for seed in seeds]


def generate_quality_report(
    *,
    seeds: Sequence[int],
    script: Sequence[str] = DEFAULT_SCRIPT,
    profile: str = "",
) -> dict:
    normalized_seeds = [int(seed) for seed in seeds]
    summaries = run_batch(normalized_seeds, script)
    gate = batch_quality_gate(summaries, profile=profile)
    selected_profile = str(gate.get("profile", "balanced"))
    return {
        "schema": {
            "name": REPORT_SCHEMA_NAME,
            "version": REPORT_SCHEMA_VERSION,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seeds": normalized_seeds,
        "script": tuple(str(action) for action in script),
        "profile": selected_profile,
        "quality_targets": quality_targets(),
        "profile_thresholds": quality_profile_thresholds(selected_profile),
        "summaries": summaries,
        "aggregate_gate": gate,
    }


def validate_quality_report_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Invalid report payload: expected top-level object.")

    schema = payload.get("schema")
    if not isinstance(schema, dict):
        raise ValueError("Invalid report payload: missing schema object.")

    schema_name = str(schema.get("name", "")).strip()
    schema_version = str(schema.get("version", "")).strip()
    if schema_name != REPORT_SCHEMA_NAME:
        raise ValueError(
            f"Unsupported report schema name: '{schema_name or '<missing>'}'. Expected '{REPORT_SCHEMA_NAME}'."
        )
    if schema_version not in SUPPORTED_REPORT_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_REPORT_SCHEMA_VERSIONS))
        raise ValueError(
            f"Unsupported report schema version: '{schema_version or '<missing>'}'. Supported versions: {supported}."
        )

    required_keys = (
        "generated_at",
        "seeds",
        "script",
        "profile",
        "quality_targets",
        "profile_thresholds",
        "summaries",
        "aggregate_gate",
    )
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"Invalid report payload: missing required keys: {', '.join(missing)}")
    return payload


def read_quality_report_artifact(input_path: str | Path) -> dict:
    path = Path(input_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return validate_quality_report_payload(payload)


def write_quality_report_artifact(output_path: str | Path, report: dict) -> Path:
    validate_quality_report_payload(report)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, default=list)
        handle.write("\n")
    return path


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _load_world_from_service(game_service: GameService):
    require_world = getattr(game_service, "_require_world", None)
    if callable(require_world):
        try:
            return require_world()
        except Exception:
            pass

    world_repo = getattr(game_service, "world_repo", None)
    load_default = getattr(world_repo, "load_default", None)
    if callable(load_default):
        try:
            return load_default()
        except Exception:
            return None
    return None


def _session_report_seed_list(game_service: GameService, character_id: int | None, seed_count: int) -> list[int]:
    world = _load_world_from_service(game_service)
    context = {
        "world_seed": int(getattr(world, "rng_seed", 1) or 1),
        "world_turn": int(getattr(world, "current_turn", 0) or 0),
        "threat_level": int(getattr(world, "threat_level", 0) or 0),
        "character_id": int(character_id or 0),
    }
    base_seed = derive_seed("narrative.session.report", context)
    total = max(1, int(seed_count))
    return [
        derive_seed(
            "narrative.session.report.seed",
            {
                **context,
                "base_seed": int(base_seed),
                "index": int(index),
            },
        )
        for index in range(total)
    ]


def maybe_emit_session_quality_report(game_service: GameService, character_id: int | None = None) -> Path | None:
    if not _bool_env(SESSION_REPORT_ENABLED_ENV, default=False):
        return None

    output_path = str(os.getenv(SESSION_REPORT_OUTPUT_ENV, DEFAULT_SESSION_REPORT_OUTPUT)).strip() or DEFAULT_SESSION_REPORT_OUTPUT
    profile = str(os.getenv(SESSION_REPORT_PROFILE_ENV, "")).strip()
    seed_count = max(1, _safe_int(os.getenv(SESSION_REPORT_SEED_COUNT_ENV), 3))
    seeds = _session_report_seed_list(game_service, character_id=character_id, seed_count=seed_count)
    report = generate_quality_report(seeds=seeds, script=DEFAULT_SCRIPT, profile=profile)
    report["session_context"] = {
        "character_id": int(character_id or 0),
        "seed_count": int(seed_count),
        "seed_source": "session_world_context",
    }
    return write_quality_report_artifact(output_path, report)
