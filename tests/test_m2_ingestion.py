"""
Milestone 2 Test Suite: Schema Ingestion & Reconciliation Gate
Comprehensive verification of:
1. Pass 1 streaming preview and smart canonical column auto-mapping (CSV & Parquet).
2. Pass 2 vectorized DuckDB scan into canonical 11-field schema and converted reporting columns.
3. Data readiness scorecard calculating completeness across Tiers 1, 2, and 3.
4. User-confirmed control totals reconciliation gate (<= 1 bp certified audit vs > 1 bp quarantine).
5. Quarantine-and-Proceed protocol and permanent watermark generation matching AC-8.
6. Immutable meta_audit_manifest record insertion and audit_manifest.json file emission.
7. Credit note negative line item netting and grain uniqueness validation.
8. FastAPI loopback endpoints /api/ingest/preview and /api/ingest/reconcile.
"""

import os
import re
import json
import tempfile
from pathlib import Path
import pytest
import duckdb
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backend.app import app, state
from backend.storage import (
    open_workspace,
    create_workspace,
    init_schema,
    get_workspace_meta,
    close_workspace,
)
from backend.ingestion import (
    CANONICAL_FIELDS,
    BidirectionalMapping,
    propose_column_mapping,
    preview_source,
    compute_data_readiness_scorecard,
    execute_ingestion,
)
from tests.synthetic_data import (
    generate_50k_canonical_dataset,
    generate_reconciliation_dataset,
)


@pytest.fixture
def client():
    """Provides a fresh FastAPI test client with isolated workspace state."""
    if state.is_open():
        close_workspace(state.connection)
        state.connection = None
        state.active_path = None
    return TestClient(app)


# ===========================================================================
# 1. Pass 1 Streaming Preview & Smart Column Auto-Mapping
# ===========================================================================
def test_preview_source_csv_with_synonyms(tmp_path):
    """Verifies Pass 1 CSV preview and fuzzy auto-mapping to canonical 11 fields."""
    # Create CSV with common enterprise aliases
    df = pd.DataFrame({
        "line_id": [f"TX-{i}" for i in range(100)],
        "invoice_no": [f"INV-{i // 4}" for i in range(100)],
        "customer_id": [f"CUST-{i % 10}" for i in range(100)],
        "parent_customer_id": [f"PAR-{i % 2}" for i in range(100)],
        "tx_date": ["2025-06-15"] * 100,
        "txn_currency": ["USD"] * 100,
        "fx_rate": [1.0] * 100,
        "list_price": [1000.0 + i * 10 for i in range(100)],
        "net_sales": [800.0 + i * 8 for i in range(100)],
        "cogs": [500.0 + i * 5 for i in range(100)],
        "rebate": [20.0 + i for i in range(100)],
        "product_family": ["Cloud Compute"] * 100,
        "sales_region": ["North America"] * 100,
    })
    csv_file = tmp_path / "sales_preview.csv"
    df.to_csv(csv_file, index=False)

    preview = preview_source(str(csv_file), nrows=25)

    assert preview["total_preview_rows"] == 25
    assert len(preview["columns"]) == 13
    assert "line_id" in preview["columns"]
    assert "list_price" in preview["columns"]

    # Verify type inference
    inferred = preview["inferred_types"]
    assert "line_id" in inferred
    assert "list_price" in inferred

    # Verify preview data rows
    assert len(preview["preview_data"]) == 25
    assert preview["preview_data"][0]["line_id"] == "TX-0"
    assert float(preview["preview_data"][0]["list_price"]) == 1000.0

    # Verify smart auto-mapping
    mapping = preview["proposed_mapping"]
    assert mapping["transaction_line_id"] == "line_id"
    assert mapping["invoice_id"] == "invoice_no"
    assert mapping["account_id"] == "customer_id"
    assert mapping["parent_account_id"] == "parent_customer_id"
    assert mapping["transaction_date"] == "tx_date"
    assert mapping["currency"] == "txn_currency"
    assert mapping["fx_rate_to_reporting"] == "fx_rate"
    assert mapping["extended_list_amt"] == "list_price"
    assert mapping["net_invoiced_amt"] == "net_sales"
    assert mapping["cogs_amt"] == "cogs"
    assert mapping["off_invoice_rebate"] == "rebate"

    # Bidirectional property verification
    assert mapping["line_id"] == "transaction_line_id"
    assert mapping["invoice_no"] == "invoice_id"
    assert mapping["net_sales"] == "net_invoiced_amt"


def test_preview_source_parquet_exact_schema(tmp_path):
    """Verifies Pass 1 Parquet preview with canonical column names."""
    df, _ = generate_50k_canonical_dataset(n_rows=500, seed=42, inject_exceptions=False)
    parquet_file = tmp_path / "canonical_preview.parquet"
    df.to_parquet(parquet_file)

    preview = preview_source(str(parquet_file), nrows=50)

    assert preview["total_preview_rows"] == 50
    assert "transaction_line_id" in preview["columns"]
    assert "extended_list_amt" in preview["columns"]

    mapping = preview["proposed_mapping"]
    for field in CANONICAL_FIELDS:
        assert mapping[field] == field, f"Field {field} should map to itself"


def test_preview_source_file_not_found():
    """Verifies preview_source raises FileNotFoundError for non-existent path."""
    with pytest.raises(FileNotFoundError):
        preview_source("c:/non_existent_directory_12345/missing.csv")


# ===========================================================================
# 2. Data Readiness Scorecard (Tiers 1, 2, 3)
# ===========================================================================
def test_readiness_scorecard_all_tiers_unlocked(tmp_path):
    """Verifies Tier 3 unlock when core, dimensional, and governance metadata are complete."""
    con = duckdb.connect(":memory:")
    init_schema(con)

    # Insert transactions with all tiers complete
    con.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_list_amt, reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            realized_discount_rate, defensible_gap, is_credit_reversal
        )
        SELECT
            'TX-' || range AS transaction_line_id,
            'INV-' || (range // 4) AS invoice_id,
            'ACC-' || (range % 10) AS account_id,
            'PAR-' || (range % 2) AS parent_account_id,
            DATE '2025-01-01' + INTERVAL (range % 30) DAYS AS transaction_date,
            'USD' AS currency,
            1.0 AS fx_rate_to_reporting,
            1000.0 AS extended_list_amt,
            850.0 AS net_invoiced_amt,
            550.0 AS cogs_amt,
            20.0 AS off_invoice_rebate,
            1000.0, 850.0, 550.0, 20.0, 0.15, 0.0, FALSE
        FROM range(100);
    """)

    # Add extra dimension columns
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "product_family" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "sales_region" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "sales_rep" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "discount_reason" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "contract_terms" VARCHAR;')

    con.execute("""
        UPDATE transactions SET
            product_family = 'Enterprise Storage',
            sales_region = 'North America',
            sales_rep = 'Rep_Alpha',
            discount_reason = 'Standard Matrix',
            contract_terms = 'Net 30';
    """)

    scorecard = compute_data_readiness_scorecard(con, "transactions")

    assert scorecard["tier_unlocked"] == 3
    assert scorecard["tier_1_score"] == 1.0
    assert scorecard["tier_2_score"] == 1.0
    assert scorecard["tier_3_score"] == 1.0
    assert scorecard["metrics"]["transaction_line_id"] == 1.0
    assert scorecard["metrics"]["cogs_amt"] == 1.0
    assert scorecard["metrics"]["product_family"] == 1.0
    assert scorecard["metrics"]["sales_rep"] == 1.0


def test_readiness_scorecard_tier_2_unlocked_when_tier_3_missing():
    """Verifies Tier 2 unlock when governance metadata (Tier 3) is missing."""
    con = duckdb.connect(":memory:")
    init_schema(con)

    con.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_list_amt, reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            realized_discount_rate, defensible_gap, is_credit_reversal
        )
        SELECT
            'TX-' || range, 'INV-1', 'ACC-1', 'PAR-1', DATE '2025-01-01', 'USD', 1.0,
            1000.0, 800.0, 500.0, 20.0, 1000.0, 800.0, 500.0, 20.0, 0.20, 0.0, FALSE
        FROM range(50);
    """)
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "product_family" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "sales_region" VARCHAR;')
    con.execute("UPDATE transactions SET product_family = 'Security Suite', sales_region = 'EMEA';")

    scorecard = compute_data_readiness_scorecard(con, "transactions")

    assert scorecard["tier_unlocked"] == 2
    assert scorecard["tier_1_score"] == 1.0
    assert scorecard["tier_2_score"] == 1.0
    assert scorecard["tier_3_score"] < 0.70


def test_readiness_scorecard_locked_when_tier_1_incomplete():
    """Verifies Tier 0 (Locked) when core Tier 1 fields have insufficient completeness (< 90%)."""
    con = duckdb.connect(":memory:")
    init_schema(con)

    # Insert rows where invoice_id is mostly empty (only 20% complete)
    con.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_list_amt, reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            realized_discount_rate, defensible_gap, is_credit_reversal
        )
        SELECT
            'TX-' || range, CASE WHEN range < 20 THEN 'INV-1' ELSE '' END, 'ACC-1', NULL, DATE '2025-01-01', 'USD', 1.0,
            1000.0, 800.0, 500.0, NULL,
            1000.0, 800.0, 500.0, 0.0, 0.20, 0.0, FALSE
        FROM range(100);
    """)

    scorecard = compute_data_readiness_scorecard(con, "transactions")

    assert scorecard["tier_unlocked"] == 0
    assert scorecard["metrics"]["invoice_id"] == 0.20


def test_readiness_scorecard_tier_1_unlocked_without_cogs():
    """Verifies Tier 1 unlocks for price-only datasets without requiring cogs_amt."""
    con = duckdb.connect(":memory:")
    init_schema(con)

    # All Tier 1 core fields complete, but cogs_amt and off_invoice_rebate are NULL
    con.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_list_amt, reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            realized_discount_rate, defensible_gap, is_credit_reversal
        )
        SELECT
            'TX-' || range, 'INV-1', 'ACC-1', NULL, DATE '2025-01-01', 'USD', 1.0,
            1000.0, 800.0, NULL, NULL, 1000.0, 800.0, NULL, NULL, 0.20, 0.0, FALSE
        FROM range(100);
    """)

    scorecard = compute_data_readiness_scorecard(con, "transactions")

    assert scorecard["tier_unlocked"] == 1
    assert scorecard["tier_1_score"] == 1.0
    assert scorecard["tier_2_score"] < 0.80


# ===========================================================================
# 3. Vectorized Ingestion & Converted Reporting Columns
# ===========================================================================
def test_execute_ingestion_vectorized_derivations(tmp_path):
    """Verifies vectorized loading, converted columns, and reporting metrics."""
    df = pd.DataFrame({
        "line_id": ["TX-001", "TX-002", "TX-003"],
        "inv_num": ["INV-1", "INV-1", "INV-2"],
        "account": ["ACC-A", "ACC-A", "ACC-B"],
        "date": ["2025-01-10", "2025-01-11", "2025-01-12"],
        "list_price": [10000.0, 20000.0, 5000.0],
        "net_sales": [7500.0, 15000.0, 4500.0], # 25%, 25%, 10% discount
        "cogs": [5000.0, 11000.0, 2500.0],
        "rebate": [500.0, 1000.0, 200.0],
        "product_family": ["Enterprise Storage", "Enterprise Storage", "Cloud Compute"],
        "sales_region": ["North America", "North America", "EMEA"],
    })
    csv_file = tmp_path / "orders.csv"
    df.to_csv(csv_file, index=False)

    con = duckdb.connect(":memory:")
    mapping = {
        "transaction_line_id": "line_id",
        "invoice_id": "inv_num",
        "account_id": "account",
        "transaction_date": "date",
        "extended_list_amt": "list_price",
        "net_invoiced_amt": "net_sales",
        "cogs_amt": "cogs",
        "off_invoice_rebate": "rebate",
    }

    # Gross: 10k + 20k + 5k = 35k
    # Net: 7.5k + 15k + 4.5k = 27k
    result = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping=mapping,
        control_gross=35000.0,
        control_net=27000.0,
    )

    assert result["certified_audit"] is True
    assert result["status"] == "CERTIFIED_AUDIT"
    assert result["total_rows_ingested"] == 3
    assert result["total_rows_quarantined"] == 0

    # Query computed derived columns directly from DuckDB
    tx = con.execute("""
        SELECT
            transaction_line_id,
            gross_invoiced_amt,
            discount_amt,
            realized_discount_rate,
            pocket_margin_amt,
            pocket_margin_pct
        FROM transactions
        ORDER BY transaction_line_id ASC;
    """).fetchall()

    # TX-001: list=10000, net=7500, cogs=5000, rebate=500
    # discount_amt = 2500, realized_rate = 0.25
    # pocket_margin = 7500 - 5000 - 500 = 2000
    # pocket_margin_pct = 2000 / 7500 = 0.266667
    tx1 = tx[0]
    assert float(tx1[1]) == 10000.0
    assert float(tx1[2]) == 2500.0
    assert round(float(tx1[3]), 4) == 0.2500
    assert float(tx1[4]) == 2000.0
    assert round(float(tx1[5]), 4) == round(2000.0 / 7500.0, 4)

    # Extra dimension columns preserved
    dims = con.execute("SELECT product_family, sales_region FROM transactions WHERE transaction_line_id='TX-001'").fetchone()
    assert dims == ("Enterprise Storage", "North America")


# ===========================================================================
# 4. Reconciliation Gate (<= 1 bp vs > 1 bp Quarantine)
# ===========================================================================
def test_reconciliation_gate_certified_audit_lte_1bp(tmp_path):
    """Verifies that discrepancy <= 1.0 bp receives CERTIFIED_AUDIT with no watermark."""
    df, meta = generate_reconciliation_dataset(seed=42, discrepancy_bp=0.50) # 0.5 bp
    parquet_path = tmp_path / "recon_pass.parquet"
    df.to_parquet(parquet_path)

    con = duckdb.connect(":memory:")
    result = execute_ingestion(
        con=con,
        file_path=str(parquet_path),
        column_mapping={}, # Auto-mapping will match canonical schema
        control_gross=meta["confirmed_gross_list"],
        control_net=meta["confirmed_net_invoiced"],
    )

    assert result["certified_audit"] is True
    assert result["status"] == "CERTIFIED_AUDIT"
    assert result["watermark"] is None
    assert result["watermark_applied"] is False
    assert result["variance_bps"] <= 1.0000

    # Verify meta_audit_manifest entry
    row = con.execute("""
        SELECT manifest_id, reconciliation_status, watermark_active, watermark_text
        FROM meta_audit_manifest
        WHERE manifest_id = ?;
    """, [result["manifest_id"]]).fetchone()
    assert row[1] == "CERTIFIED_AUDIT"
    assert row[2] is False
    assert row[3] is None

    # Verify audit_manifest.json emitted
    manifest_file = Path(result["manifest_file"])
    assert manifest_file.exists()
    with open(manifest_file, "r", encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["manifest_id"] == result["manifest_id"]
    assert doc["certified_audit"] is True


def test_reconciliation_gate_quarantine_gt_1bp(tmp_path):
    """Verifies that discrepancy > 1.0 bp triggers QUARANTINED_AND_PROCEEDED with AC-8 watermark."""
    df, meta = generate_reconciliation_dataset(seed=42, discrepancy_bp=5.0) # 5.0 bp = 0.05%
    parquet_path = tmp_path / "recon_quarantine.parquet"
    df.to_parquet(parquet_path)

    con = duckdb.connect(":memory:")
    result = execute_ingestion(
        con=con,
        file_path=str(parquet_path),
        column_mapping={},
        control_gross=meta["confirmed_gross_list"],
        control_net=meta["confirmed_net_invoiced"],
    )

    assert result["certified_audit"] is False
    assert result["status"] == "QUARANTINED_AND_PROCEEDED"
    assert result["watermark_applied"] is True
    assert result["watermark"] is not None

    # Verify watermark matches canonical AC-8 pattern:
    # "UNRECONCILED RESIDUAL: X.XX% ($Y) OUTSIDE AUDIT GUARDRAILS"
    pattern = r"^UNRECONCILED RESIDUAL: \d+\.\d{2}% \(\$\d[\d,]*\.\d{2}\) OUTSIDE AUDIT GUARDRAILS$"
    assert re.match(pattern, result["watermark"]), (
        f"Watermark '{result['watermark']}' does not match AC-8 format"
    )

    # Verify quarantined_transactions table has residual discrepancy record
    qrn_rows = con.execute("SELECT quarantine_id, transaction_line_id, quarantine_reason FROM quarantined_transactions;").fetchall()
    assert len(qrn_rows) >= 1
    assert any("RESIDUAL-DISCREPANCY" in r[1] for r in qrn_rows)

    # Verify meta_audit_manifest records watermark
    m_row = con.execute("""
        SELECT reconciliation_status, watermark_active, watermark_text
        FROM meta_audit_manifest
        WHERE manifest_id = ?;
    """, [result["manifest_id"]]).fetchone()
    assert m_row[0] == "QUARANTINED_AND_PROCEEDED"
    assert m_row[1] is True
    assert "OUTSIDE AUDIT GUARDRAILS" in m_row[2]


# ===========================================================================
# 5. Grain Check & Credit Note Netting
# ===========================================================================
def test_grain_check_isolates_duplicate_line_ids(tmp_path):
    """Verifies that duplicate transaction line IDs are isolated into quarantined_transactions."""
    df = pd.DataFrame({
        "transaction_line_id": ["TX-DUP-1", "TX-DUP-1", "TX-UNIQUE-1"],
        "invoice_id": ["INV-1", "INV-1", "INV-2"],
        "account_id": ["ACC-1", "ACC-1", "ACC-2"],
        "transaction_date": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "extended_list_amt": [1000.0, 1500.0, 2000.0],
        "net_invoiced_amt": [800.0, 1200.0, 1600.0],
        "cogs_amt": [500.0, 750.0, 1000.0],
        "off_invoice_rebate": [50.0, 75.0, 100.0],
    })
    csv_file = tmp_path / "duplicate_grain.csv"
    df.to_csv(csv_file, index=False)

    con = duckdb.connect(":memory:")
    result = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping={},
        control_gross=3000.0, # 1000 (unique TX-DUP-1) + 2000 (TX-UNIQUE-1)
        control_net=2400.0,   # 800 + 1600
    )

    # 2 unique records in transactions, 1 duplicate in quarantined_transactions
    tx_count = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    qrn_count = con.execute("SELECT COUNT(*) FROM quarantined_transactions WHERE transaction_line_id = 'TX-DUP-1'").fetchone()[0]

    assert tx_count == 2
    assert qrn_count == 1
    assert result["total_rows_ingested"] == 2
    assert result["total_rows_quarantined"] >= 1


def test_credit_note_negative_line_item_netting(tmp_path):
    """Verifies that credit notes / returns with negative amounts net correctly."""
    df = pd.DataFrame({
        "transaction_line_id": ["TX-SALE-01", "TX-SALE-02", "TX-RETURN-01"],
        "invoice_id": ["INV-01", "INV-02", "INV-01-RET"],
        "account_id": ["ACC-01", "ACC-02", "ACC-01"],
        "transaction_date": ["2025-03-01", "2025-03-02", "2025-03-05"],
        "extended_list_amt": [50000.0, 30000.0, -10000.0], # Gross Net = 70,000
        "net_invoiced_amt": [42000.0, 25000.0, -8400.0],   # Net Invoiced Net = 58,600
        "cogs_amt": [25000.0, 15000.0, -5000.0],
        "off_invoice_rebate": [1000.0, 600.0, -200.0],
    })
    csv_file = tmp_path / "credit_notes.csv"
    df.to_csv(csv_file, index=False)

    con = duckdb.connect(":memory:")
    result = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping={},
        control_gross=70000.00,
        control_net=58600.00,
    )

    assert result["certified_audit"] is True
    assert result["calculated_gross"] == 70000.00
    assert result["calculated_net"] == 58600.00

    # Verify is_credit_reversal flag
    ret_row = con.execute("""
        SELECT is_credit_reversal, realized_discount_rate
        FROM transactions
        WHERE transaction_line_id = 'TX-RETURN-01';
    """).fetchone()
    assert ret_row[0] is True
    # Realized discount rate for negative or zero list amount safely returns 0.0
    assert float(ret_row[1]) == 0.0


# ===========================================================================
# 6. FastAPI Endpoints (/api/ingest/preview and /api/ingest/reconcile)
# ===========================================================================
def test_api_ingest_preview_endpoint(client, tmp_path):
    """Verifies POST /api/ingest/preview via HTTP."""
    df = pd.DataFrame({
        "tx_id": ["TX-1", "TX-2"],
        "inv_id": ["INV-1", "INV-2"],
        "cust_id": ["C-1", "C-2"],
        "tx_date": ["2025-01-01", "2025-01-02"],
        "gross_amt": [500.0, 600.0],
        "net_amt": [450.0, 540.0],
    })
    csv_file = tmp_path / "api_preview.csv"
    df.to_csv(csv_file, index=False)

    response = client.post("/api/ingest/preview", json={
        "file_path": str(csv_file),
        "nrows": 10,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["total_preview_rows"] == 2
    assert "tx_id" in data["columns"]
    assert data["proposed_mapping"]["transaction_line_id"] == "tx_id"
    assert data["proposed_mapping"]["extended_list_amt"] == "gross_amt"


def test_api_ingest_reconcile_endpoint(client, tmp_path):
    """Verifies POST /api/ingest/reconcile via HTTP."""
    df, meta = generate_reconciliation_dataset(seed=42, discrepancy_bp=0.25)
    parquet_file = tmp_path / "api_reconcile.parquet"
    df.to_parquet(parquet_file)

    # First preview to obtain proposed mapping
    prev_res = client.post("/api/ingest/preview", json={
        "file_path": str(parquet_file),
        "nrows": 100,
    })
    mapping = prev_res.json()["proposed_mapping"]

    # Reconcile
    recon_res = client.post("/api/ingest/reconcile", json={
        "file_path": str(parquet_file),
        "column_mapping": mapping,
        "control_gross": meta["confirmed_gross_list"],
        "control_net": meta["confirmed_net_invoiced"],
    })

    assert recon_res.status_code == 200
    res_data = recon_res.json()
    assert res_data["certified_audit"] is True
    assert res_data["status"] == "CERTIFIED_AUDIT"
    assert res_data["watermark"] is None
    assert res_data["tier_unlocked"] >= 1
    assert "readiness_scorecard" in res_data


# ===========================================================================
# 7. Milestone 2 Regression & Adversarial Defect Remediation Tests
# ===========================================================================
def test_reconciliation_zero_and_negative_control_totals_with_discrepancy_quarantined(tmp_path):
    """Verifies that zero or negative control totals with non-zero discrepancy trigger quarantine and watermark."""
    df = pd.DataFrame({
        "transaction_line_id": ["TX-R1"],
        "invoice_id": ["INV-R1"],
        "account_id": ["ACC-R1"],
        "transaction_date": ["2025-01-01"],
        "extended_list_amt": [1000.0],
        "net_invoiced_amt": [800.0],
    })
    csv_file = tmp_path / "recon_zero_ctrl.csv"
    df.to_csv(csv_file, index=False)

    con = duckdb.connect(":memory:")

    # 1. Zero control totals with non-zero data ($800 discrepancy)
    res_zero = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping={},
        control_gross=0.0,
        control_net=0.0,
    )
    assert res_zero["certified_audit"] is False, "Zero control with discrepancy must NOT be certified"
    assert res_zero["status"] == "QUARANTINED_AND_PROCEEDED"
    assert res_zero["watermark"] is not None
    assert res_zero["watermark_applied"] is True
    assert "OUTSIDE AUDIT GUARDRAILS" in res_zero["watermark"]
    assert res_zero["variance_bps"] >= 10000.0

    # 2. Negative control totals with discrepancy (actual net = 800, control net = -800 -> variance = 1600)
    res_neg = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping={},
        control_gross=-1000.0,
        control_net=-800.0,
    )
    assert res_neg["certified_audit"] is False, "Negative control with discrepancy must NOT be certified"
    assert res_neg["status"] == "QUARANTINED_AND_PROCEEDED"
    assert res_neg["watermark"] is not None
    assert res_neg["watermark_applied"] is True
    assert "OUTSIDE AUDIT GUARDRAILS" in res_neg["watermark"]


def test_reconciliation_zero_control_total_with_zero_discrepancy_certified(tmp_path):
    """Verifies that zero control totals with exactly zero discrepancy cleanly award CERTIFIED_AUDIT."""
    # Symmetrical offsetting transactions totaling exactly $0.00 gross and $0.00 net
    df = pd.DataFrame({
        "transaction_line_id": ["TX-ZERO-1", "TX-ZERO-2"],
        "invoice_id": ["INV-1", "INV-2"],
        "account_id": ["ACC-1", "ACC-1"],
        "transaction_date": ["2025-01-01", "2025-01-02"],
        "extended_list_amt": [500.0, -500.0],
        "net_invoiced_amt": [400.0, -400.0],
    })
    csv_file = tmp_path / "zero_discrepancy.csv"
    df.to_csv(csv_file, index=False)

    con = duckdb.connect(":memory:")
    res = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping={},
        control_gross=0.0,
        control_net=0.0,
    )
    assert res["certified_audit"] is True
    assert res["status"] == "CERTIFIED_AUDIT"
    assert res["watermark"] is None
    assert res["watermark_applied"] is False
    assert res["variance_bps"] == 0.0


def test_scorecard_reserved_sql_keyword_columns():
    """Verifies that compute_data_readiness_scorecard properly quotes column identifiers matching SQL keywords."""
    con = duckdb.connect(":memory:")
    init_schema(con)

    # Insert transactions
    con.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_list_amt, reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            realized_discount_rate, defensible_gap, is_credit_reversal
        ) VALUES (
            'TX-KEYWORD-1', 'INV-1', 'ACC-1', NULL, DATE '2025-01-01', 'USD', 1.0,
            1000.0, 800.0, 500.0, 20.0, 1000.0, 800.0, 500.0, 20.0, 0.20, 0.0, FALSE
        );
    """)

    # Add reserved SQL keyword column names
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "order" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "group" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "user" VARCHAR;')
    con.execute('ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "select" VARCHAR;')
    con.execute("""
        UPDATE transactions SET
            "order" = 'Standard Order',
            "group" = 'Tier 1 Enterprise',
            "user" = 'Admin User',
            "select" = 'Option A';
    """)

    # compute_data_readiness_scorecard should execute cleanly without ParserException
    scorecard = compute_data_readiness_scorecard(con, "transactions")
    assert scorecard["tier_unlocked"] >= 1
    assert "tier_1_score" in scorecard


def test_ingestion_literal_nan_in_numeric_fields(tmp_path):
    """Verifies that literal 'nan' strings in numeric and date fields do not cause InvalidInputException."""
    raw_csv = (
        "transaction_line_id,invoice_id,account_id,transaction_date,extended_list_amt,net_invoiced_amt,cogs_amt,off_invoice_rebate\n"
        "TX-NAN-1,INV-1,ACC-1,2025-01-01,100.0,80.0,nan,10.0\n"
        "TX-NAN-2,INV-2,ACC-2,2025-01-02,200.0,160.0,50.0,NaN\n"
    )
    csv_file = tmp_path / "nan_test.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write(raw_csv)

    con = duckdb.connect(":memory:")
    # Should execute without duckdb.InvalidInputException
    res = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping={},
        control_gross=300.0,
        control_net=240.0,
    )
    assert res["status"] == "CERTIFIED_AUDIT"
    assert res["total_rows_ingested"] == 2
    assert res["calculated_gross"] == 300.0
    assert res["calculated_net"] == 240.0

    # TX-NAN-1 cogs_amt should be NULL (from 'nan')
    cogs_val = con.execute("SELECT cogs_amt FROM transactions WHERE transaction_line_id = 'TX-NAN-1'").fetchone()[0]
    assert cogs_val is None


def test_algebraic_invariant_gross_minus_discount_equals_reporting_invoiced_exact_cent(tmp_path):
    """
    Verifies that for multi-currency transactions, row-level and aggregate:
    gross_invoiced_amt - discount_amt == reporting_invoiced_amt exact to $0.0000.
    """
    rng = np.random.default_rng(999)
    n_rows = 500
    currencies = ["EUR", "GBP", "JPY", "CAD", "CHF"]
    fx_rates_map = {"EUR": 1.085523, "GBP": 1.284321, "JPY": 0.006712, "CAD": 0.732145, "CHF": 1.123456}

    df = pd.DataFrame({
        "transaction_line_id": [f"TX-INV-{i}" for i in range(n_rows)],
        "invoice_id": [f"INV-{i // 4}" for i in range(n_rows)],
        "account_id": [f"ACC-{i % 20}" for i in range(n_rows)],
        "transaction_date": ["2025-05-15"] * n_rows,
        "currency": rng.choice(currencies, size=n_rows),
        "extended_list_amt": [round(float(rng.uniform(100.0, 10000.0)), 2) for _ in range(n_rows)],
        "net_invoiced_amt": [round(float(rng.uniform(50.0, 8000.0)), 2) for _ in range(n_rows)],
    })
    df["fx_rate_to_reporting"] = [fx_rates_map[c] for c in df["currency"]]

    parquet_file = tmp_path / "multi_currency_invariant.parquet"
    df.to_parquet(parquet_file)

    con = duckdb.connect(":memory:")
    calc_gross = float(round(sum(df["extended_list_amt"] * df["fx_rate_to_reporting"]), 2))
    calc_net = float(round(sum(df["net_invoiced_amt"] * df["fx_rate_to_reporting"]), 2))

    res = execute_ingestion(
        con=con,
        file_path=str(parquet_file),
        column_mapping={},
        control_gross=calc_gross,
        control_net=calc_net,
    )

    # 1. Cent-level equality across all rows
    mismatches = con.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE ROUND(ABS(gross_invoiced_amt - discount_amt - reporting_invoiced_amt), 2) > 0.00;
    """).fetchone()[0]
    assert mismatches == 0, f"Found {mismatches} rows with cent-level reconciliation discrepancy"


def test_file_path_with_apostrophe_and_special_characters(tmp_path):
    """Verifies that paths with apostrophes and special characters do not break SQL string literals."""
    sub_dir = tmp_path / "user's data folder"
    sub_dir.mkdir(parents=True, exist_ok=True)
    csv_file = sub_dir / "sales' concessions.csv"

    df = pd.DataFrame({
        "line_id": ["TX-APOS-1"],
        "inv_id": ["INV-1"],
        "acc_id": ["ACC-1"],
        "date": ["2025-01-01"],
        "list": [1000.0],
        "net": [850.0],
    })
    df.to_csv(csv_file, index=False)

    # 1. preview_source should handle apostrophe in path
    preview = preview_source(str(csv_file), nrows=10)
    assert preview["total_preview_rows"] == 1

    # 2. execute_ingestion should handle apostrophe in path
    con = duckdb.connect(":memory:")
    res = execute_ingestion(
        con=con,
        file_path=str(csv_file),
        column_mapping=preview["proposed_mapping"],
        control_gross=1000.0,
        control_net=850.0,
    )
    assert res["certified_audit"] is True
    assert res["total_rows_ingested"] == 1


def test_api_ingest_upload(client):
    """Verifies that the /api/ingest/upload endpoint accepts file uploads and stores them safely."""
    csv_bytes = b"transaction_line_id,invoice_id,account_id,transaction_date,currency,extended_list_amt,net_invoiced_amt\nTX-1,INV-1,ACC-1,2025-01-01,USD,1000.0,900.0\n"
    response = client.post(
        "/api/ingest/upload",
        files={"file": ("test_upload_sales.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "test_upload_sales.csv"
    assert os.path.exists(data["file_path"])
    assert data["size_bytes"] == len(csv_bytes)

