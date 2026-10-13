"""
Comprehensive Test Suite for Milestone 6:
Lifecycle State Machine, Punitive Lockout (AC-9), Run-over-run Diffing,
Safe Exports, Formula Injection Defense (AC-5), and AES-256 Encryption.
"""

import csv
import os
import tempfile
import pytest
import pyzipper
import duckdb

from backend.storage import init_schema
from backend.lifecycle import (
    compute_finding_fingerprint,
    validate_finding_transition,
    transition_finding,
    get_finding_history,
    diff_audit_runs,
)
from backend.export import (
    sanitize_csv_cell,
    export_actionable_findings,
    export_executive_summary,
    export_restricted_deal_ledger,
)


@pytest.fixture
def workspace_con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    # Insert dummy project and calibration profile
    con.execute(
        """
        INSERT INTO meta_project (project_id, project_name, schema_version, reporting_currency)
        VALUES ('p1', 'Test Project', '1.0.0', 'USD')
        """
    )
    con.execute(
        """
        INSERT INTO meta_calibration_profiles (
            calibration_id, name, historical_start_date, historical_end_date,
            comparability_controls, investigation_dimensions, threshold_strategy,
            calibration_json
        ) VALUES (
            'calib-001', 'FY25 Baseline', '2025-01-01', '2025-12-31',
            ['product_line'], ['region'], 'P75', '{}'
        )
        """
    )
    return con


def test_deterministic_sha256_fingerprint():
    """Fingerprint must be deterministic regardless of dictionary key ordering."""
    fp1 = compute_finding_fingerprint({"region": "EMEA", "channel": "Direct"}, calib_id="calib-1")
    fp2 = compute_finding_fingerprint({"channel": "Direct", "region": "EMEA"}, calib_id="calib-1")
    assert fp1 == fp2
    assert len(fp1) == 64
    assert int(fp1, 16) > 0

    # Changing calibration changes fingerprint
    fp3 = compute_finding_fingerprint({"region": "EMEA", "channel": "Direct"}, calib_id="calib-2")
    assert fp1 != fp3


def test_punitive_lockout_ac9():
    """AC-9: Punitive codes strictly barred on Tier 1 and 2, allowed on Tier 3."""
    for tier in ["Tier 1", "Tier 2", "Tier 1 (Price Realization)"]:
        valid, msg = validate_finding_transition(
            evidence_tier=tier,
            new_state="In Review",
            disposition_code="Unapproved Concession",
        )
        assert valid is False
        assert "locked for" in msg

    # Allowed on Tier 3
    valid, msg = validate_finding_transition(
        evidence_tier="Tier 3",
        new_state="In Review",
        disposition_code="Unapproved Concession",
    )
    assert valid is True


def test_dismissal_governance_ac9():
    """Dismissal requires mandatory category and snooze date."""
    # Missing category
    valid, msg = validate_finding_transition(
        evidence_tier="Tier 1",
        new_state="Dismissed",
        dismissal_category=None,
        snooze_date="2026-12-31",
    )
    assert valid is False
    assert "Mandatory valid dismissal category" in msg

    # Missing snooze date
    valid, msg = validate_finding_transition(
        evidence_tier="Tier 1",
        new_state="Dismissed",
        dismissal_category="Strategic Investment",
        snooze_date="",
    )
    assert valid is False
    assert "snooze/expiry date required" in msg

    # Valid dismissal
    valid, msg = validate_finding_transition(
        evidence_tier="Tier 1",
        new_state="Dismissed",
        dismissal_category="Strategic Investment",
        snooze_date="2026-12-31",
    )
    assert valid is True


def test_transition_finding_with_audit_log(workspace_con):
    """Applying transition updates finding record and inserts immutable audit log."""
    fp = compute_finding_fingerprint({"region": "APAC"}, calib_id="calib-001")
    workspace_con.execute(
        """
        INSERT INTO finding_records (
            finding_fingerprint, calibration_id, depth, dimension_slice_json,
            raw_transaction_count, distinct_account_count, gross_list_volume,
            unshrunk_gap_dollars, shrunk_gap_dollars, concentration_ratio,
            bootstrap_stability_score, bootstrap_ci_lower, bootstrap_ci_upper,
            fdr_p_value, fdr_q_value, fdr_rejected, unique_incremental_gap,
            lifecycle_status, evidence_tier
        ) VALUES (
            ?, 'calib-001', 1, '{"region": "APAC"}',
            100, 15, 100000.0, 15000.0, 12000.0, 0.12,
            0.95, 8000.0, 16000.0, 0.001, 0.005, TRUE, 12000.0,
            'New', 'Tier 1'
        )
        """,
        [fp],
    )

    # Transition New -> Assigned
    res = transition_finding(
        con=workspace_con,
        finding_fingerprint=fp,
        new_state="Assigned",
        assigned_owner="alice@company.com",
        user="lead_auditor",
        notes="Assigning for initial deal desk review",
    )
    assert res["new_status"] == "Assigned"
    assert res["assigned_owner"] == "alice@company.com"

    # Transition Assigned -> Dismissed (with valid governance)
    res_dismiss = transition_finding(
        con=workspace_con,
        finding_fingerprint=fp,
        new_state="Dismissed",
        dismissal_category="Strategic Investment",
        snooze_date="2026-06-30",
        notes="Approved strategic pilot pricing",
        user="deal_desk_lead",
    )
    assert res_dismiss["new_status"] == "Dismissed"

    # Verify immutable audit log
    history = get_finding_history(workspace_con, fp)
    assert len(history) == 2
    assert history[0]["previous_status"] == "New"
    assert history[0]["new_status"] == "Assigned"
    assert history[1]["previous_status"] == "Assigned"
    assert history[1]["new_status"] == "Dismissed"


def test_diff_audit_runs(workspace_con):
    """Run-over-run diffing tracks New, Persisting/Growing, and Resolved/Narrowed findings."""
    con_hist = duckdb.connect(":memory:")
    init_schema(con_hist)
    con_curr = duckdb.connect(":memory:")
    init_schema(con_curr)

    # Shared profile
    for c in [con_hist, con_curr]:
        c.execute(
            """
            INSERT INTO meta_calibration_profiles (
                calibration_id, name, historical_start_date, historical_end_date,
                comparability_controls, investigation_dimensions, threshold_strategy,
                calibration_json
            ) VALUES ('c1', 'B', '2025-01-01', '2025-12-31', ['p'], ['r'], 'P75', '{}')
            """
        )

    fp_persisting = "fp_persisting"
    fp_resolved = "fp_resolved"
    fp_new = "fp_new"

    # Historical run has persisting and resolved
    con_hist.execute(
        """
        INSERT INTO finding_records (
            finding_fingerprint, calibration_id, depth, dimension_slice_json,
            raw_transaction_count, distinct_account_count, gross_list_volume,
            unshrunk_gap_dollars, shrunk_gap_dollars, concentration_ratio,
            bootstrap_stability_score, bootstrap_ci_lower, bootstrap_ci_upper,
            fdr_p_value, fdr_q_value, fdr_rejected, unique_incremental_gap
        ) VALUES
        ('fp_persisting', 'c1', 1, '{"region": "US"}', 50, 10, 50000, 5000, 4000, 0.08, 0.9, 2000, 6000, 0.01, 0.01, TRUE, 4000),
        ('fp_resolved', 'c1', 1, '{"region": "EU"}', 30, 8, 30000, 3000, 2500, 0.08, 0.9, 1000, 4000, 0.01, 0.01, TRUE, 2500)
        """
    )

    # Current run: fp_persisting grew from 4000 to 6000; fp_resolved disappeared; fp_new appeared
    con_curr.execute(
        """
        INSERT INTO finding_records (
            finding_fingerprint, calibration_id, depth, dimension_slice_json,
            raw_transaction_count, distinct_account_count, gross_list_volume,
            unshrunk_gap_dollars, shrunk_gap_dollars, concentration_ratio,
            bootstrap_stability_score, bootstrap_ci_lower, bootstrap_ci_upper,
            fdr_p_value, fdr_q_value, fdr_rejected, unique_incremental_gap
        ) VALUES
        ('fp_persisting', 'c1', 1, '{"region": "US"}', 70, 12, 70000, 7000, 6000, 0.08, 0.9, 3000, 8000, 0.01, 0.01, TRUE, 6000),
        ('fp_new', 'c1', 1, '{"region": "APAC"}', 40, 6, 40000, 4000, 3500, 0.08, 0.9, 1500, 5000, 0.01, 0.01, TRUE, 3500)
        """
    )

    diff = diff_audit_runs(con_hist, con_curr)
    assert diff["summary"]["new_count"] == 1
    assert diff["summary"]["persisting_growing_count"] == 1
    assert diff["summary"]["resolved_narrowed_count"] == 1
    assert diff["summary"]["total_realized_recovery_dollars"] == 2500.0


def test_sanitize_csv_cell_ac5():
    """AC-5: Pure negative numeric preservation and dangerous prefix neutralization."""
    # Negative numbers must remain untouched
    assert sanitize_csv_cell("-1450.50") == "-1450.50"
    assert sanitize_csv_cell("-0.05") == "-0.05"
    assert sanitize_csv_cell(-1450.50) == "-1450.5"
    assert sanitize_csv_cell("-1e4") == "-1e4"

    # Dangerous prefixes must be neutralized
    assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitize_csv_cell("+123-dangerous") == "'+123-dangerous"
    assert sanitize_csv_cell("@EXEC") == "'@EXEC"
    assert sanitize_csv_cell("\tCMD") == "'\tCMD"


def test_safe_exports(workspace_con, tmp_path):
    """Test all 3 export paths (Executive Summary, Actionable Findings, Restricted Deal Ledger)."""
    # Populate transactions
    workspace_con.execute(
        """
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date, currency,
            fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
            reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
        ) VALUES
        ('TX-001', 'INV-001', 'ACC-SECRET-1', '2025-06-15', 'USD', 1.0, 1000.0, 750.0, 1000.0, 750.0, 0.25),
        ('TX-002', 'INV-002', 'ACC-SECRET-2', '2025-06-16', 'USD', 1.0, 2000.0, 1400.0, 2000.0, 1400.0, 0.30)
        """
    )
    # Populate finding
    workspace_con.execute(
        """
        INSERT INTO finding_records (
            finding_fingerprint, calibration_id, depth, dimension_slice_json,
            raw_transaction_count, distinct_account_count, gross_list_volume,
            unshrunk_gap_dollars, shrunk_gap_dollars, concentration_ratio,
            bootstrap_stability_score, bootstrap_ci_lower, bootstrap_ci_upper,
            fdr_p_value, fdr_q_value, fdr_rejected, unique_incremental_gap
        ) VALUES (
            'fp-export-1', 'calib-001', 1, '{"region": "EMEA"}',
            2, 2, 3000.0, 450.0, 400.0, 0.133,
            0.98, 200.0, 500.0, 0.001, 0.002, TRUE, 400.0
        )
        """
    )

    # 1. Executive Summary: Must redact line IDs and account names
    exec_path = tmp_path / "exec_summary.html"
    export_executive_summary(workspace_con, str(exec_path))
    with open(exec_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "ACC-SECRET" not in html
    assert "TX-001" not in html
    assert "Executive Commercial Audit Summary" in html

    # 2. Actionable Findings Ledger: CSV
    act_path = tmp_path / "actionable_findings.csv"
    export_actionable_findings(workspace_con, str(act_path))
    with open(act_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    assert len(rows) == 2  # header + 1 finding
    assert "fp-export-1" in rows[1][0]

    # 3. Restricted Deal Ledger: AES-256 ZIP
    # Without user acknowledgement -> raises PermissionError
    deal_zip = tmp_path / "restricted_deal_ledger.zip"
    with pytest.raises(PermissionError):
        export_restricted_deal_ledger(workspace_con, str(deal_zip), password="ValidPassword123!", user_acknowledged=False)

    # With acknowledgement -> succeeds
    export_restricted_deal_ledger(workspace_con, str(deal_zip), password="ValidPassword123!", user_acknowledged=True)
    assert os.path.exists(deal_zip)

    # Verify AES-256 ZIP can be decrypted with password
    with pyzipper.AESZipFile(deal_zip) as zf:
        zf.setpassword(b"ValidPassword123!")
        extracted = zf.read("restricted_deal_ledger.csv").decode("utf-8")
        assert "ACC-SECRET-1" in extracted
        assert "TX-001" in extracted
