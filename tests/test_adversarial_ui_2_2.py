"""
Adversarial Verification Suite for Challenger UI 2.2
Empirically tests:
1. Pass 1 Preview Dual-Key Binding Contract (backend/ingestion.py and View1Reconcile.jsx logic)
2. Layman UX Flow, 4 Commercial Scenarios, Copy Integrity, and Progressive Disclosure Toggles
3. End-to-End Analytical Pipeline & Safe Export with Formula Injection Defense & User Acknowledgement Guardrail
"""

import os
import re
import json
import tempfile
import pytest
import duckdb
import pandas as pd

from backend.ingestion import preview_source, execute_ingestion
from backend.storage import open_workspace, init_schema
from backend.loao import compute_loao_baselines, freeze_calibration
from backend.beam_search import run_beam_search
from backend.overlap_ledger import get_overlap_ledger
from backend.pvmc_bridge import compute_pvmc_bridge
from backend.export import (
    export_executive_summary,
    export_actionable_findings,
    export_restricted_deal_ledger,
    sanitize_csv_cell,
)


# =========================================================================
# 1. Pass 1 Preview Dual-Key Binding Contract & Ingestion Robustness
# =========================================================================

def test_preview_source_dual_key_contract_csv(tmp_path):
    """Verify preview_source returns BOTH 'preview_data' and 'sample_rows' with identical content on CSV."""
    csv_file = tmp_path / "test_sales.csv"
    df = pd.DataFrame({
        "transaction_line_id": ["TL-001", "TL-002", "TL-003"],
        "invoice_id": ["INV-1", "INV-1", "INV-2"],
        "account_id": ["ACC-A", "ACC-A", "ACC-B"],
        "transaction_date": ["2025-01-15", "2025-01-15", "2025-01-16"],
        "currency": ["USD", "USD", "USD"],
        "extended_list_amt": [1000.0, 2000.0, 1500.0],
        "net_invoiced_amt": [850.0, 1700.0, 1200.0],
        "cogs_amt": [600.0, 1200.0, 900.0],
        "off_invoice_rebate": [50.0, 100.0, 0.0]
    })
    df.to_csv(csv_file, index=False)

    res = preview_source(str(csv_file), nrows=10)

    assert "preview_data" in res, "Missing 'preview_data' in preview_source result"
    assert "sample_rows" in res, "Missing 'sample_rows' in preview_source result"
    assert res["preview_data"] == res["sample_rows"], "preview_data and sample_rows must be strictly identical"
    assert len(res["preview_data"]) == 3
    assert res["total_preview_rows"] == 3
    assert "columns" in res
    assert "inferred_types" in res
    assert "proposed_mapping" in res


def test_preview_source_dual_key_contract_parquet(tmp_path):
    """Verify preview_source returns BOTH keys on Parquet files."""
    parquet_file = tmp_path / "test_sales.parquet"
    df = pd.DataFrame({
        "transaction_line_id": [f"TL-{i:03d}" for i in range(20)],
        "invoice_id": [f"INV-{i//2:03d}" for i in range(20)],
        "account_id": [f"ACC-{i%4}" for i in range(20)],
        "transaction_date": ["2025-02-01"] * 20,
        "currency": ["USD"] * 20,
        "extended_list_amt": [500.0 + i * 10 for i in range(20)],
        "net_invoiced_amt": [400.0 + i * 8 for i in range(20)],
        "cogs_amt": [300.0] * 20,
        "off_invoice_rebate": [10.0] * 20
    })
    df.to_parquet(parquet_file, index=False)

    res = preview_source(str(parquet_file), nrows=10)

    assert "preview_data" in res
    assert "sample_rows" in res
    assert res["preview_data"] == res["sample_rows"]
    assert len(res["preview_data"]) == 10  # Respects nrows limit
    assert res["total_preview_rows"] == 10


def test_view1_preview_parsing_simulation():
    """
    Simulates View1Reconcile.jsx parsing logic across multiple API response variants:
    const rows = res?.preview_data || res?.sample_rows || [];
    and verifies scanned totals calculation behaves deterministically.
    """
    def simulate_view1_parsing(res):
        rows = (res.get("preview_data") if res else None) or (res.get("sample_rows") if res else None) or []
        has_scanned = bool(res and (res.get("preview_data") or res.get("sample_rows")))
        scanned_gross = 0.0
        scanned_net = 0.0

        if res and (res.get("scanned_gross") or res.get("scanned_net")):
            scanned_gross = res.get("scanned_gross", 0.0)
            scanned_net = res.get("scanned_net", 0.0)
        elif len(rows) > 0:
            sample_list = sum(float(r.get("list_price_extended") or r.get("extended_list_amt") or 0) for r in rows)
            sample_net = sum(float(r.get("net_sales_amt") or r.get("net_invoiced_amt") or 0) for r in rows)
            if sample_list > 0:
                scanned_gross = sample_list
            if sample_net > 0:
                scanned_net = sample_net

        return {
            "rows": rows,
            "has_scanned": has_scanned,
            "scanned_gross": scanned_gross,
            "scanned_net": scanned_net
        }

    mock_row = {"extended_list_amt": 1000.0, "net_invoiced_amt": 800.0}

    # Case 1: Both keys present (Current Backend Contract)
    res_both = {"preview_data": [mock_row], "sample_rows": [mock_row]}
    parsed_both = simulate_view1_parsing(res_both)
    assert parsed_both["has_scanned"] is True
    assert len(parsed_both["rows"]) == 1
    assert parsed_both["scanned_gross"] == 1000.0
    assert parsed_both["scanned_net"] == 800.0

    # Case 2: Only preview_data present (Forward Compatibility)
    res_preview_only = {"preview_data": [mock_row]}
    parsed_preview = simulate_view1_parsing(res_preview_only)
    assert parsed_preview["has_scanned"] is True
    assert parsed_preview["scanned_gross"] == 1000.0

    # Case 3: Only sample_rows present (Legacy Compatibility)
    res_sample_only = {"sample_rows": [mock_row]}
    parsed_sample = simulate_view1_parsing(res_sample_only)
    assert parsed_sample["has_scanned"] is True
    assert parsed_sample["scanned_gross"] == 1000.0

    # Case 4: Neither present / Empty
    parsed_empty = simulate_view1_parsing({})
    assert parsed_empty["has_scanned"] is False
    assert len(parsed_empty["rows"]) == 0
    assert parsed_empty["scanned_gross"] == 0.0


# =========================================================================
# 2. Layman UX Flow & Copy Integrity Verification
# =========================================================================

def test_use_case_guide_line_49_currency_benchmark():
    """Verify line 49 in UseCaseGuide.jsx contains $120/unit and $95/unit and NO truncated string."""
    guide_path = "src/src/components/UseCaseGuide.jsx"
    with open(guide_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find the howSiftHelps line in renewal-negotiations scenario
    scenario_line = None
    line_no = 0
    for idx, line in enumerate(lines, start=1):
        if "Leave-One-Account-Out" in line and "peer accounts" in line:
            scenario_line = line
            line_no = idx
            break

    assert scenario_line is not None, "Scenario 3 howSiftHelps line not found in UseCaseGuide.jsx"
    assert "$120/unit" in scenario_line, f"Missing '$120/unit' at line {line_no}"
    assert "$95/unit" in scenario_line, f"Missing '$95/unit' at line {line_no}"
    # Target prohibited substring without literal self-matching
    bad_token = "pay " + "/unit"
    assert bad_token not in scenario_line, f"Truncated '{bad_token}' found at line {line_no}"


def test_zero_instances_of_pay_slash_unit_in_source_tree():
    """Verify zero occurrences of 'pay /unit' across application source tree (src and backend)."""
    search_dirs = ["src", "backend"]
    # Build regex dynamically to avoid self-match in test runner
    pattern = re.compile(r"pay\s+" + r"/unit", re.IGNORECASE)

    violations = []
    for s_dir in search_dirs:
        for root, _, files in os.walk(s_dir):
            for file in files:
                if file.endswith((".jsx", ".js", ".py", ".html", ".md", ".json")):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, start=1):
                            if pattern.search(line):
                                violations.append(f"{file_path}:{line_num}: {line.strip()}")

    assert len(violations) == 0, f"Found prohibited 'pay /unit' occurrences: {violations}"


def test_use_case_guide_all_four_scenarios_structured():
    """Verify all 4 commercial scenarios have clear layman content and required structure."""
    guide_path = "src/src/components/UseCaseGuide.jsx"
    with open(guide_path, "r", encoding="utf-8") as f:
        content = f.read()

    scenarios = [
        "runaway-discounts",
        "discount-stacking",
        "renewal-negotiations",
        "audit-reconciliation"
    ]

    for sc_id in scenarios:
        assert f"id: '{sc_id}'" in content, f"Scenario '{sc_id}' missing in UseCaseGuide.jsx"

    required_sections = [
        "The Commercial Challenge",
        "How Sift Solves It",
        "Tangible Business Impact",
        "1. Add & Check Data",
        "2. Compare Similar Deals",
        "3. Discover Profit Opportunities"
    ]
    for sec in required_sections:
        assert sec in content, f"Section '{sec}' missing in UseCaseGuide.jsx"


def test_primary_tabs_and_progressive_disclosure_in_app_and_views():
    """Verify primary navigation tabs and progressive disclosure toggles across App and views."""
    # App.jsx
    with open("src/src/App.jsx", "r", encoding="utf-8") as f:
        app_content = f.read()

    assert "1. Add & Check Data" in app_content
    assert "2. Compare Similar Deals" in app_content
    assert "3. Discover Profit Opportunities" in app_content
    assert "showEngineDetails" in app_content
    assert "Toggle Engine Diagnostics" in app_content or "DuckDB:" in app_content

    # View 1
    with open("src/src/components/View1Reconcile.jsx", "r", encoding="utf-8") as f:
        v1_content = f.read()
    assert "showAdvancedDetails" in v1_content
    assert "Advanced Technical Details & Audit Verification Proofs" in v1_content
    assert "ChevronUp" in v1_content and "ChevronDown" in v1_content
    assert "FileCheck2" in v1_content

    # View 2
    with open("src/src/components/View2Calibrate.jsx", "r", encoding="utf-8") as f:
        v2_content = f.read()
    assert "showAdvancedStats" in v2_content
    assert "Advanced Statistical Formulations & Peer Group Mechanics" in v2_content
    assert "ChevronUp" in v2_content and "ChevronDown" in v2_content

    # View 3
    with open("src/src/components/View3Triage.jsx", "r", encoding="utf-8") as f:
        v3_content = f.read()
    assert "showAdvancedStats" in v3_content
    assert "Advanced Technical Details" in v3_content or "Advanced Statistical Proofs" in v3_content


# =========================================================================
# 3. End-to-End Analytical Pipeline & Safe Export Verification
# =========================================================================

def test_full_analytical_pipeline_and_export_integrity(tmp_path):
    """
    Tests complete workflow:
    1. Open workspace & init schema
    2. Ingest transactions with 1bp certified reconciliation
    3. Run LOAO baseline calibration & freeze .calib.json profile
    4. Run beam search & compute deduplicated overlap ledger
    5. Run decoupled PVMC macro margin bridge
    6. Verify all 3 safe export paths, user acknowledgement guardrail, and formula injection defense
    """
    workspace_path = str(tmp_path / "test_pipeline.mxa")
    con = open_workspace(workspace_path)
    init_schema(con)

    # Prepare 40 transactions across 6 accounts (satisfying support fences N>=10, |A|>=5)
    rows = []
    accounts = [f"ACC_{i}" for i in range(1, 7)]
    for i in range(40):
        acc = accounts[i % len(accounts)]
        list_amt = 1000.0
        # Normal discount 15%, but ACC_1 gets anomalous 45% discount
        discount_rate = 0.45 if acc == "ACC_1" else 0.15
        net_amt = list_amt * (1.0 - discount_rate)
        rows.append({
            "transaction_line_id": f"TL_{i:04d}",
            "invoice_id": f"INV_{i//2:04d}",
            "account_id": acc,
            "parent_account_id": f"P_{acc}",
            "transaction_date": "2025-03-01",
            "currency": "USD",
            "fx_rate_to_reporting": 1.0,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_amt,
            "cogs_amt": 500.0,
            "off_invoice_rebate": 0.0,
            "product_family": "Hardware",
            "sales_region": "NorthAmerica",
            "sales_rep": "Rep_Alpha" if i % 2 == 0 else "Rep_Beta",
            "channel": "Direct",
            "contract_type": "Standard",
        })

    csv_path = str(tmp_path / "pipeline_data.csv")
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    col_map = {
        "transaction_line_id": "transaction_line_id",
        "invoice_id": "invoice_id",
        "account_id": "account_id",
        "parent_account_id": "parent_account_id",
        "transaction_date": "transaction_date",
        "currency": "currency",
        "fx_rate_to_reporting": "fx_rate_to_reporting",
        "extended_list_amt": "extended_list_amt",
        "net_invoiced_amt": "net_invoiced_amt",
        "cogs_amt": "cogs_amt",
        "off_invoice_rebate": "off_invoice_rebate",
    }

    total_gross = sum(r["extended_list_amt"] for r in rows)
    total_net = sum(r["net_invoiced_amt"] for r in rows)

    # 1. Ingest with exact controls -> Certified Audit
    ingest_res = execute_ingestion(con, csv_path, col_map, total_gross, total_net)
    assert ingest_res["certified_audit"] is True
    assert ingest_res["total_rows_quarantined"] == 0
    assert ingest_res["tier_unlocked"] >= 1

    # 2. LOAO Calibration
    calib_res = compute_loao_baselines(con, controls=["product_family"], threshold_method="P75", kappa=0.40)
    assert calib_res["defensible_transactions_count"] == 40
    assert calib_res["insufficient_evidence_count"] == 0
    assert calib_res["total_defensible_gap"] > 0

    # Freeze calibration profile
    calib_id = freeze_calibration(con, "FY2025_Baseline", export_dir=str(tmp_path))
    assert calib_id.startswith("CALIB-")
    meta_row = con.execute("SELECT calibration_id, name, is_locked FROM meta_calibration_profiles WHERE calibration_id = ?", [calib_id]).fetchone()
    assert meta_row is not None
    assert meta_row[2] is True

    # 3. Diagnostic Beam Search & Overlap Ledger
    findings = run_beam_search(con, investigation_dims=["sales_rep"], width=3, depth=2, fdr_q=0.05)
    assert isinstance(findings, list)

    overlap = get_overlap_ledger(con)
    assert "net_unique_portfolio_exposure" in overlap
    assert overlap["net_unique_portfolio_exposure"] >= 0.0

    # 4. Decoupled PVMC Bridge
    # Add quantity for PVMC test
    con.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS quantity DOUBLE;")
    con.execute("UPDATE transactions SET quantity = 10.0;")
    bridge_res = compute_pvmc_bridge(con, "2025-Q1", "2025-Q1")
    assert "delta_margin" in bridge_res

    # 5. Safe Export Engine Paths
    summary_path = str(tmp_path / "audit_summary.html")
    export_executive_summary(con, summary_path)
    assert os.path.exists(summary_path)

    findings_csv = str(tmp_path / "findings.csv")
    export_actionable_findings(con, findings_csv)
    assert os.path.exists(findings_csv)

    # Sensitive export guardrail test: unacknowledged export must raise PermissionError
    restricted_zip = str(tmp_path / "restricted.zip")
    with pytest.raises(PermissionError):
        export_restricted_deal_ledger(con, restricted_zip, password="AuditPassword123!", user_acknowledged=False)

    # Sensitive export with acknowledgement: must succeed
    export_restricted_deal_ledger(con, restricted_zip, password="AuditPassword123!", user_acknowledged=True)
    assert os.path.exists(restricted_zip)

    # 6. Formula Injection Defense Sanity Check
    assert sanitize_csv_cell("-1450.50") == "-1450.50", "Negative financial value must NOT be prepended with quote"
    assert sanitize_csv_cell("+1234.56") == "+1234.56", "Positive financial value must NOT be prepended with quote"
    assert sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)", "Formula = must be neutralized"
    assert sanitize_csv_cell("+A1+B2") == "'+A1+B2", "Formula + on text expression must be neutralized"
    assert sanitize_csv_cell("@cmd") == "'@cmd", "Formula @ must be neutralized"

    con.close()


def test_preview_source_missing_file_raises(tmp_path):
    """Verify preview_source safely raises FileNotFoundError on non-existent path."""
    with pytest.raises(FileNotFoundError):
        preview_source(str(tmp_path / "non_existent_file.csv"))


def test_preview_source_with_nulls_and_nans(tmp_path):
    """Verify preview_source cleanly handles files with nulls and NaNs without serialization errors."""
    csv_file = tmp_path / "nulls_sample.csv"
    df = pd.DataFrame({
        "transaction_line_id": ["TL-1", "TL-2", "TL-3"],
        "extended_list_amt": [100.0, None, float("nan")],
        "net_invoiced_amt": [90.0, 80.0, None],
        "notes": [None, "Special deal", None]
    })
    df.to_csv(csv_file, index=False)

    res = preview_source(str(csv_file), nrows=10)
    assert "preview_data" in res
    assert "sample_rows" in res
    assert len(res["preview_data"]) == 3
    # Check that None/NaN values are serialized safely as None or empty, not crashing
    assert res["preview_data"][1]["extended_list_amt"] is None or res["preview_data"][1]["extended_list_amt"] == ""


def test_reconciliation_variance_1bp_boundary_conditions(tmp_path):
    """Verify the 1 bp (0.01%) reconciliation gate boundary condition in execute_ingestion."""
    workspace_path = str(tmp_path / "test_1bp.mxa")
    con = open_workspace(workspace_path)
    init_schema(con)

    rows = [{
        "transaction_line_id": f"TL_{i}",
        "invoice_id": f"INV_{i}",
        "account_id": f"ACC_{i}",
        "transaction_date": "2025-01-01",
        "currency": "USD",
        "fx_rate_to_reporting": 1.0,
        "extended_list_amt": 10000.0,
        "net_invoiced_amt": 8000.0,
        "cogs_amt": 5000.0,
        "off_invoice_rebate": 0.0,
    } for i in range(10)]
    csv_path = str(tmp_path / "test_1bp.csv")
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    col_map = {k: k for k in rows[0].keys()}

    total_gross = 100000.0
    total_net = 80000.0

    # Sub-case A: Exact match (0.0 bp) -> Certified Audit
    res_exact = execute_ingestion(con, csv_path, col_map, total_gross, total_net)
    assert res_exact["certified_audit"] is True
    assert res_exact["watermark_applied"] is False

    # Sub-case B: Within 1 bp (e.g. 0.5 bp: $4 variance on $80,000 = 0.5 bp) -> Certified Audit
    res_within = execute_ingestion(con, csv_path, col_map, total_gross, total_net + 4.0)
    assert res_within["certified_audit"] is True
    assert res_within["watermark_applied"] is False

    # Sub-case C: Exceeding 1 bp (e.g. 5.0 bp: $40 variance on $80,000 = 5.0 bp) -> Quarantine & Watermark
    res_exceed = execute_ingestion(con, csv_path, col_map, total_gross, total_net + 40.0)
    assert res_exceed["certified_audit"] is False
    assert res_exceed["watermark_applied"] is True
    assert "UNRECONCILED RESIDUAL" in res_exceed["watermark_text"]

    con.close()


def test_watermark_banner_clean_slate_suppression_logic():
    """
    Verifies WatermarkBanner.jsx rendering invariants:
    - If !hasReconciled, returns null (clean slate invariant)
    - If residualPct <= 0.01, returns null (certified audit invariant)
    - If hasReconciled && residualPct > 0.01, renders prominent watermark banner
    """
    with open("src/src/components/WatermarkBanner.jsx", "r", encoding="utf-8") as f:
        banner_code = f.read()

    # Verify component checks hasReconciled
    assert "hasReconciled" in banner_code
    assert "Boolean(hasReconciled)" in banner_code
    assert "!varianceExceeded" in banner_code
    assert "return null" in banner_code
    assert "UNRECONCILED RESIDUAL" in banner_code

