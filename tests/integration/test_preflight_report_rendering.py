"""Opt-in Flask test-client coverage for the development enforce report."""

import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from validation.models import ValidationError, ValidationReport


def integration_is_enabled():
    """Match the safety gate used by the SMDB-dev integration checks."""
    return (
        os.environ.get("SMDB_RUN_INTEGRATION_TESTS") == "1"
        and os.environ.get("RUN_MODE", "development").lower() == "development"
        and os.environ.get("SMDB_DB_PORT", "5433") == "5433"
    )


@unittest.skipUnless(
    integration_is_enabled(),
    "set SMDB_RUN_INTEGRATION_TESTS=1 with RUN_MODE=development and SMDB_DB_PORT=5433",
)
class PreflightReportRenderingTest(unittest.TestCase):
    """Check that enforce renders findings and bypasses the legacy write path."""

    @classmethod
    def setUpClass(cls):
        cls.app_module = importlib.import_module("app")
        cls.flask_app = cls.app_module.app
        cls.flask_app.config.update(TESTING=True)

    def report_with_findings(self):
        report = ValidationReport()
        report.add(
            ValidationError(
                rule_id="field_sample.template_version_required",
                message="template_version is required.",
                template_row=11,
                template_column="Template version",
                database_column="template_version",
            )
        )
        report.add(
            ValidationError(
                rule_id="field_sample.age_interval_order",
                message="Oldest age estimate must be greater than or equal to youngest age estimate.",
                template_row=12,
                template_column="Oldest age estimate",
                database_column="field_sample_age_estimate_oldest",
                value=1.0,
            )
        )
        return report

    def create_legacy_parsed_sheet(self, session_dir):
        parsed_directory = Path(session_dir) / "parsed_sheets"
        parsed_directory.mkdir()
        (parsed_directory / "synthetic_field_sample.txt").write_text(
            "field_sample_id\nTESTPREFLIGHTCLIENT\n",
            encoding="utf-8",
        )

    def test_enforce_report_groups_findings_and_does_not_open_write_connection(self):
        report = self.report_with_findings()
        with TemporaryDirectory() as temporary_directory:
            self.create_legacy_parsed_sheet(temporary_directory)
            with self.flask_app.test_client() as client:
                with client.session_transaction() as session:
                    session["error"] = False
                    session["file_name"] = "synthetic.txt"
                    session["database_table_name"] = "field_sample"
                    session["session_dir"] = temporary_directory
                    session["session_id"] = str(uuid.uuid4())
                    session["encoding_user_input"] = "utf-8"
                    session["parser_options"] = {}

                with (
                    patch.object(
                        self.app_module.db_table_related_constants.DBTableRelated,
                        "TABLE_SPLITTER",
                        {"field_sample": ["field_sample"]},
                    ),
                    patch.object(
                        self.app_module.queries,
                        "check_if_upload_id_exists_in_schema",
                        return_value=[],
                    ),
                    patch.object(
                        self.app_module.queries,
                        "check_if_upload_id_exists_in_table",
                        return_value=False,
                    ),
                    patch.object(
                        self.app_module.queries,
                        "count_rows",
                        return_value=0,
                    ),
                    patch.object(
                        self.app_module,
                        "sheet_to_db_rename_map",
                        return_value={},
                    ),
                    patch.object(
                        self.app_module,
                        "run_upload_preflight_for_rollout",
                        return_value=report,
                    ),
                    patch.object(self.app_module, "ENGINE") as write_engine,
                ):
                    response = client.post("/confirmed")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Upload preflight report", body)
        self.assertIn("No data has been written to the database.", body)
        self.assertIn("Template row 11", body)
        self.assertIn("Template row 12", body)
        self.assertIn("field_sample.template_version_required", body)
        self.assertIn("smdb-preflight-report.tsv", body)
        write_engine.connect.assert_not_called()
