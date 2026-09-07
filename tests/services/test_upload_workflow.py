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
