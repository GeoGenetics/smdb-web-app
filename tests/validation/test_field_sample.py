"""Unit tests for the initial pure field-sample preflight rule slice."""

import unittest

from tests.validation.fixtures import common_reference_data, field_sample_row
from validation.field_sample import (
    RULE_AGE_INTERVAL_ORDER,
    RULE_DEPTH_INFERENCE_NOT_ALLOWED,
    RULE_DEPTH_INFERENCE_REQUIRED,
    RULE_DEPTH_REQUIRED,
    RULE_DEPTH_TYPES_EXCLUSIVE,
    RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID,
    RULE_FILTER_SAMPLING_NO_DEPTH,
    RULE_FIELD_CONTROL_NOT_ALLOWED,
    RULE_INTERVAL_DEPTH_ONLY,
    RULE_INTERVAL_ENDPOINTS_PAIRED,
    RULE_INTERVAL_ASCENDING,
    RULE_OTHER_VALUES_REQUIRED,
    RULE_PRIMARY_SAMPLING_METHOD_NOT_ALLOWED,
    RULE_DISCRETE_DEPTH_ONLY,
    RULE_TEMPLATE_VERSION_REQUIRED,
    RULE_WATER_DEPTH_REQUIRED,
    validate_field_sample_rows,
)
from validation.reference_data import InMemoryReferenceDataProvider


def reference_provider():
    """Return a new fixture-backed provider for each test."""
    data = common_reference_data()
    return InMemoryReferenceDataProvider(
        field_sampling_method_values=data["field_sampling_methods"],
        field_control_values=data["field_controls"],
        depth_inference_method_values=data["depth_inference_methods"],
        environment_context_pairs=data["environment_context_pairs"],
    )


class FieldSampleValidationTest(unittest.TestCase):
    def validate(self, *rows):
        return validate_field_sample_rows(rows, reference_provider())

    def test_module_imports_without_flask_or_database_access(self):
        from validation import field_sample

        self.assertIsNotNone(field_sample)

    def test_valid_baseline_row_has_no_findings(self):
        report = self.validate(field_sample_row())

        self.assertFalse(report.has_errors)
        self.assertEqual(report.findings, ())

    def test_template_version_reports_null_empty_and_whitespace(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                report = self.validate(field_sample_row(template_version=value))

                self.assertEqual(
                    [error.rule_id for error in report.errors],
                    [RULE_TEMPLATE_VERSION_REQUIRED],
                )
                self.assertEqual(report.errors[0].template_row, 11)

    def test_field_control_membership_accepts_valid_and_blank_foreign_keys(self):
        report = self.validate(
            field_sample_row(),
            field_sample_row(
                __template_row__=12,
                collected_as_field_control="",
            ),
        )

        self.assertEqual(report.findings, ())

    def test_field_control_membership_reports_an_unknown_value(self):
        report = self.validate(
            field_sample_row(
                collected_as_field_control="Maybe",
            )
        )

        self.assertEqual(
            {error.rule_id for error in report.errors},
            {RULE_FIELD_CONTROL_NOT_ALLOWED},
        )

    def test_primary_sampling_method_membership_accepts_valid_and_blank_values(self):
        report = self.validate(
            field_sample_row(),
            field_sample_row(__template_row__=12, primary_sampling_method=None),
            field_sample_row(__template_row__=13, primary_sampling_method="  "),
        )

        self.assertEqual(report.findings, ())

    def test_primary_sampling_method_membership_reports_an_unknown_value(self):
        report = self.validate(
            field_sample_row(primary_sampling_method="Unknown method")
        )

        self.assertEqual(
            [error.rule_id for error in report.errors],
            [RULE_PRIMARY_SAMPLING_METHOD_NOT_ALLOWED],
        )

    def test_age_interval_order_accepts_equal_and_skips_null_or_blank_endpoints(self):
        report = self.validate(
            field_sample_row(
                field_sample_age_estimate_oldest=1.0,
                field_sample_age_estimate_youngest=1.0,
            ),
            field_sample_row(
                __template_row__=12,
                field_sample_age_estimate_oldest=None,
            ),
            field_sample_row(
                __template_row__=13,
                field_sample_age_estimate_youngest=" ",
            ),
        )

        self.assertEqual(report.findings, ())

    def test_age_interval_order_reports_oldest_younger_than_youngest(self):
        report = self.validate(
            field_sample_row(
                field_sample_age_estimate_oldest=1.0,
                field_sample_age_estimate_youngest=2.0,
            )
        )

        self.assertEqual(
            [error.rule_id for error in report.errors],
            [RULE_AGE_INTERVAL_ORDER],
        )

    def test_environment_context_pair_accepts_valid_pair(self):
        report = self.validate(field_sample_row())

        self.assertNotIn(
            RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID,
            [error.rule_id for error in report.errors],
        )

    def test_environment_context_pair_reports_invalid_and_missing_components(self):
        rows = (
            field_sample_row(
                local_scale_environmental_context="Freshwater lake biome [ENVO:01000252]"
            ),
            field_sample_row(
                __template_row__=12,
                local_scale_environmental_context=None,
            ),
            field_sample_row(
                __template_row__=13,
                broad_scale_environmental_context=" ",
            ),
        )

        report = self.validate(*rows)

        self.assertEqual([error.template_row for error in report.errors], [11, 12, 13])
        self.assertTrue(
            all(
                error.rule_id == RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID
                for error in report.errors
            )
        )

    def test_water_depth_requirement_accepts_aquatic_depth_and_non_aquatic_blank(self):
        report = self.validate(
            field_sample_row(),
            field_sample_row(
                __template_row__=12,
                broad_scale_environmental_context="Freshwater biome [ENVO:00000873]",
                local_scale_environmental_context="Freshwater lake biome [ENVO:01000252]",
                field_sample_water_depth=4.5,
            ),
        )

        self.assertEqual(report.findings, ())

    def test_water_depth_requirement_reports_null_empty_and_whitespace(self):
        rows = tuple(
            field_sample_row(
                __template_row__=row_number,
                broad_scale_environmental_context="Freshwater biome [ENVO:00000873]",
                local_scale_environmental_context="Freshwater lake biome [ENVO:01000252]",
                field_sample_water_depth=value,
            )
            for row_number, value in ((11, None), (12, ""), (13, "  "))
        )

        report = self.validate(*rows)

        self.assertEqual(
            [error.rule_id for error in report.errors],
            [RULE_WATER_DEPTH_REQUIRED] * 3,
        )
        self.assertEqual([error.template_row for error in report.errors], [11, 12, 13])

    def test_interval_methods_require_complete_interval_depth_only(self):
        report = self.validate(
            field_sample_row(
                primary_sampling_method="Coring",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
            ),
            field_sample_row(
                __template_row__=12,
                primary_sampling_method="Bulk sampling",
                field_sampling_depth_discrete=5.0,
                field_sampling_interval_from=None,
                field_sampling_interval_to=None,
            ),
            field_sample_row(
                __template_row__=13,
                primary_sampling_method="Monolith sampling",
                field_sampling_depth_discrete=5.0,
                field_sampling_interval_from=None,
                field_sampling_interval_to=None,
            ),
        )

        self.assertEqual(
            [error.rule_id for error in report.errors],
            [RULE_INTERVAL_DEPTH_ONLY, RULE_INTERVAL_DEPTH_ONLY],
        )
        self.assertEqual([error.template_row for error in report.errors], [12, 13])

    def test_discrete_methods_require_discrete_depth_only(self):
        report = self.validate(
            field_sample_row(),
            field_sample_row(
                __template_row__=12,
                primary_sampling_method="Syringe sampling",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
            ),
            field_sample_row(
                __template_row__=13,
                primary_sampling_method="Column sampling",
                field_sampling_depth_discrete=" ",
                sampling_medium="Air [ENVO:00002005]",
                depth_inference_method=None,
            ),
        )

        self.assertEqual(
            [error.rule_id for error in report.errors],
            [RULE_DISCRETE_DEPTH_ONLY, RULE_DISCRETE_DEPTH_ONLY],
        )
        self.assertEqual([error.template_row for error in report.errors], [12, 13])

    def test_filter_sampling_requires_all_depth_fields_to_be_blank(self):
        report = self.validate(
            field_sample_row(
                primary_sampling_method="Filter sampling",
                field_sampling_depth_discrete=None,
                sampling_medium="Air [ENVO:00002005]",
                depth_inference_method=None,
            ),
            field_sample_row(
                __template_row__=12,
                primary_sampling_method="Filter sampling",
                field_sampling_depth_discrete=1.0,
            ),
            field_sample_row(
                __template_row__=13,
                primary_sampling_method="Filter sampling",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
            ),
        )

        self.assertEqual(
            [error.rule_id for error in report.errors],
            [RULE_FILTER_SAMPLING_NO_DEPTH, RULE_FILTER_SAMPLING_NO_DEPTH],
        )
        self.assertEqual([error.template_row for error in report.errors], [12, 13])

    def test_approved_uncategorized_methods_receive_no_category_error(self):
        report = self.validate(
            field_sample_row(
                primary_sampling_method='Other (specify in "Other values" column)',
                other_values="primary_sampling_method = Custom sampling method",
            ),
            field_sample_row(
                __template_row__=12,
                primary_sampling_method="Data not collected",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
            ),
        )

        self.assertEqual(report.findings, ())

    def test_generic_depth_rules_report_all_independent_issues(self):
        rows = (
            field_sample_row(
                __template_row__=11,
                primary_sampling_method="Data not collected",
                field_sampling_depth_discrete=None,
                depth_inference_method=None,
            ),
            field_sample_row(
                __template_row__=12,
                primary_sampling_method="Data not collected",
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
            ),
            field_sample_row(
                __template_row__=13,
                primary_sampling_method="Data not collected",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=None,
            ),
            field_sample_row(
                __template_row__=14,
                primary_sampling_method="Data not collected",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=10.0,
                field_sampling_interval_to=0.0,
            ),
            field_sample_row(
                __template_row__=15,
                primary_sampling_method="Data not collected",
                sampling_medium="Air [ENVO:00002005]",
                field_sampling_depth_discrete=None,
                depth_inference_method="Precise measurement",
            ),
            field_sample_row(
                __template_row__=16,
                primary_sampling_method="Data not collected",
                depth_inference_method=None,
            ),
        )

        report = self.validate(*rows)
        by_row = {
            row: {error.rule_id for error in findings}
            for row, findings in report.group_by_row().items()
        }

        self.assertEqual(by_row[11], {RULE_DEPTH_REQUIRED})
        self.assertEqual(
            by_row[12],
            {RULE_DEPTH_TYPES_EXCLUSIVE},
        )
        self.assertEqual(
            by_row[13],
            {RULE_INTERVAL_ENDPOINTS_PAIRED},
        )
        self.assertEqual(
            by_row[14],
            {RULE_INTERVAL_ASCENDING},
        )
        self.assertEqual(
            by_row[15],
            {RULE_DEPTH_INFERENCE_NOT_ALLOWED},
        )
        self.assertEqual(
            by_row[16],
            {RULE_DEPTH_INFERENCE_REQUIRED},
        )

    def test_generic_depth_rules_accept_valid_blank_and_multi_row_cases(self):
        report = self.validate(
            field_sample_row(),
            field_sample_row(
                __template_row__=12,
                primary_sampling_method="Data not collected",
                sampling_medium="Air [ENVO:00002005]",
                field_sampling_depth_discrete=None,
                depth_inference_method=None,
            ),
            field_sample_row(
                __template_row__=13,
                primary_sampling_method="Other (specify in \"Other values\" column)",
                other_values="primary_sampling_method = Custom sampling method",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
            ),
        )

        self.assertEqual(report.findings, ())

    def test_other_values_are_required_for_primary_sampling_method_other(self):
        reports = (
            self.validate(
                field_sample_row(
                    primary_sampling_method='Other (specify in "Other values" column)',
                    other_values=None,
                )
            ),
            self.validate(
                field_sample_row(
                    primary_sampling_method='Other (specify in "Other values" column)',
                    other_values="  ",
                )
            ),
            self.validate(
                field_sample_row(
                    primary_sampling_method='Other (specify in "Other values" column)',
                    other_values="primary_sampling_method = Custom sampling method",
                )
            ),
            self.validate(field_sample_row(other_values=None)),
        )

        self.assertEqual(
            [error.rule_id for error in reports[0].errors],
            [RULE_OTHER_VALUES_REQUIRED],
        )
        self.assertEqual(
            [error.rule_id for error in reports[1].errors],
            [RULE_OTHER_VALUES_REQUIRED],
        )
        self.assertEqual(reports[2].findings, ())
        self.assertEqual(reports[3].findings, ())

    def test_multiple_errors_are_aggregated_and_later_rows_are_still_checked(self):
        report = self.validate(
            field_sample_row(
                template_version=None,
                primary_sampling_method="Tube sampling",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=0.0,
                field_sampling_interval_to=10.0,
                collected_as_field_control="Maybe",
                field_sample_age_estimate_oldest=1.0,
                field_sample_age_estimate_youngest=2.0,
                local_scale_environmental_context="Forest biome [ENVO:01000174]",
                broad_scale_environmental_context="Freshwater biome [ENVO:00000873]",
                field_sample_water_depth=None,
            ),
            field_sample_row(
                __template_row__=12,
                collected_as_field_control="Maybe",
            ),
        )

        self.assertEqual(
            {error.rule_id for error in report.group_by_row()[11]},
            {
                RULE_TEMPLATE_VERSION_REQUIRED,
                RULE_FIELD_CONTROL_NOT_ALLOWED,
                RULE_AGE_INTERVAL_ORDER,
                RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID,
                RULE_WATER_DEPTH_REQUIRED,
                RULE_DISCRETE_DEPTH_ONLY,
            },
        )
        self.assertEqual(
            [error.rule_id for error in report.group_by_row()[12]],
            [RULE_FIELD_CONTROL_NOT_ALLOWED],
        )
