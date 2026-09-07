"""Framework-free presentation data for user-facing preflight reports."""

from collections import OrderedDict
from typing import Any

from validation.models import ValidationReport


def preflight_report_context(report: ValidationReport) -> dict[str, Any]:
    """Build deterministic row/column groups suitable for template rendering.

    The caller owns rendering and request/session behaviour. Findings are
    represented with the existing bounded ``ValidationError.to_dict`` format,
    so a template never receives the original parsed sheet.
    """
    if not isinstance(report, ValidationReport):
        raise TypeError("report must be a ValidationReport")

    row_groups = []
    for template_row, findings in report.group_by_row().items():
        columns: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        for finding in findings:
            column_name = finding.template_column or "General"
            columns.setdefault(column_name, []).append(finding.to_dict())

        row_groups.append(
            {
                "template_row": template_row,
                "label": (
                    f"Template row {template_row}"
                    if template_row is not None
                    else "General upload issues"
                ),
                "column_groups": tuple(
                    {
                        "template_column": column_name,
                        "findings": tuple(column_findings),
                    }
                    for column_name, column_findings in columns.items()
                ),
            }
        )

    return {
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "finding_count": len(report.findings),
        "has_errors": report.has_errors,
        "row_groups": tuple(row_groups),
    }
