"""Phase 0 import smoke test for reference-data validation."""

import unittest


class ReferenceDataImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from validation import reference_data

        self.assertIsNotNone(reference_data)
