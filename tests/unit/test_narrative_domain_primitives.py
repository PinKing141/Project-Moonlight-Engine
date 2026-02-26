import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.domain.models.faction import (
    InfluenceThreshold,
    Reputation,
    calculate_price_modifier,
    determines_aggro,
    reputation_threshold,
)
from rpg.domain.models.quest import QuestObjective, QuestObjectiveKind, is_objective_met
from rpg.domain.services.encounter_planner import plan_biome_hazards


class ReputationDomainTests(unittest.TestCase):
    def test_reputation_thresholds_map_to_expected_bands(self) -> None:
        self.assertEqual(InfluenceThreshold.HOSTILE, reputation_threshold(-15))
        self.assertEqual(InfluenceThreshold.NEUTRAL, reputation_threshold(0))
        self.assertEqual(InfluenceThreshold.FRIENDLY, reputation_threshold(14))
        self.assertEqual(InfluenceThreshold.REVERED, reputation_threshold(55))

    def test_price_modifier_uses_threshold_bands(self) -> None:
        self.assertEqual(20, calculate_price_modifier(-25))
        self.assertEqual(0, calculate_price_modifier(5))
        self.assertEqual(-10, calculate_price_modifier(11))
        self.assertEqual(-25, calculate_price_modifier(99))

    def test_aggression_logic_is_pure_and_predictable(self) -> None:
        self.assertTrue(determines_aggro("hostile", 0))
        self.assertFalse(determines_aggro("hostile", 60))
        self.assertTrue(determines_aggro("friendly", -20))

    def test_reputation_value_object_exposes_threshold(self) -> None:
        rep = Reputation(score=42)
        self.assertEqual(InfluenceThreshold.REVERED, rep.threshold)


class QuestObjectiveValidationTests(unittest.TestCase):
    def test_hunt_objective_is_met_by_progress(self) -> None:
        objective = QuestObjective(kind=QuestObjectiveKind.HUNT, target_key="kill:any", target_count=2)
        self.assertFalse(
            is_objective_met(
                objective=objective,
                inventory_state={},
                world_flags={},
                progress=1,
            )
        )
        self.assertTrue(
            is_objective_met(
                objective=objective,
                inventory_state={},
                world_flags={},
                progress=2,
            )
        )

    def test_gather_and_deliver_objectives_are_resolved_without_database(self) -> None:
        gather = QuestObjective(kind=QuestObjectiveKind.GATHER, target_key="wolf_pelt", target_count=3)
        deliver = QuestObjective(kind=QuestObjectiveKind.DELIVER, target_key="watch_supplies", target_count=1)

        self.assertTrue(
            is_objective_met(
                objective=gather,
                inventory_state={"wolf_pelt": 3},
                world_flags={},
                progress=0,
            )
        )
        self.assertTrue(
            is_objective_met(
                objective=deliver,
                inventory_state={},
                world_flags={"delivered:watch_supplies": 1},
                progress=0,
            )
        )


class BiomeHazardPlanningTests(unittest.TestCase):
    def test_biome_hazard_planning_is_deterministic_for_same_seed(self) -> None:
        hazards_a = plan_biome_hazards(biome="swamp", difficulty=3, seed=123, max_hazards=2)
        hazards_b = plan_biome_hazards(biome="swamp", difficulty=3, seed=123, max_hazards=2)
        self.assertEqual(hazards_a, hazards_b)

    def test_biome_hazard_planning_scales_with_difficulty(self) -> None:
        easier = plan_biome_hazards(biome="desert", difficulty=1, seed=9, max_hazards=3)
        harder = plan_biome_hazards(biome="desert", difficulty=5, seed=9, max_hazards=3)
        self.assertLessEqual(len(easier), len(harder))
        self.assertTrue(all(isinstance(item, str) and item for item in harder))


if __name__ == "__main__":
    unittest.main()
