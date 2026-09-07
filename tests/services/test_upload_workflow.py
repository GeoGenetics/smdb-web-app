"""Boundary tests for framework-free upload-workflow services."""

import importlib
import sys
import unittest
from unittest.mock import patch

import pandas as pd

from services.upload_workflow import (
    UploadPreflightRequest,
    run_upload_preflight,
)
from tests.validation.fixtures import common_reference_data, field_sample_row
from validation.reference_data import InMemoryReferenceDataProvider


def reference_provider():
    """Return the fixture-backed provider required by field-sample preflight."""
    data = common_reference_data()
    return InMemoryReferenceDataProvider(
        field_sampling_method_values=data["field_sampling_methods"],
        field_control_values=data["field_controls"],
        depth_inference_method_values=data["depth_inference_methods"],
        environment_context_pairs=data["environment_context_pairs"],
    )


class RecordingReferenceDataProvider(InMemoryReferenceDataProvider):
    """Fixture provider that records the read operations requested by a workflow."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lookup_calls = []
        self.write_attempts = 0

    def field_sampling_methods(self):
        self.lookup_calls.append("field_sampling_methods")
        return super().field_sampling_methods()

    def field_controls(self):
        self.lookup_calls.append("field_controls")
        return super().field_controls()

    def depth_inference_methods(self):
        self.lookup_calls.append("depth_inference_methods")
        return super().depth_inference_methods()

    def has_environment_context_pair(self, *, local_context, broad_context):
        self.lookup_calls.append("has_environment_context_pair")
        return super().has_environment_context_pair(
            local_context=local_context,
            broad_context=broad_context,
        )

    def write(self, *_args, **_kwargs):
        """A write-capable fake would fail immediately if the workflow used it."""
        self.write_attempts += 1
        raise AssertionError("Upload preflight must not write through its provider")


class UploadWorkflowImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from services import upload_workflow

        self.assertIsNotNone(upload_workflow)

    def test_module_imports_when_flask_is_unavailable(self):
        """Keep request/session/template concerns outside this service layer."""
        from services import upload_workflow

        with patch.dict(sys.modules, {"flask": None}):
            reloaded_module = importlib.reload(upload_workflow)

        self.assertIsNotNone(reloaded_module)


class UploadWorkflowParserOutputTest(unittest.TestCase):
    def test_consumes_legacy_style_clean_sheet_dataframe_without_parser_import(self):
        """A DataFrame is the current parser's clean_sheets representation."""
        clean_sheets = {"field_sample": pd.DataFrame([field_sample_row()])}
        request = UploadPreflightRequest(
            parsed_sheets=clean_sheets,
            table_type="field_sample",
            parser_options={
                "date_format": "YYYY-MM-DD",
                "decimal_point": ".",
                "thousands_separator": "not_relevant",
            },
            reference_data=reference_provider(),
        )

        result = run_upload_preflight(request)

        self.assertTrue(result.preflight_applied)
        self.assertEqual(result.validated_row_count, 1)
        self.assertEqual(result.report.findings, ())
        self.assertEqual(result.parser_options, request.parser_options)


class UploadWorkflowOrchestrationTest(unittest.TestCase):
    def test_returns_aggregate_findings_without_mutating_or_writing_the_sheet(self):
        """Preflight reads reference values and returns findings to its caller."""
        data = common_reference_data()
        provider = RecordingReferenceDataProvider(
            field_sampling_method_values=data["field_sampling_methods"],
            field_control_values=data["field_controls"],
            depth_inference_method_values=data["depth_inference_methods"],
            environment_context_pairs=data["environment_context_pairs"],
        )
        clean_sheet = pd.DataFrame(
            [
                field_sample_row(
                    template_version=None,
                    primary_sampling_method="Unknown sampling method",
                    collected_as_field_control="Unknown control",
                ),
                field_sample_row(
                    field_sample_age_estimate_oldest=1.0,
                    field_sample_age_estimate_youngest=2.0,
                ),
            ]
        )
        original_sheet = clean_sheet.copy(deep=True)
        request = UploadPreflightRequest(
            parsed_sheets={"field_sample": clean_sheet},
            table_type="field_sample",
            parser_options={},
            reference_data=provider,
        )

        result = run_upload_preflight(request)

        self.assertTrue(result.preflight_applied)
        self.assertEqual(result.validated_row_count, 2)
        self.assertEqual(
            {finding.rule_id for finding in result.report.findings},
            {
                "field_sample.age_interval_order",
                "field_sample.collected_as_field_control_not_allowed",
                "field_sample.primary_sampling_method_not_allowed",
                "field_sample.template_version_required",
            },
        )
        self.assertEqual(provider.write_attempts, 0)
        self.assertIn("field_sampling_methods", provider.lookup_calls)
        self.assertIn("field_controls", provider.lookup_calls)
        pd.testing.assert_frame_equal(clean_sheet, original_sheet)
