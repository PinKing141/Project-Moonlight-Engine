import asyncio
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.presentation import rolling_ui


class RollingUiAnimationTests(unittest.TestCase):
    def test_sync_wrapper_delegates_to_async_animation_once(self) -> None:
        with mock.patch.object(rolling_ui, "_animate_stat_roll_async", new_callable=mock.AsyncMock) as async_animator:
            rolling_ui._animate_stat_roll("STR", 14, [6, 4, 3, 1], rng=None)

        async_animator.assert_awaited_once()

    def test_async_animation_prompts_once_after_final_render(self) -> None:
        with mock.patch.object(rolling_ui, "clear_screen", lambda: None), mock.patch.object(
            rolling_ui, "_render_roll_panel", lambda *args, **kwargs: None
        ), mock.patch.object(rolling_ui, "_prompt_continue") as prompt_mock, mock.patch(
            "rpg.presentation.rolling_ui.asyncio.sleep", new=mock.AsyncMock()
        ):
            asyncio.run(rolling_ui._animate_stat_roll_async("DEX", 12, [5, 4, 2, 1], rng=None))

        prompt_mock.assert_called_once_with("Press ENTER to continue...")


if __name__ == "__main__":
    unittest.main()
