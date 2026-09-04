"""Tests that pure validation modules have no runtime-configuration import."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SMDB_ENVIRONMENT_VARIABLES = {
    "RUN_MODE",
    "SMDB_DB_NAME",
    "SMDB_DB_HOST",
    "SMDB_DB_PORT",
    "SMDB_DB_SCHEMA",
    "SMDB_DB_USER",
    "SMDB_DB_PASSWORD",
    "SMDB_DB_READ_USER",
    "SMDB_DB_READ_PASSWORD",
    "SMDB_DB_WRITE_USER",
    "SMDB_DB_WRITE_PASSWORD",
    "PGPASSWORD",
}


class ValidationImportBoundaryTest(unittest.TestCase):
    def test_validation_modules_import_without_database_configuration(self):
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in SMDB_ENVIRONMENT_VARIABLES
        }

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import validation.models; import validation.field_sample; "
                "import validation.reference_data",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
