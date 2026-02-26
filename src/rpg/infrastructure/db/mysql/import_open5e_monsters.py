"""Import Open5e monsters into the database via repository implementations.

Usage (example):
    set RPG_DATABASE_URL=mysql+mysqlconnector://user:pass@localhost:3306/rpg_game
    python -m rpg.infrastructure.db.mysql.import_open5e_monsters --pages 2 --start-page 1 --location-id 3
"""

import argparse
from typing import Optional

from rpg.infrastructure.db.mysql.open5e_monster_importer import Open5eMonsterImporter, UpsertResult
from rpg.infrastructure.db.mysql.repos import MysqlEntityRepository
from rpg.infrastructure.content_provider_factory import create_import_content_client


def import_monsters(
    pages: int,
    start_page: int = 1,
    location_id: Optional[int] = None,
    client=None,
    repository: Optional[MysqlEntityRepository] = None,
) -> UpsertResult:
    client = client or create_import_content_client()
    repository = repository or MysqlEntityRepository()
    importer = Open5eMonsterImporter(repository=repository, client=client)
    result = importer.import_monsters(pages=pages, start_page=start_page, location_id=location_id)
    client.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import monsters from Open5e into MySQL")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to import (20 items each)")
    parser.add_argument("--start-page", type=int, default=1, help="First page number to import from Open5e")
    parser.add_argument(
        "--location-id",
        type=int,
        default=None,
        help="Location ID to attach monsters to (defaults to the first location)",
    )
    args = parser.parse_args()
    result = import_monsters(pages=args.pages, start_page=args.start_page, location_id=args.location_id)
    target_location = args.location_id if args.location_id is not None else "default location"
    print(
        f"Created {result.created}, updated {result.updated}, "
        f"attached {result.attached} monsters to {target_location}."
    )


if __name__ == "__main__":
    main()
