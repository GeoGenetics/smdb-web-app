"""Read-only reference-data boundary for preflight validation.

This module will provide bounded-lifetime lookup access without embedding
allowed values in Python validation rules.
"""

from collections.abc import Set
from typing import Protocol, runtime_checkable


@runtime_checkable
class ReferenceDataProvider(Protocol):
    """Read-only reference data required by field-sample preflight rules.

    Implementations may obtain data from PostgreSQL or an in-memory test
    fixture. Validation rules depend only on this contract and must not issue
    SQL, import application configuration, or know database-table names.

    Returned value collections represent one provider/workflow snapshot. A
    production implementation must avoid a process-lifetime cache so allowed
    values can change without restarting the web application.
    """

    def field_sampling_methods(self) -> Set[str]:
        """Return approved primary field-sampling methods."""

    def field_controls(self) -> Set[str]:
        """Return approved values for ``collected_as_field_control``."""

    def depth_inference_methods(self) -> Set[str]:
        """Return approved depth-inference methods."""

    def has_environment_context_pair(
        self,
        *,
        local_context: str,
        broad_context: str,
    ) -> bool:
        """Return whether a local environmental context applies to a broad one."""
