"""Phase 0 import smoke test for field-sample validation."""

import unittest


class FieldSampleValidationImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from validation import field_sample

        self.assertIsNotNone(field_sample)
