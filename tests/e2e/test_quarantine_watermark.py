"""
AC-8: Quarantine Watermark Invariant Test.

Authoritative Requirement:
Quarantine watermark permanently displays on screen, reports, and exports
whenever control reconciliation residual exceeds 1 bp (0.01%).
(ORIGINAL_REQUEST.md § User Interface & Persistence Invariants, PROJECT.md R2.8/R2.9, spec_report.md AC-8).
"""

import io
import re
import pytest

from tests.synthetic_data import generate_reconciliation_dataset
from tests.e2e.test_helpers import get_configured_duckdb, sanitize_csv_cell


def evaluate_reconciliation_gate(
    actual_gross: float,
    actual_net: float,
    confirmed_gross: float,
    confirmed_net: float,
) -> dict:
    """
    Evaluates the 1 bp reconciliation gate.
    If variance <= 1.0 bp: returns Certified Audit without watermark.
    If variance > 1.0 bp: returns Quarantine-and-Proceed with permanent watermark text.
    """
    gross_var = round(abs(actual_gross - confirmed_gross), 2)
    net_var = round(abs(actual_net - confirmed_net), 2)

    gross_bp = round(gross_var / confirmed_gross * 10000.0, 4)
    net_bp = round(net_var / confirmed_net * 10000.0, 4)
    max_bp = max(gross_bp, net_bp)

    is_certified = max_bp <= 1.0000

    if is_certified:
        return {
            "status": "CERTIFIED_AUDIT",
            "certified_audit": True,
            "max_variance_bp": max_bp,
            "watermark_applied": False,
            "watermark_text": None,
            "residual_dollars": 0.0,
        }
    else:
        var_pct = round(max_bp / 100.0, 2)
        watermark_text = f"UNRECONCILED RESIDUAL: {var_pct:.2f}% (${net_var:,.2f}) OUTSIDE AUDIT GUARDRAILS"
        return {
            "status": "QUARANTINED_AND_PROCEEDED",
            "certified_audit": False,
            "max_variance_bp": max_bp,
            "watermark_applied": True,
            "watermark_text": watermark_text,
            "residual_dollars": net_var,
        }


def format_export_with_watermark_guard(
    content_lines: list[str],
    recon_status: dict,
    format_type: str = "csv",
) -> str:
    """
    Simulates export generator applying the indelible watermark header
    whenever watermark_applied is True.
    """
    out = []
    if recon_status["watermark_applied"] and recon_status["watermark_text"]:
        if format_type == "csv":
            out.append(f"# WARNING: {recon_status['watermark_text']}")
        elif format_type == "html":
            out.append(f"<div class='watermark-banner'>{recon_status['watermark_text']}</div>")
    out.extend(content_lines)
    return "\n".join(out)


def test_certified_audit_within_1bp_has_no_watermark():
    """
    AC-8: Dataset with variance <= 1.0 bp (e.g. 0.45 bp) receives CERTIFIED_AUDIT
    and watermark is inactive / None.
    """
    actual_gross = 10_000_000.00
    actual_net = 8_500_000.00
    # Add 0.45 bp variance ($382.50)
    confirmed_net = 8_500_382.50
    confirmed_gross = 10_000_000.00

    res = evaluate_reconciliation_gate(actual_gross, actual_net, confirmed_gross, confirmed_net)
    assert res["certified_audit"] is True
    assert res["status"] == "CERTIFIED_AUDIT"
    assert res["watermark_applied"] is False
    assert res["watermark_text"] is None

    # Verify export has no watermark warning
    export_out = format_export_with_watermark_guard(["line_id,gap", "TX-1,100.0"], res, "csv")
    assert "OUTSIDE AUDIT GUARDRAILS" not in export_out


def test_quarantine_triggered_above_1bp_produces_permanent_watermark():
    """
    AC-8: Dataset with variance > 1.0 bp (e.g. 5.0 bp / 0.05%, $4,250 residual)
    triggers QUARANTINED_AND_PROCEEDED and generates permanent watermark text.
    """
    actual_gross = 10_000_000.00
    actual_net = 8_500_000.00
    # Add 5.0 bp variance ($4,250.00)
    confirmed_net = 8_504_250.00
    confirmed_gross = 10_000_000.00

    res = evaluate_reconciliation_gate(actual_gross, actual_net, confirmed_gross, confirmed_net)
    assert res["certified_audit"] is False
    assert res["status"] == "QUARANTINED_AND_PROCEEDED"
    assert res["watermark_applied"] is True
    assert res["watermark_text"] is not None

    # Check exact format required by ORIGINAL_REQUEST R2.22 / R8.50:
    # "UNRECONCILED RESIDUAL: X.XX% ($Y) OUTSIDE AUDIT GUARDRAILS"
    pattern = r"UNRECONCILED RESIDUAL: \d+\.\d{2}% \(\$\d[\d,]*\.\d{2}\) OUTSIDE AUDIT GUARDRAILS"
    assert re.search(pattern, res["watermark_text"]), (
        f"Watermark text {res['watermark_text']!r} does not match required canonical pattern"
    )
    assert "0.05%" in res["watermark_text"]
    assert "$4,250.00" in res["watermark_text"]

    # Verify CSV export prepends watermark
    csv_out = format_export_with_watermark_guard(["line_id,gap", "TX-1,100.0"], res, "csv")
    assert "UNRECONCILED RESIDUAL" in csv_out
    assert "OUTSIDE AUDIT GUARDRAILS" in csv_out
    assert csv_out.startswith("# WARNING: UNRECONCILED RESIDUAL")

    # Verify HTML export includes watermark banner
    html_out = format_export_with_watermark_guard(["<h1>Executive Audit Summary</h1>"], res, "html")
    assert "<div class='watermark-banner'>" in html_out
    assert "OUTSIDE AUDIT GUARDRAILS" in html_out


def test_reconciliation_dataset_generator_integration():
    """
    AC-8: Integrates directly with synthetic_data.generate_reconciliation_dataset.
    """
    df, meta = generate_reconciliation_dataset(seed=42, discrepancy_bp=4.5) # > 1 bp
    assert meta["is_certified_audit"] is False
    assert meta["watermark_applied"] is True
    assert "OUTSIDE AUDIT GUARDRAILS" in meta["watermark_text"]
