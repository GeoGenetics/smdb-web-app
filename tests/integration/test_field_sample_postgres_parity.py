"""Opt-in PostgreSQL parity tests for implemented field-sample preflight rules.

Each assertion runs inside a savepoint and the outer transaction is rolled
back in ``tearDown``.  The tests therefore leave no fixture rows in SMDB-dev.
They must never be pointed at production.
"""

import os
import unittest

import psycopg2
from psycopg2 import sql

from tests.integration.fixtures.field_sample_postgres import (
    aquatic_row,
    field_sample_postgres_row,
    uncategorized_method_row,
)


INTEGRATION_OPT_IN_ENVIRONMENT_VARIABLE = "SMDB_RUN_INTEGRATION_TESTS"


def integration_is_enabled():
    """Require explicit opt-in and the standard local SMDB-dev tunnel."""
    return (
        os.environ.get(INTEGRATION_OPT_IN_ENVIRONMENT_VARIABLE) == "1"
        and os.environ.get("RUN_MODE", "development").lower() == "development"
        and os.environ.get("SMDB_DB_PORT", "5433") == "5433"
    )


def write_connection_config():
    """Build a fresh write connection without importing legacy app globals."""
    config = {
        "host": os.environ.get("SMDB_DB_HOST", "127.0.0.1"),
        "port": os.environ.get("SMDB_DB_PORT", "5433"),
        "dbname": os.environ.get("SMDB_DB_NAME", "smdb"),
        "user": os.environ.get("SMDB_DB_WRITE_USER") or os.environ.get("SMDB_DB_USER"),
    }
    password = (
        os.environ.get("SMDB_DB_WRITE_PASSWORD")
        or os.environ.get("SMDB_DB_PASSWORD")
        or os.environ.get("PGPASSWORD")
    )
    if password:
        config["password"] = password
    if not config["user"]:
        raise RuntimeError("Set SMDB_DB_WRITE_USER or SMDB_DB_USER for parity tests.")
    return config


@unittest.skipUnless(
    integration_is_enabled(),
    "set SMDB_RUN_INTEGRATION_TESTS=1 with RUN_MODE=development and SMDB_DB_PORT=5433",
)
class FieldSamplePostgresParityTest(unittest.TestCase):
    """Exercise the database authorities listed in the parity matrix."""

    def setUp(self):
        self.connection = psycopg2.connect(**write_connection_config())

    def tearDown(self):
        # Roll back successful control inserts as well as any failed test case.
        self.connection.rollback()
        self.connection.close()

    def _insert(self, row):
        columns = tuple(row)
        statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier("uploaded_data", "field_sample"),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        with self.connection.cursor() as cursor:
            cursor.execute(statement, tuple(row[column] for column in columns))

    def assert_database_accepts(self, row):
        with self.connection.cursor() as cursor:
            cursor.execute("SAVEPOINT parity_valid_case")
        try:
            self._insert(row)
        finally:
            with self.connection.cursor() as cursor:
                cursor.execute("ROLLBACK TO SAVEPOINT parity_valid_case")
                cursor.execute("RELEASE SAVEPOINT parity_valid_case")

    def assert_database_rejects(self, row, expected_message):
        with self.connection.cursor() as cursor:
            cursor.execute("SAVEPOINT parity_invalid_case")
        with self.assertRaises(psycopg2.Error) as raised:
            self._insert(row)
        self.assertIn(expected_message, str(raised.exception))
        with self.connection.cursor() as cursor:
            cursor.execute("ROLLBACK TO SAVEPOINT parity_invalid_case")
            cursor.execute("RELEASE SAVEPOINT parity_invalid_case")

    def assert_rule_parity(self, valid_row, invalid_row, expected_message):
        self.assert_database_accepts(valid_row)
        self.assert_database_rejects(invalid_row, expected_message)

    def test_template_version_required(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            field_sample_postgres_row(template_version=None),
            "template_version is required",
        )

    def test_primary_sampling_method_membership(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            field_sample_postgres_row(primary_sampling_method="Unknown synthetic method"),
            "fk_primary_sampling_method",
        )

    def test_collected_as_field_control_membership(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            field_sample_postgres_row(collected_as_field_control="Unknown synthetic control"),
            "fk_collected_as_field_control",
        )

    def test_age_interval_order(self):
        self.assert_rule_parity(
            field_sample_postgres_row(
                field_sample_age_estimate_oldest=2.0,
                field_sample_age_estimate_youngest=1.0,
            ),
            field_sample_postgres_row(
                field_sample_age_estimate_oldest=1.0,
                field_sample_age_estimate_youngest=2.0,
            ),
            "valid_age_interval_check",
        )

    def test_environment_context_pair_compatibility(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            field_sample_postgres_row(
                local_scale_environmental_context="Freshwater lake biome [ENVO:01000252]"
            ),
            "is not valid for broad_scale_environmental_context",
        )

    def test_aquatic_context_requires_water_depth(self):
        self.assert_rule_parity(
            aquatic_row(),
            aquatic_row(field_sample_water_depth=None),
            "Water depth is required",
        )

    def test_interval_method_requires_interval_depth_only(self):
        self.assert_rule_parity(
            field_sample_postgres_row(
                primary_sampling_method="Coring",
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=1.0,
                field_sampling_interval_to=2.0,
            ),
            field_sample_postgres_row(primary_sampling_method="Coring"),
            "must have interval depth and interval depth only",
        )

    def test_discrete_method_requires_discrete_depth_only(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            field_sample_postgres_row(
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=1.0,
                field_sampling_interval_to=2.0,
            ),
            "must have discrete depth and discrete depth only",
        )

    def test_filter_sampling_method_requires_no_depth(self):
        # Filter sampling has no valid database state while the separate
        # required-insert trigger unconditionally requires depth_inference_method.
        # Its database-only contradiction is recorded in the parity document.
        self.assert_database_rejects(
            field_sample_postgres_row(
                primary_sampling_method="Filter sampling",
                field_sampling_depth_discrete=1.0,
            ),
            "cannot have a depth",
        )

    def test_non_air_water_medium_requires_a_depth(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            uncategorized_method_row(
                field_sampling_depth_discrete=None,
                depth_inference_method=None,
            ),
            "At least one depth field must be filled",
        )

    def test_discrete_and_interval_depths_are_mutually_exclusive(self):
        self.assert_rule_parity(
            uncategorized_method_row(),
            uncategorized_method_row(
                field_sampling_interval_from=1.0,
                field_sampling_interval_to=2.0,
            ),
            "Discrete depth cannot be filled together",
        )

    def test_interval_depth_endpoints_must_be_paired(self):
        self.assert_rule_parity(
            uncategorized_method_row(
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=1.0,
                field_sampling_interval_to=2.0,
            ),
            uncategorized_method_row(
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=1.0,
            ),
            "must both be filled or both be empty",
        )

    def test_interval_depth_must_be_ascending(self):
        self.assert_rule_parity(
            uncategorized_method_row(
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=1.0,
                field_sampling_interval_to=2.0,
            ),
            uncategorized_method_row(
                field_sampling_depth_discrete=None,
                field_sampling_interval_from=2.0,
                field_sampling_interval_to=1.0,
            ),
            "cannot be greater than field_sampling_interval_to",
        )

    def test_depth_inference_method_is_required_with_depth(self):
        self.assert_rule_parity(
            field_sample_postgres_row(),
            field_sample_postgres_row(depth_inference_method=None),
            "depth_inference_method is required",
        )

    def test_depth_inference_method_is_not_allowed_without_depth(self):
        # No valid database control exists: the required-insert trigger demands
        # depth_inference_method while check_depth_conditionals forbids it when
        # every depth field is empty. Record the trigger's invalid behavior.
        self.assert_database_rejects(
            field_sample_postgres_row(
                primary_sampling_method="Filter sampling",
                sampling_medium="Fresh water [ENVO:00002011]",
                field_sampling_depth_discrete=None,
                depth_inference_method="Precise measurement",
            ),
            "depth_inference_method should not be filled when no depth fields are filled",
        )

    def test_other_sampling_method_requires_other_values_entry(self):
        self.assert_rule_parity(
            uncategorized_method_row(
                primary_sampling_method='Other (specify in "Other values" column)',
                other_values="Primary sampling method = Synthetic method",
            ),
            uncategorized_method_row(
                primary_sampling_method='Other (specify in "Other values" column)',
                other_values=None,
            ),
            "no corresponding entry was found",
        )
