"""Tests for the reference-data validation boundary."""

import unittest

from validation.reference_data import ReferenceDataProvider


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
