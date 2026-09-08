"""Unit tests for framework-free preflight report presentation data."""

import unittest

from services.preflight_reporting import (
    preflight_report_context,
    preflight_report_download_rows,
)
from validation.models import ValidationError, ValidationReport


class PreflightReportContextTest(unittest.TestCase):
    def test_groups_stable_findings_by_template_row_and_column(self):
        report = ValidationReport()
        report.add(
            ValidationError(
                rule_id="field_sample.second",
                message="Second issue.",
                template_row=12,
                template_column="Primary sampling method",
                template_column_number=42,
                value="Unknown method",
                value_label="Selected primary sampling method",
            )
        )
        report.add(
            ValidationError(
                rule_id="field_sample.first",
                message="First issue.",
                template_row=11,
                template_column="Template version",
            )
        )
        report.add(
            ValidationError(
                rule_id="field_sample.warning",
                message="Warning issue.",
                template_row=12,
                template_column="Primary sampling method",
                severity="warning",
            )
        )

        context = preflight_report_context(report)

        self.assertEqual(context["error_count"], 2)
        self.assertEqual(context["warning_count"], 1)
        self.assertEqual(context["finding_count"], 3)
        self.assertEqual(
            [group["template_row"] for group in context["row_groups"]],
            [11, 12],
        )
        row_12_columns = context["row_groups"][1]["column_groups"]
        self.assertEqual(row_12_columns[0]["template_column"], "Primary sampling method")
        self.assertEqual(row_12_columns[0]["template_column_number"], 42)
        self.assertEqual(
            [finding["rule_id"] for finding in row_12_columns[0]["findings"]],
            ["field_sample.second", "field_sample.warning"],
        )

    def test_rejects_a_non_report_input(self):
        with self.assertRaises(TypeError):
            preflight_report_context({})

    def test_download_rows_exclude_values_and_user_entered_messages(self):
        report = ValidationReport()
        report.add(
            ValidationError(
                rule_id="field_sample.primary_sampling_method_not_allowed",
                message="Primary sampling method (private entered value) is invalid.",
                template_row=11,
                template_column="Primary sampling method",
                database_column="primary_sampling_method",
                template_column_number=42,
                value="private entered value",
            )
        )

        rows = preflight_report_download_rows(report)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rule_id"], "field_sample.primary_sampling_method_not_allowed")
        self.assertNotIn("value", rows[0])
        self.assertNotIn("message", rows[0])
        self.assertEqual(rows[0]["template_column_number"], 42)
