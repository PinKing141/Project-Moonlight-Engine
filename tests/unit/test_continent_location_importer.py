import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.world_import.continent_location_importer import (  # noqa: E402
    render_faction_flavour_module,
    render_inmemory_module,
    render_sql_seed,
    select_locations,
)


class ContinentLocationImporterTests(unittest.TestCase):
    def test_select_locations_keeps_capitals_and_major_towns(self) -> None:
        burg_rows = [
            {
                "Id": "1",
                "Burg": "Irewick",
                "State": "Grirongria",
                "Group": "capital",
                "Population": "28002",
                "Capital": "capital",
                "X": "439.15",
                "Y": "319.55",
                "Temperature likeness": "Milan (Italy)",
                "Culture": "Dail (Human)",
                "Religion": "Neverchism",
            },
            {
                "Id": "2",
                "Burg": "Ortarith",
                "State": "Ortarith",
                "Group": "city",
                "Population": "43865",
                "Capital": "capital",
                "X": "1054.27",
                "Y": "488.7",
                "Temperature likeness": "Marrakesh (Morocco)",
                "Culture": "Lothian (Dark Elfish)",
                "Religion": "Witnesses of Elloragh",
            },
            {
                "Id": "3",
                "Burg": "Minorham",
                "State": "Ortarith",
                "Group": "town",
                "Population": "1200",
                "Capital": "",
                "X": "700.0",
                "Y": "500.0",
                "Temperature likeness": "London (England)",
                "Culture": "Lothian (Dark Elfish)",
                "Religion": "Witnesses of Elloragh",
            },
        ]
        state_rows = [
            {"State": "Grirongria", "Full Name": "Duchy of Grirongria"},
            {"State": "Ortarith", "Full Name": "Duchy of Ortarith"},
        ]
        military_rows = [
            {"State": "Grirongria", "War Alert": "5"},
            {"State": "Ortarith", "War Alert": "2.38"},
        ]

        locations = select_locations(
            burg_rows=burg_rows,
            state_rows=state_rows,
            military_rows=military_rows,
            continent_name="Taklamakan",
            location_id_offset=1000,
            major_town_min_population=5000,
            max_major_towns_per_state=8,
        )

        self.assertEqual(2, len(locations))
        self.assertEqual("Irewick", locations[0].name)
        self.assertEqual(1001, locations[0].location_id)
        self.assertEqual("warfront", locations[0].hazard_profile_key)
        self.assertEqual("Ortarith", locations[1].name)
        self.assertEqual("contested", locations[1].hazard_profile_key)

    def test_render_outputs_include_seed_and_inmemory_records(self) -> None:
        locations = select_locations(
            burg_rows=[
                {
                    "Id": "11",
                    "Burg": "Yepeli",
                    "State": "Sazyurt",
                    "Group": "capital",
                    "Population": "13842",
                    "Capital": "capital",
                    "X": "996.25",
                    "Y": "212.56",
                    "Temperature likeness": "Copenhagen (Denmark)",
                    "Culture": "Rohand (Human)",
                    "Religion": "Blasphemy of the Blond Spirit",
                }
            ],
            state_rows=[{"State": "Sazyurt", "Full Name": "Republic of Sazyurt"}],
            military_rows=[{"State": "Sazyurt", "War Alert": "0.65"}],
            continent_name="Taklamakan",
            location_id_offset=1000,
            major_town_min_population=5000,
            max_major_towns_per_state=8,
        )

        sql = render_sql_seed(locations, continent_name="Taklamakan")
        py_module = render_inmemory_module(locations, continent_name="Taklamakan")

        self.assertIn("INSERT INTO place", sql)
        self.assertIn("Yepeli", sql)
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertIn("culture_raw:Rohand (Human)", sql)

        self.assertIn("GENERATED_LOCATIONS", py_module)
        self.assertIn("1011", py_module)
        self.assertIn("HazardProfile", py_module)
        self.assertIn("culture:rohand_(human)", py_module)

    def test_render_faction_flavour_module_includes_culture_descriptions(self) -> None:
        module_text = render_faction_flavour_module(
            [
                {
                    "State": "Ortarith",
                    "Full Name": "Duchy of Ortarith",
                    "Form": "Duchy",
                    "Culture": "Lothian (Dark Elfish)",
                }
            ]
        )

        self.assertIn("FACTION_DESCRIPTION_OVERRIDES", module_text)
        self.assertIn("duchy_of_ortarith", module_text)
        self.assertIn("Lothian (Dark Elfish)", module_text)


if __name__ == "__main__":
    unittest.main()
