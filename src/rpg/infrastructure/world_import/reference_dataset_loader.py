from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


_REFERENCE_FILE_PREFIXES: dict[str, str] = {
    "biomes": "Pres Biomes ",
    "burgs": "Pres Burgs ",
    "markers": "Pres Markers ",
    "military": "Pres Military ",
    "provinces": "Pres Provinces ",
    "relations": "Pres Relations ",
    "religions": "Pres Religions ",
    "rivers": "Pres Rivers ",
    "routes": "Pres Routes ",
    "states": "Pres States ",
}


@dataclass(frozen=True)
class ReferenceWorldDataset:
    source_files: dict[str, str]
    states_by_slug: dict[str, dict[str, object]]
    provinces_by_state_slug: dict[str, list[dict[str, object]]]
    military_by_state_slug: dict[str, dict[str, object]]
    relations_matrix: dict[str, dict[str, str]]
    biome_rows: list[dict[str, object]]
    biome_severity_index: dict[str, int]
    burg_rows: list[dict[str, object]]
    marker_rows: list[dict[str, object]]
    religion_rows: list[dict[str, object]]
    river_rows: list[dict[str, object]]
    route_rows: list[dict[str, object]]


def _slugify(value: str) -> str:
    cleaned = str(value or "").strip().lower().replace("-", " ")
    return "_".join(part for part in cleaned.split() if part)


def _parse_int(raw_value, *, default: int = 0) -> int:
    text = str(raw_value or "").strip().replace(",", "")
    if not text:
        return int(default)
    try:
        return int(float(text))
    except ValueError:
        return int(default)


def _parse_float(raw_value, *, default: float = 0.0) -> float:
    text = str(raw_value or "").strip().replace(",", "")
    if not text:
        return float(default)
    try:
        return float(text)
    except ValueError:
        return float(default)


def _parse_percent(raw_value, *, default: float = 0.0) -> float:
    text = str(raw_value or "").strip().replace("%", "")
    return _parse_float(text, default=default)


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def discover_reference_files(reference_dir: Path) -> dict[str, Path]:
    resolved = Path(reference_dir)
    files: dict[str, Path] = {}
    for key, prefix in _REFERENCE_FILE_PREFIXES.items():
        candidates = sorted(resolved.glob(f"{prefix}*.csv"), key=lambda row: row.name)
        if candidates:
            files[key] = candidates[-1]
    return files


def _load_states(state_rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    mapped: dict[str, dict[str, object]] = {}
    for row in state_rows:
        state_name = str(row.get("State", "") or "").strip()
        state_slug = _slugify(state_name)
        if not state_slug:
            continue
        mapped[state_slug] = {
            "id": _parse_int(row.get("Id"), default=0),
            "state": state_name,
            "full_name": str(row.get("Full Name", "") or "").strip(),
            "capital": str(row.get("Capital", "") or "").strip(),
            "culture": str(row.get("Culture", "") or "").strip(),
            "population": _parse_int(row.get("Population") or row.get("Total Population"), default=0),
        }
    return mapped


def _load_provinces(province_rows: list[dict[str, str]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in province_rows:
        state_name = str(row.get("State", "") or "").strip()
        state_slug = _slugify(state_name)
        if not state_slug:
            continue
        grouped.setdefault(state_slug, []).append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "province": str(row.get("Province", "") or "").strip(),
                "province_full_name": str(row.get("Province Full Name") or row.get("Full Name") or "").strip(),
                "population": _parse_int(row.get("Population") or row.get("Total Population"), default=0),
            }
        )
    for rows in grouped.values():
        rows.sort(key=lambda item: (-int(item.get("population", 0) or 0), str(item.get("province", "")).lower()))
    return grouped


def _load_military(military_rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    mapped: dict[str, dict[str, object]] = {}
    for row in military_rows:
        state_name = str(row.get("State", "") or "").strip()
        state_slug = _slugify(state_name)
        if not state_slug:
            continue
        mapped[state_slug] = {
            "state": state_name,
            "total": _parse_int(row.get("Total"), default=0),
            "population": _parse_int(row.get("Population"), default=0),
            "rate": _parse_percent(row.get("Rate"), default=0.0),
            "war_alert": _parse_float(row.get("War Alert"), default=0.0),
        }
    return mapped


def _load_relations_matrix(relations_csv_path: Path) -> dict[str, dict[str, str]]:
    with relations_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = [list(row) for row in reader]

    if not rows:
        return {}

    header = rows[0]
    column_states = [_slugify(row) for row in header[1:]]
    matrix: dict[str, dict[str, str]] = {}

    for row in rows[1:]:
        if not row:
            continue
        row_state = _slugify(row[0])
        if not row_state:
            continue
        row_map: dict[str, str] = {}
        for idx, value in enumerate(row[1:]):
            if idx >= len(column_states):
                break
            target_state = column_states[idx]
            if not target_state:
                continue
            relation = str(value or "").strip()
            if relation:
                row_map[target_state] = relation
        matrix[row_state] = row_map
    return matrix


def _load_biomes(biome_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in biome_rows:
        biome_name = str(row.get("Biome", "") or "").strip()
        biome_slug = _slugify(biome_name)
        if not biome_slug:
            continue
        rows.append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "name": biome_name,
                "slug": biome_slug,
                "color": str(row.get("Color", "") or "").strip(),
                "habitability_pct": _parse_percent(row.get("Habitability"), default=0.0),
                "cells": _parse_int(row.get("Cells"), default=0),
                "area_mi2": _parse_float(row.get("Area mi2"), default=0.0),
                "population": _parse_int(row.get("Population"), default=0),
            }
        )
    rows.sort(key=lambda item: int(item.get("id", 0) or 0))
    return rows


def _load_burgs(burg_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in burg_rows:
        name = str(row.get("Burg", "") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "burg": name,
                "state": str(row.get("State", "") or "").strip(),
                "state_slug": _slugify(str(row.get("State", "") or "")),
                "province": str(row.get("Province", "") or "").strip(),
                "population": _parse_int(row.get("Population"), default=0),
                "group": str(row.get("Group", "") or "").strip(),
                "capital": str(row.get("Capital", "") or "").strip(),
                "port": str(row.get("Port", "") or "").strip(),
                "culture": str(row.get("Culture", "") or "").strip(),
                "religion": str(row.get("Religion", "") or "").strip(),
                "x": _parse_float(row.get("X"), default=0.0),
                "y": _parse_float(row.get("Y"), default=0.0),
            }
        )
    rows.sort(key=lambda item: int(item.get("id", 0) or 0))
    return rows


def _load_markers(marker_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in marker_rows:
        marker_type = str(row.get("Type", "") or "").strip()
        name = str(row.get("Name", "") or "").strip()
        if not marker_type and not name:
            continue
        rows.append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "type": marker_type,
                "icon": str(row.get("Icon", "") or "").strip(),
                "name": name,
                "note": str(row.get("Note", "") or "").strip(),
                "x": _parse_float(row.get("X"), default=0.0),
                "y": _parse_float(row.get("Y"), default=0.0),
                "latitude": _parse_float(row.get("Latitude"), default=0.0),
                "longitude": _parse_float(row.get("Longitude"), default=0.0),
            }
        )
    rows.sort(key=lambda item: int(item.get("id", 0) or 0))
    return rows


def _load_religions(religion_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in religion_rows:
        name = str(row.get("Name", "") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "name": name,
                "type": str(row.get("Type", "") or "").strip(),
                "form": str(row.get("Form", "") or "").strip(),
                "supreme_deity": str(row.get("Supreme Deity", "") or "").strip(),
                "believers": _parse_int(row.get("Believers"), default=0),
                "expansionism": _parse_float(row.get("Expansionism"), default=0.0),
            }
        )
    rows.sort(key=lambda item: int(item.get("id", 0) or 0))
    return rows


def _load_rivers(river_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in river_rows:
        name = str(row.get("River", "") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "river": name,
                "type": str(row.get("Type", "") or "").strip(),
                "discharge": str(row.get("Discharge", "") or "").strip(),
                "length": str(row.get("Length", "") or "").strip(),
                "width": str(row.get("Width", "") or "").strip(),
                "basin": str(row.get("Basin", "") or "").strip(),
            }
        )
    rows.sort(key=lambda item: int(item.get("id", 0) or 0))
    return rows


def _load_routes(route_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in route_rows:
        name = str(row.get("Route", "") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "id": _parse_int(row.get("Id"), default=0),
                "route": name,
                "group": str(row.get("Group", "") or "").strip(),
                "length": str(row.get("Length", "") or "").strip(),
            }
        )
    rows.sort(key=lambda item: int(item.get("id", 0) or 0))
    return rows


def _load_from_unified_json(unified_json_path: Path) -> ReferenceWorldDataset | None:
    try:
        payload = json.loads(unified_json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    dataset = payload.get("dataset") if isinstance(payload, dict) else None
    if not isinstance(dataset, dict):
        return None
    return ReferenceWorldDataset(
        source_files=dict(dataset.get("source_files", {}) or {}),
        states_by_slug=dict(dataset.get("states_by_slug", {}) or {}),
        provinces_by_state_slug=dict(dataset.get("provinces_by_state_slug", {}) or {}),
        military_by_state_slug=dict(dataset.get("military_by_state_slug", {}) or {}),
        relations_matrix=dict(dataset.get("relations_matrix", {}) or {}),
        biome_rows=list(dataset.get("biome_rows", []) or []),
        biome_severity_index=dict(dataset.get("biome_severity_index", {}) or {}),
        burg_rows=list(dataset.get("burg_rows", []) or []),
        marker_rows=list(dataset.get("marker_rows", []) or []),
        religion_rows=list(dataset.get("religion_rows", []) or []),
        river_rows=list(dataset.get("river_rows", []) or []),
        route_rows=list(dataset.get("route_rows", []) or []),
    )


def _build_biome_severity_index(biome_rows: list[dict[str, object]]) -> dict[str, int]:
    if not biome_rows:
        return {}

    max_population = max(int(row.get("population", 0) or 0) for row in biome_rows) or 1
    max_area = max(float(row.get("area_mi2", 0.0) or 0.0) for row in biome_rows) or 1.0

    index: dict[str, int] = {}
    for row in biome_rows:
        slug = str(row.get("slug", "") or "").strip().lower()
        if not slug:
            continue
        habitability_ratio = max(0.0, min(1.0, float(row.get("habitability_pct", 0.0) or 0.0) / 100.0))
        population_ratio = max(0.0, min(1.0, int(row.get("population", 0) or 0) / float(max_population)))
        area_ratio = max(0.0, min(1.0, float(row.get("area_mi2", 0.0) or 0.0) / float(max_area)))

        severity = int(round(((1.0 - habitability_ratio) * 50.0) + (population_ratio * 35.0) + (area_ratio * 15.0)))
        index[slug] = max(0, min(100, int(severity)))
    return index


def load_reference_world_dataset(reference_dir: Path | None = None) -> ReferenceWorldDataset:
    resolved_reference_dir = (
        Path(reference_dir)
        if reference_dir is not None
        else Path(__file__).resolve().parents[4] / "data" / "reference_world"
    )
    files = discover_reference_files(resolved_reference_dir)

    if not files:
        unified_path = resolved_reference_dir / "unified_reference_world.json"
        loaded = _load_from_unified_json(unified_path)
        if loaded is not None:
            return loaded

    states = _load_states(_read_csv_rows(files["states"])) if "states" in files else {}
    provinces = _load_provinces(_read_csv_rows(files["provinces"])) if "provinces" in files else {}
    military = _load_military(_read_csv_rows(files["military"])) if "military" in files else {}
    relations = _load_relations_matrix(files["relations"]) if "relations" in files else {}
    biome_rows = _load_biomes(_read_csv_rows(files["biomes"])) if "biomes" in files else []
    biome_severity = _build_biome_severity_index(biome_rows)
    burg_rows = _load_burgs(_read_csv_rows(files["burgs"])) if "burgs" in files else []
    marker_rows = _load_markers(_read_csv_rows(files["markers"])) if "markers" in files else []
    religion_rows = _load_religions(_read_csv_rows(files["religions"])) if "religions" in files else []
    river_rows = _load_rivers(_read_csv_rows(files["rivers"])) if "rivers" in files else []
    route_rows = _load_routes(_read_csv_rows(files["routes"])) if "routes" in files else []

    source_files = {key: str(path) for key, path in files.items()}
    return ReferenceWorldDataset(
        source_files=source_files,
        states_by_slug=states,
        provinces_by_state_slug=provinces,
        military_by_state_slug=military,
        relations_matrix=relations,
        biome_rows=biome_rows,
        biome_severity_index=biome_severity,
        burg_rows=burg_rows,
        marker_rows=marker_rows,
        religion_rows=religion_rows,
        river_rows=river_rows,
        route_rows=route_rows,
    )
