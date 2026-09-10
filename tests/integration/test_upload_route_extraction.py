"""Flask route-contract tests for incrementally extracted upload endpoints."""

import importlib
import os
import unittest


def integration_is_enabled():
    """Match the safety gate used by the SMDB-dev integration checks."""
    return (
        os.environ.get("SMDB_RUN_INTEGRATION_TESTS") == "1"
        and os.environ.get("RUN_MODE", "development").lower() == "development"
        and os.environ.get("SMDB_DB_PORT", "5433") == "5433"
    )


@unittest.skipUnless(
    integration_is_enabled(),
    "set SMDB_RUN_INTEGRATION_TESTS=1 with RUN_MODE=development and SMDB_DB_PORT=5433",
)
class UploadRouteExtractionTest(unittest.TestCase):
    """Protect external behavior while routes leave the legacy module."""

    @classmethod
    def setUpClass(cls):
        cls.app_module = importlib.import_module("app")
        cls.flask_app = cls.app_module.app
        cls.flask_app.config.update(TESTING=True)

    def test_accept_warning_preserves_post_url_endpoint_and_redirect(self):
        """The duplicate-warning Continue action remains a POST to the same URL."""
        with self.flask_app.test_request_context():
            self.assertEqual(
                self.app_module.url_for("accept_warning"),
                "/accept_warning",
            )

        with self.flask_app.test_client() as client:
            response = client.post("/accept_warning", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/confirmation_request"))

    def test_upload_flow_endpoints_are_registered_from_the_route_module(self):
        """The real application keeps its public endpoint names after extraction."""
        with self.flask_app.test_request_context():
            self.assertEqual(self.app_module.url_for("upload_file"), "/upload")
            self.assertEqual(self.app_module.url_for("confirmed"), "/confirmed")

        self.assertEqual(
            self.flask_app.view_functions["accept_warning"].__module__,
            "routes.uploads",
        )
        self.assertEqual(
            self.flask_app.view_functions["upload_file"].__module__,
            "routes.uploads",
        )
        self.assertEqual(
            self.flask_app.view_functions["confirmed"].__module__,
            "routes.uploads",
        )
