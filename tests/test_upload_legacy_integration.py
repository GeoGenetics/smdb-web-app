"""Status marker for the legacy upload-route integration test.

The previous placeholder test imported app.py, required a live database, and
referenced nonexistent files and a nonexistent table. It did not provide
reliable coverage. Proper upload-route tests will be introduced in Phase 5
after the upload workflow can be injected and tested deterministically.
"""

import unittest


@unittest.skip(
    "Legacy upload-route test deferred until Phase 5 dependency injection."
)
class LegacyUploadRouteIntegrationTest(unittest.TestCase):
    def test_upload_route_placeholder(self):
        """Reserved for a deterministic Flask test-client upload test."""
