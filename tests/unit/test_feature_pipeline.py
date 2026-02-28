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

    def test_combat_round_counter_advances_without_shield_flags(self) -> None:
        hero = Character(id=41, name="Ari", class_name="fighter", hp_current=40, hp_max=40)
        hero.armour_class = 25
        hero.attack_bonus = 0
        hero.attack_min = 1
        hero.attack_max = 1

        enemy = Entity(
            id=42,
            name="Dummy",
            level=1,
            hp=200,
            hp_current=200,
            hp_max=200,
            armour_class=25,
            attack_min=1,
            attack_max=1,
            attack_bonus=0,
            damage_die="d4",
        )

        service = CombatService()
        service.set_seed(11)
        seen_rounds: list[int] = []

        def choose_dodge(_options, _player, _enemy, _round_no, _scene):
            seen_rounds.append(int(_round_no))
            return "Dodge"

        service.fight_turn_based(hero, enemy, choose_dodge)

        self.assertIn(2, seen_rounds)

    def test_combat_does_not_mutate_original_inventory_on_copied_state(self) -> None:
        hero = Character(id=51, name="Mira", class_name="fighter", hp_current=14, hp_max=20)
        hero.attributes["strength"] = 32
        hero.inventory = ["Healing Potion"]

        enemy = Entity(
            id=52,
            name="Raider",
            level=1,
            hp=40,
            hp_current=40,
            hp_max=40,
            armour_class=15,
            attack_min=1,
            attack_max=1,
            attack_bonus=0,
            damage_die="d4",
        )

        service = CombatService()
        service.set_seed(13)

        def choose_action(_options, _player, _enemy, round_no, _scene):
            if round_no == 1:
                return ("Use Item", "Healing Potion")
            return "Flee"

        result = service.fight_turn_based(hero, enemy, choose_action)
        self.assertTrue(result.fled)
        self.assertIn("Healing Potion", hero.inventory)

    def test_shield_temp_bonus_is_cleared_on_flee_exit(self) -> None:
        hero = Character(id=61, name="Aerin", class_name="wizard", hp_current=16, hp_max=16)
        hero.attributes["strength"] = 32
        hero.known_spells = ["Shield"]
        hero.spell_slots_max = 1
        hero.spell_slots_current = 1

        enemy = Entity(
            id=62,
            name="Sentinel",
            level=1,
            hp=50,
            hp_current=50,
            hp_max=50,
            armour_class=16,
            attack_min=1,
            attack_max=1,
            attack_bonus=0,
            damage_die="d4",
        )

        service = CombatService()
        service.set_seed(21)

        def choose_action(options, _player, _enemy, round_no, _scene):
            if round_no == 1 and "Cast Spell" in options:
                return ("Cast Spell", "shield")
            return "Flee"

        result = service.fight_turn_based(hero, enemy, choose_action)

        self.assertTrue(result.fled)
        self.assertNotIn("temp_ac_bonus", result.player.flags)
        self.assertNotIn("shield_rounds", result.player.flags)

    def test_status_burning_ticks_and_expires(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(4)
        hero = Character(id=71, name="Rhea", class_name="fighter", hp_current=20, hp_max=20)
        log = []

        service._apply_status(actor=hero, status_id="burning", rounds=1, potency=1, log=log, source_name="Test")
        service._apply_start_turn_statuses(hero, log)
        service._tick_actor_statuses_end_turn(hero, log)

        self.assertLess(hero.hp_current, 20)
        self.assertFalse(service._has_status(hero, "burning"))

    def test_stunned_actor_loses_turn_in_party_combat(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(9)

        stunned_ally = Character(id=81, name="Ari", class_name="fighter", hp_current=18, hp_max=18)
        stunned_ally.flags = {"combat_statuses": [{"id": "stunned", "rounds": 1, "potency": 1}]}
        stunned_ally.attributes["strength"] = 18

        enemy = Entity(id=82, name="Bandit", level=1, hp=12, hp_current=12, hp_max=12, armour_class=10, attack_bonus=0, damage_die="d4")

        action_calls = {"count": 0}

        def choose_action(options, _player, _enemy, _round_no, _scene):
            action_calls["count"] += 1
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_party_turn_based([stunned_ally], [enemy], choose_action)

        self.assertTrue(any("stunned and loses the turn" in row.text.lower() for row in result.log))
        self.assertNotIn("combat_statuses", getattr(result.allies[0], "flags", {}))

    def test_paralysed_actor_loses_turn_in_party_combat(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(9)

        ally = Character(id=91, name="Bex", class_name="fighter", hp_current=18, hp_max=18)
        ally.flags = {"combat_statuses": [{"id": "paralysed", "rounds": 1, "potency": 1}]}
        ally.attributes["strength"] = 18

        enemy = Entity(id=92, name="Bandit", level=1, hp=12, hp_current=12, hp_max=12, armour_class=10, attack_bonus=0, damage_die="d4")

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_party_turn_based([ally], [enemy], choose_action)

        self.assertTrue(any("incapacitated and loses the turn" in row.text.lower() for row in result.log))

    def test_restrained_actor_cannot_dash_or_flee(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(3)

        hero = Character(id=101, name="Kite", class_name="rogue", hp_current=16, hp_max=16)
        hero.flags = {"combat_statuses": [{"id": "restrained", "rounds": 2, "potency": 1}]}
        hero.attributes["dexterity"] = 16

        enemy = Entity(id=102, name="Sentry", level=1, hp=30, hp_current=30, hp_max=30, armour_class=12, attack_bonus=0, damage_die="d4")

        def choose_action(_options, _player, _enemy, round_no, _scene):
            if round_no == 1:
                return "Dash"
            return "Flee"

        result = service.fight_turn_based(hero, enemy, choose_action)

        self.assertTrue(any("cannot dash" in row.text.lower() for row in result.log))
        self.assertTrue(any("cannot flee" in row.text.lower() for row in result.log))

    def test_exhaustion_six_causes_collapse(self) -> None:
        service = CombatService(verbosity="compact")
        hero = Character(id=111, name="Lio", class_name="fighter", hp_current=20, hp_max=20)
        hero.flags = {"combat_statuses": [{"id": "exhaustion", "rounds": 2, "potency": 6}]}
        log = []

        service._apply_start_turn_statuses(hero, log)

        self.assertEqual(0, hero.hp_current)
        self.assertTrue(any("collapses from exhaustion" in row.text.lower() for row in log))

    def test_condition_feature_applies_status_with_duration(self) -> None:
        repo = InMemoryFeatureRepository(
            {
                "feature.snare_strike": Feature(
                    id=12,
                    slug="feature.snare_strike",
                    name="Snare Strike",
                    trigger_key="on_attack_hit",
                    effect_kind="condition_restrained",
                    effect_value=2,
                )
            }
        )
        hero = Character(id=121, name="Shade", class_name="rogue", hp_current=12, hp_max=12)
        hero.attributes["dexterity"] = 16
        repo.grant_feature_by_slug(int(hero.id or 0), "feature.snare_strike")

        enemy = Entity(id=122, name="Guard", level=1, hp=40, hp_current=40, hp_max=40, armour_class=1, attack_min=1, attack_max=1)
        service = CombatService(feature_repo=repo, verbosity="compact")
        service.set_seed(5)

        def choose_action(_options, _player, _enemy, round_no, _scene):
            return "Attack"

        result = service.fight_turn_based(hero, enemy, choose_action)

        self.assertTrue(any("is now Restrained (2 rounds)" in row.text for row in result.log))

    def test_weather_rain_disadvantages_ranged_attackers(self) -> None:
        service = CombatService(verbosity="compact")
        ranged_actor = Character(id=131, name="Iri", class_name="wizard", hp_current=12, hp_max=12)
        melee_actor = Character(id=132, name="Brakk", class_name="fighter", hp_current=12, hp_max=12)

        self.assertEqual(
            "disadvantage",
            service._weather_attack_advantage(weather="rain", attacker=ranged_actor, action="attack"),
        )
        self.assertIsNone(service._weather_attack_advantage(weather="rain", attacker=melee_actor, action="attack"))

    def test_weather_rain_logs_ranged_attack_disadvantage(self) -> None:
        service = CombatService(verbosity="compact")
        service.set_seed(17)

        hero = Character(id=141, name="Lyra", class_name="wizard", hp_current=14, hp_max=14)
        enemy = Entity(id=142, name="Bandit", level=1, hp=12, hp_current=12, hp_max=12, armour_class=12, damage_die="d4")

        def choose_action(options, _player, _enemy, _round_no, _scene):
            return "Attack" if "Attack" in options else options[0]

        result = service.fight_turn_based(
            hero,
            enemy,
            choose_action,
            scene={"distance": "engaged", "terrain": "open", "surprise": "none", "weather": "Rain"},
        )

        self.assertTrue(any("disadvantage on your ranged attack" in row.text.lower() for row in result.log))


if __name__ == "__main__":
    unittest.main()
