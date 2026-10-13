"""
AC-5: Negative Numeric Integrity & Formula Injection Defense Test.

Authoritative Requirement:
Negative numbers and currency amounts (e.g., -1450.50, -0.05) parse cleanly as
numeric values and are not prepended with single quotes during CSV export.
Formula injection strings starting with dangerous prefixes (=, +, -, @, \\t, \\r)
are neutralized by prepending a single quote (').
(ORIGINAL_REQUEST.md § Acceptance Criteria, PROJECT.md R8.4, spec_report.md AC-5).
"""

import io
import os
import csv
import pytest

from tests.e2e.test_helpers import sanitize_csv_cell


def test_negative_numeric_preservation_unit():
    """
    AC-5: Valid negative and signed numbers must remain raw and unquoted.
    """
    valid_numbers = [
        "-1450.50",
        "-0.05",
        "-100",
        "-0.0001",
        "-1234567.89",
        "-1e4",
        "-2.5E-3",
        "+500.25",
        "0.0",
        "0",
        "1450.50",
    ]
    for num_str in valid_numbers:
        sanitized = sanitize_csv_cell(num_str)
        assert sanitized == num_str.strip(), (
            f"Numeric integrity violated: {num_str} was altered to {sanitized}"
        )
        assert not sanitized.startswith("'"), (
            f"Numeric integrity violated: {num_str} was prepended with single quote: {sanitized}"
        )


def test_formula_injection_defense_unit():
    """
    AC-5: Malicious non-numeric text strings starting with =, +, -, @, \\t, \\r
    must be neutralized with a single quote prefix (').
    """
    dangerous_payloads = [
        ("=SUM(A1:A10)", "'=SUM(A1:A10)"),
        ("=cmd|' /C calc'!A0", "'=cmd|' /C calc'!A0"),
        ("@SUM(1+1)", "'@SUM(1+1)"),
        ("+cmd|' /C notepad'!A0", "'+cmd|' /C notepad'!A0"),
        ("-DANGEROUS_CALL", "'-DANGEROUS_CALL"),
        ("-1450.50 USD", "'-1450.50 USD"), # Text suffix makes it non-numeric
        ("-1450.50.22", "'-1450.50.22"),   # Malformed number
        ("\t=1+1", "'\t=1+1"),
        ("\r=cmd", "'\r=cmd"),
    ]
    for raw, expected in dangerous_payloads:
        sanitized = sanitize_csv_cell(raw)
        assert sanitized == expected, (
            f"Formula injection defense failed: {raw!r} was sanitized to {sanitized!r}, expected {expected!r}"
        )


def test_csv_export_byte_stream_integrity(tmp_path):
    """
    AC-5: Verifies that in an actual exported CSV file:
    1. Negative financial values (-1450.50, -0.05) appear as clean unquoted numbers.
    2. Formula strings appear prepended with single quote.
    3. The file re-parses into clean numeric float types without conversion errors.
    """
    test_rows = [
        {"account": "ACC-01", "variance_amt": -1450.50, "note": "=SUM(B2:B10)"},
        {"account": "ACC-02", "variance_amt": -0.05, "note": "@cmd|'calc'!A0"},
        {"account": "ACC-03", "variance_amt": 2500.00, "note": "Standard review"},
    ]

    csv_file = tmp_path / "test_export_sanitized.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["account", "variance_amt", "note"])
        for r in test_rows:
            writer.writerow([
                sanitize_csv_cell(r["account"]),
                sanitize_csv_cell(r["variance_amt"]),
                sanitize_csv_cell(r["note"]),
            ])

    # Inspect raw text content of file
    with open(csv_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Assert negative numbers are raw (not '-1450.50)
    assert "-1450.5" in content or "-1450.50" in content
    assert "'-1450.50" not in content
    assert "'-1450.5" not in content
    assert "'-0.05" not in content

    # Assert dangerous formulas ARE quoted
    assert "'=SUM(B2:B10)" in content
    assert "'@cmd|'calc'!A0" in content

    # Re-read through CSV reader and verify float parsing
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3
        # Assert variance_amt converts directly to float without ValueError
        val_0 = float(rows[0]["variance_amt"])
        assert val_0 == -1450.50
        val_1 = float(rows[1]["variance_amt"])
        assert val_1 == -0.05
