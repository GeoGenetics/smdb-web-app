"""Incremental ownership for Flask upload routes.

Routes are registered directly on the application during the first extraction
steps so their existing endpoint names remain stable. A future blueprint move
must either preserve those names or update every ``url_for`` caller in the
same change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, redirect, url_for


def register_upload_routes(
    app: Flask,
    *,
    log_info: Callable[[Flask], Callable[[Callable[..., Any]], Callable[..., Any]]],
    upload_file_handler: Callable[[], Any] | None = None,
    confirmed_handler: Callable[[], Any] | None = None,
) -> None:
    """Register extracted upload routes without changing their public contract."""

    @app.route("/accept_warning", methods=["POST"])
    @log_info(app)
    def accept_warning():
        """Continue from the duplicate-warning page to upload confirmation."""
        return redirect(url_for("confirmation_request"))

    if upload_file_handler is not None:

        @app.route("/upload", methods=["POST"])
        @log_info(app)
        def upload_file():
            """Delegate parsing/upload preparation to its retained legacy helper."""
            return upload_file_handler()

    if confirmed_handler is not None:

        @app.route("/confirmed", methods=["POST"])
        @log_info(app)
        def confirmed():
            """Delegate confirmation/write behavior to its retained legacy helper."""
            return confirmed_handler()
