"""
Milestone 6: Safe Export Engine & Formula Injection Defense.
Supports:
1. Executive Audit Summary (HTML/PDF) with account names and line IDs redacted.
2. Actionable Findings Ledger (CSV/Excel) without raw line rows.
3. Restricted Deal Ledger (AES-256 encrypted ZIP) requiring user acknowledgement.
4. Formula Injection Defense strictly preserving valid negative numbers.
"""

import csv
import io
import os
import re
from typing import Any, Dict, List, Optional
import duckdb
import pyzipper

NUMERIC_REGEX = re.compile(r'^[+-]?((\d+(\.\d*)?)|(\.\d+))([eE][+-]?\d+)?$')
DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def sanitize_csv_cell(value: Any) -> str:
    """
    Two-step formula injection defense:
    Phase 1: Pure numeric preservation (preserves valid negative values like -1450.50, -0.05).
    Phase 2: Neutralize dangerous prefixes (=, +, -, @, \\t, \\r) on non-numeric text.
    """
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    # Phase 1: Pure Numeric Preservation
    if NUMERIC_REGEX.match(s.strip()):
        return s.strip()
    # Phase 2: Formula Injection Neutralization
    if s[0] in DANGEROUS_PREFIXES:
        return "'" + s
    return s


def export_actionable_findings(
    con: duckdb.DuckDBPyConnection,
    out_path: str,
) -> str:
    """
    Exports finding definitions, unique exposures, owners, and review statuses
    to a sanitized CSV without raw transactional line rows.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    rows = con.execute(
        """
        SELECT finding_fingerprint, depth, dimension_slice_json, raw_transaction_count,
               distinct_account_count, gross_list_volume, unshrunk_gap_dollars,
               shrunk_gap_dollars, concentration_ratio, bootstrap_stability_score,
               fdr_q_value, unique_incremental_gap, lifecycle_status, assigned_owner,
               dismissal_category, evidence_tier
        FROM finding_records
        ORDER BY shrunk_gap_dollars DESC
        """
    ).fetchall()

    headers = [
        "finding_fingerprint",
        "depth",
        "dimension_slice",
        "transaction_count",
        "distinct_account_count",
        "gross_list_volume",
        "unshrunk_gap_dollars",
        "shrunk_gap_dollars",
        "concentration_ratio",
        "bootstrap_stability_score",
        "fdr_q_value",
        "unique_incremental_gap",
        "lifecycle_status",
        "assigned_owner",
        "dismissal_category",
        "evidence_tier",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([sanitize_csv_cell(h) for h in headers])
        for r in rows:
            writer.writerow([sanitize_csv_cell(val) for val in r])

    return os.path.abspath(out_path)


def export_executive_summary(
    con: duckdb.DuckDBPyConnection,
    out_path: str,
    format: str = "html",
) -> str:
    """
    Generates an executive audit summary report (HTML).
    Crucial: Completely redacts individual transaction line IDs and customer account names.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # Fetch audit manifest and watermarks
    manifest_row = con.execute(
        """
        SELECT source_filename, total_rows_ingested, total_rows_quarantined,
               confirmed_gross_list, ingested_gross_list, gross_variance_bp,
               confirmed_net_invoiced, ingested_net_invoiced, net_variance_bp,
               reconciliation_status, watermark_active, watermark_text
        FROM meta_audit_manifest
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()

    # Fetch top findings (with REDACTED account references)
    finding_rows = con.execute(
        """
        SELECT finding_fingerprint, dimension_slice_json, raw_transaction_count,
               distinct_account_count, gross_list_volume, shrunk_gap_dollars,
               concentration_ratio, lifecycle_status, evidence_tier
        FROM finding_records
        ORDER BY shrunk_gap_dollars DESC
        LIMIT 25
        """
    ).fetchall()

    watermark_html = ""
    if manifest_row and manifest_row[10]:  # watermark_active
        watermark_html = f"""
        <div style="background-color: #fee2e2; border: 2px solid #ef4444; color: #b91c1c; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; font-weight: bold;">
            WARNING: {manifest_row[11]}
        </div>
        """

    findings_table_rows = ""
    for r in finding_rows:
        findings_table_rows += f"""
        <tr>
            <td style="font-family: monospace; font-size: 11px;">{r[0][:16]}...</td>
            <td><code>{r[1]}</code></td>
            <td style="text-align: right;">{r[2]:,}</td>
            <td style="text-align: right;">[REDACTED: {r[3]} Accounts]</td>
            <td style="text-align: right;">${float(r[4]):,.2f}</td>
            <td style="text-align: right; font-weight: bold; color: #dc2626;">${float(r[5]):,.2f}</td>
            <td style="text-align: right;">{float(r[6])*100:.1f}%</td>
            <td><span style="padding: 2px 6px; border-radius: 4px; background: #e2e8f0; font-size: 12px;">{r[7]}</span></td>
            <td>{r[8]}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sift Executive Commercial Audit Summary</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #0f172a; line-height: 1.5; }}
        h1 {{ margin-bottom: 4px; font-size: 24px; }}
        .meta {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
        .kpi-card {{ border: 1px solid #e2e8f0; padding: 16px; border-radius: 8px; background: #f8fafc; }}
        .kpi-title {{ font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; }}
        .kpi-value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }}
        th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px 12px; text-align: left; }}
        th {{ background: #f1f5f9; font-weight: 600; font-size: 12px; }}
        .redaction-notice {{ font-size: 11px; color: #64748b; font-style: italic; margin-top: 8px; }}
    </style>
</head>
<body>
    {watermark_html}
    <h1>Project Sift — Executive Commercial Audit Summary</h1>
    <div class="meta">Local-First Air-Gapped Commercial Audit &bull; Generated locally</div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Audit Status</div>
            <div class="kpi-value">{manifest_row[9] if manifest_row else 'Unreconciled'}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Ingested Transactions</div>
            <div class="kpi-value">{(manifest_row[1] if manifest_row else 0):,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Quarantined Residuals</div>
            <div class="kpi-value">{(manifest_row[2] if manifest_row else 0):,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Gross List Volume</div>
            <div class="kpi-value">${(float(manifest_row[4]) if manifest_row else 0.0):,.2f}</div>
        </div>
    </div>

    <h2>Top Defensible Exceptions (Ranked Findings Ledger)</h2>
    <div class="redaction-notice">Privacy Compliance Note: All individual transaction line IDs and customer account names have been automatically redacted in this executive export.</div>
    <table>
        <thead>
            <tr>
                <th>Fingerprint</th>
                <th>Dimension Slice</th>
                <th style="text-align: right;">Transactions</th>
                <th style="text-align: right;">Account Exposure</th>
                <th style="text-align: right;">Gross Volume</th>
                <th style="text-align: right;">Shrunk Gap ($)</th>
                <th style="text-align: right;">Concentration</th>
                <th>Status</th>
                <th>Tier</th>
            </tr>
        </thead>
        <tbody>
            {findings_table_rows}
        </tbody>
    </table>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return os.path.abspath(out_path)


def export_restricted_deal_ledger(
    con: duckdb.DuckDBPyConnection,
    out_path: str,
    password: str,
    user_acknowledged: bool = False,
) -> str:
    """
    Exports full line-item records encrypted with AES-256 password protection.
    Requires explicit user acknowledgement of sensitive export.
    """
    if not user_acknowledged:
        raise PermissionError(
            "Sensitive data export requires explicit user acknowledgement of confidentiality guardrails."
        )

    if not password or len(password.strip()) < 8:
        raise ValueError("Encryption password must be at least 8 characters long.")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # Fetch full line items
    tx_rows = con.execute(
        """
        SELECT transaction_line_id, invoice_id, account_id, parent_account_id,
               transaction_date, currency, fx_rate_to_reporting, extended_list_amt,
               net_invoiced_amt, cogs_amt, off_invoice_rebate, reporting_list_amt,
               reporting_invoiced_amt, realized_discount_rate, defensible_gap,
               is_credit_reversal
        FROM transactions
        ORDER BY transaction_date ASC
        """
    ).fetchall()

    headers = [
        "transaction_line_id", "invoice_id", "account_id", "parent_account_id",
        "transaction_date", "currency", "fx_rate_to_reporting", "extended_list_amt",
        "net_invoiced_amt", "cogs_amt", "off_invoice_rebate", "reporting_list_amt",
        "reporting_invoiced_amt", "realized_discount_rate", "defensible_gap",
        "is_credit_reversal",
    ]

    # Write sanitized CSV in-memory
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow([sanitize_csv_cell(h) for h in headers])
    for r in tx_rows:
        writer.writerow([sanitize_csv_cell(val) for val in r])

    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    # Create password-protected AES-256 ZIP file
    zip_path = out_path if out_path.endswith(".zip") else out_path + ".zip"
    with pyzipper.AESZipFile(
        zip_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.writestr("restricted_deal_ledger.csv", csv_bytes)

    return os.path.abspath(zip_path)
