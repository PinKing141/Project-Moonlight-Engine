import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.combat_service import CombatLogEntry, CombatService
from rpg.domain.events import ConcentrationBrokenEvent, EntityDamagedEvent
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity


class CombatConcentrationAndTacticalTests(unittest.TestCase):
    def test_concentration_starts_and_breaks_on_failed_check(self) -> None:
        service = CombatService(verbosity="compact")
        caster = Character(101, "Elara")
        caster.class_name = "wizard"
        caster.hp_current = 18
        caster.hp_max = 18
        target = Entity(102, "Raider", 1)
        target.hp = 14
        target.hp_current = 14
        target.hp_max = 14
        target.armour_class = 11
        log: list[CombatLogEntry] = []

        service._start_concentration(
            caster=caster,
            spell_slug="hex",
            spell_name="Hex",
            targets=[target],
            log=log,
            round_no=1,
        )
        self.assertIsNotNone(service._actor_concentration(caster))

        with mock.patch.object(service.rng, "randint", return_value=1):
            service._check_concentration_after_damage(
                target_actor=caster,
                source_actor=target,
                damage=12,
                log=log,
                round_no=2,
            )

        self.assertIsNone(service._actor_concentration(caster))
        self.assertTrue(any("concentration check" in row.text.lower() for row in log))
        self.assertTrue(any("hex fades" in row.text.lower() for row in log))

    def test_concentration_break_publishes_events(self) -> None:
        captured: list[object] = []
        service = CombatService(verbosity="compact", event_publisher=captured.append)
        caster = Character(201, "Mira")
        caster.class_name = "wizard"
        caster.hp_current = 16
        caster.hp_max = 16
        source = Entity(202, "Bandit", 1)
        source.hp = 10
        source.hp_current = 10
        source.hp_max = 10
        source.armour_class = 10
        log: list[CombatLogEntry] = []

        service._start_concentration(
            caster=caster,
            spell_slug="hex",
            spell_name="Hex",
            targets=[source],
            log=log,
            round_no=1,
        )

        with mock.patch.object(service.rng, "randint", return_value=1):
            service._check_concentration_after_damage(
                target_actor=caster,
                source_actor=source,
                damage=14,
                log=log,
                round_no=3,
            )

        self.assertTrue(any(isinstance(evt, EntityDamagedEvent) for evt in captured))
        self.assertTrue(any(isinstance(evt, ConcentrationBrokenEvent) for evt in captured))

    def test_cover_bonus_supports_three_quarters(self) -> None:
        service = CombatService(verbosity="compact")
        actor = Character(301, "Kora")
        actor.class_name = "rogue"
        actor.hp_current = 14
        actor.hp_max = 14

        service._set_actor_tactical_state(actor, stance="in_cover", cover="three_quarters", engaged_with=[])
        self.assertEqual(5, service._actor_cover_bonus(actor))

    def test_opportunity_attack_deals_damage(self) -> None:
        service = CombatService(verbosity="compact")
        attacker = Entity(401, "Orc", 2)
        attacker.hp = 18
        attacker.hp_current = 18
        attacker.hp_max = 18
        attacker.armour_class = 12
        attacker.attack_bonus = 6
        attacker.damage_die = "d6"
        defender = Character(402, "Rin")
        defender.class_name = "wizard"
        defender.hp_current = 20
        defender.hp_max = 20
        log: list[CombatLogEntry] = []

        with mock.patch.object(service, "_attack_roll", return_value=(True, False, 15, 21)), mock.patch.object(service, "_deal_damage", return_value=6):
            service._resolve_opportunity_attack(attacker=attacker, defender=defender, log=log, reason="cast in melee", round_no=1)

        self.assertEqual(14, defender.hp_current)
        self.assertTrue(any("opportunity attack" in row.text.lower() for row in log))

    def test_break_concentration_removes_target_effects_from_spell_source(self) -> None:
        service = CombatService(verbosity="compact")
        caster = Character(501, "Neris")
        caster.class_name = "wizard"
        caster.hp_current = 16
        caster.hp_max = 16
        target = Entity(502, "Mercenary", 2)
        target.hp = 20
        target.hp_current = 20
        target.hp_max = 20
        target.armour_class = 12
        log: list[CombatLogEntry] = []

        service._apply_status(
            actor=target,
            status_id="poisoned",
            rounds=2,
            potency=1,
            log=log,
            source_name=caster.name,
            source_actor=caster,
            source_spell="hex",
        )
        self.assertTrue(service._has_status(target, "poisoned"))

        service._start_concentration(
            caster=caster,
            spell_slug="hex",
            spell_name="Hex",
            targets=[target],
            log=log,
            round_no=1,
        )
        service._break_concentration(actor=caster, reason="test cleanup", log=log, round_no=2)

        self.assertFalse(service._has_status(target, "poisoned"))
        self.assertTrue(any("concentration ends" in row.text.lower() for row in log))

    def test_party_flanking_only_applies_when_enabled(self) -> None:
        service = CombatService(verbosity="compact")
        ally_a = Character(601, "Vera")
        ally_a.class_name = "fighter"
        ally_a.hp_current = 24
        ally_a.hp_max = 24
        ally_b = Character(602, "Garrick")
        ally_b.class_name = "rogue"
        ally_b.hp_current = 20
        ally_b.hp_max = 20
        foe = Entity(603, "Ogre", 5)
        foe.hp = 90
        foe.hp_current = 90
        foe.hp_max = 90
        foe.armour_class = 13
        foe.attack_bonus = -20
        foe.damage_die = "d4"

        attack_advantages: list[object] = []

        def _capture_attack(*args, **kwargs):
            attack_advantages.append(args[4])
            return (False, False, 1, 1)

        with mock.patch.object(service, "_attack_roll", side_effect=_capture_attack):
            service.fight_party_turn_based(
                allies=[ally_a, ally_b],
                enemies=[foe],
                choose_action=lambda options, actor, _enemy, _round, _ctx: "Attack",
                scene={"distance": "engaged", "terrain": "open", "enable_flanking": False},
                evaluate_ai_action=lambda *_args, **_kwargs: "flee",
            )

        self.assertNotIn("advantage", [str(row) for row in attack_advantages])

        attack_advantages_enabled: list[object] = []

        def _capture_attack_enabled(*args, **kwargs):
            attack_advantages_enabled.append(args[4])
            return (False, False, 1, 1)

        with mock.patch.object(service, "_attack_roll", side_effect=_capture_attack_enabled):
            service.fight_party_turn_based(
                allies=[ally_a, ally_b],
                enemies=[foe],
                choose_action=lambda options, actor, _enemy, _round, _ctx: "Attack",
                scene={"distance": "engaged", "terrain": "open", "enable_flanking": True},
                evaluate_ai_action=lambda *_args, **_kwargs: "flee",
            )

        self.assertIn("advantage", [str(row) for row in attack_advantages_enabled])

    def test_war_caster_grants_concentration_save_advantage(self) -> None:
        service = CombatService(verbosity="compact")
        caster = Character(701, "Lyra")
        caster.class_name = "wizard"
        caster.hp_current = 18
        caster.hp_max = 18
        caster.flags = {"war_caster": True}
        target = Entity(702, "Raider", 1)
        target.hp = 14
        target.hp_current = 14
        target.hp_max = 14
        log: list[CombatLogEntry] = []

        service._start_concentration(
            caster=caster,
            spell_slug="hex",
            spell_name="Hex",
            targets=[target],
            log=log,
            round_no=1,
        )

        with mock.patch.object(service.rng, "randint", side_effect=[1, 20]):
            service._check_concentration_after_damage(
                target_actor=caster,
                source_actor=target,
                damage=12,
                log=log,
                round_no=2,
            )

        self.assertIsNotNone(service._actor_concentration(caster))

    def test_alert_flag_adds_to_initiative_roll(self) -> None:
        service = CombatService(verbosity="normal")
        player = Character(801, "Kest")
        player.class_name = "fighter"
        player.hp_current = 20
        player.hp_max = 20
        player.flags = {"initiative_bonus": 5}
        enemy = Entity(802, "Bandit", 1)
        enemy.hp = 14
        enemy.hp_current = 14
        enemy.hp_max = 14
        enemy.attack_bonus = 0

        with mock.patch.object(service.rng, "randint", return_value=10):
            result = service.fight_turn_based(
                player=player,
                enemy=enemy,
                choose_action=lambda *_args, **_kwargs: "Flee",
                scene={"distance": "engaged", "terrain": "open"},
            )

        initiative_lines = [row.text for row in list(result.log or []) if "Initiative:" in str(row.text)]
        self.assertTrue(initiative_lines)
        self.assertIn("You 15", initiative_lines[0])


if __name__ == "__main__":
    unittest.main()
