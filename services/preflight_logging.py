"""Safe, structured observability helpers for upload preflight.

The returned JSON is intended for the existing application logger. It records
operational metadata only: never call ``str(error)`` or serialize parsed rows,
because exception messages and row values may contain upload data.
"""

import json
import traceback
from pathlib import Path


UNEXPECTED_FAILURE_EVENT = "smdb_preflight_unexpected_failure"
REPORT_EVENT = "smdb_preflight_report"
LEGACY_DATABASE_ERROR_EVENT = "smdb_preflight_legacy_database_error"
LEGACY_DATABASE_SUCCESS_EVENT = "smdb_preflight_legacy_database_success"
LEGACY_WRITE_BLOCKED_EVENT = "smdb_preflight_legacy_write_blocked"
MAX_STACK_FRAMES = 12


def _safe_stack_frames(error: BaseException) -> list[dict[str, object]]:
    """Return bounded source locations without exception text or local values."""
    if error.__traceback__ is None:
        return []

    frames = traceback.extract_tb(error.__traceback__)[-MAX_STACK_FRAMES:]
    return [
        {
            "file": Path(frame.filename).name,
            "line": frame.lineno,
            "function": frame.name,
        }
        for frame in frames
    ]


def _serialize_event(event: dict[str, object]) -> str:
    """Return one compact JSON event for the legacy text logger."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def preflight_report_event(
    *, correlation_id: str, mode: str, table_type: str, validated_row_count: int,
    error_count: int, warning_count: int, rule_ids: tuple[str, ...],
) -> str:
    """Serialize aggregate preflight findings without row values or identities."""
    return _serialize_event(
        {
            "event": REPORT_EVENT,
            "correlation_id": correlation_id,
            "mode": mode,
            "table_type": table_type,
            "validated_row_count": validated_row_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "rule_ids": list(rule_ids),
        }
    )


def legacy_database_outcome_event(
    *, event_name: str, correlation_id: str, mode: str,
    database_error: BaseException | None = None,
) -> str:
    """Serialize a legacy write outcome that can be correlated to preflight."""
    if event_name not in {
        LEGACY_DATABASE_ERROR_EVENT,
        LEGACY_DATABASE_SUCCESS_EVENT,
        LEGACY_WRITE_BLOCKED_EVENT,
    }:
        raise ValueError(f"Unsupported legacy database outcome event: {event_name!r}")

    event: dict[str, object] = {
        "event": event_name,
        "correlation_id": correlation_id,
        "mode": mode,
    }
    if database_error is not None:
        # Error messages may embed submitted values or database details.
        event["database_error_type"] = type(database_error).__name__
    return _serialize_event(event)


def unexpected_preflight_failure_event(
    *, correlation_id: str, mode: str, table_type: str, error: BaseException
) -> str:
    """Serialize a value-free event for an unexpected preflight failure."""
    event = {
        "event": UNEXPECTED_FAILURE_EVENT,
        "correlation_id": correlation_id,
        "mode": mode,
        "table_type": table_type,
        "error_type": type(error).__name__,
        "stack_frames": _safe_stack_frames(error),
    }
    return _serialize_event(event)
