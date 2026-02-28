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
    def _column_exists(column_name: str) -> bool:
        count = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'class'
                  AND COLUMN_NAME = :column_name
                """
            ),
            {"column_name": column_name},
        ).scalar()
        return bool(count)

    def _index_exists(index_name: str) -> bool:
        count = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'class'
                  AND INDEX_NAME = :index_name
                """
            ),
            {"index_name": index_name},
        ).scalar()
        return bool(count)

    if not _column_exists("hit_die"):
        session.execute(text("ALTER TABLE class ADD COLUMN hit_die VARCHAR(8) NULL"))
    if not _column_exists("primary_ability"):
        session.execute(text("ALTER TABLE class ADD COLUMN primary_ability VARCHAR(32) NULL"))
    if not _column_exists("source"):
        session.execute(text("ALTER TABLE class ADD COLUMN source VARCHAR(32) NULL"))
    if not _column_exists("open5e_slug"):
        session.execute(text("ALTER TABLE class ADD COLUMN open5e_slug VARCHAR(128) NULL"))
    if not _index_exists("uk_class_open5e_slug"):
        session.execute(text("ALTER TABLE class ADD UNIQUE KEY uk_class_open5e_slug (open5e_slug)"))


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
