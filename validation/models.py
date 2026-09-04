"""Validation-report data models.

Future models in this module must remain independent of Flask and database
connections so validation rules can be unit-tested in isolation.
"""

from dataclasses import dataclass, field
from typing import Any


VALID_SEVERITIES = frozenset({"error", "warning"})
MAX_DISPLAY_VALUE_LENGTH = 500


@dataclass(frozen=True, slots=True)
class ValidationError:
    """One user-actionable validation finding.

    Despite its historical name, this is a data record rather than an exception
    intended to be raised. Rules return instances of this class so one upload
    can report multiple independent findings at once.
    """

    rule_id: str
    message: str
    template_row: int | None = None
    template_column: str | None = None
    database_column: str | None = None
    value: Any | None = None
    severity: str = "error"

    def __post_init__(self):
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("rule_id must be a non-empty string")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty string")
        if self.template_row is not None and (
            not isinstance(self.template_row, int)
            or isinstance(self.template_row, bool)
            or self.template_row < 1
        ):
            raise ValueError("template_row must be a positive integer or None")
        if not isinstance(self.severity, str) or self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(VALID_SEVERITIES)}, "
                f"got {self.severity!r}"
            )

    @property
    def display_value(self) -> str | None:
        """Return a bounded string suitable for a user-facing report."""
        if self.value is None:
            return None

        value = str(self.value)
        if len(value) <= MAX_DISPLAY_VALUE_LENGTH:
            return value
        return f"{value[: MAX_DISPLAY_VALUE_LENGTH - 1]}…"

    def to_dict(self) -> dict[str, Any]:
        """Return JSON/Jinja-friendly scalar data for this finding."""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "template_row": self.template_row,
            "template_column": self.template_column,
            "database_column": self.database_column,
            "value": self.display_value,
            "severity": self.severity,
        }


@dataclass(slots=True)
class ValidationReport:
    """Mutable collection of validation findings for one upload attempt."""

    _findings: list[ValidationError] = field(default_factory=list, repr=False)

    @staticmethod
    def _sort_key(finding: ValidationError) -> tuple[Any, ...]:
        """Keep reports deterministic regardless of rule execution order."""
        return (
            finding.template_row is None,
            finding.template_row if finding.template_row is not None else 0,
            finding.template_column or "",
            finding.database_column or "",
            finding.rule_id,
            finding.severity,
            finding.message,
            finding.display_value or "",
        )

    @property
    def findings(self) -> tuple[ValidationError, ...]:
        """Return findings in their stable presentation order."""
        return tuple(sorted(self._findings, key=self._sort_key))

    @property
    def errors(self) -> tuple[ValidationError, ...]:
        """Return error-severity findings in stable presentation order."""
        return tuple(finding for finding in self.findings if finding.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationError, ...]:
        """Return warning-severity findings in stable presentation order."""
        return tuple(
            finding for finding in self.findings if finding.severity == "warning"
        )

    @property
    def has_errors(self) -> bool:
        """Whether this report should prevent an upload from continuing."""
        return bool(self.errors)

    def add(self, finding: ValidationError) -> ValidationError:
        """Add one finding and return it for convenient rule construction."""
        if not isinstance(finding, ValidationError):
            raise TypeError("finding must be a ValidationError")
        self._findings.append(finding)
        return finding

    def merge(self, other: "ValidationReport") -> "ValidationReport":
        """Add all findings from another report and return this report."""
        if not isinstance(other, ValidationReport):
            raise TypeError("other must be a ValidationReport")
        self._findings.extend(other._findings)
        return self

    def group_by_row(self) -> dict[int | None, tuple[ValidationError, ...]]:
        """Return stable findings grouped by user-visible template row."""
        grouped: dict[int | None, list[ValidationError]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.template_row, []).append(finding)
        return {row: tuple(findings) for row, findings in grouped.items()}

    def to_dict(self) -> dict[str, Any]:
        """Return JSON/Jinja-friendly report data."""
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "has_errors": self.has_errors,
        }
