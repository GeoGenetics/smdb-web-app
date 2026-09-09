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
) -> None:
    """Register extracted upload routes without changing their public contract."""

    @app.route("/accept_warning", methods=["POST"])
    @log_info(app)
    def accept_warning():
        """Continue from the duplicate-warning page to upload confirmation."""
        return redirect(url_for("confirmation_request"))
