"""Regression tests for locating the field-sample template header row."""

import unittest

import numpy as np
import pandas as pd

from utils.field_sample_template import (
    FieldSampleTemplateLayoutError,
    find_header_row_position,
)


TEMPLATE_VERSION = "Template version"


class FieldSampleTemplateLayoutTest(unittest.TestCase):
    def template_with_header_at(self, header_position):
        """Create a synthetic template with Template version in its last column."""
        sheet = pd.DataFrame(
            None,
            index=range(max(header_position + 3, 13)),
            columns=range(62),
            dtype=object,
        )
        sheet.iloc[header_position, 0] = np.nan
        sheet.iloc[header_position, 1] = "Unique GeoGenetics Sample ID"
        sheet.iloc[header_position, 61] = TEMPLATE_VERSION
        sheet.iloc[header_position + 1, 1] = "PTPIC2026001"
        sheet.iloc[header_position + 1, 61] = "Version: 2.20260825"
        return sheet

    def test_locates_legacy_fixed_position_header(self):
        sheet = self.template_with_header_at(8)

        self.assertEqual(
            find_header_row_position(sheet, template_version_column=TEMPLATE_VERSION),
            8,
        )

    def test_locates_current_template_header_in_final_column_after_extra_rows(self):
        # Mirrors the reported layout: the real header is later than the old
        # fixed row and Template version is the final spreadsheet column.
        sheet = self.template_with_header_at(16)

        header_position = find_header_row_position(
            sheet,
            template_version_column=TEMPLATE_VERSION,
        )
        sheet.columns = sheet.iloc[header_position]
        data_rows = sheet.iloc[header_position + 1:].reset_index(drop=True)

        self.assertEqual(header_position, 16)
        self.assertEqual(data_rows[TEMPLATE_VERSION].iloc[0], "Version: 2.20260825")

    def test_reports_a_missing_required_header_with_an_actionable_error(self):
        sheet = pd.DataFrame([["instruction"], ["sample value"]])

        with self.assertRaisesRegex(
            FieldSampleTemplateLayoutError,
            r'required column "Template version" was not found',
        ):
            find_header_row_position(sheet, template_version_column=TEMPLATE_VERSION)

    def test_rejects_ambiguous_header_rows(self):
        sheet = self.template_with_header_at(8)
        sheet.iloc[12, 61] = TEMPLATE_VERSION

        with self.assertRaisesRegex(
            FieldSampleTemplateLayoutError,
            r"unique field-sample column-header row",
        ):
            find_header_row_position(sheet, template_version_column=TEMPLATE_VERSION)
