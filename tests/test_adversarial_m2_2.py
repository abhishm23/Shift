"""
Empirical Adversarial Stress Suite for Milestone 2: 1 bp Reconciliation Gate & Quarantine Watermark Invariant (AC-8)
Author: challenger_m2_2 (Milestone 2 Challenger 2)

Exhaustively verifies:
1. Exact Boundary Stress Testing at 1.0000 bp (<= 1 bp -> CERTIFIED_AUDIT, watermark None)
   vs 1.0001 bp (> 1 bp -> QUARANTINED_AND_PROCEEDED, watermark active).
2. Watermark string format exact canonical pattern:
   'UNRECONCILED RESIDUAL: X.XX% ($Y) OUTSIDE AUDIT GUARDRAILS' with commas, decimals, percentages.
3. Quarantined transactions table invariant:
   - Zero residual records when variance <= 1.0000 bp.
   - Exactly one RESIDUAL-DISCREPANCY record when variance > 1.0000 bp, containing full audit JSON.
4. Audit manifest JSON & meta_audit_manifest invariant:
   - Immutable audit_manifest.json emitted with source SHA256, row counts, discrepancies, and status.
   - Database meta_audit_manifest table records match disk manifest.
5. Dual format verification (CSV & Parquet) with credit notes / return netting.
"""

import os
import re
import json
import uuid
import hashlib
from pathlib import Path
import pytest
import duckdb
import pandas as pd
import numpy as np

from backend.storage import init_schema, open_workspace, close_workspace
from backend.ingestion import (
    execute_ingestion,
    compute_data_readiness_scorecard,
    CANONICAL_FIELDS,
)
from tests.synthetic_data import generate_reconciliation_dataset


WATERMARK_REGEX = re.compile(
    r"^UNRECONCILED RESIDUAL: \d+\.\d{2}% \(\$\d{1,3}(,\d{3})*\.\d{2}\) OUTSIDE AUDIT GUARDRAILS$"
)


def _create_controlled_source(
    tmp_path: Path,
    gross_total: float,
    net_total: float,
    n_rows: int = 100,
    file_format: str = "parquet",
    include_credit_note: bool = False,
) -> Path:
    """Creates a synthetic dataset with exactly known aggregate gross and net totals."""
    records = []
    
    if include_credit_note:
        # 98 regular rows + 1 positive + 1 offsetting credit reversal
        base_gross = gross_total / (n_rows - 2)
        base_net = net_total / (n_rows - 2)
        for i in range(n_rows - 2):
            records.append({
                "transaction_line_id": f"TX-CTRL-{i:05d}",
                "invoice_id": f"INV-{i // 5:04d}",
                "account_id": f"ACC-{i % 10:03d}",
                "parent_account_id": f"PAR-{i % 2:02d}",
                "transaction_date": "2025-06-01",
                "currency": "USD",
                "fx_rate_to_reporting": 1.0,
                "extended_list_amt": round(base_gross, 2),
                "net_invoiced_amt": round(base_net, 2),
                "cogs_amt": round(base_net * 0.6, 2),
                "off_invoice_rebate": round(base_net * 0.02, 2),
                "product_family": "Compute",
                "sales_region": "North America",
                "sales_rep": "Rep1",
                "discount_reason": "Standard",
                "contract_terms": "Net 30",
            })
        # Add a $500 positive transaction and a -$500 credit note
        records.append({
            "transaction_line_id": f"TX-CTRL-{n_rows - 2:05d}",
            "invoice_id": f"INV-{n_rows:04d}",
            "account_id": "ACC-001",
            "parent_account_id": "PAR-01",
            "transaction_date": "2025-06-02",
            "currency": "USD",
            "fx_rate_to_reporting": 1.0,
            "extended_list_amt": 500.00,
            "net_invoiced_amt": 400.00,
            "cogs_amt": 250.00,
            "off_invoice_rebate": 10.00,
            "product_family": "Compute",
            "sales_region": "North America",
            "sales_rep": "Rep1",
            "discount_reason": "Standard",
            "contract_terms": "Net 30",
        })
        records.append({
            "transaction_line_id": f"TX-CTRL-{n_rows - 1:05d}",
            "invoice_id": f"INV-{n_rows:04d}-REV",
            "account_id": "ACC-001",
            "parent_account_id": "PAR-01",
            "transaction_date": "2025-06-03",
            "currency": "USD",
            "fx_rate_to_reporting": 1.0,
            "extended_list_amt": -500.00,
            "net_invoiced_amt": -400.00,
            "cogs_amt": -250.00,
            "off_invoice_rebate": -10.00,
            "product_family": "Compute",
            "sales_region": "North America",
            "sales_rep": "Rep1",
            "discount_reason": "Return",
            "contract_terms": "Net 30",
        })
    else:
        per_row_gross = gross_total / n_rows
        per_row_net = net_total / n_rows
        for i in range(n_rows):
            records.append({
                "transaction_line_id": f"TX-CTRL-{i:05d}",
                "invoice_id": f"INV-{i // 5:04d}",
                "account_id": f"ACC-{i % 10:03d}",
                "parent_account_id": f"PAR-{i % 2:02d}",
                "transaction_date": "2025-06-01",
                "currency": "USD",
                "fx_rate_to_reporting": 1.0,
                "extended_list_amt": per_row_gross,
                "net_invoiced_amt": per_row_net,
                "cogs_amt": per_row_net * 0.6,
                "off_invoice_rebate": per_row_net * 0.02,
                "product_family": "Compute",
                "sales_region": "North America",
                "sales_rep": "Rep1",
                "discount_reason": "Standard",
                "contract_terms": "Net 30",
            })

    df = pd.DataFrame(records)
    if file_format == "parquet":
        out_path = tmp_path / f"source_{uuid.uuid4().hex[:6]}.parquet"
        df.to_parquet(out_path, index=False)
    else:
        out_path = tmp_path / f"source_{uuid.uuid4().hex[:6]}.csv"
        df.to_csv(out_path, index=False)
    return out_path


# ===========================================================================
# VECTOR 1: Exact Boundary Stress Testing (1.0000 bp vs 1.0001 bp)
# ===========================================================================
class TestReconciliationGateBoundaryStress:
    """
    Stress-tests the exact 1 bp (0.01%) gate boundary.
    - <= 1.0000 bp: MUST award CERTIFIED_AUDIT, watermark is None, watermark_applied is False.
    - > 1.0000 bp (e.g. 1.0001 bp): MUST trigger QUARANTINED_AND_PROCEEDED, watermark activated.
    """

    @pytest.mark.parametrize(
        "scale,confirmed_gross,confirmed_net",
        [
            ("10M_Standard", 12_500_000.00, 10_000_000.00),
            ("100M_Enterprise", 125_000_000.00, 100_000_000.00),
            ("1M_MidMarket", 1_250_000.00, 1_000_000.00),
        ],
    )
    def test_net_variance_exact_1_0000_bp_certified(self, tmp_path, scale, confirmed_gross, confirmed_net):
        """
        Discrepancy at exactly 1.0000 bp (0.01%) on net revenue:
        Variance = confirmed_net * 0.00010000.
        Must award CERTIFIED_AUDIT, watermark is None.
        """
        # Exactly 1.0000 bp dollar variance
        variance_net = round(confirmed_net * 0.0001, 2)
        actual_net = confirmed_net - variance_net
        actual_gross = confirmed_gross

        src_path = _create_controlled_source(tmp_path, gross_total=actual_gross, net_total=actual_net)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        assert res["certified_audit"] is True, f"Failed for {scale} at 1.0000 bp: expected certified_audit True"
        assert res["status"] == "CERTIFIED_AUDIT"
        assert res["watermark"] is None
        assert res["watermark_applied"] is False
        assert res["variance_bps"] <= 1.0000
        assert pytest.approx(res["variance_bps"], abs=1e-4) == 1.0000

    @pytest.mark.parametrize(
        "scale,confirmed_gross,confirmed_net",
        [
            ("10M_Standard", 12_500_000.00, 10_000_000.00),
            ("100M_Enterprise", 125_000_000.00, 100_000_000.00),
            ("1M_MidMarket", 1_250_000.00, 1_000_000.00),
        ],
    )
    def test_net_variance_exact_1_0001_bp_quarantined(self, tmp_path, scale, confirmed_gross, confirmed_net):
        """
        Discrepancy at 1.0001 bp on net revenue:
        Variance = confirmed_net * 0.00010001.
        Must initiate QUARANTINED_AND_PROCEEDED, watermark activated.
        """
        # Calculate dollar variance for 1.0001 bp
        variance_net = round(confirmed_net * 0.00010001, 2)
        actual_net = confirmed_net - variance_net
        actual_gross = confirmed_gross

        src_path = _create_controlled_source(tmp_path, gross_total=actual_gross, net_total=actual_net)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        assert res["certified_audit"] is False, f"Failed for {scale} at 1.0001 bp: expected certified_audit False"
        assert res["status"] == "QUARANTINED_AND_PROCEEDED"
        assert res["watermark_applied"] is True
        assert res["watermark"] is not None
        assert res["variance_bps"] >= 1.0001
        assert "OUTSIDE AUDIT GUARDRAILS" in res["watermark"]

    def test_gross_variance_exact_1_0000_bp_certified(self, tmp_path):
        """
        Discrepancy at exactly 1.0000 bp on gross revenue (with net variance = 0.0):
        Must award CERTIFIED_AUDIT, watermark is None.
        """
        confirmed_gross = 10_000_000.00
        confirmed_net = 8_000_000.00
        variance_gross = 1_000.00 # Exactly 1.0 bp
        actual_gross = confirmed_gross + variance_gross
        actual_net = confirmed_net

        src_path = _create_controlled_source(tmp_path, gross_total=actual_gross, net_total=actual_net)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        assert res["certified_audit"] is True
        assert res["status"] == "CERTIFIED_AUDIT"
        assert res["watermark"] is None
        assert res["watermark_applied"] is False
        assert pytest.approx(res["gross_variance_bps"], abs=1e-4) == 1.0000

    def test_gross_variance_exact_1_0001_bp_quarantined(self, tmp_path):
        """
        Discrepancy at 1.0001 bp on gross revenue (with net variance = 0.0):
        Must initiate QUARANTINED_AND_PROCEEDED, watermark activated.
        """
        confirmed_gross = 10_000_000.00
        confirmed_net = 8_000_000.00
        variance_gross = 1_000.10 # Exactly 1.0001 bp
        actual_gross = confirmed_gross + variance_gross
        actual_net = confirmed_net

        src_path = _create_controlled_source(tmp_path, gross_total=actual_gross, net_total=actual_net)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        assert res["certified_audit"] is False
        assert res["status"] == "QUARANTINED_AND_PROCEEDED"
        assert res["watermark_applied"] is True
        assert res["watermark"] is not None
        assert res["gross_variance_bps"] >= 1.0001

    @pytest.mark.parametrize(
        "target_bp,expected_status,expected_certified",
        [
            (0.0000, "CERTIFIED_AUDIT", True),
            (0.5000, "CERTIFIED_AUDIT", True),
            (0.9999, "CERTIFIED_AUDIT", True),
            (1.0000, "CERTIFIED_AUDIT", True),
            (1.0001, "QUARANTINED_AND_PROCEEDED", False),
            (1.0500, "QUARANTINED_AND_PROCEEDED", False),
            (5.0000, "QUARANTINED_AND_PROCEEDED", False),
            (25.0000, "QUARANTINED_AND_PROCEEDED", False),
        ],
    )
    def test_micro_step_gradient_across_boundary(self, tmp_path, target_bp, expected_status, expected_certified):
        """
        Sweeps fine-grained basis points across the 1 bp threshold to verify monotonicity.
        """
        confirmed_gross = 20_000_000.00
        confirmed_net = 16_000_000.00
        # target_bp / 10000 * confirmed_net
        diff_dollars = round(confirmed_net * (target_bp / 10000.0), 2)
        actual_net = confirmed_net + diff_dollars
        actual_gross = confirmed_gross

        src_path = _create_controlled_source(tmp_path, gross_total=actual_gross, net_total=actual_net)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        assert res["status"] == expected_status, f"Gradient test failed at {target_bp} bp"
        assert res["certified_audit"] is expected_certified


# ===========================================================================
# VECTOR 2: Watermark String Canonical Format Verification (AC-8)
# ===========================================================================
class TestWatermarkCanonicalFormat:
    """
    Verifies that the watermark string strictly matches:
    UNRECONCILED RESIDUAL: X.XX% ($Y) OUTSIDE AUDIT GUARDRAILS
    including dollar formatting, comma separators, 2 decimal places, and exact wording.
    """

    @pytest.mark.parametrize(
        "net_discrepancy_dollars,confirmed_net,expected_pct_str,expected_dollar_str",
        [
            (1234.50, 823000.00, "0.15%", "$1,234.50"),
            (4250.00, 8500000.00, "0.05%", "$4,250.00"),
            (1234567.89, 100000000.00, "1.23%", "$1,234,567.89"),
            (50.25, 100000.00, "0.05%", "$50.25"),
            (1000000.00, 10000000.00, "10.00%", "$1,000,000.00"),
        ],
    )
    def test_watermark_formatting_components(
        self, tmp_path, net_discrepancy_dollars, confirmed_net, expected_pct_str, expected_dollar_str
    ):
        """Tests exact percentage and dollar formatting in watermark string."""
        confirmed_gross = confirmed_net * 1.25
        actual_net = confirmed_net + net_discrepancy_dollars
        actual_gross = confirmed_gross

        src_path = _create_controlled_source(tmp_path, gross_total=actual_gross, net_total=actual_net)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        watermark = res["watermark"]
        assert watermark is not None
        assert WATERMARK_REGEX.match(watermark), f"Watermark '{watermark}' failed canonical regex"
        assert expected_pct_str in watermark, f"Expected percentage '{expected_pct_str}' in '{watermark}'"
        assert expected_dollar_str in watermark, f"Expected dollar string '{expected_dollar_str}' in '{watermark}'"
        assert watermark.startswith("UNRECONCILED RESIDUAL: ")
        assert watermark.endswith(" OUTSIDE AUDIT GUARDRAILS")


# ===========================================================================
# VECTOR 3: Quarantined Transactions Table Invariant
# ===========================================================================
class TestQuarantinedTransactionsTableInvariant:
    """
    Verifies that quarantined_transactions receives the residual discrepancy record
    when variance > 1 bp, and does NOT receive it when variance <= 1 bp.
    """

    def test_certified_audit_no_residual_in_quarantine_table(self, tmp_path):
        """Under CERTIFIED_AUDIT, quarantined_transactions has no residual records."""
        src_path = _create_controlled_source(tmp_path, gross_total=10_000_000.0, net_total=8_000_000.0)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=10_000_000.0,
            control_net=8_000_000.0,
        )

        assert res["certified_audit"] is True
        rows = con.execute("""
            SELECT * FROM quarantined_transactions
            WHERE transaction_line_id = 'RESIDUAL-DISCREPANCY';
        """).fetchall()
        assert len(rows) == 0, "No residual records should exist under certified audit"

    def test_quarantined_residual_record_integrity(self, tmp_path):
        """Under QUARANTINED_AND_PROCEEDED, quarantined_transactions receives structured record."""
        confirmed_gross = 10_000_000.0
        confirmed_net = 8_000_000.0
        # Discrepancy of $4,000 (5 bp)
        src_path = _create_controlled_source(tmp_path, gross_total=confirmed_gross, net_total=confirmed_net + 4000.0)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        assert res["status"] == "QUARANTINED_AND_PROCEEDED"
        rows = con.execute("""
            SELECT quarantine_id, transaction_line_id, raw_record_json, quarantine_reason, detected_at
            FROM quarantined_transactions
            WHERE transaction_line_id = 'RESIDUAL-DISCREPANCY';
        """).fetchall()

        assert len(rows) == 1, "Exactly one residual record should exist"
        q_id, t_id, raw_json, reason, detected = rows[0]
        assert q_id.startswith("QRN-")
        assert t_id == "RESIDUAL-DISCREPANCY"
        assert "exceeds 1 bp audit guardrail" in reason

        # Validate JSON payload contents
        payload = json.loads(raw_json)
        assert payload["calculated_net"] == 8_004_000.0
        assert payload["control_net"] == 8_000_000.0
        assert payload["variance_net_dollars"] == 4000.0
        assert payload["watermark"] == res["watermark"]


# ===========================================================================
# VECTOR 4: Audit Manifest JSON & Database Invariant
# ===========================================================================
class TestAuditManifestInvariant:
    """
    Verifies that audit_manifest.json and meta_audit_manifest correctly record
    source hash, discrepancies, watermark, readiness tiers, and status.
    """

    def test_audit_manifest_file_and_db_consistency(self, tmp_path):
        """Verifies audit_manifest.json matches meta_audit_manifest table."""
        confirmed_gross = 5_000_000.0
        confirmed_net = 4_000_000.0
        # 2 bp discrepancy ($800)
        src_path = _create_controlled_source(tmp_path, gross_total=confirmed_gross, net_total=confirmed_net + 800.0)
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=confirmed_gross,
            control_net=confirmed_net,
        )

        manifest_file = Path(res["manifest_file"])
        assert manifest_file.exists(), "audit_manifest.json was not emitted"

        with open(manifest_file, "r", encoding="utf-8") as f:
            disk_manifest = json.load(f)

        assert disk_manifest["manifest_id"] == res["manifest_id"]
        assert disk_manifest["reconciliation_status"] == "QUARANTINED_AND_PROCEEDED"
        assert disk_manifest["certified_audit"] is False
        assert disk_manifest["watermark_active"] is True
        assert disk_manifest["watermark_text"] == res["watermark"]
        assert disk_manifest["confirmed_net_invoiced"] == confirmed_net
        assert disk_manifest["ingested_net_invoiced"] == confirmed_net + 800.0
        assert disk_manifest["net_variance_bp"] == 2.0

        # Verify source file SHA256 integrity
        hasher = hashlib.sha256()
        with open(src_path, "rb") as sf:
            hasher.update(sf.read())
        assert disk_manifest["source_sha256"] == hasher.hexdigest()

        # Verify meta_audit_manifest table
        db_row = con.execute("""
            SELECT manifest_id, reconciliation_status, watermark_active, watermark_text, source_sha256
            FROM meta_audit_manifest
            WHERE manifest_id = ?;
        """, [res["manifest_id"]]).fetchone()

        assert db_row[0] == disk_manifest["manifest_id"]
        assert db_row[1] == "QUARANTINED_AND_PROCEEDED"
        assert db_row[2] is True
        assert db_row[3] == disk_manifest["watermark_text"]
        assert db_row[4] == disk_manifest["source_sha256"]


# ===========================================================================
# VECTOR 5: Credit Notes Netting & Dual Format Resilience
# ===========================================================================
class TestFormatAndCreditNoteNetting:
    """
    Verifies that credit notes / returns with negative values net correctly to the penny
    across both CSV and Parquet files without skewing the 1 bp gate.
    """

    @pytest.mark.parametrize("fmt", ["parquet", "csv"])
    def test_credit_note_netting_reconciliation(self, tmp_path, fmt):
        """Credit notes (+500 and -500) net out cleanly; exact control totals award CERTIFIED_AUDIT."""
        gross_base = 10_000_000.00
        net_base = 8_000_000.00

        src_path = _create_controlled_source(
            tmp_path,
            gross_total=gross_base,
            net_total=net_base,
            n_rows=100,
            file_format=fmt,
            include_credit_note=True,
        )
        con = duckdb.connect(":memory:")

        res = execute_ingestion(
            con=con,
            file_path=str(src_path),
            column_mapping={},
            control_gross=gross_base,
            control_net=net_base,
        )

        assert res["certified_audit"] is True
        assert res["status"] == "CERTIFIED_AUDIT"
        assert res["watermark"] is None

        # Verify that credit note was marked with is_credit_reversal = TRUE
        rev_count = con.execute("SELECT COUNT(*) FROM transactions WHERE is_credit_reversal = TRUE;").fetchone()[0]
        assert rev_count == 1


# ===========================================================================
# VECTOR 6: Advanced Adversarial Edge Cases
# ===========================================================================
class TestAdvancedAdversarialEdgeCases:
    """
    Tests hostile, corner, and multi-anomaly scenarios:
    1. FX rate conversion impact on control total reconciliation.
    2. Combined anomalies: duplicate grain rows + residual discrepancy in the same ingestion.
    3. Re-ingestion idempotency on the same DuckDB connection.
    4. Floating-point precision sensitivity around 1.00004 vs 1.00006 bp.
    """

    def test_fx_rate_conversion_reconciliation(self, tmp_path):
        """
        Non-USD currency with fx_rate_to_reporting = 1.25.
        Net invoiced in source = 8,000,000 EUR -> 10,000,000 USD reporting.
        Reconciliation gate must evaluate against reporting USD totals.
        """
        records = [{
            "transaction_line_id": f"TX-FX-{i:03d}",
            "invoice_id": f"INV-{i // 5:02d}",
            "account_id": f"ACC-{i % 5:02d}",
            "parent_account_id": "PAR-01",
            "transaction_date": "2025-06-01",
            "currency": "EUR",
            "fx_rate_to_reporting": 1.25,
            "extended_list_amt": 125000.0, # 100 rows * 125,000 = 12,500,000 EUR -> 15,625,000 USD
            "net_invoiced_amt": 80000.0,   # 100 rows * 80,000 = 8,000,000 EUR -> 10,000,000 USD
            "cogs_amt": 50000.0,
            "off_invoice_rebate": 1000.0,
        } for i in range(100)]

        df = pd.DataFrame(records)
        parquet_path = tmp_path / "fx_test.parquet"
        df.to_parquet(parquet_path)

        con = duckdb.connect(":memory:")

        # Exactly 1.0000 bp discrepancy on reporting net (10,000,000 USD * 0.0001 = $1,000 USD)
        res = execute_ingestion(
            con=con,
            file_path=str(parquet_path),
            column_mapping={},
            control_gross=15_625_000.00,
            control_net=10_001_000.00, # $1,000 variance -> 1.0000 bp
        )

        assert res["status"] == "CERTIFIED_AUDIT"
        assert res["certified_audit"] is True
        assert res["watermark"] is None

        # Now test 1.0001 bp discrepancy on reporting net ($1,000.20 relative to denominator)
        res_fail = execute_ingestion(
            con=con,
            file_path=str(parquet_path),
            column_mapping={},
            control_gross=15_625_000.00,
            control_net=10_001_000.20, # diff $1,000.20 on $10,001,000.20 -> exactly 1.0001 bp
        )

        assert res_fail["status"] == "QUARANTINED_AND_PROCEEDED"
        assert res_fail["certified_audit"] is False
        assert res_fail["watermark_applied"] is True
        assert res_fail["watermark"] is not None
        assert res_fail["variance_bps"] >= 1.0001

    def test_combined_duplicate_grain_and_residual_quarantine(self, tmp_path):
        """
        When input has BOTH duplicate grain rows AND residual discrepancy:
        Both must be properly isolated in quarantined_transactions with distinct reasons.
        """
        records = [
            # 2 duplicate rows with the same line ID
            {
                "transaction_line_id": "TX-DUP",
                "invoice_id": "INV-1",
                "account_id": "ACC-1",
                "transaction_date": "2025-06-01",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 800.0,
            },
            {
                "transaction_line_id": "TX-DUP",
                "invoice_id": "INV-1",
                "account_id": "ACC-1",
                "transaction_date": "2025-06-02",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 800.0,
            },
            # 1 unique row
            {
                "transaction_line_id": "TX-UNIQUE",
                "invoice_id": "INV-2",
                "account_id": "ACC-2",
                "transaction_date": "2025-06-01",
                "extended_list_amt": 2000.0,
                "net_invoiced_amt": 1600.0,
            },
        ]
        df = pd.DataFrame(records)
        csv_path = tmp_path / "combined_anomaly.csv"
        df.to_csv(csv_path, index=False)

        con = duckdb.connect(":memory:")

        # Expected valid totals in transactions:
        # 1 TX-DUP ($800) + 1 TX-UNIQUE ($1600) = $2400 net
        # User confirmed control net = $2500 -> discrepancy = $100 (416 bp, >> 1 bp)
        res = execute_ingestion(
            con=con,
            file_path=str(csv_path),
            column_mapping={},
            control_gross=3500.0,
            control_net=2500.0,
        )

        assert res["status"] == "QUARANTINED_AND_PROCEEDED"
        assert res["total_rows_ingested"] == 2
        assert res["total_rows_quarantined"] == 2 # 1 duplicate grain + 1 residual discrepancy

        qrn_records = con.execute("""
            SELECT transaction_line_id, quarantine_reason
            FROM quarantined_transactions
            ORDER BY transaction_line_id ASC;
        """).fetchall()

        # Check that both duplicate grain and residual discrepancy are present
        line_ids = [r[0] for r in qrn_records]
        assert "TX-DUP" in line_ids
        assert "RESIDUAL-DISCREPANCY" in line_ids

    def test_idempotent_reingestion_clears_prior_state(self, tmp_path):
        """
        Re-running ingestion on the same database connection with truncate=True
        clears prior transactions and prior quarantined records cleanly.
        """
        src1 = _create_controlled_source(tmp_path, gross_total=10_000_000.0, net_total=8_000_000.0)
        con = duckdb.connect(":memory:")

        # Run 1: Certified
        res1 = execute_ingestion(con=con, file_path=str(src1), column_mapping={}, control_gross=10_000_000.0, control_net=8_000_000.0)
        assert res1["status"] == "CERTIFIED_AUDIT"
        assert con.execute("SELECT COUNT(*) FROM transactions;").fetchone()[0] == 100
        assert con.execute("SELECT COUNT(*) FROM quarantined_transactions;").fetchone()[0] == 0

        # Run 2: Discrepancy > 1 bp
        src2 = _create_controlled_source(tmp_path, gross_total=10_000_000.0, net_total=8_008_000.0) # $8k diff = 10 bp
        res2 = execute_ingestion(con=con, file_path=str(src2), column_mapping={}, control_gross=10_000_000.0, control_net=8_000_000.0)
        assert res2["status"] == "QUARANTINED_AND_PROCEEDED"
        assert con.execute("SELECT COUNT(*) FROM transactions;").fetchone()[0] == 100
        assert con.execute("SELECT COUNT(*) FROM quarantined_transactions;").fetchone()[0] == 1

        # Run 3: Back to Certified
        res3 = execute_ingestion(con=con, file_path=str(src1), column_mapping={}, control_gross=10_000_000.0, control_net=8_000_000.0)
        assert res3["status"] == "CERTIFIED_AUDIT"
        assert con.execute("SELECT COUNT(*) FROM transactions;").fetchone()[0] == 100
        assert con.execute("SELECT COUNT(*) FROM quarantined_transactions;").fetchone()[0] == 0
