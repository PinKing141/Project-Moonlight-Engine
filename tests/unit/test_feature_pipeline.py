import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.character_creation_service import CharacterCreationService
from rpg.application.services.combat_service import CombatService
from rpg.domain.events import CombatFeatureTriggered
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.feature import Feature
from rpg.infrastructure.inmemory.inmemory_character_repo import InMemoryCharacterRepository
from rpg.infrastructure.inmemory.inmemory_class_repo import InMemoryClassRepository
from rpg.infrastructure.inmemory.inmemory_feature_repo import InMemoryFeatureRepository
from rpg.infrastructure.inmemory.inmemory_location_repo import InMemoryLocationRepository


class FeaturePipelineTests(unittest.TestCase):
    def test_db_backed_feature_applies_bonus_damage_and_publishes_event(self) -> None:
        repo = InMemoryFeatureRepository(
            {
                "feature.sneak_attack": Feature(
                    id=1,
                    slug="feature.sneak_attack",
                    name="Sneak Attack",
                    trigger_key="on_attack_hit",
                    effect_kind="bonus_damage",
                    effect_value=10,
                )
            }
        )
        hero = Character(id=11, name="Shade", class_name="rogue", hp_current=12, hp_max=12)
        hero.attributes["dexterity"] = 10
        self.assertIsNotNone(hero.id)
        hero_id = int(hero.id or 0)
        repo.grant_feature_by_slug(hero_id, "feature.sneak_attack")

        enemy = Entity(id=22, name="Guard", level=1, hp=8, hp_current=8, hp_max=8, armour_class=1, attack_min=2, attack_max=2)

        published: list[object] = []
        service = CombatService(feature_repo=repo, event_publisher=published.append)
        service.set_seed(7)

        def choose_attack(options, _player, _enemy, _round_no, _scene):
            return "Attack"

        result = service.fight_turn_based(hero, enemy, choose_attack)

        self.assertTrue(result.player_won)
        self.assertTrue(any(isinstance(evt, CombatFeatureTriggered) for evt in published))
        trigger = next(evt for evt in published if isinstance(evt, CombatFeatureTriggered))
        self.assertEqual("feature.sneak_attack", trigger.feature_slug)
        self.assertEqual("on_attack_hit", trigger.trigger_key)
        self.assertEqual("bonus_damage", trigger.effect_kind)

    def test_character_creation_grants_race_feature_from_db_backed_repo(self) -> None:
        feature_repo = InMemoryFeatureRepository(
            {
                "feature.darkvision": Feature(
                    id=2,
                    slug="feature.darkvision",
                    name="Darkvision",
                    trigger_key="on_initiative",
                    effect_kind="initiative_bonus",
                    effect_value=2,
                )
            }
        )
        char_repo = InMemoryCharacterRepository()
        class_repo = InMemoryClassRepository()
        location_repo = InMemoryLocationRepository()

        creation = CharacterCreationService(
            char_repo,
            class_repo,
            location_repo,
            feature_repo=feature_repo,
        )
        dwarf = next(race for race in creation.list_races() if race.name.lower() == "dwarf")

        created = creation.create_character(name="", class_index=0, race=dwarf)
        granted = feature_repo.list_for_character(created.id)

        self.assertTrue(any(feature.slug == "feature.darkvision" for feature in granted))

    def test_generic_attack_roll_feature_strategy_increases_hit_rate(self) -> None:
        feature_repo = InMemoryFeatureRepository(
            {
                "feature.martial_precision": Feature(
                    id=3,
                    slug="feature.martial_precision",
                    name="Martial Precision",
                    trigger_key="on_attack_roll",
                    effect_kind="attack_bonus",
                    effect_value=100,
                )
            }
        )
        hero = Character(id=31, name="Varr", class_name="fighter", hp_current=12, hp_max=12)
        hero.attributes["strength"] = 10
        feature_repo.grant_feature_by_slug(int(hero.id or 0), "feature.martial_precision")

        enemy = Entity(id=32, name="Veteran", level=1, hp=6, hp_current=6, hp_max=6, armour_class=20, attack_min=0, attack_max=0)
        service = CombatService(feature_repo=feature_repo)
        service.set_seed(3)

        def choose_attack(options, _player, _enemy, _round_no, _scene):
            return "Attack"

        result = service.fight_turn_based(hero, enemy, choose_attack)

        self.assertTrue(result.player_won)


if __name__ == "__main__":
    unittest.main()
