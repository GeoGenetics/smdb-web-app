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
        self.calls = []
        self.app.add_url_rule(
            "/confirmation_request",
            endpoint="confirmation_request",
            view_func=lambda: "confirmation",
        )
        register_upload_routes(
            self.app,
            log_info=no_op_log_info,
            upload_file_handler=self.upload_file_handler,
            confirmed_handler=self.confirmed_handler,
        )

    def upload_file_handler(self):
        self.calls.append("upload")
        return "upload prepared"

    def confirmed_handler(self):
        self.calls.append("confirmed")
        return "upload confirmed"

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

    def test_upload_and_confirmed_preserve_post_urls_methods_and_handlers(self):
        with self.app.test_request_context():
            from flask import url_for

            self.assertEqual(url_for("upload_file"), "/upload")
            self.assertEqual(url_for("confirmed"), "/confirmed")

        with self.app.test_client() as client:
            upload_response = client.post("/upload")
            confirmed_response = client.post("/confirmed")
            upload_get_response = client.get("/upload")
            confirmed_get_response = client.get("/confirmed")

        self.assertEqual(upload_response.status_code, 200)
        self.assertEqual(upload_response.get_data(as_text=True), "upload prepared")
        self.assertEqual(confirmed_response.status_code, 200)
        self.assertEqual(confirmed_response.get_data(as_text=True), "upload confirmed")
        self.assertEqual(upload_get_response.status_code, 405)
        self.assertEqual(confirmed_get_response.status_code, 405)
        self.assertEqual(self.calls, ["upload", "confirmed"])
