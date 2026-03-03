import unittest

from rpg.domain.services.class_progression_catalog import (
    CLASS_PROGRESSION_SCHEMA_VERSION,
    CLASS_PROGRESSION_TABLES,
    ClassProgressionRow,
    gains_text_for_row,
    normalize_progression_contract,
    progression_contract_for_class,
    progression_rows_for_class,
)


class ClassProgressionCatalogTests(unittest.TestCase):
    def test_wizard_progression_has_20_levels_and_expected_milestones(self) -> None:
        rows = progression_rows_for_class("wizard")

        self.assertEqual(20, len(rows))
        self.assertEqual(1, rows[0].level)
        self.assertIn("Spellcasting", rows[0].gains)
        self.assertEqual(20, rows[-1].level)
        self.assertIn("Signature Spells", rows[-1].gains)

    def test_lookup_supports_name_and_slug_variants(self) -> None:
        from_slug = progression_rows_for_class("warlock")
        from_name = progression_rows_for_class("Warlock")
        from_spaced = progression_rows_for_class("war lock")

        self.assertEqual(from_slug, from_name)
        self.assertEqual(from_slug, from_spaced)

    def test_unknown_class_returns_empty_rows(self) -> None:
        self.assertEqual((), progression_rows_for_class("shadowblade"))

    def test_every_class_contains_required_breakpoint_rows(self) -> None:
        required_breakpoints = {1, 3, 5, 11, 17, 20}

        for class_slug in sorted(CLASS_PROGRESSION_TABLES.keys()):
            rows = progression_rows_for_class(class_slug)
            levels = {int(row.level) for row in rows}
            self.assertTrue(required_breakpoints.issubset(levels), msg=f"missing breakpoint in {class_slug}")
            for row in rows:
                self.assertTrue(tuple(row.gains), msg=f"empty gains at {class_slug} level {row.level}")

    def test_progression_contract_includes_version_and_schema_fields(self) -> None:
        payload = progression_contract_for_class("wizard")

        self.assertEqual(CLASS_PROGRESSION_SCHEMA_VERSION, payload.get("version"))
        rows = payload.get("rows", [])
        self.assertTrue(isinstance(rows, list) and rows)
        first = rows[0]
        self.assertEqual({"class_slug", "level", "gains", "resource_tags", "feature_flags"}, set(first.keys()))

    def test_normalize_progression_contract_applies_defaults_and_warns_on_unknown_flags(self) -> None:
        payload = {
            "version": CLASS_PROGRESSION_SCHEMA_VERSION,
            "rows": [
                {
                    "class_slug": "wizard",
                    "level": 21,
                    "gains": [],
                    "resource_tags": ["lr"],
                    "feature_flags": ["unknown_flag", "asi"],
                    "extra_field": "ignored",
                }
            ],
        }

        version, rows, warnings = normalize_progression_contract(payload)

        self.assertEqual(CLASS_PROGRESSION_SCHEMA_VERSION, version)
        self.assertEqual(1, len(rows))
        self.assertEqual(21, rows[0].level)
        self.assertEqual((), rows[0].gains)
        self.assertEqual(("lr",), rows[0].resource_tags)
        self.assertEqual(("asi",), rows[0].feature_flags)
        self.assertTrue(any("unsupported fields" in message.lower() for message in warnings))
        self.assertTrue(any("unknown feature flag" in message.lower() for message in warnings))

    def test_gains_text_uses_fallback_when_row_has_no_gains(self) -> None:
        row = ClassProgressionRow(level=99, gains=())

        text = gains_text_for_row(row)

        self.assertIn("Future feature", text)


if __name__ == "__main__":
    unittest.main()
