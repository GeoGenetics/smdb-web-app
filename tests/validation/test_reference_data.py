"""Tests for the reference-data validation boundary."""

import unittest

from validation.reference_data import (
    ENVIRONMENT_CONTEXT_PAIR_QUERY,
    FIELD_CONTROLS_QUERY,
    FIELD_SAMPLING_METHODS_QUERY,
    InMemoryReferenceDataProvider,
    PostgresReferenceDataProvider,
    ReferenceDataProvider,
    ReferenceDataLookupError,
    WorkflowCachedReferenceDataProvider,
)
from tests.validation.fixtures import common_reference_data


class TestReferenceDataProvider:
    """Minimal local implementation used only to test the protocol contract."""

    def field_sampling_methods(self):
        return frozenset({"Tube sampling"})

    def field_controls(self):
        return frozenset({"No", "Yes"})

    def depth_inference_methods(self):
        return frozenset({"Precise measurement"})

    def has_environment_context_pair(self, *, local_context, broad_context):
        return (
            local_context,
            broad_context,
        ) == (
            "Forest biome [ENVO:01000174]",
            "Terrestrial biome [ENVO:00000446]",
        )


class FakeCursor:
    def __init__(self, *, rows=(), row=None):
        self.rows = rows
        self.row = row
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=None):
        self.executions.append((query, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


class FailingCursor(FakeCursor):
    def execute(self, query, params=None):
        raise OSError("simulated database failure")


class CountingReferenceDataProvider:
    """Test double that records each delegated lookup."""

    def __init__(self):
        self.calls = {
            "field_sampling_methods": 0,
            "field_controls": 0,
            "depth_inference_methods": 0,
            "environment_context_pair": 0,
        }

    def field_sampling_methods(self):
        self.calls["field_sampling_methods"] += 1
        return {"Tube sampling"}

    def field_controls(self):
        self.calls["field_controls"] += 1
        return {"No", "Yes"}

    def depth_inference_methods(self):
        self.calls["depth_inference_methods"] += 1
        return {"Precise measurement"}

    def has_environment_context_pair(self, *, local_context, broad_context):
        self.calls["environment_context_pair"] += 1
        return local_context == "Forest" and broad_context == "Terrestrial"


class ReferenceDataImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from validation import reference_data

        self.assertIsNotNone(reference_data)

    def test_local_implementation_matches_the_provider_contract(self):
        provider = TestReferenceDataProvider()

        self.assertIsInstance(provider, ReferenceDataProvider)
        self.assertIn("Tube sampling", provider.field_sampling_methods())
        self.assertTrue(
            provider.has_environment_context_pair(
                local_context="Forest biome [ENVO:01000174]",
                broad_context="Terrestrial biome [ENVO:00000446]",
            )
        )

    def test_postgres_provider_reads_values_and_closes_the_connection(self):
        cursor = FakeCursor(rows=[("Tube sampling",), ("Coring",)])
        connection = FakeConnection(cursor)
        provider = PostgresReferenceDataProvider(lambda: connection)

        values = provider.field_sampling_methods()

        self.assertIsInstance(provider, ReferenceDataProvider)
        self.assertEqual(values, frozenset({"Tube sampling", "Coring"}))
        self.assertEqual(cursor.executions, [(FIELD_SAMPLING_METHODS_QUERY, None)])
        self.assertTrue(connection.closed)

    def test_postgres_provider_uses_parameterized_environment_pair_query(self):
        cursor = FakeCursor(row=(True,))
        connection = FakeConnection(cursor)
        provider = PostgresReferenceDataProvider(lambda: connection)

        is_valid = provider.has_environment_context_pair(
            local_context="Freshwater lake biome [ENVO:01000252]",
            broad_context="Freshwater biome [ENVO:00000873]",
        )

        self.assertTrue(is_valid)
        self.assertEqual(
            cursor.executions,
            [
                (
                    ENVIRONMENT_CONTEXT_PAIR_QUERY,
                    (
                        "Freshwater lake biome [ENVO:01000252]",
                        "Freshwater biome [ENVO:00000873]",
                    ),
                )
            ],
        )
        self.assertTrue(connection.closed)

    def test_postgres_provider_exposes_each_explicit_reference_table(self):
        cursor = FakeCursor(rows=[("No",), ("Yes",)])
        connection = FakeConnection(cursor)
        provider = PostgresReferenceDataProvider(lambda: connection)

        self.assertEqual(provider.field_controls(), frozenset({"No", "Yes"}))
        self.assertEqual(cursor.executions, [(FIELD_CONTROLS_QUERY, None)])

    def test_postgres_provider_raises_predictable_error_for_connection_failure(self):
        def failing_connection_factory():
            raise ConnectionError("simulated connection failure")

        provider = PostgresReferenceDataProvider(failing_connection_factory)

        with self.assertRaises(ReferenceDataLookupError) as captured:
            provider.field_sampling_methods()

        self.assertEqual(
            captured.exception.lookup_name,
            "allowed_values.field_sampling_method",
        )
        self.assertIsInstance(captured.exception.__cause__, ConnectionError)

    def test_postgres_provider_never_treats_query_failure_as_invalid_context(self):
        connection = FakeConnection(FailingCursor())
        provider = PostgresReferenceDataProvider(lambda: connection)

        with self.assertRaises(ReferenceDataLookupError) as captured:
            provider.has_environment_context_pair(
                local_context="Forest biome [ENVO:01000174]",
                broad_context="Terrestrial biome [ENVO:00000446]",
            )

        self.assertEqual(
            captured.exception.lookup_name,
            "allowed_values.local_env_context",
        )
        self.assertIsInstance(captured.exception.__cause__, OSError)
        self.assertTrue(connection.closed)


class InMemoryReferenceDataProviderTest(unittest.TestCase):
    @staticmethod
    def provider_from_common_fixture():
        reference_data = common_reference_data()
        return InMemoryReferenceDataProvider(
            field_sampling_method_values=reference_data["field_sampling_methods"],
            field_control_values=reference_data["field_controls"],
            depth_inference_method_values=reference_data["depth_inference_methods"],
            environment_context_pairs=reference_data["environment_context_pairs"],
        )

    def test_implements_the_reference_data_provider_contract(self):
        provider = self.provider_from_common_fixture()

        self.assertIsInstance(provider, ReferenceDataProvider)
        self.assertIn("Data not collected", provider.field_sampling_methods())
        self.assertEqual(provider.field_controls(), frozenset({"Yes", "No"}))

    def test_context_pair_lookup_supports_valid_and_invalid_pairs(self):
        provider = self.provider_from_common_fixture()

        self.assertTrue(
            provider.has_environment_context_pair(
                local_context="Freshwater lake biome [ENVO:01000252]",
                broad_context="Freshwater biome [ENVO:00000873]",
            )
        )
        self.assertFalse(
            provider.has_environment_context_pair(
                local_context="Freshwater lake biome [ENVO:01000252]",
                broad_context="Terrestrial biome [ENVO:00000446]",
            )
        )

    def test_provider_snapshots_mutable_input_values(self):
        methods = {"Tube sampling"}
        provider = InMemoryReferenceDataProvider(
            field_sampling_method_values=methods,
        )

        methods.add("Coring")

        self.assertEqual(provider.field_sampling_methods(), frozenset({"Tube sampling"}))


class WorkflowCachedReferenceDataProviderTest(unittest.TestCase):
    def test_caches_each_value_lookup_within_one_workflow(self):
        source = CountingReferenceDataProvider()
        provider = WorkflowCachedReferenceDataProvider(source)

        self.assertIsInstance(provider, ReferenceDataProvider)
        self.assertEqual(provider.field_sampling_methods(), frozenset({"Tube sampling"}))
        self.assertEqual(provider.field_sampling_methods(), frozenset({"Tube sampling"}))
        self.assertEqual(provider.field_controls(), frozenset({"No", "Yes"}))
        self.assertEqual(provider.field_controls(), frozenset({"No", "Yes"}))
        self.assertEqual(
            provider.depth_inference_methods(), frozenset({"Precise measurement"})
        )
        self.assertEqual(
            provider.depth_inference_methods(), frozenset({"Precise measurement"})
        )
        self.assertEqual(
            source.calls,
            {
                "field_sampling_methods": 1,
                "field_controls": 1,
                "depth_inference_methods": 1,
                "environment_context_pair": 0,
            },
        )

    def test_caches_environment_context_pairs_independently(self):
        source = CountingReferenceDataProvider()
        provider = WorkflowCachedReferenceDataProvider(source)

        self.assertTrue(
            provider.has_environment_context_pair(
                local_context="Forest",
                broad_context="Terrestrial",
            )
        )
        self.assertTrue(
            provider.has_environment_context_pair(
                local_context="Forest",
                broad_context="Terrestrial",
            )
        )
        self.assertFalse(
            provider.has_environment_context_pair(
                local_context="Lake",
                broad_context="Freshwater",
            )
        )
        self.assertEqual(source.calls["environment_context_pair"], 2)

    def test_separate_workflows_do_not_share_cache_state(self):
        source = CountingReferenceDataProvider()
        first_workflow = WorkflowCachedReferenceDataProvider(source)
        second_workflow = WorkflowCachedReferenceDataProvider(source)

        first_workflow.field_sampling_methods()
        second_workflow.field_sampling_methods()

        self.assertEqual(source.calls["field_sampling_methods"], 2)
