import unittest

from rpg.presentation.live_game_loop import CombatState, ExplorationState, RootState, _music_context_for_state


class LiveGameLoopMusicContextTests(unittest.TestCase):
    def test_combat_state_maps_to_combat_context(self) -> None:
        self.assertEqual("combat", _music_context_for_state(CombatState(player=object(), enemies=[], scene={})))

    def test_non_combat_states_map_to_exploration_context(self) -> None:
        self.assertEqual("exploration", _music_context_for_state(ExplorationState()))
        self.assertEqual("exploration", _music_context_for_state(RootState()))


if __name__ == "__main__":
    unittest.main()
