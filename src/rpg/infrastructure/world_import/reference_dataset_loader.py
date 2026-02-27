from __future__ import annotations

import csv
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
            "population": _parse_int(row.get("Population"), default=0),
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
                "province_full_name": str(row.get("Province Full Name", "") or "").strip(),
                "population": _parse_int(row.get("Population"), default=0),
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
    resolved_reference_dir = Path(reference_dir) if reference_dir is not None else Path(__file__).resolve().parents[4] / "reference_"
    files = discover_reference_files(resolved_reference_dir)

    states = _load_states(_read_csv_rows(files["states"])) if "states" in files else {}
    provinces = _load_provinces(_read_csv_rows(files["provinces"])) if "provinces" in files else {}
    military = _load_military(_read_csv_rows(files["military"])) if "military" in files else {}
    relations = _load_relations_matrix(files["relations"]) if "relations" in files else {}
    biome_rows = _load_biomes(_read_csv_rows(files["biomes"])) if "biomes" in files else []
    biome_severity = _build_biome_severity_index(biome_rows)

    source_files = {key: str(path) for key, path in files.items()}
    return ReferenceWorldDataset(
        source_files=source_files,
        states_by_slug=states,
        provinces_by_state_slug=provinces,
        military_by_state_slug=military,
        relations_matrix=relations,
        biome_rows=biome_rows,
        biome_severity_index=biome_severity,
    )
