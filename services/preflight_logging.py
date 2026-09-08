"""Safe, structured observability helpers for upload preflight.

The returned JSON is intended for the existing application logger. It records
operational metadata only: never call ``str(error)`` or serialize parsed rows,
because exception messages and row values may contain upload data.
"""

import json
import traceback
from pathlib import Path


UNEXPECTED_FAILURE_EVENT = "smdb_preflight_unexpected_failure"
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


def unexpected_preflight_failure_event(*, mode: str, table_type: str, error: BaseException) -> str:
    """Serialize a value-free event for an unexpected preflight failure."""
    event = {
        "event": UNEXPECTED_FAILURE_EVENT,
        "mode": mode,
        "table_type": table_type,
        "error_type": type(error).__name__,
        "stack_frames": _safe_stack_frames(error),
    }
    return json.dumps(event, sort_keys=True, separators=(",", ":"))
