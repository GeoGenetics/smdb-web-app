"""Synthetic field-sample rows for preflight-validation unit tests.

These fixtures are deliberately fictional and contain no production-derived
sample, project, location, or personal data. Values use canonical database
column names after parser normalization.
"""


REFERENCE_DATA_UNAVAILABLE = object()


def common_reference_data():
    """Return independent, minimal reference data for validation unit tests.

    The shape is intentionally simple while Phase 1 establishes fixtures. The
    Phase 2 provider interface will consume the same concepts through a typed
    boundary rather than embedding these values in production validation code.
    """
    return {
        "field_sampling_methods": frozenset(
            {
                "Tube sampling",
                "Coring",
                "Filter sampling",
                "Data not collected",
                'Other (specify in "Other values" column)',
            }
        ),
        "field_controls": frozenset({"Yes", "No"}),
        "depth_inference_methods": frozenset(
            {"Precise measurement", "Data not collected"}
        ),
        "environment_context_pairs": frozenset(
            {
                (
                    "Forest biome [ENVO:01000174]",
                    "Terrestrial biome [ENVO:00000446]",
                ),
                (
                    "Freshwater lake biome [ENVO:01000252]",
                    "Freshwater biome [ENVO:00000873]",
                ),
            }
        ),
        "water_depth_broad_contexts": frozenset(
            {
                "Freshwater biome [ENVO:00000873]",
                "Marine biome [ENVO:00000447]",
            }
        ),
    }


def missing_reference_data():
    """Return reference data with a deliberately empty field-control lookup."""
    reference_data = common_reference_data()
    reference_data["field_controls"] = frozenset()
    return reference_data


def unavailable_reference_data():
    """Return a sentinel representing a failed reference-data lookup."""
    return REFERENCE_DATA_UNAVAILABLE


def field_sample_row(**overrides):
    """Return an independent, valid baseline row for future rule tests."""
    row = {
        "__template_row__": 11,
        "field_sample_id": "TEST_FIELD_SAMPLE_001",
        "template_version": "Version: test",
        "primary_sampling_method": "Tube sampling",
        "other_values": None,
        "sampling_medium": "Sediment [ENVO:00002007]",
        "field_sampling_depth_discrete": 10.0,
        "field_sampling_interval_from": None,
        "field_sampling_interval_to": None,
        "depth_inference_method": "Precise measurement",
        "field_sample_water_depth": None,
        "field_sample_age_estimate_oldest": 2.0,
        "field_sample_age_estimate_youngest": 1.0,
        "broad_scale_environmental_context": "Terrestrial biome [ENVO:00000446]",
        "local_scale_environmental_context": "Forest biome [ENVO:01000174]",
        "collected_as_field_control": "No",
    }
    row.update(overrides)
    return row


def invalid_age_interval_row():
    """Return a row whose oldest age is younger than its youngest age."""
    return field_sample_row(
        field_sample_age_estimate_oldest=1.0,
        field_sample_age_estimate_youngest=2.0,
    )


def invalid_mixed_depth_row():
    """Return a row with both discrete and interval depths populated."""
    return field_sample_row(
        field_sampling_interval_from=0.0,
        field_sampling_interval_to=10.0,
    )
