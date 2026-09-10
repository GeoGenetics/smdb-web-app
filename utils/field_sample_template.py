"""Layout helpers for the multi-row field-sample upload template."""

from __future__ import annotations

import pandas as pd


class FieldSampleTemplateLayoutError(ValueError):
    """Raised when a field-sample template does not have one usable header row."""


def find_header_row_position(
    sheet: pd.DataFrame,
    *,
    template_version_column: str,
) -> int:
    """Return the positional row containing the required template-version header.

    Field-sample templates contain instructional rows before their actual
    column names. Older templates placed that row at a fixed position, but the
    current template can contain a different number of instructions. Locate it
    by its required ``Template version`` column instead of assuming a row
    number. The returned value is suitable for ``DataFrame.iloc``.
    """
    if sheet.empty:
        raise FieldSampleTemplateLayoutError(
            "The field-sample template is empty; the required "
            f'column "{template_version_column}" was not found.'
        )

    normalized = sheet.map(
        lambda value: value.strip() if isinstance(value, str) else value
    )
    matching_positions = [
        position
        for position, is_match in enumerate(
            normalized.eq(template_version_column).any(axis="columns")
        )
        if is_match
    ]

    if len(matching_positions) == 1:
        return matching_positions[0]

    if not matching_positions:
        raise FieldSampleTemplateLayoutError(
            "Unable to locate the field-sample column-header row: the required "
            f'column "{template_version_column}" was not found.'
        )

    human_positions = ", ".join(str(position + 1) for position in matching_positions)
    raise FieldSampleTemplateLayoutError(
        "Unable to identify a unique field-sample column-header row: the "
        f'required column "{template_version_column}" appears in rows '
        f"{human_positions}."
    )
