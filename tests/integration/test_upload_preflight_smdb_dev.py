"""Read-only integration checks for field-sample preflight against SMDB-dev.

Run this module only with ``SMDB_RUN_INTEGRATION_TESTS=1`` and a development
database tunnel on port 5433. It does not insert, update, or delete rows. A
unique synthetic field-sample ID is checked before and after the workflow as a
guard against an unexpected write.
"""

import os
import unittest
import uuid

from services.upload_workflow import UploadPreflightRequest, run_upload_preflight
from tests.validation.fixtures import field_sample_row
from validation.reference_data import (
    PostgresReferenceDataProvider,
    WorkflowCachedReferenceDataProvider,
    _read_only_connection,
)


INTEGRATION_OPT_IN_ENVIRONMENT_VARIABLE = "SMDB_RUN_INTEGRATION_TESTS"


def integration_is_enabled():
    """Require an explicit opt-in and the standard user-owned dev port."""
    return (
        os.environ.get(INTEGRATION_OPT_IN_ENVIRONMENT_VARIABLE) == "1"
        and os.environ.get("RUN_MODE", "development").lower() == "development"
        and os.environ.get("SMDB_DB_PORT", "5433") == "5433"
    )


@unittest.skipUnless(
    integration_is_enabled(),
    "set SMDB_RUN_INTEGRATION_TESTS=1 with RUN_MODE=development and SMDB_DB_PORT=5433",
)
class SMDBDevUploadPreflightIntegrationTest(unittest.TestCase):
    """Confirm preflight works with real read-only SMDB-dev reference data."""

    @classmethod
    def setUpClass(cls):
        cls.synthetic_field_sample_id = f"TESTPREFLIGHT{uuid.uuid4().hex[:16]}"
        cls.reference_data = WorkflowCachedReferenceDataProvider(
            PostgresReferenceDataProvider()
        )
        cls.assert_synthetic_id_absent()

    @classmethod
    def synthetic_id_count(cls):
        connection = _read_only_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM uploaded_data.field_sample
                    WHERE field_sample_id = %s;
                    """,
                    (cls.synthetic_field_sample_id,),
                )
                return cursor.fetchone()[0]
        finally:
            connection.close()

    @classmethod
    def assert_synthetic_id_absent(cls):
        if cls.synthetic_id_count() != 0:
            raise AssertionError(
                "Integration test synthetic field-sample ID unexpectedly exists"
            )

    @classmethod
    def tearDownClass(cls):
        # This test creates no rows. Do not delete anything here: an unexpected
        # row must remain visible for investigation rather than being removed.
        cls.assert_synthetic_id_absent()

    def request_for(self, *rows):
        return UploadPreflightRequest(
            parsed_sheets={"field_sample": rows},
            table_type="field_sample",
            parser_options={"source": "SMDB-dev integration test"},
            reference_data=self.reference_data,
        )

    def baseline_row(self, **overrides):
        """Return a minimal synthetic row accepted by the implemented rules."""
        row = field_sample_row(
            field_sample_id=self.synthetic_field_sample_id,
            primary_sampling_method="Data not collected",
            collected_as_field_control="No",
            sampling_medium=None,
            field_sampling_depth_discrete=None,
            field_sampling_interval_from=None,
            field_sampling_interval_to=None,
            depth_inference_method=None,
            field_sample_age_estimate_oldest=None,
            field_sample_age_estimate_youngest=None,
            broad_scale_environmental_context="Freshwater biome [ENVO:00000873]",
            local_scale_environmental_context="Freshwater lake biome [ENVO:01000252]",
            field_sample_water_depth=1.0,
        )
        row.update(overrides)
        return row

    def test_synthetic_valid_row_has_no_preflight_errors(self):
        result = run_upload_preflight(self.request_for(self.baseline_row()))

        self.assertTrue(result.preflight_applied)
        self.assertEqual(result.validated_row_count, 1)
        self.assertEqual(result.report.errors, ())

    def test_targeted_invalid_rows_return_multiple_real_reference_backed_errors(self):
        result = run_upload_preflight(
            self.request_for(
                self.baseline_row(template_version=None),
                self.baseline_row(primary_sampling_method="Not an SMDB method"),
                self.baseline_row(collected_as_field_control="Not an SMDB control"),
                self.baseline_row(
                    field_sample_age_estimate_oldest=1.0,
                    field_sample_age_estimate_youngest=2.0,
                ),
                self.baseline_row(
                    broad_scale_environmental_context="Not an SMDB broad context",
                    local_scale_environmental_context="Not an SMDB local context",
                ),
            )
        )

        self.assertEqual(
            {finding.rule_id for finding in result.report.errors},
            {
                "field_sample.age_interval_order",
                "field_sample.collected_as_field_control_not_allowed",
                "field_sample.environment_context_pair_invalid",
                "field_sample.primary_sampling_method_not_allowed",
                "field_sample.template_version_required",
            },
        )
