"""Unit tests for value-free preflight failure logging."""

import json
import unittest

from services.preflight_logging import (
    UNEXPECTED_FAILURE_EVENT,
    unexpected_preflight_failure_event,
)


class PreflightLoggingTest(unittest.TestCase):
    def test_event_contains_operational_metadata_without_exception_message(self):
        sensitive_value = "secret@example.org; field_sample_id=PRIVATE_001"
        try:
            raise RuntimeError(f"unexpected parser state: {sensitive_value}")
        except RuntimeError as error:
            serialized = unexpected_preflight_failure_event(
                mode="shadow",
                table_type="field_sample",
                error=error,
            )

        event = json.loads(serialized)
        self.assertEqual(event["event"], UNEXPECTED_FAILURE_EVENT)
        self.assertEqual(event["mode"], "shadow")
        self.assertEqual(event["table_type"], "field_sample")
        self.assertEqual(event["error_type"], "RuntimeError")
        self.assertTrue(event["stack_frames"])
        self.assertNotIn(sensitive_value, serialized)
        self.assertNotIn("unexpected parser state", serialized)

    def test_event_without_traceback_uses_an_empty_stack(self):
        serialized = unexpected_preflight_failure_event(
            mode="enforce",
            table_type="field_sample",
            error=ValueError(),
        )

        self.assertEqual(json.loads(serialized)["stack_frames"], [])
