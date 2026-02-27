"""Build a unified spells dataset from local references and Open5e API.

Usage:
    python -m rpg.infrastructure.data_tools.build_unified_spells
    python -m rpg.infrastructure.data_tools.build_unified_spells --no-api
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from rpg.infrastructure.open5e_client import Open5eClient


_XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _slugify(value: str) -> str:
    token = str(value or "").strip().lower()
    token = re.sub(r"[^a-z0-9]+", "-", token)
    return token.strip("-")


def _column_letters(cell_ref: str) -> str:
    letters = []
    for character in str(cell_ref or ""):
        if character.isalpha():
            letters.append(character.upper())
        else:
            break
    return "".join(letters)


def _column_index(letters: str) -> int:
    total = 0
    for character in letters:
        total = (total * 26) + (ord(character) - ord("A") + 1)
    return max(0, total - 1)


def _parse_shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        xml_data = book.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml_data)
    values: list[str] = []
    for item in root.findall("main:si", _XML_NS):
        runs = item.findall("main:r/main:t", _XML_NS)
        if runs:
            values.append("".join(run.text or "" for run in runs))
            continue
        text = item.find("main:t", _XML_NS)
        values.append((text.text if text is not None else "") or "")
    return values


def _resolve_first_sheet_path(book: zipfile.ZipFile) -> str:
    workbook_xml = ET.fromstring(book.read("xl/workbook.xml"))
    first_sheet = workbook_xml.find("main:sheets/main:sheet", _XML_NS)
    if first_sheet is None:
        return "xl/worksheets/sheet1.xml"

    relation_id = first_sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    if not relation_id:
        return "xl/worksheets/sheet1.xml"

    rels_xml = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    for relation in rels_xml.findall("pkgrel:Relationship", _XML_NS):
        if relation.get("Id") != relation_id:
            continue
        target = str(relation.get("Target") or "").strip()
        if not target:
            break
        normalized = target.replace("\\", "/")
        if normalized.startswith("/"):
            return normalized.lstrip("/")
        if normalized.startswith("xl/"):
            return normalized
        return f"xl/{normalized}"
    return "xl/worksheets/sheet1.xml"


def load_xlsx_rows(path: Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []

    with zipfile.ZipFile(source) as book:
        shared = _parse_shared_strings(book)
        sheet_path = _resolve_first_sheet_path(book)
        try:
            sheet_xml = ET.fromstring(book.read(sheet_path))
        except KeyError:
            return []

    rows: list[list[str]] = []
    for row in sheet_xml.findall("main:sheetData/main:row", _XML_NS):
        values: dict[int, str] = {}
        for cell in row.findall("main:c", _XML_NS):
            cell_ref = str(cell.get("r") or "")
            col = _column_index(_column_letters(cell_ref))
            cell_type = str(cell.get("t") or "").strip().lower()
            value_text = ""
            if cell_type == "inlineStr":
                node = cell.find("main:is/main:t", _XML_NS)
                value_text = (node.text if node is not None else "") or ""
            else:
                node = cell.find("main:v", _XML_NS)
                raw = (node.text if node is not None else "") or ""
                if cell_type == "s":
                    try:
                        value_text = shared[int(raw)]
                    except Exception:
                        value_text = ""
                else:
                    value_text = raw
            values[col] = str(value_text).strip()

        if not values:
            continue
        width = max(values.keys()) + 1
        rows.append([values.get(index, "") for index in range(width)])

    if not rows:
        return []

    headers = [str(item or "").strip() for item in rows[0]]
    data_rows: list[dict[str, str]] = []
    for row in rows[1:]:
        if not any(str(item).strip() for item in row):
            continue
        payload: dict[str, str] = {}
        for index, value in enumerate(row):
            if index >= len(headers):
                continue
            key = str(headers[index] or "").strip()
            if not key:
                continue
            payload[key] = str(value or "").strip()
        if payload:
            data_rows.append(payload)
    return data_rows


def _row_name(row: dict[str, object]) -> str:
    preferred = (
        "name",
        "Name",
        "spell",
        "Spell",
        "spell_name",
        "Spell Name",
        "full_name",
        "index",
    )
    for key in preferred:
        value = row.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_local_spell(row: dict[str, str]) -> dict[str, object] | None:
    name = _row_name(row)
    if not name:
        return None
    slug = _slugify(name)
    if not slug:
        return None

    level_value = row.get("level") or row.get("Level") or row.get("level_int") or ""
    try:
        level_int = int(float(str(level_value).strip()))
    except Exception:
        level_int = 0

    school = str(row.get("school") or row.get("School") or "").strip()
    classes = str(row.get("classes") or row.get("dnd_class") or row.get("class") or "").strip()
    components = str(row.get("components") or "").strip()
    if not components:
        component_bits = [token for token in [row.get("V"), row.get("S"), row.get("M")] if str(token or "").strip()]
        components = ", ".join(str(item).strip() for item in component_bits)

    return {
        "slug": slug,
        "name": name,
        "level_int": level_int,
        "school": school,
        "classes": classes,
        "components": components,
        "source": "local_reference",
    }


def _normalize_api_spell(row: dict[str, object]) -> dict[str, object] | None:
    slug = _slugify(str(row.get("slug") or ""))
    name = _row_name(row)
    if not slug and name:
        slug = _slugify(name)
    if not slug or not name:
        return None

    level_value = row.get("level_int", row.get("level", 0))
    try:
        level_int = int(level_value)
    except Exception:
        level_int = 0

    return {
        "slug": slug,
        "name": name,
        "level_int": level_int,
        "school": str(row.get("school") or "").strip(),
        "classes": str(row.get("dnd_class") or row.get("class") or row.get("classes") or "").strip(),
        "components": str(row.get("components") or "").strip(),
        "source": "open5e_api",
    }


def fetch_open5e_spells() -> list[dict[str, object]]:
    client = Open5eClient()
    spells: list[dict[str, object]] = []
    page = 1
    try:
        while True:
            payload = client.list_spells(page=page)
            rows = payload.get("results", []) if isinstance(payload, dict) else []
            if not rows:
                break
            for row in rows:
                if isinstance(row, dict):
                    spells.append(dict(row))
            if not payload.get("next"):
                break
            page += 1
    finally:
        client.close()
    return spells


def build_unified_spells_payload(
    *,
    local_rows: list[dict[str, str]],
    api_rows: list[dict[str, object]],
) -> dict[str, object]:
    normalized_api: list[dict[str, object]] = []
    api_slugs: set[str] = set()
    for row in api_rows:
        normalized = _normalize_api_spell(row)
        if not normalized:
            continue
        slug = str(normalized["slug"])
        if slug in api_slugs:
            continue
        api_slugs.add(slug)
        normalized_api.append(normalized)

    normalized_local: list[dict[str, object]] = []
    local_seen: set[str] = set()
    skipped_as_duplicate = 0
    for row in local_rows:
        normalized = _normalize_local_spell(row)
        if not normalized:
            continue
        slug = str(normalized["slug"])
        if slug in api_slugs:
            skipped_as_duplicate += 1
            continue
        if slug in local_seen:
            continue
        local_seen.add(slug)
        normalized_local.append(normalized)

    merged = [*normalized_api, *normalized_local]
    merged.sort(key=lambda item: (str(item.get("name", "")).lower(), str(item.get("slug", "")).lower()))

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "counts": {
            "api_spells": len(normalized_api),
            "local_rows": len(local_rows),
            "local_unique_non_api": len(normalized_local),
            "local_duplicates_in_api": skipped_as_duplicate,
            "total_unified": len(merged),
        },
        "spells": merged,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build one unified spells dataset and remove API duplicates")
    parser.add_argument(
        "--local-xlsx",
        default="data/spells_reference/datasets/D&D 5E Spells.xlsx",
        help="Path to local XLSX spell dataset",
    )
    parser.add_argument(
        "--output",
        default="data/spells/unified_spells.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Skip Open5e API fetch (disables API dedupe)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    local_path = Path(args.local_xlsx)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    local_rows = load_xlsx_rows(local_path)
    api_rows: list[dict[str, object]] = []
    if not bool(args.no_api):
        try:
            api_rows = fetch_open5e_spells()
        except Exception as exc:
            print(f"Warning: Open5e fetch failed; writing local-only dataset ({exc}).")

    payload = build_unified_spells_payload(local_rows=local_rows, api_rows=api_rows)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    counts = payload.get("counts", {}) if isinstance(payload, dict) else {}
    print(f"Unified spells written to {output_path}")
    print(
        "Counts: "
        f"api={counts.get('api_spells', 0)} "
        f"local_rows={counts.get('local_rows', 0)} "
        f"local_non_api={counts.get('local_unique_non_api', 0)} "
        f"duplicates_removed={counts.get('local_duplicates_in_api', 0)} "
        f"total={counts.get('total_unified', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
