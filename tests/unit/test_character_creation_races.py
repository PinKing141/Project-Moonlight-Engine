import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.character_creation_service import CharacterCreationService
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.location import Location


class _DummyRepo:
    """Minimal stub for repositories not used in these tests."""

    pass


class _FakeCharacterRepo:
    def __init__(self) -> None:
        self.created = []

    def list_all(self):
        return []

    def create(self, character, location_id: int):
        character.id = 1
        character.location_id = location_id
        self.created.append(character)
        return character


class _FakeLocationRepo:
    def get_starting_location(self):
        return Location(id=1, name="Town", base_level=1)


class _FakeClassRepo:
    def __init__(self, classes=None):
        self._classes = classes or []

    def list_playable(self):
        return list(self._classes)


class _FakeRaceClient:
    def __init__(self, pages, should_raise: bool = False):
        self.pages = pages
        self.should_raise = should_raise
        self.calls = []
        self.get_calls = []
        self.race_details = {}
        self.closed = False

    def list_races(self, page: int = 1) -> dict:
        if self.should_raise:
            raise RuntimeError("boom")
        self.calls.append(page)
        return self.pages.get(page, {"results": []})

    def close(self) -> None:
        self.closed = True

    def get_race(self, slug: str) -> dict:
        self.get_calls.append(slug)
        if slug in self.race_details:
            return self.race_details[slug]
        raise KeyError(slug)


class _FakeCatalogClient(_FakeRaceClient):
    def __init__(self, pages, endpoint_payloads=None):
        super().__init__(pages=pages, should_raise=False)
        self.endpoint_payloads = endpoint_payloads or {}

    def list_endpoint(self, endpoint: str, page: int = 1) -> dict:
        payload = self.endpoint_payloads.get((str(endpoint), int(page)))
        if payload is None:
            return {"results": []}
        return payload


class CharacterCreationRacesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.char_repo = _DummyRepo()
        self.class_repo = _DummyRepo()
        self.location_repo = _DummyRepo()

    def test_merges_open5e_races_and_parses_bonuses(self) -> None:
        client = _FakeRaceClient(
            pages={
                1: {
                    "results": [
                        {
                            "name": "Aarakocra",
                            "speed": "50",
                            "asi": [{"ability": "dex", "value": 2}, {"ability": "wis", "value": 1}],
                            "traits": ["Flight", "Talons"],
                        }
                    ],
                    "next": "has-more",
                },
                2: {
                    "results": [
                        {"name": "Genasi", "speed": 30, "ability_bonuses": {"str": 2}, "asi_desc": "Elemental Heritage"},
                        {"name": "Human", "speed": 30, "asi": "STR +1, DEX +1"},  # duplicate of default should be ignored
                    ],
                    "next": None,
                },
            }
        )

        service = CharacterCreationService(
            self.char_repo, self.class_repo, self.location_repo, open5e_client=client
        )
        races = service.list_races()

        names = [race.name for race in races]
        self.assertIn("Aarakocra", names)
        self.assertIn("Genasi", names)
        # Default races remain and duplicates are not double-added
        self.assertEqual(names.count("Human"), 1)

        aarakocra = next(r for r in races if r.name == "Aarakocra")
        self.assertEqual(50, aarakocra.speed)
        self.assertEqual({"DEX": 2, "WIS": 1}, aarakocra.bonuses)
        self.assertIn("Flight", aarakocra.traits)

        genasi = next(r for r in races if r.name == "Genasi")
        self.assertEqual({"STR": 2}, genasi.bonuses)
        self.assertIn("Elemental Heritage", genasi.traits)

        self.assertTrue(client.closed, "Open5e client should be closed after loading races")
        self.assertEqual([1, 2], client.calls)

    def test_hydrates_sparse_race_rows_with_get_race_details(self) -> None:
        client = _FakeRaceClient(
            pages={
                1: {
                    "results": [
                        {"index": "half-elf", "name": "Half-Elf", "speed": 30},
                    ],
                    "next": None,
                }
            }
        )
        client.race_details["half-elf"] = {
            "name": "Half-Elf",
            "speed": 30,
            "ability_bonuses": [
                {"ability_score": {"index": "cha"}, "bonus": 2},
                {"ability": "dex", "value": 1},
            ],
            "traits": [
                {"name": "Darkvision"},
                {"index": "fey-ancestry"},
            ],
        }

        service = CharacterCreationService(
            self.char_repo, self.class_repo, self.location_repo, open5e_client=client
        )
        races = service.list_races()

        half_elf = next(r for r in races if r.name == "Half-Elf")
        self.assertEqual({"CHA": 2, "DEX": 1}, half_elf.bonuses)
        self.assertIn("Darkvision", half_elf.traits)
        self.assertIn("fey-ancestry", half_elf.traits)
        self.assertIn("half-elf", client.get_calls)

    def test_falls_back_to_defaults_when_client_fails(self) -> None:
        client = _FakeRaceClient(pages={}, should_raise=True)

        service = CharacterCreationService(
            self.char_repo, self.class_repo, self.location_repo, open5e_client=client
        )
        races = service.list_races()

        names = {race.name for race in races}
        self.assertIn("Human", names)
        self.assertIn("Elf", names)
        self.assertTrue(client.closed)
        self.assertEqual([], client.calls)

    def test_provides_race_background_and_difficulty_option_labels(self) -> None:
        class_repo = _FakeClassRepo(
            [
                CharacterClass(
                    id=1,
                    name="Fighter",
                    slug="fighter",
                    hit_die="d10",
                    primary_ability="strength",
                    base_attributes={"STR": 15, "CON": 14, "DEX": 12},
                )
            ]
        )
        service = CharacterCreationService(
            self.char_repo, class_repo, self.location_repo, open5e_client=None
        )

        race_labels = service.race_option_labels()
        background_labels = service.background_option_labels()
        difficulty_labels = service.difficulty_option_labels()
        class_names = service.list_class_names()

        self.assertTrue(any("Speed" in label for label in race_labels))
        self.assertTrue(any("|" in label for label in background_labels))
        self.assertTrue(any("|" in label for label in difficulty_labels))
        self.assertEqual(["Fighter"], class_names)

    def test_builds_class_detail_view_payload(self) -> None:
        class_repo = _FakeClassRepo(
            [
                CharacterClass(
                    id=2,
                    name="Wizard",
                    slug="wizard",
                    hit_die="d6",
                    primary_ability="intelligence",
                    base_attributes={"INT": 16, "DEX": 12, "CON": 12},
                )
            ]
        )
        service = CharacterCreationService(
            self.char_repo, class_repo, self.location_repo, open5e_client=None
        )
        wizard = class_repo.list_playable()[0]

        detail = service.class_detail_view(wizard)

        self.assertEqual("Class: Wizard", detail.title)
        self.assertIn("Fragile scholar", detail.description)
        self.assertEqual("intelligence", detail.primary_ability)
        self.assertEqual("d6", detail.hit_die)
        self.assertIn("AC", detail.combat_profile_line)
        self.assertIn("INT 16", detail.recommended_line)
        self.assertEqual(["Choose this class", "Back"], detail.options)

    def test_loads_creation_reference_categories_from_generic_endpoint(self) -> None:
        class_repo = _FakeClassRepo(
            [
                CharacterClass(
                    id=1,
                    name="Fighter",
                    slug="fighter",
                    hit_die="d10",
                    primary_ability="strength",
                    base_attributes={"STR": 15},
                )
            ]
        )
        client = _FakeCatalogClient(
            pages={1: {"results": [], "next": None}},
            endpoint_payloads={
                ("spells", 1): {"results": [{"name": "Fire Bolt"}, {"name": "Mage Hand"}]},
                ("equipment", 1): {"results": [{"name": "Longsword"}, {"name": "Shield"}]},
                ("classes", 1): {"results": [{"name": "Wizard"}, {"name": "Rogue"}]},
            },
        )

        service = CharacterCreationService(
            self.char_repo,
            class_repo,
            self.location_repo,
            open5e_client=client,
        )

        categories = service.list_creation_reference_categories()
        self.assertIn("Spells", categories)
        self.assertIn("Equipment", categories)

        spells = service.list_creation_reference_items("spells")
        equipment = service.list_creation_reference_items("equipment")
        classes = service.list_creation_reference_items("classes")

        self.assertIn("Fire Bolt", spells)
        self.assertIn("Longsword", equipment)
        self.assertIn("Wizard", classes)

    def test_reference_categories_fall_back_to_defaults_when_unavailable(self) -> None:
        class_repo = _FakeClassRepo(
            [
                CharacterClass(
                    id=1,
                    name="Fighter",
                    slug="fighter",
                    hit_die="d10",
                    primary_ability="strength",
                    base_attributes={"STR": 15},
                )
            ]
        )
        service = CharacterCreationService(
            self.char_repo,
            class_repo,
            self.location_repo,
            open5e_client=None,
        )

        self.assertIn("Human", service.list_creation_reference_items("races"))
        self.assertIn("Fighter", service.list_creation_reference_items("classes"))

    def test_lists_default_subraces_for_selected_race(self) -> None:
        service = CharacterCreationService(
            self.char_repo,
            self.class_repo,
            self.location_repo,
            open5e_client=None,
        )

        elf_subraces = service.list_subraces_for_race(race_name="Elf")
        names = [row.name for row in elf_subraces]
        self.assertIn("Wood Elf", names)
        self.assertIn("Dark Elf", names)
        self.assertIn("Black", [row.name for row in service.list_subraces_for_race(race_name="Dragonborn")])

    def test_lists_custom_dragonborn_lineages(self) -> None:
        service = CharacterCreationService(
            self.char_repo,
            self.class_repo,
            self.location_repo,
            open5e_client=None,
        )

        race_names = [row.name for row in service.list_races()]
        self.assertIn("Dragonborn", race_names)

        lineages = service.list_subraces_for_race(race_name="Dragonborn")
        lineage_names = [row.name for row in lineages]
        self.assertIn("Black", lineage_names)
        self.assertIn("Blue", lineage_names)
        self.assertIn("Gold", lineage_names)

    def test_dragonborn_lineage_alignment_mapping(self) -> None:
        service = CharacterCreationService(
            self.char_repo,
            self.class_repo,
            self.location_repo,
            open5e_client=None,
        )

        lineages = {row.name: row for row in service.list_subraces_for_race(race_name="Dragonborn")}
        expected = {
            "Black": "Alignment: Evil",
            "Blue": "Alignment: Evil",
            "Brass": "Alignment: Good",
            "Bronze": "Alignment: Good",
            "Copper": "Alignment: Good",
            "Gold": "Alignment: Good",
            "Green": "Alignment: Evil",
            "Red": "Alignment: Evil",
            "Silver": "Alignment: Good",
            "White": "Alignment: Evil",
        }
        self.assertEqual(set(expected.keys()), set(lineages.keys()))
        for lineage, alignment in expected.items():
            self.assertIn(alignment, lineages[lineage].traits)

    def test_applies_selected_subrace_to_created_character(self) -> None:
        class_repo = _FakeClassRepo(
            [
                CharacterClass(
                    id=1,
                    name="Fighter",
                    slug="fighter",
                    hit_die="d10",
                    primary_ability="strength",
                    base_attributes={"STR": 15},
                )
            ]
        )
        char_repo = _FakeCharacterRepo()
        service = CharacterCreationService(
            char_repo,
            class_repo,
            _FakeLocationRepo(),
            open5e_client=None,
        )

        elf = next(r for r in service.list_races() if r.name == "Elf")
        wood_elf = next(s for s in service.list_subraces_for_race(race=elf) if s.name == "Wood Elf")

        created = service.create_character(
            name="Lia",
            class_index=0,
            ability_scores={"STR": 10, "DEX": 12, "CON": 11, "INT": 10, "WIS": 10, "CHA": 10},
            race=elf,
            subrace=wood_elf,
        )

        self.assertEqual("Elf (Wood Elf)", created.race)
        self.assertEqual(35, created.speed)
        self.assertIn("Keen Senses", created.race_traits)
        self.assertIn("Mask of the Wild", created.race_traits)
        self.assertEqual(14, created.attributes["dexterity"])
        self.assertEqual(11, created.attributes["wisdom"])


if __name__ == "__main__":
    unittest.main()
