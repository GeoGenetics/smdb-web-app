"""Database-valid, fictional field-sample rows for SMDB-dev parity tests.

These fixtures are deliberately separate from ``tests.validation.fixtures``:
they exercise PostgreSQL's real table, foreign keys, and triggers.  No values
come from production application data; categorical values are part of the
versioned SMDB-dev reference-data snapshot.
"""

from datetime import date
from uuid import uuid4


PERSON = "Synthetic Tester, synthetic.tester@example.org, SMDB"


def field_sample_postgres_row(**overrides):
    """Return one complete synthetic row accepted by the field-sample schema.

    A ``CGG`` identifier intentionally uses the database's documented test-ID
    branch.  Every invocation receives a new identifier and upload UUID.
    """
    sample_number = uuid4().int % 1_000_000
    field_sample_id = f"CGG_1_{sample_number:06d}"
    row = {
        "field_sample_id": field_sample_id,
        "field_sample_country_region": "Denmark",
        "field_sample_site_name": "Synthetic SMDB-dev site",
        "latitude": 55.6761,
        "longitude": 12.5683,
        "field_sample_sample_date": date.today(),
        "field_sample_running_project_title": "SMDB-dev parity tests",
        "field_sampling_depth_discrete": 1.0,
        "field_sampling_interval_to": None,
        "field_sample_water_depth": None,
        "field_sample_age_estimate_oldest": 2.0,
        "field_sample_storage_setting": "Data not collected",
        "field_sample_storage_location": "Data not collected",
        # Pass the canonical text representation so this fixture has no
        # driver-specific UUID-adapter dependency.
        "upload_uuid": str(uuid4()),
        "field_sampling_interval_from": None,
        "field_sample_age_estimate_youngest": 1.0,
        "field_sample_pi": PERSON,
        "field_sample_master_id": f"{field_sample_id}M",
        "field_sample_label_informal": "Synthetic parity fixture",
        "field_sample_biggest_container_stored_at_globe": "Data not collected",
        "field_sample_age_estimate_unit": "ka BP",
        "geographical_location_names": "Synthetic SMDB-dev location",
        "sample_created_from": "Field sampling",
        "part_of_aegis": "No",
        "coordinates_inference_method": "Map reading",
        "elevation_inference_method": "Map reading",
        "depth_inference_method": "Precise measurement",
        "sample_description": "Synthetic field-sample parity fixture.",
        "age_inference_method": "Previous investigations",
        "primary_sampling_method": "Tube sampling",
        "collected_as_field_control": "No",
        "sampling_responsible": PERSON,
        "sampling_institution": "GeoGenetics, Globe, University of Copenhagen",
        "field_trip_staff": PERSON,
        "sampling_medium": "Sediment [ENVO:00002007]",
        "broad_scale_environmental_context": "Terrestrial biome [ENVO:00000446]",
        "local_scale_environmental_context": "Forest biome [ENVO:01000174]",
        "primary_depositional_environment": "Lacustrine",
        "permafrosted": "No",
        "template_fillers": PERSON,
        "sample_contacts": PERSON,
        "acquisition_type": "Field sampling",
        "template_version": "Version: synthetic-parity-test",
    }
    row.update(overrides)
    return row


def aquatic_row(**overrides):
    """Return a valid freshwater variation of the synthetic baseline."""
    row = field_sample_postgres_row(
        broad_scale_environmental_context="Freshwater biome [ENVO:00000873]",
        local_scale_environmental_context="Freshwater lake biome [ENVO:01000252]",
        field_sample_water_depth=1.0,
    )
    row.update(overrides)
    return row


def uncategorized_method_row(**overrides):
    """Return a baseline for generic depth rules, outside fixed categories."""
    row = field_sample_postgres_row(primary_sampling_method="Data not collected")
    row.update(overrides)
    return row
