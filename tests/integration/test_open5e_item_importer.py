import sys
from pathlib import Path
import unittest
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.db.mysql import import_open5e_items as importer_module


class _FakeClient:
    def __init__(self, pages: dict[int, dict]) -> None:
        self.pages = dict(pages)
        self.closed = False

    def list_magicitems(self, page: int = 1) -> dict:
        return self.pages.get(page, {"results": []})

    def close(self) -> None:
        self.closed = True


class Open5eItemImporterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE item_type (
                        item_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        `desc` TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE item (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_type_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        required_level INTEGER,
                        durability INTEGER NOT NULL
                    )
                    """
                )
            )

        self.patcher = mock.patch.object(importer_module, "SessionLocal", self.SessionLocal)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.engine.dispose()

    def test_import_items_inserts_and_updates_rows(self) -> None:
        client = _FakeClient(
            {
                1: {
                    "results": [
                        {"name": "Moonlit Blade", "rarity": "rare"},
                        {"name": "Warden Cloak", "rarity": "uncommon"},
                    ]
                },
                2: {
                    "results": [
                        {"name": "Moonlit Blade", "rarity": "very rare"},
                    ]
                },
            }
        )

        imported = importer_module.import_items(pages=2, start_page=1, client=client)

        self.assertEqual(3, imported)
        self.assertTrue(client.closed)

        with self.SessionLocal() as session:
            count = session.execute(text("SELECT COUNT(*) FROM item")).scalar_one()
            blade_level = session.execute(
                text("SELECT required_level FROM item WHERE LOWER(name) = 'moonlit blade'")
            ).scalar_one()
            self.assertEqual(2, int(count))
            self.assertEqual(7, int(blade_level))


if __name__ == "__main__":
    unittest.main()
