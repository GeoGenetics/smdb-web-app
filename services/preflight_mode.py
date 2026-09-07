"""Configuration parsing for additive upload-preflight rollout modes.

This module has no Flask, database, or legacy application-configuration
dependency. Callers pass an environment mapping explicitly when testability or
an alternative runtime environment requires it.
"""

import os
from collections.abc import Mapping
from enum import Enum


PREFLIGHT_MODE_ENVIRONMENT_VARIABLE = "SMDB_PREFLIGHT_MODE"
RUN_MODE_ENVIRONMENT_VARIABLE = "RUN_MODE"


class PreflightMode(str, Enum):
    """Supported preflight rollout modes."""

    OFF = "off"
    SHADOW = "shadow"
    ENFORCE = "enforce"


def preflight_mode_from_environment(
    environment: Mapping[str, str] | None = None,
) -> PreflightMode:
    """Return a validated preflight mode from an environment mapping.

    ``off`` is the safe default and preserves legacy upload behavior. Non-off
    modes are deliberately development-only during the additive rollout, so a
    production environment variable cannot enable preflight prematurely.
    """
    environment = os.environ if environment is None else environment
    configured_mode = environment.get(PREFLIGHT_MODE_ENVIRONMENT_VARIABLE, "off")
    run_mode = environment.get(RUN_MODE_ENVIRONMENT_VARIABLE, "development")

    normalized_mode = configured_mode.strip().lower()
    normalized_run_mode = run_mode.strip().lower()
    try:
        mode = PreflightMode(normalized_mode)
    except ValueError as error:
        allowed_modes = ", ".join(option.value for option in PreflightMode)
        raise ValueError(
            f"{PREFLIGHT_MODE_ENVIRONMENT_VARIABLE} must be one of "
            f"{allowed_modes}; got {configured_mode!r}"
        ) from error

    if mode is not PreflightMode.OFF and normalized_run_mode != "development":
        raise ValueError(
            f"{PREFLIGHT_MODE_ENVIRONMENT_VARIABLE}={mode.value!r} is currently "
            "allowed only when RUN_MODE='development'"
        )
    return mode
