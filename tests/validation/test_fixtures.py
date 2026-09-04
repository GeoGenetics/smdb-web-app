"""Tests for synthetic field-sample unit-test fixtures."""

import unittest

from tests.validation.fixtures import (
    REFERENCE_DATA_UNAVAILABLE,
    common_reference_data,
    field_sample_row,
    invalid_age_interval_row,
    invalid_mixed_depth_row,
    missing_reference_data,
    unavailable_reference_data,
)


class FieldSampleFixtureTest(unittest.TestCase):
    def test_baseline_rows_are_independent(self):
        first = field_sample_row()
        second = field_sample_row()

        first["field_sample_id"] = "CHANGED"

        self.assertEqual(second["field_sample_id"], "TEST_FIELD_SAMPLE_001")

    def test_invalid_age_fixture_has_reversed_bounds(self):
        row = invalid_age_interval_row()

        self.assertLess(
            row["field_sample_age_estimate_oldest"],
            row["field_sample_age_estimate_youngest"],
        )

    def test_invalid_depth_fixture_has_both_depth_representations(self):
        row = invalid_mixed_depth_row()

        self.assertIsNotNone(row["field_sampling_depth_discrete"])
        self.assertIsNotNone(row["field_sampling_interval_from"])
        self.assertIsNotNone(row["field_sampling_interval_to"])

    def test_common_reference_data_is_independent_and_contains_expected_values(self):
        first = common_reference_data()
        second = common_reference_data()

        first["field_controls"] = frozenset({"Test-only value"})

        self.assertEqual(second["field_controls"], frozenset({"Yes", "No"}))
        self.assertIn("Tube sampling", second["field_sampling_methods"])

    def test_missing_reference_data_is_distinct_from_common_reference_data(self):
        reference_data = missing_reference_data()

        self.assertEqual(reference_data["field_controls"], frozenset())
        self.assertTrue(reference_data["field_sampling_methods"])

    def test_unavailable_reference_data_uses_a_distinct_sentinel(self):
        self.assertIs(unavailable_reference_data(), REFERENCE_DATA_UNAVAILABLE)
