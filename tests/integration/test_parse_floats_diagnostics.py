"""Opt-in regression tests for legacy numeric-parser diagnostics.

The implementation is otherwise pure, but importing ``utils.parsers`` still
initializes the legacy database configuration. Keep these tests behind the
same SMDB-dev opt-in gate until that import boundary is repaired.
"""

import importlib
import os
import unittest

import pandas as pd


def integration_is_enabled():
    return (
        os.environ.get("SMDB_RUN_INTEGRATION_TESTS") == "1"
        and os.environ.get("RUN_MODE", "development").lower() == "development"
        and os.environ.get("SMDB_DB_PORT", "5433") == "5433"
    )


@unittest.skipUnless(
    integration_is_enabled(),
    "set SMDB_RUN_INTEGRATION_TESTS=1 with RUN_MODE=development and SMDB_DB_PORT=5433",
)
class ParseFloatsDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsers = importlib.import_module("utils.parsers")

    def test_reports_column_source_row_and_offending_value(self):
        sheet = pd.DataFrame(
            {"latitude": ["51.654374", "Data not collected", "52.000000"]}
        )
        source_rows = pd.Series([11, 12, 13], index=sheet.index)

        with self.assertRaisesRegex(
            ValueError,
            r'column "latitude" at spreadsheet row\(s\) \[12\].*Data not collected',
        ):
            self.parsers.parse_floats(
                sheet,
                ["latitude"],
                decimal_point=".",
                thousands_seperator="not_relevant",
                source_row_numbers=source_rows,
            )

    def test_allows_blank_optional_values(self):
        sheet = pd.DataFrame({"latitude": ["51.654374", None, ""]})
        source_rows = pd.Series([11, 12, 13], index=sheet.index)

        parsed = self.parsers.parse_floats(
            sheet,
            ["latitude"],
            decimal_point=".",
            thousands_seperator="not_relevant",
            source_row_numbers=source_rows,
        )

        self.assertEqual(parsed["latitude"].iloc[0], 51.654374)
        self.assertTrue(pd.isna(parsed["latitude"].iloc[1]))
        self.assertTrue(pd.isna(parsed["latitude"].iloc[2]))

    def test_normalizes_selected_thousands_and_decimal_separators(self):
        sheet = pd.DataFrame({"depth": ["1.234,5"]})

        parsed = self.parsers.parse_floats(
            sheet,
            ["depth"],
            decimal_point=",",
            thousands_seperator=".",
            source_row_numbers=pd.Series([11], index=sheet.index),
        )

        self.assertEqual(parsed["depth"].iloc[0], 1234.5)

    def test_allows_decimal_fraction_ending_in_zero(self):
        sheet = pd.DataFrame({"latitude": ["52.000000"]})

        parsed = self.parsers.parse_floats(
            sheet,
            ["latitude"],
            decimal_point=".",
            thousands_seperator="not_relevant",
            source_row_numbers=pd.Series([12], index=sheet.index),
        )

        self.assertEqual(parsed["latitude"].iloc[0], 52.0)
