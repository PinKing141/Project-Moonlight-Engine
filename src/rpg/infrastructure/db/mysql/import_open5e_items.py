"""Import canonical equipment/magic items into MySQL item tables.

Usage:
    set RPG_DATABASE_URL=mysql+mysqlconnector://user:pass@localhost:3306/rpg_game
    python -m rpg.infrastructure.db.mysql.import_open5e_items --pages 2
"""

from __future__ import annotations

import argparse
from sqlalchemy import text

from rpg.infrastructure.content_provider_factory import create_import_content_client
from rpg.infrastructure.db.mysql.connection import SessionLocal


def _coerce_required_level(raw_value) -> int:
    if isinstance(raw_value, int):
        return max(1, raw_value)
    text_value = str(raw_value or "").strip().lower()
    if not text_value:
        return 1
    rarity_map = [
        ("very rare", 7),
        ("legendary", 10),
        ("artifact", 12),
        ("uncommon", 2),
        ("rare", 4),
        ("common", 1),
    ]
    for rarity, level in rarity_map:
        if rarity in text_value:
            return level
    return 1


def _resolve_item_type_id(session) -> int:
    existing = session.execute(
        text("SELECT item_type_id FROM item_type WHERE LOWER(name) = 'equipment' LIMIT 1")
    ).scalar()
    if existing:
        return int(existing)
    result = session.execute(text("INSERT INTO item_type (name, `desc`) VALUES ('equipment', 'Canonical imported equipment')"))
    session.flush()
    return int(result.lastrowid)


def import_items(pages: int = 1, start_page: int = 1, client=None) -> int:
    provider = client or create_import_content_client()
    imported = 0

    with SessionLocal.begin() as session:
        item_type_id = _resolve_item_type_id(session)
        for page in range(max(1, int(start_page)), max(1, int(start_page)) + max(1, int(pages))):
            payload = provider.list_magicitems(page=page)
            rows = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                rows = []

            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name", "")).strip()
                if not name:
                    continue
                required_level = _coerce_required_level(row.get("rarity") or row.get("type") or row.get("meta") or row.get("level"))

                existing_id = session.execute(
                    text("SELECT item_id FROM item WHERE LOWER(name) = :name LIMIT 1"),
                    {"name": name.lower()},
                ).scalar()

                if existing_id:
                    session.execute(
                        text(
                            """
                            UPDATE item
                            SET item_type_id = :item_type_id,
                                required_level = :required_level,
                                durability = :durability
                            WHERE item_id = :item_id
                            """
                        ),
                        {
                            "item_type_id": int(item_type_id),
                            "required_level": int(required_level),
                            "durability": 100,
                            "item_id": int(existing_id),
                        },
                    )
                else:
                    session.execute(
                        text(
                            """
                            INSERT INTO item (item_type_id, name, required_level, durability)
                            VALUES (:item_type_id, :name, :required_level, :durability)
                            """
                        ),
                        {
                            "item_type_id": int(item_type_id),
                            "name": name,
                            "required_level": int(required_level),
                            "durability": 100,
                        },
                    )
                imported += 1

    provider.close()
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Import canonical equipment/magic items into MySQL")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to import")
    parser.add_argument("--start-page", type=int, default=1, help="Starting page")
    args = parser.parse_args()

    imported = import_items(pages=args.pages, start_page=args.start_page)
    print(f"Imported/updated {imported} canonical items into MySQL.")


if __name__ == "__main__":
    main()
