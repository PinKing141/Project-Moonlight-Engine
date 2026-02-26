import ast
import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


ROOT = Path(__file__).resolve().parents[2]


def _class_methods_from_file(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, ast.FunctionDef)
            }
    raise AssertionError(f"Class {class_name} not found in {path}")


class RepositoryParityAuditTests(unittest.TestCase):
    def test_inmemory_mysql_adapters_cover_application_used_methods(self) -> None:
        mysql_path = ROOT / "src" / "rpg" / "infrastructure" / "db" / "mysql" / "repos.py"

        inmemory_paths = {
            "InMemoryCharacterRepository": ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_character_repo.py",
            "InMemoryEntityRepository": ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_entity_repo.py",
            "InMemoryWorldRepository": ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_world_repo.py",
            "InMemoryLocationRepository": ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_location_repo.py",
            "InMemoryClassRepository": ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_class_repo.py",
            "InMemoryEncounterDefinitionRepository": ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_encounter_definition_repo.py",
        }

        requirements = {
            ("InMemoryCharacterRepository", "MysqlCharacterRepository"): {"get", "list_all", "save", "create", "find_by_location"},
            ("InMemoryEntityRepository", "MysqlEntityRepository"): {"get_many", "list_by_location", "list_for_level", "list_by_level_band"},
            ("InMemoryWorldRepository", "MysqlWorldRepository"): {"load_default", "save"},
            ("InMemoryLocationRepository", "MysqlLocationRepository"): {"get", "list_all", "get_starting_location"},
            ("InMemoryClassRepository", "MysqlClassRepository"): {"list_playable"},
            ("InMemoryEncounterDefinitionRepository", "MysqlEncounterDefinitionRepository"): {"list_for_location", "list_global"},
        }

        for (inmemory_class, mysql_class), required in requirements.items():
            in_mem_methods = _class_methods_from_file(inmemory_paths[inmemory_class], inmemory_class)
            mysql_methods = _class_methods_from_file(mysql_path, mysql_class)

            self.assertTrue(required.issubset(in_mem_methods), f"{inmemory_class} missing {sorted(required - in_mem_methods)}")
            self.assertTrue(required.issubset(mysql_methods), f"{mysql_class} missing {sorted(required - mysql_methods)}")

    def test_application_layer_has_no_adapter_specific_assumptions(self) -> None:
        app_dir = ROOT / "src" / "rpg" / "application"
        forbidden_patterns = [
            re.compile(r"\bMysql\w+\b"),
            re.compile(r"\bInMemory\w+\b"),
            re.compile(r"\bSessionLocal\b"),
            re.compile(r"sqlalchemy", re.IGNORECASE),
        ]

        violations: list[str] = []
        excluded_files = {"narrative_quality_batch.py"}
        for path in app_dir.rglob("*.py"):
            if path.name in excluded_files:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                if pattern.search(text):
                    violations.append(f"{path.relative_to(ROOT)} :: {pattern.pattern}")

        self.assertEqual([], violations, "Application layer includes adapter-specific references")

    def test_v12_content_ids_are_present_in_inmemory_and_mysql_paths(self) -> None:
        in_memory_faction = (ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_faction_repo.py").read_text(encoding="utf-8")
        in_memory_encounters = (
            ROOT / "src" / "rpg" / "infrastructure" / "inmemory" / "inmemory_encounter_definition_repo.py"
        ).read_text(encoding="utf-8")
        mysql_repos = (ROOT / "src" / "rpg" / "infrastructure" / "db" / "mysql" / "repos.py").read_text(encoding="utf-8")

        faction_ids = ("the_crown", "thieves_guild", "arcane_syndicate")
        encounter_table_ids = ("forest_patrol_table", "ruins_ambush_table", "caves_depths_table")

        for faction_id in faction_ids:
            self.assertIn(faction_id, in_memory_faction)
            self.assertIn(faction_id, mysql_repos)

        for table_id in encounter_table_ids:
            self.assertIn(table_id, in_memory_encounters)
            self.assertIn(table_id, mysql_repos)


if __name__ == "__main__":
    unittest.main()
