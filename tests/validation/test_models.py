"""Phase 0 import smoke test for validation models."""

import unittest


class ValidationModelsImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from validation import models

        self.assertIsNotNone(models)
