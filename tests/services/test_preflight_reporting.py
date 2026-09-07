"""Unit tests for framework-free preflight report presentation data."""

import unittest

from services.preflight_reporting import preflight_report_context
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
                value="Unknown method",
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
        self.assertEqual(
            [finding["rule_id"] for finding in row_12_columns[0]["findings"]],
            ["field_sample.second", "field_sample.warning"],
        )

    def test_rejects_a_non_report_input(self):
        with self.assertRaises(TypeError):
            preflight_report_context({})
