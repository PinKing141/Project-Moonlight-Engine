import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application import dtos
from rpg.application.contract import (
    COMMAND_INTENTS,
    CONTRACT_DTO_TYPES,
    CONTRACT_VERSION,
    QUERY_INTENTS,
)
from rpg.application.services.game_service import GameService


class ApplicationContractTests(unittest.TestCase):
    def test_contract_version_uses_semver(self) -> None:
        self.assertRegex(CONTRACT_VERSION, r"^\d+\.\d+\.\d+$")

    def test_game_service_implements_declared_command_and_query_intents(self) -> None:
        for name in COMMAND_INTENTS + QUERY_INTENTS:
            self.assertTrue(hasattr(GameService, name), f"Missing contract intent: {name}")

    def test_declared_dto_types_exist(self) -> None:
        for dto_name in CONTRACT_DTO_TYPES:
            self.assertTrue(hasattr(dtos, dto_name), f"Missing contract DTO: {dto_name}")


if __name__ == "__main__":
    unittest.main()
