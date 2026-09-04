"""Pure preflight validation rules for field-sample uploads.

The functions in this module consume canonical row dictionaries *after* the
legacy parser has normalised an uploaded template. They return all detectable
findings instead of raising expected user-data errors or writing to PostgreSQL.
PostgreSQL constraints, foreign keys, and triggers remain the final integrity
boundary.
"""

from collections.abc import Iterable, Mapping
from numbers import Number
from typing import Any

from validation.models import ValidationError, ValidationReport
from validation.reference_data import ReferenceDataProvider


TEMPLATE_ROW_KEY = "__template_row__"

TEMPLATE_COLUMNS = {
    "template_version": "Template version",
    "primary_sampling_method": "Primary sampling method",
    "collected_as_field_control": "Collected as field control",
    "field_sample_water_depth": "Water depth",
    "field_sample_age_estimate_oldest": "Oldest age estimate",
    "field_sample_age_estimate_youngest": "Youngest age estimate",
    "broad_scale_environmental_context": "Broad-scale environmental context",
    "local_scale_environmental_context": "Local-scale environmental context",
}

RULE_TEMPLATE_VERSION_REQUIRED = "field_sample.template_version_required"
RULE_PRIMARY_SAMPLING_METHOD_NOT_ALLOWED = (
    "field_sample.primary_sampling_method_not_allowed"
)
RULE_FIELD_CONTROL_NOT_ALLOWED = "field_sample.collected_as_field_control_not_allowed"
RULE_AGE_INTERVAL_ORDER = "field_sample.age_interval_order"
RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID = "field_sample.environment_context_pair_invalid"
RULE_WATER_DEPTH_REQUIRED = "field_sample.water_depth_required_for_aquatic_context"

# These are the two literal categories in
# uploaded_data.check_water_depth_conditionals(), not a copied allowed-values
# list. The rule itself is database-defined as a fixed marine/freshwater pair.
WATER_DEPTH_REQUIRED_BROAD_CONTEXTS = frozenset(
    {
        "Marine biome [ENVO:00000447]",
        "Freshwater biome [ENVO:00000873]",
    }
)


def _is_blank(value: Any) -> bool:
    """Return whether a parser-normalised value is absent."""
    return value is None or (isinstance(value, str) and not value.strip())


def _template_row(row: Mapping[str, Any]) -> int | None:
    """Return a valid user-visible row number without failing validation."""
    value = row.get(TEMPLATE_ROW_KEY)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _add_membership_error(
    report: ValidationReport,
    *,
    row: Mapping[str, Any],
    column: str,
    value: Any,
    allowed_values: Iterable[str],
    rule_id: str,
) -> None:
    """Add one foreign-key-style finding when a nonblank value is unknown."""
    if _is_blank(value) or value in allowed_values:
        return

    report.add(
        ValidationError(
            rule_id=rule_id,
            message=f"{column} ({value}) is not present in its allowed-values table.",
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS[column],
            database_column=column,
            value=value,
        )
    )


def _validate_template_version(row: Mapping[str, Any], report: ValidationReport) -> None:
    value = row.get("template_version")
    if not _is_blank(value):
        return

    report.add(
        ValidationError(
            rule_id=RULE_TEMPLATE_VERSION_REQUIRED,
            message="template_version is required.",
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["template_version"],
            database_column="template_version",
            value=value,
        )
    )


def _validate_primary_sampling_method(
    row: Mapping[str, Any],
    report: ValidationReport,
    reference_data: ReferenceDataProvider,
) -> None:
    _add_membership_error(
        report,
        row=row,
        column="primary_sampling_method",
        value=row.get("primary_sampling_method"),
        allowed_values=reference_data.field_sampling_methods(),
        rule_id=RULE_PRIMARY_SAMPLING_METHOD_NOT_ALLOWED,
    )


def _validate_field_control(
    row: Mapping[str, Any],
    report: ValidationReport,
    reference_data: ReferenceDataProvider,
) -> None:
    _add_membership_error(
        report,
        row=row,
        column="collected_as_field_control",
        value=row.get("collected_as_field_control"),
        allowed_values=reference_data.field_controls(),
        rule_id=RULE_FIELD_CONTROL_NOT_ALLOWED,
    )


def _validate_age_interval(row: Mapping[str, Any], report: ValidationReport) -> None:
    oldest = row.get("field_sample_age_estimate_oldest")
    youngest = row.get("field_sample_age_estimate_youngest")

    # PostgreSQL CHECK constraints pass when an expression evaluates to NULL.
    # The legacy parser remains responsible for reporting non-numeric input.
    if (
        _is_blank(oldest)
        or _is_blank(youngest)
        or not isinstance(oldest, Number)
        or isinstance(oldest, bool)
        or not isinstance(youngest, Number)
        or isinstance(youngest, bool)
        or oldest >= youngest
    ):
        return

    report.add(
        ValidationError(
            rule_id=RULE_AGE_INTERVAL_ORDER,
            message=(
                "field_sample_age_estimate_oldest must be greater than or equal "
                "to field_sample_age_estimate_youngest."
            ),
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["field_sample_age_estimate_oldest"],
            database_column="field_sample_age_estimate_oldest",
            value=oldest,
        )
    )


def _validate_environment_context_pair(
    row: Mapping[str, Any],
    report: ValidationReport,
    reference_data: ReferenceDataProvider,
) -> None:
    local_context = row.get("local_scale_environmental_context")
    broad_context = row.get("broad_scale_environmental_context")

    # The database trigger rejects a missing component too: its SELECT EXISTS
    # expression is false when either value is NULL. Avoid a provider query for
    # blank values while retaining that user-visible outcome.
    pair_is_valid = (
        not _is_blank(local_context)
        and not _is_blank(broad_context)
        and reference_data.has_environment_context_pair(
            local_context=str(local_context),
            broad_context=str(broad_context),
        )
    )
    if pair_is_valid:
        return

    report.add(
        ValidationError(
            rule_id=RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID,
            message=(
                "local_scale_environmental_context "
                f"({local_context}) is not valid for "
                f"broad_scale_environmental_context ({broad_context})."
            ),
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["local_scale_environmental_context"],
            database_column="local_scale_environmental_context",
            value=local_context,
        )
    )


def _validate_water_depth_requirement(
    row: Mapping[str, Any],
    report: ValidationReport,
) -> None:
    broad_context = row.get("broad_scale_environmental_context")
    water_depth = row.get("field_sample_water_depth")
    if (
        broad_context not in WATER_DEPTH_REQUIRED_BROAD_CONTEXTS
        or not _is_blank(water_depth)
    ):
        return

    report.add(
        ValidationError(
            rule_id=RULE_WATER_DEPTH_REQUIRED,
            message=(
                "Water depth is required when broad_scale_environmental_context "
                "is marine or freshwater."
            ),
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["field_sample_water_depth"],
            database_column="field_sample_water_depth",
            value=water_depth,
        )
    )


def validate_field_sample_rows(
    rows: Iterable[Mapping[str, Any]],
    reference_data: ReferenceDataProvider,
) -> ValidationReport:
    """Return aggregate findings for the implemented field-sample rules.

    Rules intentionally do not short-circuit: every row and every independent
    rule is assessed so users can correct multiple issues in one iteration.
    Reference-data provider failures intentionally propagate rather than being
    misreported as invalid user data.
    """
    report = ValidationReport()
    for row in rows:
        _validate_template_version(row, report)
        _validate_primary_sampling_method(row, report, reference_data)
        _validate_field_control(row, report, reference_data)
        _validate_age_interval(row, report)
        _validate_environment_context_pair(row, report, reference_data)
        _validate_water_depth_requirement(row, report)
    return report
