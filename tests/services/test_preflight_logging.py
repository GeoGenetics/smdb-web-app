"""Unit tests for value-free preflight failure logging."""

import json
import unittest

from services.preflight_logging import (
    LEGACY_DATABASE_ERROR_EVENT,
    LEGACY_DATABASE_SUCCESS_EVENT,
    REPORT_EVENT,
    UNEXPECTED_FAILURE_EVENT,
    legacy_database_outcome_event,
    preflight_report_event,
    unexpected_preflight_failure_event,
)


class PreflightLoggingTest(unittest.TestCase):
    def test_event_contains_operational_metadata_without_exception_message(self):
        sensitive_value = "secret@example.org; field_sample_id=PRIVATE_001"
        try:
            raise RuntimeError(f"unexpected parser state: {sensitive_value}")
        except RuntimeError as error:
            serialized = unexpected_preflight_failure_event(
                correlation_id="preflight-123",
                mode="shadow",
                table_type="field_sample",
                error=error,
            )

        event = json.loads(serialized)
        self.assertEqual(event["event"], UNEXPECTED_FAILURE_EVENT)
        self.assertEqual(event["correlation_id"], "preflight-123")
        self.assertEqual(event["mode"], "shadow")
        self.assertEqual(event["table_type"], "field_sample")
        self.assertEqual(event["error_type"], "RuntimeError")
        self.assertTrue(event["stack_frames"])
        self.assertNotIn(sensitive_value, serialized)
        self.assertNotIn("unexpected parser state", serialized)

    def test_event_without_traceback_uses_an_empty_stack(self):
        serialized = unexpected_preflight_failure_event(
            correlation_id="preflight-123",
            mode="enforce",
            table_type="field_sample",
            error=ValueError(),
        )

        self.assertEqual(json.loads(serialized)["stack_frames"], [])

    def test_report_event_contains_counts_and_stable_rule_ids_only(self):
        serialized = preflight_report_event(
            correlation_id="preflight-123",
            mode="shadow",
            table_type="field_sample",
            validated_row_count=2,
            error_count=3,
            warning_count=1,
            rule_ids=("field_sample.age_interval_order",),
        )

        self.assertEqual(
            json.loads(serialized),
            {
                "correlation_id": "preflight-123",
                "error_count": 3,
                "event": REPORT_EVENT,
                "mode": "shadow",
                "rule_ids": ["field_sample.age_interval_order"],
                "table_type": "field_sample",
                "validated_row_count": 2,
                "warning_count": 1,
            },
        )

    def test_database_error_event_excludes_database_error_message(self):
        sensitive_value = "password=not-for-logs"
        serialized = legacy_database_outcome_event(
            event_name=LEGACY_DATABASE_ERROR_EVENT,
            correlation_id="preflight-123",
            mode="shadow",
            database_error=RuntimeError(sensitive_value),
        )

        event = json.loads(serialized)
        self.assertEqual(event["database_error_type"], "RuntimeError")
        self.assertNotIn(sensitive_value, serialized)

    def test_database_success_event_has_no_error_type(self):
        event = json.loads(
            legacy_database_outcome_event(
                event_name=LEGACY_DATABASE_SUCCESS_EVENT,
                correlation_id="preflight-123",
                mode="enforce",
            )
        )

        self.assertNotIn("database_error_type", event)
