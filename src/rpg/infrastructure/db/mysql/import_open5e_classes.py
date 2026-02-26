"""Import class metadata from Open5e into the local MySQL database.

Usage:
    python -m rpg.infrastructure.db.mysql.import_open5e_classes --pages 1
"""

import argparse

from sqlalchemy import text

from rpg.infrastructure.db.mysql.connection import SessionLocal
from rpg.infrastructure.content_provider_factory import create_import_content_client


def _ensure_class_table_columns(session) -> None:
    """Backfill optional columns if the table was created before this import existed."""
    session.execute(
        text(
            """
            ALTER TABLE class
                ADD COLUMN IF NOT EXISTS hit_die VARCHAR(8) NULL,
                ADD COLUMN IF NOT EXISTS primary_ability VARCHAR(32) NULL,
                ADD COLUMN IF NOT EXISTS source VARCHAR(32) NULL,
                ADD COLUMN IF NOT EXISTS open5e_slug VARCHAR(128) NULL,
                ADD UNIQUE KEY IF NOT EXISTS uk_class_open5e_slug (open5e_slug)
            """
        )
    )


def import_classes(pages: int = 1, source: str = "open5e") -> None:
    client = create_import_content_client()
    imported = 0
    with SessionLocal() as session:
        _ensure_class_table_columns(session)
        for page in range(1, pages + 1):
            payload = client.list_classes(page=page)
            for cls in payload.get("results", []):
                name = cls.get("name", "Unknown")
                slug = cls.get("slug") or name.lower()
                hit_die = cls.get("hit_die")
                primary = cls.get("primary_ability")

                session.execute(
                    text(
                        """
                        INSERT INTO class (name, open5e_slug, hit_die, primary_ability, source)
                        VALUES (:name, :slug, :hit_die, :primary, :source)
                        ON DUPLICATE KEY UPDATE
                            hit_die = VALUES(hit_die),
                            primary_ability = VALUES(primary_ability),
                            source = VALUES(source),
                            name = VALUES(name)
                        """
                    ),
                    {
                        "name": name,
                        "slug": slug,
                        "hit_die": hit_die,
                        "primary": primary,
                        "source": source,
                    },
                )
                imported += 1
        session.commit()

    client.close()
    print(f"Imported or updated {imported} class records from Open5e.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Open5e classes into MySQL")
    parser.add_argument("--pages", type=int, default=1, help="How many pages of classes to import")
    args = parser.parse_args()
    import_classes(pages=args.pages)


if __name__ == "__main__":
    main()
