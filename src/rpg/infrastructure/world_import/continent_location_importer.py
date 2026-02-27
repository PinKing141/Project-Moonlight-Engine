from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SelectedLocation:
    source_burg_id: int
    location_id: int
    name: str
    state_name: str
    state_full_name: str
    group: str
    population: int
    x: int
    y: int
    biome_key: str
    hazard_profile_key: str
    hazard_severity: int
    faction_slug: str
    tags: list[str]
    culture: str
    religion: str
    settlement_description: str


def _slugify(value: str) -> str:
    lowered = str(value or "").strip().lower().replace("-", " ")
    return "_".join(part for part in lowered.split() if part)


def _parse_int(raw_value, *, default: int = 0) -> int:
    text_value = str(raw_value or "").strip()
    if not text_value:
        return int(default)
    normalized = text_value.replace(",", "")
    try:
        return int(float(normalized))
    except ValueError:
        return int(default)


def _parse_float(raw_value, *, default: float = 0.0) -> float:
    text_value = str(raw_value or "").strip()
    if not text_value:
        return float(default)
    normalized = text_value.replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return float(default)


def _csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _classify_biome(temp_likeness: str) -> str:
    text = str(temp_likeness or "").strip().lower()
    if "iceland" in text or "tromsø" in text or "stockholm" in text or "copenhagen" in text:
        return "tundra"
    if "marrakesh" in text or "alexandria" in text or "guangzhou" in text:
        return "desert"
    if "dubrovnik" in text or "barcelona" in text or "rio" in text:
        return "coast"
    if "rome" in text or "milan" in text or "paris" in text or "london" in text or "prague" in text:
        return "forest"
    return "wilderness"


def _hazard_profile_for_alert(war_alert: float) -> tuple[str, int]:
    if war_alert >= 4.0:
        return "warfront", 4
    if war_alert >= 2.0:
        return "contested", 3
    if war_alert >= 1.0:
        return "frontier", 2
    return "standard", 1


def _sql_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("'", "''")


def _resolve_unique_coordinate(x: int, y: int, seen: set[tuple[int, int]]) -> tuple[int, int]:
    current = (x, y)
    while current in seen:
        current = (current[0], current[1] + 1)
    seen.add(current)
    return current


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def select_locations(
    *,
    burg_rows: list[dict[str, str]],
    state_rows: list[dict[str, str]],
    military_rows: list[dict[str, str]],
    continent_name: str,
    location_id_offset: int,
    major_town_min_population: int,
    max_major_towns_per_state: int,
) -> list[SelectedLocation]:
    state_full_name_by_state: dict[str, str] = {}
    state_form_by_state: dict[str, str] = {}
    state_culture_by_state: dict[str, str] = {}
    for row in state_rows:
        state_key = str(row.get("State", "")).strip()
        if not state_key or state_key.lower() == "neutrals":
            continue
        state_full_name_by_state[state_key] = str(row.get("Full Name") or row.get("State") or state_key).strip()
        state_form_by_state[state_key] = str(row.get("Form") or "realm").strip()
        state_culture_by_state[state_key] = str(row.get("Culture") or "mixed").strip()

    war_alert_by_state: dict[str, float] = {}
    for row in military_rows:
        state_key = str(row.get("State", "")).strip()
        if not state_key:
            continue
        war_alert_by_state[state_key] = _parse_float(row.get("War Alert"), default=0.0)

    selected: list[SelectedLocation] = []
    major_candidates_by_state: dict[str, list[SelectedLocation]] = {}
    used_coordinates: set[tuple[int, int]] = set()

    for row in burg_rows:
        source_burg_id = _parse_int(row.get("Id"), default=0)
        if source_burg_id <= 0:
            continue
        name = str(row.get("Burg") or "").strip()
        if not name:
            continue

        state_name = str(row.get("State") or "").strip()
        state_full_name = state_full_name_by_state.get(state_name, state_name)
        state_form = state_form_by_state.get(state_name, "realm")
        group = str(row.get("Group") or "").strip().lower()
        population = _parse_int(row.get("Population"), default=0)
        is_capital = str(row.get("Capital") or "").strip().lower() == "capital"
        is_major_town = group in {"city", "town"} and population >= int(major_town_min_population)

        if not (is_capital or is_major_town):
            continue

        x_raw = _parse_float(row.get("X"), default=0.0)
        y_raw = _parse_float(row.get("Y"), default=0.0)
        x, y = _resolve_unique_coordinate(int(round(x_raw)), int(round(y_raw)), used_coordinates)

        war_alert = war_alert_by_state.get(state_name, 0.0)
        hazard_profile_key, hazard_severity = _hazard_profile_for_alert(war_alert)
        biome_key = _classify_biome(str(row.get("Temperature likeness") or ""))

        culture = str(row.get("Culture") or state_culture_by_state.get(state_name) or "mixed").strip()
        religion = str(row.get("Religion") or "").strip()

        faction_slug = _slugify(state_full_name or state_name)
        location_tags = [
            _slugify(continent_name),
            "capital" if is_capital else "major_town",
            _slugify(group or "settlement"),
            _slugify(state_name),
            f"culture:{_slugify(culture)}" if culture else "",
            f"religion:{_slugify(religion)}" if religion else "",
        ]
        location_tags = _dedupe_preserving_order([item for item in location_tags if item])

        settlement_label = (group or "settlement").lower()
        settlement_description = (
            f"A major {settlement_label} within the {state_full_name}. "
            f"It is a stronghold of the {culture} people. Population: {population}."
        )
        if is_capital:
            settlement_description = (
                f"A major capital within the {state_full_name}, a {state_form.lower()}. "
                f"Its streets are primarily populated by the {culture} culture. Population: {population}."
            )

        mapped = SelectedLocation(
            source_burg_id=source_burg_id,
            location_id=int(location_id_offset) + source_burg_id,
            name=name,
            state_name=state_name,
            state_full_name=state_full_name,
            group=group or "settlement",
            population=population,
            x=x,
            y=y,
            biome_key=biome_key,
            hazard_profile_key=hazard_profile_key,
            hazard_severity=hazard_severity,
            faction_slug=faction_slug,
            tags=location_tags,
            culture=culture,
            religion=religion,
            settlement_description=settlement_description,
        )
        if is_capital:
            selected.append(mapped)
        else:
            major_candidates_by_state.setdefault(state_name, []).append(mapped)

    per_state_cap = max(1, int(max_major_towns_per_state))
    for state_name, candidates in major_candidates_by_state.items():
        _ = state_name
        candidates.sort(key=lambda item: (-item.population, item.name.lower()))
        selected.extend(candidates[:per_state_cap])

    selected.sort(key=lambda item: (item.group != "capital", item.state_name.lower(), -item.population, item.name.lower()))
    return selected


def render_sql_seed(locations: list[SelectedLocation], *, continent_name: str) -> str:
    lines: list[str] = [
        "-- Generated by continent_location_importer.py",
        f"-- Continent: {continent_name}",
        f"-- Locations: {len(locations)}",
        "",
    ]
    for location in locations:
        place_name = _sql_escape(location.name)
        biome_key = _sql_escape(location.biome_key)
        hazard_profile_key = _sql_escape(location.hazard_profile_key)
        env_flags = json.dumps([
            f"continent:{continent_name}",
            f"state:{location.state_name}",
            f"state_full:{location.state_full_name}",
            f"group:{location.group}",
            f"faction:{location.faction_slug}",
            f"culture_raw:{location.culture}",
            f"religion_raw:{location.religion}",
            f"settlement_description:{location.settlement_description}",
            f"hazard_severity:{location.hazard_severity}",
        ])
        env_flags_sql = _sql_escape(env_flags)

        lines.extend(
            [
                "INSERT INTO place (name)",
                f"SELECT '{place_name}'",
                f"WHERE NOT EXISTS (SELECT 1 FROM place WHERE LOWER(name) = LOWER('{place_name}'));",
                "",
                "INSERT INTO location (location_id, x, y, place_id, biome_key, hazard_profile_key, environmental_flags)",
                f"SELECT {location.location_id}, {location.x}, {location.y}, p.place_id, '{biome_key}', '{hazard_profile_key}', '{env_flags_sql}'",
                "FROM place p",
                f"WHERE LOWER(p.name) = LOWER('{place_name}')",
                "ON DUPLICATE KEY UPDATE",
                "    x = VALUES(x),",
                "    y = VALUES(y),",
                "    place_id = VALUES(place_id),",
                "    biome_key = VALUES(biome_key),",
                "    hazard_profile_key = VALUES(hazard_profile_key),",
                "    environmental_flags = VALUES(environmental_flags);",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_inmemory_module(locations: list[SelectedLocation], *, continent_name: str) -> str:
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from rpg.domain.models.location import HazardProfile, Location",
        "",
        f'CONTINENT_NAME = "{continent_name}"',
        "",
        "GENERATED_LOCATIONS: dict[int, Location] = {",
    ]
    for location in locations:
        name_json = json.dumps(location.name)
        biome_json = json.dumps(location.biome_key)
        faction_json = json.dumps(location.faction_slug)
        tags_json = json.dumps(location.tags)
        hazard_key_json = json.dumps(location.hazard_profile_key)
        env_flags_json = json.dumps(
            [
                f"continent:{continent_name}",
                f"state:{location.state_name}",
                f"state_full:{location.state_full_name}",
                f"group:{location.group}",
                f"faction:{location.faction_slug}",
                f"culture_raw:{location.culture}",
                f"religion_raw:{location.religion}",
                f"settlement_description:{location.settlement_description}",
                f"hazard_severity:{location.hazard_severity}",
            ]
        )
        lines.extend(
            [
                f"    {location.location_id}: Location(",
                f"        id={location.location_id},",
                f"        name={name_json},",
                f"        biome={biome_json},",
                f"        base_level={max(1, min(10, location.hazard_severity + 1))},",
                f"        recommended_level={max(1, min(12, location.hazard_severity + 2))},",
                f"        x={float(location.x):.2f},",
                f"        y={float(location.y):.2f},",
                f"        factions=[{faction_json}],",
                f"        tags={tags_json},",
                "        hazard_profile=HazardProfile(",
                f"            key={hazard_key_json},",
                f"            severity={location.hazard_severity},",
                f"            environmental_flags={env_flags_json},",
                "        ),",
                "    ),",
            ]
        )
    lines.extend(["}", ""])
    return "\n".join(lines)


def render_faction_flavour_module(state_rows: list[dict[str, str]]) -> str:
    rows: list[tuple[str, str]] = []
    for row in state_rows:
        state_name = str(row.get("State") or "").strip()
        if not state_name or state_name.lower() == "neutrals":
            continue
        full_name = str(row.get("Full Name") or state_name).strip()
        form = str(row.get("Form") or "realm").strip()
        culture = str(row.get("Culture") or "mixed").strip()
        slug = _slugify(full_name)
        description = f"A sprawling {form.lower()} dominated by the {culture} culture."
        rows.append((slug, description))

    rows.sort(key=lambda item: item[0])

    lines = [
        "from __future__ import annotations",
        "",
        "FACTION_DESCRIPTION_OVERRIDES: dict[str, str] = {",
    ]
    for slug, description in rows:
        lines.append(f"    {json.dumps(slug)}: {json.dumps(description)},")
    lines.extend(["}", ""])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import continent CSV exports, filter to capitals + major towns, and emit SQL + in-memory location data."
    )
    parser.add_argument("--continent-name", default="Taklamakan", help="Canonical continent/world map name")
    parser.add_argument("--burgs-csv", required=True, type=Path, help="Path to Pres Burgs CSV")
    parser.add_argument("--states-csv", required=True, type=Path, help="Path to Pres States CSV")
    parser.add_argument("--military-csv", required=False, type=Path, help="Path to Pres Military CSV")
    parser.add_argument(
        "--major-town-min-population",
        type=int,
        default=15000,
        help="Minimum population required for non-capital towns/cities",
    )
    parser.add_argument(
        "--max-major-towns-per-state",
        type=int,
        default=8,
        help="Maximum number of major towns/cities (excluding capitals) to keep per state",
    )
    parser.add_argument(
        "--location-id-offset",
        type=int,
        default=1000,
        help="Offset added to source burg IDs to generate stable location IDs",
    )
    parser.add_argument("--out-sql", required=True, type=Path, help="Output SQL seed file path")
    parser.add_argument("--out-inmemory", required=True, type=Path, help="Output Python module file path")
    parser.add_argument(
        "--out-faction-flavour",
        required=False,
        type=Path,
        default=Path("src/rpg/infrastructure/inmemory/generated_taklamakan_faction_flavour.py"),
        help="Output Python module path for generated faction description overrides",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    burg_rows = _csv_rows(args.burgs_csv)
    state_rows = _csv_rows(args.states_csv)
    military_rows = _csv_rows(args.military_csv) if args.military_csv else []

    locations = select_locations(
        burg_rows=burg_rows,
        state_rows=state_rows,
        military_rows=military_rows,
        continent_name=args.continent_name,
        location_id_offset=args.location_id_offset,
        major_town_min_population=args.major_town_min_population,
        max_major_towns_per_state=args.max_major_towns_per_state,
    )

    args.out_sql.parent.mkdir(parents=True, exist_ok=True)
    args.out_inmemory.parent.mkdir(parents=True, exist_ok=True)
    args.out_faction_flavour.parent.mkdir(parents=True, exist_ok=True)
    args.out_sql.write_text(render_sql_seed(locations, continent_name=args.continent_name), encoding="utf-8")
    args.out_inmemory.write_text(render_inmemory_module(locations, continent_name=args.continent_name), encoding="utf-8")
    args.out_faction_flavour.write_text(render_faction_flavour_module(state_rows), encoding="utf-8")

    capitals = sum(1 for item in locations if item.group == "capital")
    majors = len(locations) - capitals
    print(
        "Generated continent location outputs "
        f"(total={len(locations)}, capitals={capitals}, major_towns={majors}) "
        f"-> SQL: {args.out_sql} | in-memory: {args.out_inmemory} | faction flavour: {args.out_faction_flavour}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
