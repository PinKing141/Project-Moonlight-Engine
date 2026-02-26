"""Import Open5e spells into the local MySQL spell table.

Usage:
    set RPG_DATABASE_URL=mysql+mysqlconnector://user:pass@localhost:3306/rpg_game
    python -m rpg.infrastructure.db.mysql.import_open5e_spells
"""

import json

import httpx
from sqlalchemy import text

from rpg.infrastructure.db.mysql.connection import SessionLocal

OPEN5E_BASE = "https://api.open5e.com"


def iter_open5e(endpoint: str, limit: int = 100):
    url = f"{OPEN5E_BASE}{endpoint}"
    params = {"limit": limit}
    with httpx.Client(timeout=30.0) as client:
        while url:
            resp = client.get(url, params=params if url.endswith(endpoint) else None)
            resp.raise_for_status()
            data = resp.json()
            for row in data.get("results", []):
                yield row
            url = data.get("next")
            params = None


def _normalise_classes(spell_row: dict) -> list[str]:
    # Open5e may return classes as list or comma string
    if isinstance(spell_row.get("classes"), list):
        return [str(x).strip() for x in spell_row["classes"] if str(x).strip()]
    dnd_class = spell_row.get("dnd_class") or spell_row.get("class") or ""
    if isinstance(dnd_class, str):
        return [c.strip() for c in dnd_class.split(",") if c.strip()]
    return []


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def import_spells() -> None:
    count = 0
    with SessionLocal() as session:
        for s in iter_open5e("/spells/", limit=100):
            slug = s.get("slug")
            name = s.get("name")
            if not slug or not name:
                continue
            level_val = s.get("level_int")
            if level_val is None:
                level_val = s.get("level", 0)
            try:
                level_int = int(level_val)
            except Exception:
                level_int = 0
            classes = _normalise_classes(s)
            session.execute(
                text(
                    """
                    INSERT INTO spell (
                        slug, name, level_int, school, casting_time, range_text, duration,
                        components, concentration, ritual, desc_text, higher_level, classes_json
                    )
                    VALUES (
                        :slug, :name, :level_int, :school, :casting_time, :range_text, :duration,
                        :components, :concentration, :ritual, :desc_text, :higher_level, :classes_json
                    )
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        level_int = VALUES(level_int),
                        school = VALUES(school),
                        casting_time = VALUES(casting_time),
                        range_text = VALUES(range_text),
                        duration = VALUES(duration),
                        components = VALUES(components),
                        concentration = VALUES(concentration),
                        ritual = VALUES(ritual),
                        desc_text = VALUES(desc_text),
                        higher_level = VALUES(higher_level),
                        classes_json = VALUES(classes_json)
                    """
                ),
                {
                    "slug": slug,
                    "name": name,
                    "level_int": level_int,
                    "school": s.get("school"),
                    "casting_time": s.get("casting_time"),
                    "range_text": s.get("range"),
                    "duration": s.get("duration"),
                    "components": s.get("components"),
                    "concentration": 1 if _to_bool(s.get("concentration")) else 0,
                    "ritual": 1 if _to_bool(s.get("ritual")) else 0,
                    "desc_text": s.get("desc"),
                    "higher_level": s.get("higher_level"),
                    "classes_json": json.dumps(classes) if classes else None,
                },
            )
            count += 1
        session.commit()
    print(f"Imported/updated {count} spells into MySQL.")


def main() -> None:
    import_spells()


if __name__ == "__main__":
    main()
