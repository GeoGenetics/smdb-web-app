"""Contract tests for routes owned by :mod:`routes.uploads`."""

import unittest

from flask import Flask

from routes.uploads import register_upload_routes


def no_op_log_info(_app):
    """Return a decorator with no logging side effect for route registration."""

    def decorator(view):
        return view

    return decorator


class UploadRouteRegistrationTest(unittest.TestCase):
    """Verify extracted routes retain their original Flask contract."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.app.add_url_rule(
            "/confirmation_request",
            endpoint="confirmation_request",
            view_func=lambda: "confirmation",
        )
        register_upload_routes(self.app, log_info=no_op_log_info)

    def test_accept_warning_preserves_url_method_endpoint_and_redirect(self):
        with self.app.test_request_context():
            from flask import url_for

            self.assertEqual(url_for("accept_warning"), "/accept_warning")

        with self.app.test_client() as client:
            response = client.post("/accept_warning", follow_redirects=False)
            get_response = client.get("/accept_warning")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/confirmation_request"))
        self.assertEqual(get_response.status_code, 405)
