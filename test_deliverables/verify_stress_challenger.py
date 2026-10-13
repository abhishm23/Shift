"""
verify_stress_challenger.py
Empirical Adversarial Verification of Sift Stress Datasets (1M CSV and 15M Parquet)
Author: challenger_stress_1
"""

import sys
import time
import hashlib
import json
from pathlib import Path
from typing import Tuple, List, Dict
import duckdb

CSV_PATH = Path(r"c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv")
PARQUET_PATH = Path(r"c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet")
MANIFEST_PATH = Path(r"c:/Shift/test_deliverables/datasets/DATASET_MANIFEST.md")

EXPECTED_HASHES = {
    "1m_csv": "ee54dd538f4158bf7ca4317e1b4fbbaee2fef70b99c2b084c9d8eb9ebce865af",
    "15m_parquet": "f079a90595101d9a1e5c6323cd0389e9f651c23f9f2caa89d3996b5190633c2c",
}

EXPECTED_GROUND_TRUTH = {
    "1m_csv": {
        "row_count": 1000000,
        "col_count": 87,
        "alpha": {
            "rows": 2465,
            "mean_list": 31449.65,
            "mean_disc_pct": 62.55,
            "def_gap": 36863807.07,
            "act_opp": 14745522.83,
        },
        "beta": {
            "rows": 462,
            "mean_list": 31838.08,
            "mean_disc_pct": 65.02,
            "def_gap": 7420727.14,
            "act_opp": 2968290.86,
        },
        "gamma": {
            "rows": 15785,
            "mean_list": 31526.35,
            "mean_disc_pct": 59.01,
            "def_gap": 218951306.69,
            "act_opp": 87580522.67,
        },
    },
    "15m_parquet": {
        "row_count": 15000000,
        "col_count": 87,
        "alpha": {
            "rows": 37472,
            "mean_list": 31795.44,
            "mean_disc_pct": 62.48,
            "def_gap": 565779610.76,
            "act_opp": 226311844.30,
        },
        "beta": {
            "rows": 7877,
            "mean_list": 30969.73,
            "mean_disc_pct": 65.01,
            "def_gap": 122057902.51,
            "act_opp": 48823161.00,
        },
        "gamma": {
            "rows": 235374,
            "mean_list": 31473.99,
            "mean_disc_pct": 58.99,
            "def_gap": 3258354279.89,
            "act_opp": 1303341711.96,
        },
    }
}

CANONICAL_GRAIN = [
    "transaction_line_id", "invoice_id", "account_id", "customer_name",
    "parent_account_id", "transaction_date", "currency"
]

NUMERICAL_COLS = [
    "extended_list_amt", "net_invoiced_amt", "cogs_amt", "off_invoice_rebate",
    "fx_rate_to_reporting", "list_unit_price", "order_quantity", "base_discount_amt",
    "promo_discount_amt", "freight_shipping_amt", "tax_vat_amt", "standard_margin_amt",
    "pocket_margin_amt", "gross_booking_val", "net_booking_val", "rebate_accrual_pct",
    "payment_terms_penalty", "credit_adjustment_amt"
]

def compute_sha256(filepath: Path) -> Tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with open(filepath, "rb") as f:
        while chunk := f.read(10 * 1024 * 1024):  # 10MB chunks
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size

def run_adversarial_verification():
    print("=" * 80)
    print("EMPIRICAL ADVERSARIAL VERIFICATION — SIFT STRESS DATASETS & BURIED CULPRIT MATH")
    print("=" * 80)
    
    results = {}
    passed_all = True

    # -------------------------------------------------------------
    # 1. Checksum and File Existence Verification
    # -------------------------------------------------------------
    print("\n[Phase 1] Checksum & File Integrity Verification")
    if not CSV_PATH.exists():
        print(f"FAIL: CSV file missing at {CSV_PATH}")
        return False
    if not PARQUET_PATH.exists():
        print(f"FAIL: Parquet file missing at {PARQUET_PATH}")
        return False
    if not MANIFEST_PATH.exists():
        print(f"FAIL: Manifest missing at {MANIFEST_PATH}")
        return False

    print(f"Hashing CSV: {CSV_PATH.name}...")
    t0 = time.time()
    csv_hash, csv_bytes = compute_sha256(CSV_PATH)
    t_csv_hash = time.time() - t0
    print(f"  CSV SHA-256: {csv_hash} (computed in {t_csv_hash:.2f}s, {csv_bytes:,} bytes)")
    csv_hash_ok = (csv_hash == EXPECTED_HASHES["1m_csv"])
    print(f"  CSV Hash Match: {'PASS' if csv_hash_ok else 'FAIL'}")
    if not csv_hash_ok:
        passed_all = False

    print(f"Hashing Parquet: {PARQUET_PATH.name}...")
    t0 = time.time()
    pq_hash, pq_bytes = compute_sha256(PARQUET_PATH)
    t_pq_hash = time.time() - t0
    print(f"  Parquet SHA-256: {pq_hash} (computed in {t_pq_hash:.2f}s, {pq_bytes:,} bytes)")
    pq_hash_ok = (pq_hash == EXPECTED_HASHES["15m_parquet"])
    print(f"  Parquet Hash Match: {'PASS' if pq_hash_ok else 'FAIL'}")
    if not pq_hash_ok:
        passed_all = False

    results["checksums"] = {
        "csv": {"hash": csv_hash, "size": csv_bytes, "match": csv_hash_ok},
        "parquet": {"hash": pq_hash, "size": pq_bytes, "match": pq_hash_ok},
    }

    # -------------------------------------------------------------
    # Initialize DuckDB
    # -------------------------------------------------------------
    con = duckdb.connect(":memory:")
    con.execute("SET memory_limit = '4GB'")
    con.execute("SET threads = 4")

    # -------------------------------------------------------------
    # 2. Verify 1M CSV Schema & Rows
    # -------------------------------------------------------------
    print("\n[Phase 2] In-Process DuckDB Scan: 1M Wide CSV")
    t0 = time.time()
    csv_escaped = str(CSV_PATH).replace("\\", "/")
    
    # Get column names and types
    col_info = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{csv_escaped}', header=True) LIMIT 0").fetchall()
    csv_cols = [c[0] for c in col_info]
    csv_col_count = len(csv_cols)
    print(f"  Detected Columns: {csv_col_count} (Expected: 87)")
    col_count_ok = (csv_col_count == 87)
    if not col_count_ok:
        passed_all = False

    # Check breakdown
    csv_canonical = [c for c in csv_cols if c in CANONICAL_GRAIN]
    csv_numerical = [c for c in csv_cols if c in NUMERICAL_COLS]
    csv_categorical = [c for c in csv_cols if c not in CANONICAL_GRAIN and c not in NUMERICAL_COLS]
    print(f"  Canonical Identifiers: {len(csv_canonical)} (Expected: 7)")
    print(f"  Numerical Metrics: {len(csv_numerical)} (Expected: 18)")
    print(f"  Categorical Dimensions: {len(csv_categorical)} (Expected: 62)")
    
    csv_rows = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{csv_escaped}', header=True)").fetchone()[0]
    t_csv_scan = time.time() - t0
    print(f"  Row Count: {csv_rows:,} in {t_csv_scan:.2f}s (Expected: 1,000,000)")
    csv_rows_ok = (csv_rows == 1000000)
    if not csv_rows_ok:
        passed_all = False

    # Check uniqueness of transaction_line_id
    distinct_ids = con.execute(f"SELECT COUNT(DISTINCT transaction_line_id) FROM read_csv_auto('{csv_escaped}', header=True)").fetchone()[0]
    line_unique_ok = (distinct_ids == csv_rows)
    print(f"  Unique line IDs: {distinct_ids:,} (100% unique: {'PASS' if line_unique_ok else 'FAIL'})")
    if not line_unique_ok:
        passed_all = False

    # Check financial invariant: net_invoiced_amt <= extended_list_amt and positive values
    inv_violations = con.execute(f"""
        SELECT COUNT(*) FROM read_csv_auto('{csv_escaped}', header=True)
        WHERE extended_list_amt < 0 OR net_invoiced_amt < 0 OR net_invoiced_amt > extended_list_amt
    """).fetchone()[0]
    print(f"  Discount/Amount Integrity Violations: {inv_violations} (Expected: 0)")
    if inv_violations > 0:
        passed_all = False

    # Single-dimension distribution health
    print("  Testing 1D Single-Dimension Aggregate Health (sales_theater)...")
    theaters_csv = con.execute(f"""
        SELECT sales_theater, COUNT(*) as cnt,
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc
        FROM read_csv_auto('{csv_escaped}', header=True)
        GROUP BY sales_theater ORDER BY sales_theater
    """).fetchall()
    for th, cnt, md in theaters_csv:
        in_band = (11.0 <= md <= 15.0)
        print(f"    * {th}: {cnt:,} rows, Mean Discount: {md}% (Healthy 11-15%: {'PASS' if in_band else 'FAIL'})")
        if not in_band:
            passed_all = False

    # Test prod_family 1D distribution
    print("  Testing 1D Single-Dimension Aggregate Health (prod_family)...")
    families_csv = con.execute(f"""
        SELECT prod_family, COUNT(*) as cnt,
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc
        FROM read_csv_auto('{csv_escaped}', header=True)
        GROUP BY prod_family ORDER BY prod_family
    """).fetchall()
    for pf, cnt, md in families_csv:
        in_band = (11.0 <= md <= 15.5)
        print(f"    * {pf}: {cnt:,} rows, Mean Discount: {md}% (Healthy 11-15.5%: {'PASS' if in_band else 'FAIL'})")
        if not in_band:
            passed_all = False

    # Culprit checks in 1M CSV
    print("  Testing Culprit Math in 1M CSV:")
    
    # Culprit Alpha
    alpha_1m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_csv_auto('{csv_escaped}', header=True)
        WHERE sales_theater = 'EMEA'
          AND partner_program_tier = 'Gold'
          AND contract_commitment_type = 'MultiYear'
          AND prod_family = 'EnterpriseCloud'
    """).fetchone()
    print(f"    [Alpha 4-Level]: Rows={alpha_1m[0]:,}, MeanList=${alpha_1m[1]:,}, MeanDisc={alpha_1m[2]}%, DefGap=${alpha_1m[3]:,}, ActOpp=${alpha_1m[4]:,}")
    exp_a = EXPECTED_GROUND_TRUTH["1m_csv"]["alpha"]
    alpha_1m_ok = (alpha_1m[0] == exp_a["rows"] and abs(alpha_1m[3] - exp_a["def_gap"]) < 0.05 and abs(alpha_1m[4] - exp_a["act_opp"]) < 0.05)
    print(f"    [Alpha 1M Verdict]: {'PASS' if alpha_1m_ok else 'FAIL'}")
    if not alpha_1m_ok:
        passed_all = False

    # Culprit Beta
    beta_1m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_csv_auto('{csv_escaped}', header=True)
        WHERE sales_theater = 'Americas'
          AND cust_industry_vertical = 'Financial Services'
          AND channel_type = 'System Integrator'
          AND deal_discount_governance_tier = 'Tier 4 Exception Policy'
          AND prod_line_of_business = 'Software Solutions'
    """).fetchone()
    print(f"    [Beta 5-Level]: Rows={beta_1m[0]:,}, MeanList=${beta_1m[1]:,}, MeanDisc={beta_1m[2]}%, DefGap=${beta_1m[3]:,}, ActOpp=${beta_1m[4]:,}")
    exp_b = EXPECTED_GROUND_TRUTH["1m_csv"]["beta"]
    beta_1m_ok = (beta_1m[0] == exp_b["rows"] and abs(beta_1m[3] - exp_b["def_gap"]) < 0.05 and abs(beta_1m[4] - exp_b["act_opp"]) < 0.05)
    print(f"    [Beta 1M Verdict]: {'PASS' if beta_1m_ok else 'FAIL'}")
    if not beta_1m_ok:
        passed_all = False

    # Culprit Gamma
    gamma_1m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_csv_auto('{csv_escaped}', header=True)
        WHERE sales_theater = 'APAC'
          AND prod_deployment_mode = 'Sovereign Air-Gap'
          AND contract_sla_tier = 'Ultra Five-Nines'
    """).fetchone()
    print(f"    [Gamma 3-Level]: Rows={gamma_1m[0]:,}, MeanList=${gamma_1m[1]:,}, MeanDisc={gamma_1m[2]}%, DefGap=${gamma_1m[3]:,}, ActOpp=${gamma_1m[4]:,}")
    exp_g = EXPECTED_GROUND_TRUTH["1m_csv"]["gamma"]
    gamma_1m_ok = (gamma_1m[0] == exp_g["rows"] and abs(gamma_1m[3] - exp_g["def_gap"]) < 0.05 and abs(gamma_1m[4] - exp_g["act_opp"]) < 0.05)
    print(f"    [Gamma 1M Verdict]: {'PASS' if gamma_1m_ok else 'FAIL'}")
    if not gamma_1m_ok:
        passed_all = False

    # -------------------------------------------------------------
    # 3. Verify 15M Parquet Schema & Rows
    # -------------------------------------------------------------
    print("\n[Phase 3] In-Process DuckDB Scan: 15M Wide Parquet")
    t0 = time.time()
    pq_escaped = str(PARQUET_PATH).replace("\\", "/")

    # Get column names and types
    pq_col_info = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{pq_escaped}') LIMIT 0").fetchall()
    pq_cols = [c[0] for c in pq_col_info]
    pq_col_count = len(pq_cols)
    print(f"  Detected Columns: {pq_col_count} (Expected: 87)")
    pq_col_count_ok = (pq_col_count == 87 and pq_cols == csv_cols)
    print(f"  Schema Column Alignment: {'PASS' if pq_col_count_ok else 'FAIL'}")
    if not pq_col_count_ok:
        passed_all = False

    pq_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{pq_escaped}')").fetchone()[0]
    t_pq_scan = time.time() - t0
    print(f"  Row Count: {pq_rows:,} in {t_pq_scan:.2f}s (Expected: 15,000,000)")
    pq_rows_ok = (pq_rows == 15000000)
    if not pq_rows_ok:
        passed_all = False

    # Check financial invariants in Parquet
    pq_inv_violations = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{pq_escaped}')
        WHERE extended_list_amt < 0 OR net_invoiced_amt < 0 OR net_invoiced_amt > extended_list_amt
    """).fetchone()[0]
    print(f"  Discount/Amount Integrity Violations: {pq_inv_violations} (Expected: 0)")
    if pq_inv_violations > 0:
        passed_all = False

    # Single-dimension distribution health on 15M
    print("  Testing 1D Single-Dimension Aggregate Health (sales_theater)...")
    theaters_pq = con.execute(f"""
        SELECT sales_theater, COUNT(*) as cnt,
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc
        FROM read_parquet('{pq_escaped}')
        GROUP BY sales_theater ORDER BY sales_theater
    """).fetchall()
    for th, cnt, md in theaters_pq:
        in_band = (11.0 <= md <= 15.0)
        print(f"    * {th}: {cnt:,} rows, Mean Discount: {md}% (Healthy 11-15%: {'PASS' if in_band else 'FAIL'})")
        if not in_band:
            passed_all = False

    # Test prod_family 1D distribution on 15M
    print("  Testing 1D Single-Dimension Aggregate Health (prod_family)...")
    families_pq = con.execute(f"""
        SELECT prod_family, COUNT(*) as cnt,
               ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc
        FROM read_parquet('{pq_escaped}')
        GROUP BY prod_family ORDER BY prod_family
    """).fetchall()
    for pf, cnt, md in families_pq:
        in_band = (11.0 <= md <= 15.5)
        print(f"    * {pf}: {cnt:,} rows, Mean Discount: {md}% (Healthy 11-15.5%: {'PASS' if in_band else 'FAIL'})")
        if not in_band:
            passed_all = False

    # Culprit checks in 15M Parquet
    print("  Testing Culprit Math in 15M Parquet:")
    
    # Culprit Alpha 15M
    alpha_15m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_parquet('{pq_escaped}')
        WHERE sales_theater = 'EMEA'
          AND partner_program_tier = 'Gold'
          AND contract_commitment_type = 'MultiYear'
          AND prod_family = 'EnterpriseCloud'
    """).fetchone()
    print(f"    [Alpha 4-Level]: Rows={alpha_15m[0]:,}, MeanList=${alpha_15m[1]:,}, MeanDisc={alpha_15m[2]}%, DefGap=${alpha_15m[3]:,}, ActOpp=${alpha_15m[4]:,}")
    exp_a_15 = EXPECTED_GROUND_TRUTH["15m_parquet"]["alpha"]
    alpha_15m_ok = (alpha_15m[0] == exp_a_15["rows"] and abs(alpha_15m[3] - exp_a_15["def_gap"]) < 0.05 and abs(alpha_15m[4] - exp_a_15["act_opp"]) < 0.05)
    print(f"    [Alpha 15M Verdict]: {'PASS' if alpha_15m_ok else 'FAIL'}")
    if not alpha_15m_ok:
        passed_all = False

    # Culprit Beta 15M
    beta_15m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_parquet('{pq_escaped}')
        WHERE sales_theater = 'Americas'
          AND cust_industry_vertical = 'Financial Services'
          AND channel_type = 'System Integrator'
          AND deal_discount_governance_tier = 'Tier 4 Exception Policy'
          AND prod_line_of_business = 'Software Solutions'
    """).fetchone()
    print(f"    [Beta 5-Level]: Rows={beta_15m[0]:,}, MeanList=${beta_15m[1]:,}, MeanDisc={beta_15m[2]}%, DefGap=${beta_15m[3]:,}, ActOpp=${beta_15m[4]:,}")
    exp_b_15 = EXPECTED_GROUND_TRUTH["15m_parquet"]["beta"]
    beta_15m_ok = (beta_15m[0] == exp_b_15["rows"] and abs(beta_15m[3] - exp_b_15["def_gap"]) < 0.05 and abs(beta_15m[4] - exp_b_15["act_opp"]) < 0.05)
    print(f"    [Beta 15M Verdict]: {'PASS' if beta_15m_ok else 'FAIL'}")
    if not beta_15m_ok:
        passed_all = False

    # Culprit Gamma 15M
    gamma_15m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_parquet('{pq_escaped}')
        WHERE sales_theater = 'APAC'
          AND prod_deployment_mode = 'Sovereign Air-Gap'
          AND contract_sla_tier = 'Ultra Five-Nines'
    """).fetchone()
    print(f"    [Gamma 3-Level]: Rows={gamma_15m[0]:,}, MeanList=${gamma_15m[1]:,}, MeanDisc={gamma_15m[2]}%, DefGap=${gamma_15m[3]:,}, ActOpp=${gamma_15m[4]:,}")
    exp_g_15 = EXPECTED_GROUND_TRUTH["15m_parquet"]["gamma"]
    gamma_15m_ok = (gamma_15m[0] == exp_g_15["rows"] and abs(gamma_15m[3] - exp_g_15["def_gap"]) < 0.05 and abs(gamma_15m[4] - exp_g_15["act_opp"]) < 0.05)
    print(f"    [Gamma 15M Verdict]: {'PASS' if gamma_15m_ok else 'FAIL'}")
    if not gamma_15m_ok:
        passed_all = False

    # -------------------------------------------------------------
    # 4. Background Transaction Non-Anomalous Distribution Check
    # -------------------------------------------------------------
    print("\n[Phase 4] Verifying Background Distribution (Uninjected Slices)")
    bg_stats = con.execute(f"""
        SELECT 
            COUNT(*) as bg_rows,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc,
            ROUND(APPROX_QUANTILE((extended_list_amt - net_invoiced_amt) / extended_list_amt, 0.75) * 100, 2) as p75_disc
        FROM read_parquet('{pq_escaped}')
        WHERE NOT (
            (sales_theater = 'EMEA' AND partner_program_tier = 'Gold' AND contract_commitment_type = 'MultiYear' AND prod_family = 'EnterpriseCloud')
            OR
            (sales_theater = 'Americas' AND cust_industry_vertical = 'Financial Services' AND channel_type = 'System Integrator' AND deal_discount_governance_tier = 'Tier 4 Exception Policy' AND prod_line_of_business = 'Software Solutions')
            OR
            (sales_theater = 'APAC' AND prod_deployment_mode = 'Sovereign Air-Gap' AND contract_sla_tier = 'Ultra Five-Nines')
        )
    """).fetchone()
    print(f"  Background Non-Culprit Rows: {bg_stats[0]:,} / {pq_rows:,}")
    print(f"  Background Mean Discount: {bg_stats[1]}% (Expected: ~12.0% - 12.5%)")
    print(f"  Background P75 Discount: {bg_stats[2]}% (Expected: ~15.00%)")
    bg_ok = (11.8 <= bg_stats[1] <= 12.3 and 14.8 <= bg_stats[2] <= 15.2)
    print(f"  Background Health & Baseline Integrity: {'PASS' if bg_ok else 'FAIL'}")
    if not bg_ok:
        passed_all = False

    con.close()

    print("\n" + "=" * 80)
    print(f"ADVERSARIAL VERIFICATION RESULT: {'OVERALL PASS (APPROVE)' if passed_all else 'OVERALL FAIL (REQUEST_CHANGES)'}")
    print("=" * 80)
    return passed_all

if __name__ == "__main__":
    from typing import Tuple
    success = run_adversarial_verification()
    sys.exit(0 if success else 1)
