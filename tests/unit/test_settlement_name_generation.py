import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.settlement_naming import generate_settlement_name
from rpg.application.services.settlement_layering import generate_town_layer_tags
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class SettlementNameGenerationTests(unittest.TestCase):
    ELVEN_MARKERS = ("ael", "elar", "lyth", "syl", "fael", "vaer", "thael", "myr", "cael", "aer")
    DWARVEN_MARKERS = ("kar", "dur", "bar", "thor", "grim", "khaz", "drak", "brom", "dorn", "keld")
    OLD_ENGLISH_SUFFIXES = (
        "ton", "ham", "ford", "vale", "keep", "hold", "haven", "gate", "watch", "port",
        "crest", "reach", "mouth", "stead", "wick", "borough", "shire", "wall", "court", "landing",
    )

    def test_generation_is_deterministic_for_same_seed(self):
        a = generate_settlement_name(culture="human", seed=41, scale="town")
        b = generate_settlement_name(culture="human", seed=41, scale="town")
        self.assertEqual(a, b)

    def test_generation_varies_across_cultures(self):
        human = generate_settlement_name(culture="human", seed=99, scale="town")
        elven = generate_settlement_name(culture="elven", seed=99, scale="town")
        dwarven = generate_settlement_name(culture="dwarven", seed=99, scale="town")

        self.assertTrue(human.isalpha())
        self.assertTrue(elven.isalpha())
        self.assertTrue(dwarven.isalpha())
        self.assertGreaterEqual(len({human, elven, dwarven}), 2)

    def test_generation_avoids_awkward_old_english_compounds(self):
        generated = [generate_settlement_name(culture="human", seed=seed, scale="town").lower() for seed in range(1000)]
        self.assertFalse(any("passtead" in name for name in generated))
        self.assertFalse(any("crossingstead" in name for name in generated))

    def test_human_generation_blends_fantasy_and_old_english_style(self):
        generated = [generate_settlement_name(culture="human", seed=seed, scale="town").lower() for seed in range(300)]
        fantasy_markers = ("ael", "vael", "myr", "syl", "thal", "kael", "lyth", "wyn", "thiel", "delve", "spire")

        has_old_english_signal = any(name.endswith(old_suffix) for name in generated for old_suffix in self.OLD_ENGLISH_SUFFIXES)
        has_fantasy_signal = any(marker in name for name in generated for marker in fantasy_markers)

        self.assertTrue(has_old_english_signal)
        self.assertTrue(has_fantasy_signal)

    def test_elven_generation_uses_elven_rules_not_human_suffixes(self):
        generated = [generate_settlement_name(culture="elven", seed=seed, scale="town").lower() for seed in range(300)]
        has_elven_signal = any(marker in name for name in generated for marker in self.ELVEN_MARKERS)
        has_human_old_english_suffix = any(name.endswith(suffix) for name in generated for suffix in self.OLD_ENGLISH_SUFFIXES)

        self.assertTrue(has_elven_signal)
        self.assertFalse(has_human_old_english_suffix)

    def test_dwarven_generation_uses_dwarven_rules(self):
        generated = [generate_settlement_name(culture="dwarven", seed=seed, scale="town").lower() for seed in range(300)]
        has_dwarven_signal = any(marker in name for name in generated for marker in self.DWARVEN_MARKERS)

        self.assertTrue(has_dwarven_signal)

    def test_travel_destinations_use_deterministic_settlement_display_names(self):
        event_bus = EventBus()
        world_repo_a = InMemoryWorldRepository(seed=21)
        world_repo_b = InMemoryWorldRepository(seed=21)
        character_a = Character(id=1, name="Ari", location_id=1)
        character_b = Character(id=1, name="Ari", location_id=1)
        character_repo_a = InMemoryCharacterRepository({character_a.id: character_a})
        character_repo_b = InMemoryCharacterRepository({character_b.id: character_b})
        entity_repo_a = InMemoryEntityRepository([])
        entity_repo_b = InMemoryEntityRepository([])
        location_map = {
            1: Location(id=1, name="Starter Village", biome="village", tags=["town"]),
            2: Location(id=2, name="Verdant Reach", biome="forest", tags=["sylvan"]),
            3: Location(id=3, name="Stone Spine", biome="mountain", tags=["forge"]),
        }
        location_repo_a = InMemoryLocationRepository(dict(location_map))
        location_repo_b = InMemoryLocationRepository(dict(location_map))
        progression_a = WorldProgression(world_repo_a, entity_repo_a, event_bus)
        progression_b = WorldProgression(world_repo_b, entity_repo_b, event_bus)

        service_a = GameService(
            character_repo=character_repo_a,
            entity_repo=entity_repo_a,
            location_repo=location_repo_a,
            world_repo=world_repo_a,
            progression=progression_a,
        )
        service_b = GameService(
            character_repo=character_repo_b,
            entity_repo=entity_repo_b,
            location_repo=location_repo_b,
            world_repo=world_repo_b,
            progression=progression_b,
        )

        names_a = [row.name for row in service_a.get_travel_destinations_intent(character_a.id)]
        names_b = [row.name for row in service_b.get_travel_destinations_intent(character_b.id)]

        self.assertEqual(names_a, names_b)
        self.assertTrue(all(name and name.isalpha() for name in names_a))

    def test_town_layer_tags_are_deterministic_for_same_seed(self):
        first = generate_town_layer_tags(culture="human", biome="village", scale="town", seed=77)
        second = generate_town_layer_tags(culture="human", biome="village", scale="town", seed=77)
        self.assertEqual(first, second)
        self.assertTrue(first[0])
        self.assertTrue(first[1])

    def test_town_layer_tags_vary_by_culture(self):
        human = generate_town_layer_tags(culture="human", biome="village", scale="town", seed=50)
        elven = generate_town_layer_tags(culture="elven", biome="forest", scale="town", seed=50)
        dwarven = generate_town_layer_tags(culture="dwarven", biome="mountain", scale="town", seed=50)
        self.assertGreaterEqual(len({human, elven, dwarven}), 2)

    def test_town_view_includes_generated_location_name(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=21)
        character = Character(id=1, name="Ari", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Starting Town", biome="village", tags=["town"]),
            }
        )
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        town = service.get_town_view_intent(character.id)
        context = service.get_location_context_intent(character.id)

        self.assertTrue(town.location_name)
        self.assertEqual(context.current_location_name, town.location_name)
        self.assertNotEqual("Starting Town", town.location_name)

    def test_character_creation_summary_uses_generated_location_name(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=21)
        character = Character(id=1, name="Ari", location_id=1)
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Starting Town", biome="village", tags=["town"]),
            }
        )
        progression = WorldProgression(world_repo, entity_repo, event_bus)

        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )

        summary = service.build_character_creation_summary(character)
        expected = service._settlement_display_name(world_repo.load_default(), location_repo.get(1))

        self.assertEqual(expected, summary.starting_location_name)
        self.assertNotEqual("Starting Town", summary.starting_location_name)


if __name__ == "__main__":
    unittest.main()
