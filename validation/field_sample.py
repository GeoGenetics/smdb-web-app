"""Pure preflight validation rules for field-sample uploads.

The functions in this module consume canonical row dictionaries *after* the
legacy parser has normalised an uploaded template. They return all detectable
findings instead of raising expected user-data errors or writing to PostgreSQL.
PostgreSQL constraints, foreign keys, and triggers remain the final integrity
boundary.
"""

from collections.abc import Iterable, Mapping
from math import isnan
from numbers import Number
import re
from typing import Any

from validation.models import ValidationError, ValidationReport
from validation.reference_data import ReferenceDataProvider


TEMPLATE_ROW_KEY = "__template_row__"

TEMPLATE_COLUMNS = {
    "field_sample_id": "Unique GeoGenetics Sample ID",
    "field_sample_running_project_title": "Running project title",
    "template_version": "Template version",
    "primary_sampling_method": "Primary sampling method",
    "collected_as_field_control": "Collected as field control",
    "field_sampling_depth_discrete": "Sampling depth (discrete)",
    "field_sampling_interval_from": "Top depth",
    "field_sampling_interval_to": "Bottom depth",
    "depth_inference_method": "Depth inference method",
    "sampling_medium": "Sampling medium",
    "other_values": "Other values",
    "field_sample_water_depth": "Water depth",
    "field_sample_age_estimate_oldest": "Oldest age estimate",
    "field_sample_age_estimate_youngest": "Youngest age estimate",
    "broad_scale_environmental_context": "Broad-scale environmental context",
    "local_scale_environmental_context": "Local-scale environmental context",
    "primary_depositional_environment": "Primary depositional field sampling environment",
    "secondary_depositional_environment": "Secondary depositional field sampling environment",
    "archaeological_registry_number": "Archaeological Site Registry Number",
    "archaeological_context_description": "Archaeological field sampling context description",
    "archaeological_context_identifier": "Archaeological Field Sampling Context Identifier",
    "feature_function_class": "Interpreted field sampling feature/function class",
}

RULE_TEMPLATE_VERSION_REQUIRED = "field_sample.template_version_required"
RULE_RUNNING_PROJECT_TITLE_REQUIRED = "field_sample.running_project_title_required"
RULE_FIELD_SAMPLE_ID_UPPERCASE = "field_sample.field_sample_id_uppercase"
RULE_FIELD_SAMPLE_ID_FORMAT_INVALID = "field_sample.field_sample_id_format_invalid"
RULE_PRIMARY_SAMPLING_METHOD_NOT_ALLOWED = (
    "field_sample.primary_sampling_method_not_allowed"
)
RULE_FIELD_CONTROL_NOT_ALLOWED = "field_sample.collected_as_field_control_not_allowed"
RULE_AGE_INTERVAL_ORDER = "field_sample.age_interval_order"
RULE_ENVIRONMENT_CONTEXT_PAIR_INVALID = "field_sample.environment_context_pair_invalid"
RULE_WATER_DEPTH_REQUIRED = "field_sample.water_depth_required_for_aquatic_context"
RULE_INTERVAL_DEPTH_ONLY = "field_sample.interval_sampling_method_requires_interval_depth_only"
RULE_DISCRETE_DEPTH_ONLY = "field_sample.discrete_sampling_method_requires_discrete_depth_only"
RULE_FILTER_SAMPLING_NO_DEPTH = "field_sample.filter_sampling_method_requires_no_depth"
RULE_DEPTH_REQUIRED = "field_sample.depth_required_for_non_air_water_medium"
RULE_DEPTH_TYPES_EXCLUSIVE = "field_sample.discrete_and_interval_depth_mutually_exclusive"
RULE_INTERVAL_ENDPOINTS_PAIRED = "field_sample.interval_depth_endpoints_must_be_paired"
RULE_INTERVAL_ASCENDING = "field_sample.interval_depth_must_be_ascending"
RULE_DEPTH_INFERENCE_REQUIRED = "field_sample.depth_inference_method_required"
RULE_DEPTH_INFERENCE_NOT_ALLOWED = "field_sample.depth_inference_method_without_depth"
RULE_OTHER_VALUES_REQUIRED = "field_sample.other_values_required_for_primary_sampling_method"
RULE_ARCHAEOLOGICAL_CONTEXT_DESCRIPTION_REQUIRED = (
    "field_sample.archaeological_context_description_required"
)
RULE_ARCHAEOLOGICAL_CONTEXT_IDENTIFIER_REQUIRED = (
    "field_sample.archaeological_context_identifier_required"
)
RULE_FEATURE_FUNCTION_CLASS_REQUIRED = "field_sample.feature_function_class_required"
RULE_ARCHAEOLOGICAL_CONTEXT_DESCRIPTION_NOT_ALLOWED = (
    "field_sample.archaeological_context_description_not_allowed"
)
RULE_ARCHAEOLOGICAL_CONTEXT_IDENTIFIER_NOT_ALLOWED = (
    "field_sample.archaeological_context_identifier_not_allowed"
)
RULE_FEATURE_FUNCTION_CLASS_NOT_ALLOWED = "field_sample.feature_function_class_not_allowed"
RULE_ARCHAEOLOGICAL_REGISTRY_NUMBER_NOT_ALLOWED = (
    "field_sample.archaeological_registry_number_not_allowed"
)

# These are the two literal categories in
# uploaded_data.check_water_depth_conditionals(), not a copied allowed-values
# list. The rule itself is database-defined as a fixed marine/freshwater pair.
WATER_DEPTH_REQUIRED_BROAD_CONTEXTS = frozenset(
    {
        "Marine biome [ENVO:00000447]",
        "Freshwater biome [ENVO:00000873]",
    }
)

# These categories mirror the literal arrays in
# uploaded_data.check_depth_conditionals(). Any other approved method follows
# the trigger's generic-depth branch, implemented in the next Phase 3 slice.
INTERVAL_SAMPLING_METHODS = frozenset(
    {"Monolith sampling", "Coring", "Bulk sampling"}
)
DISCRETE_SAMPLING_METHODS = frozenset(
    {
        "Tube sampling",
        "Syringe sampling",
        "Column sampling",
        "Scraping",
        "Block sampling",
    }
)
NO_DEPTH_SAMPLING_METHODS = frozenset({"Filter sampling"})
UNCATEGORIZED_SAMPLING_METHODS = frozenset(
    {"Other (specify in \"Other values\" column)", "Data not collected"}
)
AIR_OR_WATER_MEDIA = frozenset(
    {
        "Air [ENVO:00002005]",
        "Sea water [ENVO:00002149]",
        "Brackish water [ENVO:00002019]",
        "Fresh water [ENVO:00002011]",
        "Rainwater [ENVO:01000600]",
    }
)
OTHER_SAMPLING_METHOD = 'Other (specify in "Other values" column)'
ARCHAEOLOGICAL_DEPOSITIONAL_ENVIRONMENT = "Anthropogenic / archaeological"
ARCHAEOLOGICAL_LOCAL_CONTEXTS = frozenset(
    {
        "Anthropogenic terrestrial biome [ENVO:01000219]",
        "Archaeological site [ENVO:00000564]",
    }
)
CGG_FIELD_SAMPLE_ID_PATTERN = re.compile(r"^CGG_\d{1}_\d{6}$")
GENERAL_FIELD_SAMPLE_ID_PATTERN = re.compile(
    r"^[A-Z]{2}[A-Z0-9]{3}(?:\d{4}|UNKNOWN)\d{3}$"
)


def _is_blank(value: Any) -> bool:
    """Return whether a parser-normalised value is absent.

    The legacy float parser represents blank optional numeric cells as IEEE
    ``NaN``. Treat that parser-level missing-value marker exactly like ``None``
    or an empty template cell, rather than mistaking it for a supplied depth.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    return (
        isinstance(value, Number)
        and not isinstance(value, bool)
        and isnan(value)
    )


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


def _validate_running_project_title(row: Mapping[str, Any], report: ValidationReport) -> None:
    """Report the parser-normalised missing value rejected by the NOT NULL column."""
    value = row.get("field_sample_running_project_title")
    if not _is_blank(value):
        return

    report.add(
        ValidationError(
            rule_id=RULE_RUNNING_PROJECT_TITLE_REQUIRED,
            message="field_sample_running_project_title is required.",
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["field_sample_running_project_title"],
            database_column="field_sample_running_project_title",
            value=value,
        )
    )


def _validate_field_sample_id_format(
    row: Mapping[str, Any], report: ValidationReport
) -> None:
    """Mirror the format/uppercase branch of the ID trigger without DB lookups.

    Country-code, sample-year, uniqueness, and parent-ID checks deliberately
    remain database-backed because they depend on other columns or current
    table state.  The legacy ``CGG`` branch runs first in PostgreSQL, so it is
    intentionally checked before the general uppercase/shape branch here.
    """
    value = row.get("field_sample_id")
    if _is_blank(value):
        return

    field_sample_id = str(value)
    if field_sample_id.upper().startswith("CGG"):
        if CGG_FIELD_SAMPLE_ID_PATTERN.fullmatch(field_sample_id):
            return
        report.add(
            ValidationError(
                rule_id=RULE_FIELD_SAMPLE_ID_FORMAT_INVALID,
                message=(
                    'CGG ID has invalid format (expected CGG_X_XXXXXX).'
                ),
                template_row=_template_row(row),
                template_column=TEMPLATE_COLUMNS["field_sample_id"],
                database_column="field_sample_id",
                value=value,
            )
        )
        return

    if field_sample_id != field_sample_id.upper():
        report.add(
            ValidationError(
                rule_id=RULE_FIELD_SAMPLE_ID_UPPERCASE,
                message=f'Field sample ID must be UPPERCASE: got "{field_sample_id}".',
                template_row=_template_row(row),
                template_column=TEMPLATE_COLUMNS["field_sample_id"],
                database_column="field_sample_id",
                value=value,
            )
        )
        return

    if GENERAL_FIELD_SAMPLE_ID_PATTERN.fullmatch(field_sample_id):
        return
    report.add(
        ValidationError(
            rule_id=RULE_FIELD_SAMPLE_ID_FORMAT_INVALID,
            message=(
                "Field sample ID has invalid format "
                "(expected C{2}XXX(YYYY|UNKNOWN)NNN)."
            ),
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["field_sample_id"],
            database_column="field_sample_id",
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


def _validate_sampling_method_depth_category(
    row: Mapping[str, Any],
    report: ValidationReport,
) -> None:
    """Apply the trigger's interval, discrete, and no-depth category rules.

    Approved methods outside those fixed database arrays deliberately produce
    no category finding here. They are handled by the generic depth rules in a
    later Phase 3 checkpoint.
    """
    method = row.get("primary_sampling_method")
    discrete_depth = row.get("field_sampling_depth_discrete")
    interval_from = row.get("field_sampling_interval_from")
    interval_to = row.get("field_sampling_interval_to")
    has_discrete_depth = not _is_blank(discrete_depth)
    has_interval_from = not _is_blank(interval_from)
    has_interval_to = not _is_blank(interval_to)

    if method in INTERVAL_SAMPLING_METHODS:
        if not (not has_discrete_depth and has_interval_from and has_interval_to):
            report.add(
                ValidationError(
                    rule_id=RULE_INTERVAL_DEPTH_ONLY,
                    message=(
                        f"Samples collected using {method} must have interval depth "
                        "and interval depth only."
                    ),
                    template_row=_template_row(row),
                    template_column=TEMPLATE_COLUMNS["primary_sampling_method"],
                    database_column="primary_sampling_method",
                    value=method,
                    value_label="Selected primary sampling method",
                )
            )
        return

    if method in DISCRETE_SAMPLING_METHODS:
        if not (has_discrete_depth and not has_interval_from and not has_interval_to):
            report.add(
                ValidationError(
                    rule_id=RULE_DISCRETE_DEPTH_ONLY,
                    message=(
                        f"Samples collected using {method} must have discrete depth "
                        "and discrete depth only."
                    ),
                    template_row=_template_row(row),
                    template_column=TEMPLATE_COLUMNS["primary_sampling_method"],
                    database_column="primary_sampling_method",
                    value=method,
                    value_label="Selected primary sampling method",
                )
            )
        return

    if method in NO_DEPTH_SAMPLING_METHODS and (
        has_discrete_depth or has_interval_from or has_interval_to
    ):
        report.add(
            ValidationError(
                rule_id=RULE_FILTER_SAMPLING_NO_DEPTH,
                message=(
                    f"Samples collected using {method} cannot have a depth. "
                    "Use water depth and/or elevation instead."
                ),
                template_row=_template_row(row),
                template_column=TEMPLATE_COLUMNS["primary_sampling_method"],
                database_column="primary_sampling_method",
                value=method,
                value_label="Selected primary sampling method",
            )
        )
        return

    if method in UNCATEGORIZED_SAMPLING_METHODS:
        # Explicitly preserve the production fix for Other and Data not
        # collected: neither receives an "unknown method" category error.
        return


def _validate_generic_depth_rules(
    row: Mapping[str, Any],
    report: ValidationReport,
) -> None:
    """Apply the non-category-specific checks from check_depth_conditionals."""
    discrete_depth = row.get("field_sampling_depth_discrete")
    interval_from = row.get("field_sampling_interval_from")
    interval_to = row.get("field_sampling_interval_to")
    depth_inference_method = row.get("depth_inference_method")
    sampling_medium = row.get("sampling_medium")
    has_discrete_depth = not _is_blank(discrete_depth)
    has_interval_from = not _is_blank(interval_from)
    has_interval_to = not _is_blank(interval_to)
    has_any_depth = has_discrete_depth or has_interval_from or has_interval_to
    template_row = _template_row(row)

    if (
        not has_any_depth
        and not _is_blank(sampling_medium)
        and sampling_medium not in AIR_OR_WATER_MEDIA
    ):
        report.add(
            ValidationError(
                rule_id=RULE_DEPTH_REQUIRED,
                message=(
                    "At least one depth field must be filled when sampling_medium "
                    "is not air or water type."
                ),
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS["sampling_medium"],
                database_column="sampling_medium",
                value=sampling_medium,
            )
        )

    if has_discrete_depth and (has_interval_from or has_interval_to):
        report.add(
            ValidationError(
                rule_id=RULE_DEPTH_TYPES_EXCLUSIVE,
                message=(
                    "Discrete depth cannot be filled together with top depth "
                    "(field_sampling_interval_from) or bottom depth "
                    "(field_sampling_interval_to)."
                ),
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS["field_sampling_depth_discrete"],
                database_column="field_sampling_depth_discrete",
                value=discrete_depth,
            )
        )

    if has_interval_from != has_interval_to:
        report.add(
            ValidationError(
                rule_id=RULE_INTERVAL_ENDPOINTS_PAIRED,
                message=(
                    "field_sampling_interval_from and field_sampling_interval_to "
                    "must both be filled or both be empty."
                ),
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS["field_sampling_interval_from"],
                database_column="field_sampling_interval_from",
                value=interval_from,
            )
        )

    if (
        has_interval_from
        and has_interval_to
        and isinstance(interval_from, Number)
        and not isinstance(interval_from, bool)
        and isinstance(interval_to, Number)
        and not isinstance(interval_to, bool)
        and interval_from > interval_to
    ):
        report.add(
            ValidationError(
                rule_id=RULE_INTERVAL_ASCENDING,
                message=(
                    f"field_sampling_interval_from ({interval_from}) cannot be "
                    f"greater than field_sampling_interval_to ({interval_to})."
                ),
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS["field_sampling_interval_from"],
                database_column="field_sampling_interval_from",
                value=interval_from,
            )
        )

    # This uses the trigger's precise condition: discrete depth or top depth,
    # rather than bottom depth alone, requires a depth inference method.
    if (has_discrete_depth or has_interval_from) and _is_blank(depth_inference_method):
        report.add(
            ValidationError(
                rule_id=RULE_DEPTH_INFERENCE_REQUIRED,
                message="depth_inference_method is required when any depth field is filled.",
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS["depth_inference_method"],
                database_column="depth_inference_method",
                value=depth_inference_method,
            )
        )

    if not has_any_depth and not _is_blank(depth_inference_method):
        report.add(
            ValidationError(
                rule_id=RULE_DEPTH_INFERENCE_NOT_ALLOWED,
                message="depth_inference_method should not be filled when no depth fields are filled.",
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS["depth_inference_method"],
                database_column="depth_inference_method",
                value=depth_inference_method,
            )
        )


def _validate_other_values_requirement(
    row: Mapping[str, Any],
    report: ValidationReport,
) -> None:
    """Require a nonblank Other values entry for primary_sampling_method=Other."""
    if (
        row.get("primary_sampling_method") != OTHER_SAMPLING_METHOD
        or not _is_blank(row.get("other_values"))
    ):
        return

    report.add(
        ValidationError(
            rule_id=RULE_OTHER_VALUES_REQUIRED,
            message=(
                'Column "primary_sampling_method" is set to '
                '"Other (specify in \"Other values\" column)" but no '
                'corresponding entry was found in "other_values".'
            ),
            template_row=_template_row(row),
            template_column=TEMPLATE_COLUMNS["other_values"],
            database_column="other_values",
            value=row.get("other_values"),
        )
    )


def _validate_archaeological_conditionals(
    row: Mapping[str, Any], report: ValidationReport
) -> None:
    """Mirror ``check_archaeological_conditionals`` without short-circuiting.

    PostgreSQL raises only the first missing or disallowed archaeological field.
    Preflight intentionally returns every independent finding so that a user can
    correct an archaeological row, or remove accidental archaeological values
    from a non-archaeological row, in one edit cycle.
    """
    # Preserve SQL's three-valued OR semantics. In the trigger, a NULL
    # secondary depositional environment makes ``false OR NULL OR false``
    # evaluate to NULL; both following ``IF`` branches are then skipped. This
    # surprising database behavior is covered by the SMDB-dev parity tests and
    # must not turn into a preflight-only rejection.
    def equals_archaeological_environment(value: Any) -> bool | None:
        if _is_blank(value):
            return None
        return value == ARCHAEOLOGICAL_DEPOSITIONAL_ENVIRONMENT

    def is_archaeological_local_context(value: Any) -> bool | None:
        if _is_blank(value):
            return None
        return value in ARCHAEOLOGICAL_LOCAL_CONTEXTS

    conditions = (
        equals_archaeological_environment(
            row.get("primary_depositional_environment")
        ),
        equals_archaeological_environment(
            row.get("secondary_depositional_environment")
        ),
        is_archaeological_local_context(row.get("local_scale_environmental_context")),
    )
    if True in conditions:
        is_archaeological: bool | None = True
    elif None in conditions:
        is_archaeological = None
    else:
        is_archaeological = False
    template_row = _template_row(row)

    if is_archaeological is True:
        required_fields = (
            (
                "archaeological_context_description",
                RULE_ARCHAEOLOGICAL_CONTEXT_DESCRIPTION_REQUIRED,
            ),
            (
                "archaeological_context_identifier",
                RULE_ARCHAEOLOGICAL_CONTEXT_IDENTIFIER_REQUIRED,
            ),
            ("feature_function_class", RULE_FEATURE_FUNCTION_CLASS_REQUIRED),
        )
        for column, rule_id in required_fields:
            value = row.get(column)
            if not _is_blank(value):
                continue
            report.add(
                ValidationError(
                    rule_id=rule_id,
                    message=(
                        f"{column} is required when the depositional environment "
                        "is anthropogenic or archaeological."
                    ),
                    template_row=template_row,
                    template_column=TEMPLATE_COLUMNS[column],
                    database_column=column,
                    value=value,
                )
            )
        return

    # As in PL/pgSQL, ``IF NOT NULL`` does not execute. Only an explicitly
    # false condition reaches the trigger's non-archaeological branch.
    if is_archaeological is not False:
        return

    disallowed_fields = (
        (
            "archaeological_context_description",
            RULE_ARCHAEOLOGICAL_CONTEXT_DESCRIPTION_NOT_ALLOWED,
        ),
        (
            "archaeological_context_identifier",
            RULE_ARCHAEOLOGICAL_CONTEXT_IDENTIFIER_NOT_ALLOWED,
        ),
        ("feature_function_class", RULE_FEATURE_FUNCTION_CLASS_NOT_ALLOWED),
        (
            "archaeological_registry_number",
            RULE_ARCHAEOLOGICAL_REGISTRY_NUMBER_NOT_ALLOWED,
        ),
    )
    for column, rule_id in disallowed_fields:
        value = row.get(column)
        if _is_blank(value):
            continue
        database_column = (
            "archaeological_site_registry_number"
            if column == "archaeological_registry_number"
            else column
        )
        report.add(
            ValidationError(
                rule_id=rule_id,
                message=(
                    f"{database_column} was filled but no environment was set to "
                    "anthropogenic or archaeological."
                ),
                template_row=template_row,
                template_column=TEMPLATE_COLUMNS[column],
                database_column=column,
                value=value,
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
        _validate_running_project_title(row, report)
        _validate_field_sample_id_format(row, report)
        _validate_primary_sampling_method(row, report, reference_data)
        _validate_field_control(row, report, reference_data)
        _validate_age_interval(row, report)
        _validate_environment_context_pair(row, report, reference_data)
        _validate_water_depth_requirement(row, report)
        _validate_sampling_method_depth_category(row, report)
        _validate_generic_depth_rules(row, report)
        _validate_other_values_requirement(row, report)
        _validate_archaeological_conditionals(row, report)
    return report
