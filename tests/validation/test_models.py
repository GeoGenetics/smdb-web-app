"""Unit tests for framework-independent validation-report models."""

import json
import unittest

from validation.models import ValidationError, ValidationReport


class ValidationModelsImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from validation import models

        self.assertIsNotNone(models)


class ValidationModelsConstructionTest(unittest.TestCase):
    def test_report_accepts_a_user_actionable_error(self):
        finding = ValidationError(
            rule_id="field_sample.template_version_required",
            message="Template version is required.",
            template_row=11,
            template_column="Template version",
            database_column="template_version",
        )
        report = ValidationReport()

        report.add(finding)

        self.assertTrue(report.has_errors)
        self.assertEqual(report.errors, (finding,))

    def test_error_rejects_an_unknown_severity(self):
        with self.assertRaises(ValueError):
            ValidationError(
                rule_id="field_sample.example",
                message="Example message.",
                severity="notice",
            )


class ValidationReportContractTest(unittest.TestCase):
    @staticmethod
    def finding(*, rule_id, row=None, column=None, severity="error", value=None):
        return ValidationError(
            rule_id=rule_id,
            message=f"Message for {rule_id}.",
            template_row=row,
            template_column=column,
            database_column="database_column" if column else None,
            severity=severity,
            value=value,
        )

    def test_empty_report_has_no_findings_or_errors(self):
        report = ValidationReport()

        self.assertEqual(report.findings, ())
        self.assertEqual(report.errors, ())
        self.assertEqual(report.warnings, ())
        self.assertFalse(report.has_errors)
        self.assertEqual(report.group_by_row(), {})
        self.assertEqual(
            report.to_dict(),
            {
                "findings": [],
                "error_count": 0,
                "warning_count": 0,
                "has_errors": False,
            },
        )

    def test_findings_have_deterministic_row_and_column_order(self):
        row_11_b = self.finding(
            rule_id="field_sample.b", row=11, column="B column"
        )
        global_finding = self.finding(rule_id="field_sample.global")
        row_10 = self.finding(rule_id="field_sample.z", row=10, column="Z column")
        row_11_a = self.finding(
            rule_id="field_sample.a", row=11, column="A column"
        )
        report = ValidationReport()

        for finding in (row_11_b, global_finding, row_10, row_11_a):
            report.add(finding)

        self.assertEqual(
            report.findings,
            (row_10, row_11_a, row_11_b, global_finding),
        )

    def test_warning_only_report_does_not_block_an_upload(self):
        warning = self.finding(
            rule_id="field_sample.other_values_missing",
            row=11,
            column="Other values",
            severity="warning",
        )
        report = ValidationReport()
        report.add(warning)

        self.assertFalse(report.has_errors)
        self.assertEqual(report.errors, ())
        self.assertEqual(report.warnings, (warning,))

    def test_merge_adds_findings_without_mutating_the_source_report(self):
        target_finding = self.finding(rule_id="field_sample.target", row=11)
        source_finding = self.finding(rule_id="field_sample.source", row=12)
        target = ValidationReport()
        source = ValidationReport()
        target.add(target_finding)
        source.add(source_finding)

        returned_report = target.merge(source)

        self.assertIs(returned_report, target)
        self.assertEqual(target.findings, (target_finding, source_finding))
        self.assertEqual(source.findings, (source_finding,))

    def test_group_by_row_keeps_row_and_finding_order_stable(self):
        row_12 = self.finding(rule_id="field_sample.row_12", row=12, column="C")
        row_11_b = self.finding(rule_id="field_sample.row_11_b", row=11, column="B")
        row_11_a = self.finding(rule_id="field_sample.row_11_a", row=11, column="A")
        global_finding = self.finding(rule_id="field_sample.global")
        report = ValidationReport()

        for finding in (row_12, row_11_b, global_finding, row_11_a):
            report.add(finding)

        self.assertEqual(
            report.group_by_row(),
            {
                11: (row_11_a, row_11_b),
                12: (row_12,),
                None: (global_finding,),
            },
        )

    def test_serialization_uses_display_values_and_json_scalars(self):
        finding = self.finding(
            rule_id="field_sample.invalid_value",
            row=11,
            column="Primary sampling method",
            value="Not an approved method",
        )
        report = ValidationReport()
        report.add(finding)

        serialized = report.to_dict()

        self.assertEqual(serialized["error_count"], 1)
        self.assertEqual(serialized["warning_count"], 0)
        self.assertTrue(serialized["has_errors"])
        self.assertEqual(serialized["findings"][0]["value"], "Not an approved method")
        self.assertEqual(
            json.loads(json.dumps(serialized))["findings"][0]["rule_id"],
            "field_sample.invalid_value",
        )
