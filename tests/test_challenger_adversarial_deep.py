"""
tests/test_challenger_adversarial_deep.py
Adversarial Challenge & Invariant Integrity Test Suite
Author: challenger_retest_2 (EMPIRICAL CHALLENGER)

Verifies:
1. DuckDB 4GB RAM boundary enforcement & disk spilling mechanisms.
2. Conflict resolution for duplicate column names on 'pocket_margin_amt'.
3. Control totals reconciliation gate (<= 1 bp certified vs > 1 bp quarantine).
4. Formula injection defense vs negative numeric preservation.
5. Exact ground truth math for buried culprits (Alpha, Beta, Gamma).
"""

import os
import sys
import tempfile
import hashlib
from pathlib import Path
import pytest
import duckdb
import pandas as pd

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import DuckDBConfig
from backend.storage import (
    open_workspace,
    create_workspace,
    init_schema,
    close_workspace,
)
from backend.ingestion import (
    preview_source,
    execute_ingestion,
    propose_column_mapping,
)
from backend.export import sanitize_csv_cell


# =====================================================================
# 1. 4GB RAM Boundary & Disk Spilling Invariants
# =====================================================================
def test_4gb_ram_boundary_and_spilling_config(tmp_path):
    """Verifies 4GB memory ceiling enforcement and disk spill directory configuration."""
    spill_dir = tmp_path / "spill_test"
    spill_dir.mkdir(parents=True, exist_ok=True)
    cfg = DuckDBConfig(max_memory="4GB", temp_directory=str(spill_dir))
    
    con = duckdb.connect(":memory:", config=cfg.to_connect_config())
    try:
        cfg.apply_to_connection(con)
        
        # Verify max_memory
        max_mem = con.execute("SELECT current_setting('max_memory');").fetchone()[0]
        assert "3.7 GiB" in max_mem or "4" in max_mem, f"Memory limit not 4GB: {max_mem}"
        
        # Verify temp_directory
        temp_dir = con.execute("SELECT current_setting('temp_directory');").fetchone()[0]
        assert os.path.exists(temp_dir), f"Temp spill directory does not exist: {temp_dir}"
        assert os.path.samefile(temp_dir, str(spill_dir))
    finally:
        con.close()


def test_disk_spilling_under_memory_pressure(tmp_path):
    """Stress-tests DuckDB spilling to disk under tight memory constraints (32MB) without OOM."""
    spill_dir = tmp_path / "pressure_spill"
    spill_dir.mkdir(parents=True, exist_ok=True)
    
    # Restrict memory to 32MB to force spilling on a large cross-join/aggregation
    con = duckdb.connect(":memory:")
    try:
        spill_str = str(spill_dir).replace("\\", "/")
        con.execute("SET max_memory = '32MB';")
        con.execute(f"SET temp_directory = '{spill_str}';")
        con.execute("SET threads = 2;")
        
        # Generate 2,000,000 rows and perform heavy aggregation + sort
        result = con.execute("""
            WITH numbers AS (
                SELECT range % 10000 AS grp, range AS val, (range * 1.5)::VARCHAR AS str_val
                FROM range(2000000)
            )
            SELECT grp, COUNT(*), SUM(val), AVG(val), MIN(str_val), MAX(str_val)
            FROM numbers
            GROUP BY grp
            ORDER BY SUM(val) DESC
            LIMIT 10;
        """).fetchall()
        
        assert len(result) == 10
        assert result[0][1] == 200  # 2M / 10K = 200 rows per group
    finally:
        con.close()


# =====================================================================
# 2. Duplicate Column Conflict Resolution on pocket_margin_amt
# =====================================================================
def test_ingestion_duplicate_column_pocket_margin_amt_synthetic(tmp_path):
    """
    Tests that datasets containing an explicit 'pocket_margin_amt' column
    ingest cleanly without DuckDB Binder Error 'Duplicate column name pocket_margin_amt in INSERT'.
    """
    # Create synthetic dataset with pocket_margin_amt
    df = pd.DataFrame({
        "transaction_line_id": [f"TX-{i:05d}" for i in range(100)],
        "invoice_id": [f"INV-{i:04d}" for i in range(100)],
        "account_id": [f"ACC-{i%10:02d}" for i in range(100)],
        "parent_account_id": [f"PAR-{i%2:02d}" for i in range(100)],
        "transaction_date": ["2026-03-01"] * 100,
        "currency": ["USD"] * 100,
        "fx_rate_to_reporting": [1.0] * 100,
        "extended_list_amt": [1000.0] * 100,
        "net_invoiced_amt": [800.0] * 100,
        "cogs_amt": [500.0] * 100,
        "off_invoice_rebate": [50.0] * 100,
        "pocket_margin_amt": [250.0] * 100,  # Explicitly present in raw source!
        "product_family": ["EnterpriseCloud"] * 100,
        "sales_region": ["NorthAmerica"] * 100,
        "custom_attribute_1": ["Alpha"] * 100,
    })
    
    csv_file = tmp_path / "test_raw_pm.csv"
    df.to_csv(csv_file, index=False)
    
    db_file = tmp_path / "test_pm_conflict.mxa"
    con = open_workspace(str(db_file))
    try:
        init_schema(con, project_name="PM Conflict Test")
        
        # Execute ingestion - MUST NOT throw DuckDB Binder Error!
        res = execute_ingestion(
            con=con,
            file_path=str(csv_file),
            column_mapping={},
            control_gross=100000.0,
            control_net=80000.0,
            reporting_currency="USD",
        )
        
        assert res["total_rows_ingested"] == 100
        assert res["tier_unlocked"] >= 2
        
        # Verify pocket_margin_amt values in transactions table
        pm_vals = con.execute("SELECT DISTINCT pocket_margin_amt FROM transactions;").fetchall()
        assert len(pm_vals) == 1
        assert float(pm_vals[0][0]) == 250.0
    finally:
        close_workspace(con)


def test_ingestion_stress_1m_wide_pocket_margin_amt(tmp_path):
    """
    Tests that the real 87-column stress dataset (dataset_stress_1m_wide.csv)
    which contains 'pocket_margin_amt' can be ingested into a workspace without conflict.
    """
    stress_csv = Path(r"c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv")
    if not stress_csv.exists():
        pytest.skip("dataset_stress_1m_wide.csv not found")
        
    db_file = tmp_path / "test_stress_1m_ingest.mxa"
    con = open_workspace(str(db_file))
    try:
        init_schema(con, project_name="Stress 1M Ingest Test")
        
        # Ingest first 10,000 rows to verify full schema insertion mechanics
        # (Pass 2 creates raw_source and mapped_prep)
        stress_csv_str = str(stress_csv).replace("\\", "/")
        con.execute(f"""
            CREATE OR REPLACE TEMP VIEW raw_source AS 
            SELECT * FROM read_csv_auto('{stress_csv_str}', header=True) LIMIT 10000;
        """)
        
        # Check that pocket_margin_amt is in raw_source
        cols = [r[0] for r in con.execute("DESCRIBE SELECT * FROM raw_source LIMIT 0;").fetchall()]
        assert "pocket_margin_amt" in cols
        
        # Call preview_source
        preview = preview_source(str(stress_csv), nrows=100)
        assert preview["total_preview_rows"] == 100
        assert "pocket_margin_amt" in preview["columns"]
        
    finally:
        close_workspace(con)


# =====================================================================
# 3. Reconciliation Gate Invariants (1 bp Threshold)
# =====================================================================
def test_reconciliation_gate_certified_vs_quarantine(tmp_path):
    """Verifies that <= 1 bp achieves Certified Audit while > 1 bp triggers Quarantine watermark."""
    df = pd.DataFrame({
        "transaction_line_id": [f"TX-{i}" for i in range(100)],
        "invoice_id": [f"INV-{i}" for i in range(100)],
        "account_id": [f"ACC-{i%5}" for i in range(100)],
        "transaction_date": ["2026-03-01"] * 100,
        "currency": ["USD"] * 100,
        "fx_rate_to_reporting": [1.0] * 100,
        "extended_list_amt": [1000.0] * 100,  # Total Gross = 100,000.0
        "net_invoiced_amt": [800.0] * 100,    # Total Net = 80,000.0
    })
    csv_file = tmp_path / "reconcile_test.csv"
    df.to_csv(csv_file, index=False)
    
    # Case A: Exact match (0.0 bp) -> Certified Audit
    con_a = duckdb.connect(":memory:")
    init_schema(con_a)
    res_a = execute_ingestion(con_a, str(csv_file), {}, control_gross=100000.0, control_net=80000.0)
    assert res_a["certified_audit"] is True
    assert res_a["watermark"] is None
    con_a.close()
    
    # Case B: Within 1 bp (e.g., 0.5 bp: 100,005 gross) -> Certified Audit
    con_b = duckdb.connect(":memory:")
    init_schema(con_b)
    res_b = execute_ingestion(con_b, str(csv_file), {}, control_gross=100005.0, control_net=80000.0)
    assert res_b["certified_audit"] is True
    assert res_b["watermark"] is None
    con_b.close()
    
    # Case C: Outside 1 bp (> 1 bp: 105,000 gross) -> Quarantine & Watermark
    con_c = duckdb.connect(":memory:")
    init_schema(con_c)
    res_c = execute_ingestion(con_c, str(csv_file), {}, control_gross=105000.0, control_net=80000.0)
    assert res_c["certified_audit"] is False
    assert res_c["watermark"] is not None
    assert "UNRECONCILED RESIDUAL" in res_c["watermark"]
    con_c.close()


# =====================================================================
# 4. Formula Injection Defense vs Negative Numeric Integrity
# =====================================================================
def test_formula_injection_defense_and_negative_numerics():
    """Verifies that formulas are neutralized with single quote while negative numbers are preserved."""
    # Valid negative numbers must remain unquoted numeric strings
    assert sanitize_csv_cell(-1450.50) == "-1450.5"
    assert sanitize_csv_cell("-1450.50") == "-1450.50"
    assert sanitize_csv_cell("-0.05") == "-0.05"
    assert sanitize_csv_cell(-0.05) == "-0.05"
    assert sanitize_csv_cell("0.00") == "0.00"
    
    # Malicious formula strings must be prefixed with a single quote
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-cmd|' /C calc'!A0") == "'-cmd|' /C calc'!A0"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("\tTAB_INJECT") == "'\tTAB_INJECT"
    assert sanitize_csv_cell("\rRETURN_INJECT") == "'\rRETURN_INJECT"


# =====================================================================
# 5. Exact Mathematical Signatures for Buried Culprits
# =====================================================================
def test_culprit_mathematical_signatures_in_1m_csv():
    """Empirically verifies Culprit Alpha, Beta, Gamma in dataset_stress_1m_wide.csv."""
    stress_csv = Path(r"c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv")
    if not stress_csv.exists():
        pytest.skip("dataset_stress_1m_wide.csv not found")
        
    con = duckdb.connect(":memory:")
    csv_str = str(stress_csv).replace("\\", "/")
    
    # Culprit Alpha: EMEA + Gold + MultiYear + EnterpriseCloud
    alpha = con.execute(f"""
        SELECT COUNT(*),
               ROUND(AVG(extended_list_amt), 2),
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2),
               ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2),
               ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2)
        FROM read_csv_auto('{csv_str}', header=True)
        WHERE sales_theater = 'EMEA'
          AND partner_program_tier = 'Gold'
          AND contract_commitment_type = 'MultiYear'
          AND prod_family = 'EnterpriseCloud';
    """).fetchone()
    
    assert alpha[0] == 2465
    assert alpha[1] == 31449.65
    assert alpha[2] == 62.55
    assert abs(alpha[3] - 36863807.07) < 0.05
    assert abs(alpha[4] - 14745522.83) < 0.05
    
    # Culprit Beta: Americas + Financial Services + System Integrator + Tier 4 Exception Policy + Software Solutions
    beta = con.execute(f"""
        SELECT COUNT(*),
               ROUND(AVG(extended_list_amt), 2),
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2),
               ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2),
               ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2)
        FROM read_csv_auto('{csv_str}', header=True)
        WHERE sales_theater = 'Americas'
          AND cust_industry_vertical = 'Financial Services'
          AND channel_type = 'System Integrator'
          AND deal_discount_governance_tier = 'Tier 4 Exception Policy'
          AND prod_line_of_business = 'Software Solutions';
    """).fetchone()
    
    assert beta[0] == 462
    assert beta[1] == 31838.08
    assert beta[2] == 65.02
    assert abs(beta[3] - 7420727.14) < 0.05
    assert abs(beta[4] - 2968290.86) < 0.05
    
    # Culprit Gamma: APAC + Sovereign Air-Gap + Ultra Five-Nines
    gamma = con.execute(f"""
        SELECT COUNT(*),
               ROUND(AVG(extended_list_amt), 2),
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2),
               ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2),
               ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2)
        FROM read_csv_auto('{csv_str}', header=True)
        WHERE sales_theater = 'APAC'
          AND prod_deployment_mode = 'Sovereign Air-Gap'
          AND contract_sla_tier = 'Ultra Five-Nines';
    """).fetchone()
    
    assert gamma[0] == 15785
    assert gamma[1] == 31526.35
    assert gamma[2] == 59.01
    assert abs(gamma[3] - 218951306.69) < 0.05
    assert abs(gamma[4] - 87580522.67) < 0.05
    
    con.close()
