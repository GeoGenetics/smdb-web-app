"""Framework-free orchestration for parsed-upload preflight validation.

This module deliberately does not import or access Flask request, session,
redirect, flash, template globals, application configuration, or write-side
database connections. It receives parsed data and a reference-data provider as
explicit inputs, then returns a validation report as explicit output.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from validation.field_sample import validate_field_sample_rows
from validation.models import ValidationReport
from validation.reference_data import ReferenceDataProvider


FIELD_SAMPLE_TABLE_TYPE = "field_sample"


@dataclass(frozen=True, slots=True)
class UploadPreflightRequest:
    """Explicit inputs needed to run one preflight workflow.

    ``parsed_sheets`` is keyed by canonical table type. A sheet can be either
    an iterable of canonical row mappings or a pandas-like object exposing
    ``to_dict(orient="records")``. This keeps the workflow compatible with the
    current parser output without adding a pandas dependency to this module.
    ``parser_options`` are preserved as context only in this first checkpoint;
    later workflow steps may use them when parser orchestration moves here.
    """

    parsed_sheets: Mapping[str, Any]
    table_type: str
    parser_options: Mapping[str, Any]
    reference_data: ReferenceDataProvider

    def __post_init__(self) -> None:
        if not isinstance(self.table_type, str) or not self.table_type.strip():
            raise ValueError("table_type must be a non-empty string")
        if not isinstance(self.parsed_sheets, Mapping):
            raise TypeError("parsed_sheets must be a mapping keyed by table type")
        if not isinstance(self.parser_options, Mapping):
            raise TypeError("parser_options must be a mapping")
        if self.table_type not in self.parsed_sheets:
            raise KeyError(
                f"parsed_sheets does not contain the requested table type: "
                f"{self.table_type!r}"
            )
        if not isinstance(self.reference_data, ReferenceDataProvider):
            raise TypeError("reference_data must implement ReferenceDataProvider")


@dataclass(frozen=True, slots=True)
class UploadPreflightResult:
    """Explicit output from one preflight workflow.

    ``preflight_applied`` distinguishes a successful empty field-sample report
    from a table type for which no Python rules exist yet. It does not indicate
    whether a legacy upload should proceed; mode selection remains a later
    Flask-free workflow concern.
    """

    table_type: str
    parser_options: Mapping[str, Any]
    report: ValidationReport
    validated_row_count: int
    preflight_applied: bool


def _canonical_rows(parsed_sheet: Any) -> tuple[Mapping[str, Any], ...]:
    """Return immutable row traversal input from supported parser outputs."""
    if isinstance(parsed_sheet, Mapping):
        raise TypeError(
            "a parsed sheet must be row mappings or a pandas-like sheet, not a mapping"
        )

    to_dict = getattr(parsed_sheet, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict(orient="records")
        except TypeError as error:
            raise TypeError(
                "a pandas-like parsed sheet must support to_dict(orient='records')"
            ) from error
    else:
        rows = parsed_sheet

    try:
        canonical_rows = tuple(rows)
    except TypeError as error:
        raise TypeError("a parsed sheet must be iterable") from error

    if not all(isinstance(row, Mapping) for row in canonical_rows):
        raise TypeError("parsed sheet rows must be mappings keyed by canonical columns")
    return canonical_rows


def run_upload_preflight(request: UploadPreflightRequest) -> UploadPreflightResult:
    """Run available pure preflight rules for one parsed table type.

    This is intentionally read-only orchestration: it does not parse files,
    open a write connection, or call any upload/insert code. Field-sample is
    the only implemented table type in this first workflow checkpoint.
    """
    rows = _canonical_rows(request.parsed_sheets[request.table_type])

    if request.table_type == FIELD_SAMPLE_TABLE_TYPE:
        report = validate_field_sample_rows(rows, request.reference_data)
        return UploadPreflightResult(
            table_type=request.table_type,
            parser_options=request.parser_options,
            report=report,
            validated_row_count=len(rows),
            preflight_applied=True,
        )

    return UploadPreflightResult(
        table_type=request.table_type,
        parser_options=request.parser_options,
        report=ValidationReport(),
        validated_row_count=len(rows),
        preflight_applied=False,
    )
