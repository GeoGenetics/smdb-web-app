"""Phase 0 import smoke test for upload-workflow services."""

import unittest


class UploadWorkflowImportTest(unittest.TestCase):
    def test_module_imports_without_flask_or_database_access(self):
        from services import upload_workflow

        self.assertIsNotNone(upload_workflow)
