"""Unit tests for framework-free preflight rollout configuration."""

import unittest

from services.preflight_mode import PreflightMode, preflight_mode_from_environment


class PreflightModeConfigurationTest(unittest.TestCase):
    def test_default_mode_is_off(self):
        self.assertIs(preflight_mode_from_environment({}), PreflightMode.OFF)

    def test_development_accepts_every_supported_mode(self):
        for value, expected in (
            ("off", PreflightMode.OFF),
            (" shadow ", PreflightMode.SHADOW),
            ("ENFORCE", PreflightMode.ENFORCE),
        ):
            with self.subTest(value=value):
                self.assertIs(
                    preflight_mode_from_environment(
                        {"RUN_MODE": "development", "SMDB_PREFLIGHT_MODE": value}
                    ),
                    expected,
                )

    def test_invalid_mode_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "SMDB_PREFLIGHT_MODE must be one of"):
            preflight_mode_from_environment({"SMDB_PREFLIGHT_MODE": "enabled"})

    def test_non_off_modes_are_rejected_outside_development(self):
        for mode in ("shadow", "enforce"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "only when RUN_MODE='development'"):
                    preflight_mode_from_environment(
                        {"RUN_MODE": "production", "SMDB_PREFLIGHT_MODE": mode}
                    )

    def test_production_allows_the_safe_off_mode(self):
        self.assertIs(
            preflight_mode_from_environment(
                {"RUN_MODE": "production", "SMDB_PREFLIGHT_MODE": "off"}
            ),
            PreflightMode.OFF,
        )
