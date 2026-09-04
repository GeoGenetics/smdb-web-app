"""Read-only reference-data boundary for preflight validation.

This module will provide bounded-lifetime lookup access without embedding
allowed values in Python validation rules.
"""

from collections.abc import Callable, Iterable, Set
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


FIELD_SAMPLING_METHODS_QUERY = """
SELECT value
FROM allowed_values.field_sampling_method
ORDER BY value;
"""

FIELD_CONTROLS_QUERY = """
SELECT value
FROM allowed_values.field_control
ORDER BY value;
"""

DEPTH_INFERENCE_METHODS_QUERY = """
SELECT value
FROM allowed_values.depth_inference_method
ORDER BY value;
"""

ENVIRONMENT_CONTEXT_PAIR_QUERY = """
SELECT EXISTS (
    SELECT 1
    FROM allowed_values.local_env_context
    WHERE value = %s
      AND applies_to = %s
);
"""


class ReferenceDataLookupError(RuntimeError):
    """Required reference data could not be read from its provider."""

    def __init__(self, lookup_name: str):
        self.lookup_name = lookup_name
        super().__init__(f"Unable to read required reference data: {lookup_name}")


def _read_only_connection() -> Any:
    """Open a fresh connection using the existing read-only configuration.

    Imports are intentionally local. Importing ``constants.db_connections`` at
    module import time would create its legacy global connections and make pure
    validation imports depend on database configuration.
    """
    import psycopg2

    from constants.db_connections import DATABASE_CONFIG_READ_ONLY

    return psycopg2.connect(**DATABASE_CONFIG_READ_ONLY)


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


class PostgresReferenceDataProvider:
    """Read approved reference data from PostgreSQL through a read-only role.

    Each lookup obtains and closes its own connection. Workflow-level caching,
    if needed, belongs in a later wrapper rather than this provider, so its
    data cannot become stale for the lifetime of the Flask process.
    """

    def __init__(
        self,
        connection_factory: Callable[[], Any] = _read_only_connection,
    ):
        self._connection_factory = connection_factory

    def _run_lookup(self, lookup_name: str, operation: Callable[[Any], Any]) -> Any:
        """Run one lookup and normalize provider failures for callers."""
        connection = None
        lookup_failed = False
        try:
            connection = self._connection_factory()
            return operation(connection)
        except Exception as error:
            lookup_failed = True
            raise ReferenceDataLookupError(lookup_name) from error
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception as error:
                    if not lookup_failed:
                        raise ReferenceDataLookupError(lookup_name) from error

    def _values(self, lookup_name: str, query: str) -> frozenset[str]:
        def fetch_values(connection: Any) -> frozenset[str]:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return frozenset(value for (value,) in cursor.fetchall())

        return self._run_lookup(lookup_name, fetch_values)

    def field_sampling_methods(self) -> frozenset[str]:
        """Return approved primary field-sampling methods."""
        return self._values(
            "allowed_values.field_sampling_method",
            FIELD_SAMPLING_METHODS_QUERY,
        )

    def field_controls(self) -> frozenset[str]:
        """Return approved values for ``collected_as_field_control``."""
        return self._values("allowed_values.field_control", FIELD_CONTROLS_QUERY)

    def depth_inference_methods(self) -> frozenset[str]:
        """Return approved depth-inference methods."""
        return self._values(
            "allowed_values.depth_inference_method",
            DEPTH_INFERENCE_METHODS_QUERY,
        )

    def has_environment_context_pair(
        self,
        *,
        local_context: str,
        broad_context: str,
    ) -> bool:
        """Return whether a local environmental context applies to a broad one."""
        def fetch_pair(connection: Any) -> bool:
            with connection.cursor() as cursor:
                cursor.execute(
                    ENVIRONMENT_CONTEXT_PAIR_QUERY,
                    (local_context, broad_context),
                )
                row = cursor.fetchone()
                return bool(row[0])

        return self._run_lookup("allowed_values.local_env_context", fetch_pair)


@dataclass(frozen=True, slots=True)
class InMemoryReferenceDataProvider:
    """Immutable reference-data provider for unit tests and local workflows.

    Inputs are snapshotted at construction so later mutation of a caller's set
    cannot change validation results during a test or workflow.
    """

    field_sampling_method_values: Iterable[str] = field(default_factory=frozenset)
    field_control_values: Iterable[str] = field(default_factory=frozenset)
    depth_inference_method_values: Iterable[str] = field(default_factory=frozenset)
    environment_context_pairs: Iterable[tuple[str, str]] = field(
        default_factory=frozenset
    )

    def __post_init__(self):
        object.__setattr__(
            self,
            "field_sampling_method_values",
            frozenset(self.field_sampling_method_values),
        )
        object.__setattr__(
            self,
            "field_control_values",
            frozenset(self.field_control_values),
        )
        object.__setattr__(
            self,
            "depth_inference_method_values",
            frozenset(self.depth_inference_method_values),
        )
        object.__setattr__(
            self,
            "environment_context_pairs",
            frozenset(self.environment_context_pairs),
        )

    def field_sampling_methods(self) -> frozenset[str]:
        """Return the configured field-sampling methods."""
        return self.field_sampling_method_values

    def field_controls(self) -> frozenset[str]:
        """Return the configured field-control values."""
        return self.field_control_values

    def depth_inference_methods(self) -> frozenset[str]:
        """Return the configured depth-inference methods."""
        return self.depth_inference_method_values

    def has_environment_context_pair(
        self,
        *,
        local_context: str,
        broad_context: str,
    ) -> bool:
        """Return whether the configured context pair is valid."""
        return (local_context, broad_context) in self.environment_context_pairs


@dataclass(slots=True)
class WorkflowCachedReferenceDataProvider:
    """Cache reference lookups for one preflight workflow only.

    Construct one instance per upload/preflight attempt and discard it when
    that workflow ends. This wrapper intentionally has no global state and no
    Flask request dependency, preventing stale values from persisting across
    uploads or application restarts.
    """

    provider: ReferenceDataProvider
    _field_sampling_methods: frozenset[str] | None = field(
        default=None, init=False, repr=False
    )
    _field_controls: frozenset[str] | None = field(
        default=None, init=False, repr=False
    )
    _depth_inference_methods: frozenset[str] | None = field(
        default=None, init=False, repr=False
    )
    _environment_context_pairs: dict[tuple[str, str], bool] = field(
        default_factory=dict, init=False, repr=False
    )

    def field_sampling_methods(self) -> frozenset[str]:
        """Return workflow-cached field-sampling methods."""
        if self._field_sampling_methods is None:
            self._field_sampling_methods = frozenset(
                self.provider.field_sampling_methods()
            )
        return self._field_sampling_methods

    def field_controls(self) -> frozenset[str]:
        """Return workflow-cached field-control values."""
        if self._field_controls is None:
            self._field_controls = frozenset(self.provider.field_controls())
        return self._field_controls

    def depth_inference_methods(self) -> frozenset[str]:
        """Return workflow-cached depth-inference methods."""
        if self._depth_inference_methods is None:
            self._depth_inference_methods = frozenset(
                self.provider.depth_inference_methods()
            )
        return self._depth_inference_methods

    def has_environment_context_pair(
        self,
        *,
        local_context: str,
        broad_context: str,
    ) -> bool:
        """Return a workflow-cached environmental-context-pair result."""
        key = (local_context, broad_context)
        if key not in self._environment_context_pairs:
            self._environment_context_pairs[key] = (
                self.provider.has_environment_context_pair(
                    local_context=local_context,
                    broad_context=broad_context,
                )
            )
        return self._environment_context_pairs[key]
