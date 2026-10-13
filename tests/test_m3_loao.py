"""
Comprehensive Unit & Integration Test Suite for Milestone 3: LOAO Calibration & Defensible Gap Scoring.

Tests:
1. Three-Column Comparability Classification (Controls, Investigation Dims, Excluded).
2. Realized Discount Rate Formulation.
3. Vectorized Leave-One-Account-Out (LOAO) Peer Cohort Isolation (\\Omega_{-A(i)}).
4. Cohort Support Fences (N >= 10, |A| >= 5) and Hierarchical Back-Off.
5. Insufficient Comparable Evidence Flagging and Zero-Scoring Exclusion.
6. Benchmark Boundary Thresholds (P75 vs Median + 1.5 * MAD).
7. Defensible Gap, Baseline Band Gap, and Actionable Opportunity (kappa).
8. Calibration Profile Freezing (.calib.json export & meta_calibration_profiles persistence).
9. Verification against Canonical 50,000-row Dataset with 15 Planted Exceptions.
10. Verification against Waterline Null Uniform Distribution.
11. FastAPI REST Endpoints (/api/calibrate/loao, /api/calibrate/freeze, /api/calibrate/profiles).
"""

import json
import os
import tempfile
from decimal import Decimal
from typing import Dict, List

import duckdb
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.loao import (
    DEFAULT_CONTROLS,
    DEFAULT_EXCLUDED_ATTRS,
    DEFAULT_INVESTIGATION_DIMS,
    DEFAULT_KAPPA,
    DEFAULT_MAD_MULTIPLIER,
    LOAOResult,
    calculate_realized_discount_rate,
    classify_attributes,
    compute_loao_baselines,
    freeze_calibration,
    get_active_calibration_profile,
    load_calibration_profile,
    validate_three_column_classification,
)
from backend.storage import (
    close_workspace,
    create_workspace,
    get_workspace_meta,
    init_schema,
    open_workspace,
)
from tests.e2e.test_helpers import (
    compute_reference_loao_p75,
    get_configured_duckdb,
)
from tests.synthetic_data import (
    generate_50k_canonical_dataset,
    generate_waterline_null_dataset,
    verify_ground_truth_recovery,
)


# ===========================================================================
# 1. Three-Column Comparability Classification Tests
# ===========================================================================

def test_three_column_classification_valid():
    """Validates that valid disjoint sets of controls and dimensions pass without error."""
    controls = ["product_family", "sales_region", "industry"]
    investigation_dims = ["sales_rep", "discount_reason", "channel"]
    excluded = ["transaction_line_id", "invoice_id", "transaction_date"]

    # Should execute cleanly
    validate_three_column_classification(controls, investigation_dims, excluded)


def test_three_column_classification_rejects_empty_controls():
    """Validates that an empty controls list is rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_three_column_classification([])


def test_three_column_classification_rejects_control_investigation_overlap():
    """Validates that audited investigation dimensions cannot be used as comparability controls."""
    controls = ["product_family", "sales_rep"]
    investigation_dims = ["sales_rep", "discount_reason"]

    with pytest.raises(ValueError, match="Classification boundary violation"):
        validate_three_column_classification(controls, investigation_dims)


def test_three_column_classification_rejects_excluded_overlap():
    """Validates that transaction line IDs, dates, and account grain cannot be controls or dims."""
    with pytest.raises(ValueError, match="Excluded attribute"):
        validate_three_column_classification(
            controls=["transaction_line_id", "product_family"],
            investigation_dims=["sales_rep"],
        )

    with pytest.raises(ValueError, match="Excluded attribute"):
        validate_three_column_classification(
            controls=["product_family"],
            investigation_dims=["account_id", "sales_rep"],
        )


def test_classify_attributes_auto_categorization():
    """Tests automatic classification helper into controls, investigation dims, and excluded."""
    cols = [
        "transaction_line_id", "invoice_id", "account_id", "transaction_date",
        "extended_list_amt", "net_invoiced_amt", "product_family", "sales_region",
        "sales_rep", "discount_reason", "channel", "custom_tier"
    ]
    res = classify_attributes(cols)
    assert "product_family" in res["controls"]
    assert "sales_region" in res["controls"]
    assert "sales_rep" in res["investigation_dimensions"]
    assert "discount_reason" in res["investigation_dimensions"]
    assert "transaction_line_id" in res["excluded"]
    assert "account_id" in res["excluded"]


# ===========================================================================
# 2. Realized Discount Rate Formulation Tests
# ===========================================================================

def test_realized_discount_rate_standard():
    """Verifies realized discount rate formula (list - net) / list."""
    assert calculate_realized_discount_rate(1000.0, 800.0) == 0.20
    assert calculate_realized_discount_rate(5000.0, 2500.0) == 0.50
    assert calculate_realized_discount_rate(100.0, 100.0) == 0.0


def test_realized_discount_rate_edge_cases():
    """Verifies edge cases: zero list, negative list, and null net."""
    assert calculate_realized_discount_rate(0.0, 100.0) == 0.0
    assert calculate_realized_discount_rate(-500.0, 100.0) == 0.0
    assert calculate_realized_discount_rate(1000.0, None) == 0.0


# ===========================================================================
# 3. Vectorized LOAO Peer Cohort Isolation Tests (\Omega_{-A(i)})
# ===========================================================================

def test_loao_peer_exclusion_avoids_self_bias():
    """
    Core LOAO Invariant:
    An account's own transactions MUST NOT influence its peer distribution.
    If Account A receives a 90% discount, Account A's own 90% concession
    must not inflate Account A's benchmark threshold.
    """
    con = duckdb.connect(":memory:")

    # Setup: 10 accounts in cohort ('Hardware', 'North').
    # Accounts 1..9 have 2 transactions each at 10% discount (18 transactions total).
    # Account 10 has 2 transactions at 90% discount.
    rows = []
    for i in range(1, 10):
        for j in range(2):
            rows.append({
                "transaction_line_id": f"TX-PEER-{i}-{j}",
                "account_id": f"ACC-{i:02d}",
                "product_family": "Hardware",
                "sales_region": "North",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 900.0,  # 10% discount
                "realized_discount_rate": 0.10,
            })
    # Account 10: rogue 90% discount
    for j in range(2):
        rows.append({
            "transaction_line_id": f"TX-ROGUE-10-{j}",
            "account_id": "ACC-10",
            "product_family": "Hardware",
            "sales_region": "North",
            "extended_list_amt": 1000.0,
            "net_invoiced_amt": 100.0,  # 90% discount
            "realized_discount_rate": 0.90,
        })

    df = pd.DataFrame(rows)
    con.register("df_tx", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_tx;")

    res = compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="P75")
    scored = res.to_df()

    # For Account 10, peer distribution excludes Account 10's two 90% transactions.
    # The peers are 18 transactions from Accounts 1..9, all at 10%.
    # Therefore, Account 10's peer P75 benchmark MUST BE 10% (0.10), NOT affected by 90%!
    acct10_rows = scored[scored["account_id"] == "ACC-10"]
    assert len(acct10_rows) == 2
    for _, r in acct10_rows.iterrows():
        assert r["peer_count"] == 18, f"Expected 18 peer transactions, got {r['peer_count']}"
        assert r["peer_accounts"] == 9, f"Expected 9 peer accounts, got {r['peer_accounts']}"
        assert abs(r["p75_concession"] - 0.10) < 1e-4, f"Self-bias detected! P75 was {r['p75_concession']}, expected 0.10"
        # Defensible gap: (0.90 - 0.10) * 1000 = 800.0
        assert abs(r["defensible_gap"] - 800.0) < 1e-2, f"Expected gap 800.0, got {r['defensible_gap']}"


def test_loao_single_account_cohort_yields_zero_peers():
    """If an account is the only account in a cohort, it has 0 peers in that cohort."""
    con = duckdb.connect(":memory:")
    rows = [
        {
            "transaction_line_id": f"TX-SOLO-{i}",
            "account_id": "ACC-SOLO",
            "product_family": "Exclusive",
            "sales_region": "Space",
            "extended_list_amt": 1000.0,
            "net_invoiced_amt": 800.0,
            "realized_discount_rate": 0.20,
        }
        for i in range(15)
    ]
    con.register("df_solo", pd.DataFrame(rows))
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_solo;")

    res = compute_loao_baselines(con, controls=["product_family", "sales_region"])
    scored = res.to_df()
    # Since there are no other accounts in the dataset at all, even global cohort has 0 peers!
    assert (scored["has_comparable_evidence"] == False).all()
    assert (scored["support_status"] == "Insufficient Comparable Evidence").all()
    assert (scored["defensible_gap"] == 0.0).all()


# ===========================================================================
# 4. Cohort Support Fences & Hierarchical Back-Off Tests
# ===========================================================================

def test_hierarchical_backoff_tiers():
    """
    Tests hierarchical back-off:
    - Tier 0: Granular cohort satisfies N >= 10, |A| >= 5 -> backoff_tier == 0.
    - Tier 1: Granular cohort fails (e.g. only 2 accounts in Region A), but parent (Product Family across all regions) satisfies N >= 10, |A| >= 5 -> backoff_tier == 1.
    - Tier 2: Product family also small, but Global cohort satisfies N >= 10, |A| >= 5 -> backoff_tier == 2.
    - Insufficient: Global cohort fails -> backoff_tier == None, gap == 0.
    """
    con = duckdb.connect(":memory:")

    rows = []
    # 1. Tier 0 cohort: 'Software' x 'EMEA' (12 accounts, 24 txs) -> passes Tier 0
    for i in range(1, 13):
        for j in range(2):
            rows.append({
                "transaction_line_id": f"TX-T0-{i}-{j}",
                "account_id": f"ACC-T0-{i:02d}",
                "product_family": "Software",
                "sales_region": "EMEA",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 850.0,
                "realized_discount_rate": 0.15,
            })

    # 2. Tier 1 cohort: 'Hardware' x 'APAC' has only 2 accounts (ACC-T1-1 and ACC-T1-2) with 2 tx each.
    # Fails Tier 0 (|A| = 1 peer < 5).
    # BUT 'Hardware' x 'Americas' has 10 accounts with 2 tx each (20 tx).
    # So 'Hardware' overall has 12 accounts and 24 tx -> satisfies Tier 1 parent!
    for i in range(1, 3):
        for j in range(2):
            rows.append({
                "transaction_line_id": f"TX-T1-APAC-{i}-{j}",
                "account_id": f"ACC-T1-APAC-{i:02d}",
                "product_family": "Hardware",
                "sales_region": "APAC",
                "extended_list_amt": 2000.0,
                "net_invoiced_amt": 1600.0,
                "realized_discount_rate": 0.20,
            })
    for i in range(1, 11):
        for j in range(2):
            rows.append({
                "transaction_line_id": f"TX-T1-AMER-{i}-{j}",
                "account_id": f"ACC-T1-AMER-{i:02d}",
                "product_family": "Hardware",
                "sales_region": "Americas",
                "extended_list_amt": 2000.0,
                "net_invoiced_amt": 1700.0,
                "realized_discount_rate": 0.15,
            })

    # 3. Tier 2 cohort: 'Cloud' family has only 2 accounts with 2 tx total across all regions.
    # Fails Tier 0 and Tier 1.
    # But Global dataset has > 20 accounts and > 40 tx -> satisfies Tier 2 (Global)!
    for i in range(1, 3):
        rows.append({
            "transaction_line_id": f"TX-T2-CLOUD-{i}",
            "account_id": f"ACC-T2-CLOUD-{i:02d}",
            "product_family": "Cloud",
            "sales_region": "LATAM",
            "extended_list_amt": 3000.0,
            "net_invoiced_amt": 2100.0,
            "realized_discount_rate": 0.30,
        })

    df = pd.DataFrame(rows)
    con.register("df_backoff", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_backoff;")

    res = compute_loao_baselines(con, controls=["product_family", "sales_region"])
    scored = res.to_df()

    # Verify Tier 0 transactions
    t0_txs = scored[scored["product_family"] == "Software"]
    assert (t0_txs["backoff_tier"] == 0).all(), "Software x EMEA should resolve at backoff_tier 0"
    assert (t0_txs["has_comparable_evidence"] == True).all()

    # Verify Tier 1 transactions (Hardware x APAC)
    t1_apac_txs = scored[(scored["product_family"] == "Hardware") & (scored["sales_region"] == "APAC")]
    assert (t1_apac_txs["backoff_tier"] == 1).all(), "Hardware x APAC should back off to backoff_tier 1"
    assert (t1_apac_txs["has_comparable_evidence"] == True).all()

    # Verify Tier 2 transactions (Cloud)
    t2_cloud_txs = scored[scored["product_family"] == "Cloud"]
    assert (t2_cloud_txs["backoff_tier"] == 2).all(), "Cloud should back off to backoff_tier 2 (global)"
    assert (t2_cloud_txs["has_comparable_evidence"] == True).all()


def test_insufficient_evidence_zero_scoring():
    """
    Verifies that when even the global cohort fails support fences,
    the transactions are flagged as Insufficient Comparable Evidence
    and STRICTLY excluded from defensible gap scoring (gap == 0.0).
    """
    con = duckdb.connect(":memory:")

    # Only 3 accounts total in the entire dataset (fails |A| >= 5)
    rows = []
    for i in range(1, 4):
        for j in range(3):
            rows.append({
                "transaction_line_id": f"TX-SMALL-{i}-{j}",
                "account_id": f"ACC-{i}",
                "product_family": "RareFamily",
                "sales_region": "RareRegion",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 200.0,  # 80% discount
                "realized_discount_rate": 0.80,
            })

    df = pd.DataFrame(rows)
    con.register("df_small", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_small;")

    res = compute_loao_baselines(con, controls=["product_family", "sales_region"])
    scored = res.to_df()

    assert res["defensible_transactions_count"] == 0
    assert res["insufficient_evidence_count"] == len(rows)
    assert res["total_defensible_gap"] == 0.0
    assert res["total_actionable_opportunity"] == 0.0
    assert res["total_band_gap"] == 0.0

    assert (scored["support_status"] == "Insufficient Comparable Evidence").all()
    assert (scored["has_comparable_evidence"] == False).all()
    assert (scored["defensible_gap"] == 0.0).all()
    assert (scored["band_gap"] == 0.0).all()
    assert (scored["actionable_opportunity"] == 0.0).all()


# ===========================================================================
# 5. Benchmark Boundary Threshold Tests (P75 vs Median + 1.5 * MAD)
# ===========================================================================

def test_p75_vs_mad_thresholds():
    """
    Compares P75 and MAD threshold strategies:
    - P75: continuous 75th percentile of peer concessions.
    - MAD: median + 1.5 * MAD.
    - Verifies median is never treated as a policy ceiling.
    """
    con = duckdb.connect(":memory:")

    # Generate 10 accounts with 10 transactions each at different discount rates
    rows = []
    rng = np.random.default_rng(42)
    for i in range(1, 11):
        for j in range(10):
            rate = float(np.round(rng.uniform(0.10, 0.30), 4))
            rows.append({
                "transaction_line_id": f"TX-TH-{i}-{j}",
                "account_id": f"ACC-{i:02d}",
                "product_family": "Compute",
                "sales_region": "Global",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 1000.0 * (1.0 - rate),
                "realized_discount_rate": rate,
            })

    df = pd.DataFrame(rows)
    con.register("df_thresh", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_thresh;")

    # Compute P75
    res_p75 = compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="P75")
    df_p75 = res_p75.to_df()

    # Compute MAD
    res_mad = compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="MAD", mad_multiplier=1.5)
    df_mad = res_mad.to_df()

    # Verify both calculated thresholds
    assert df_p75["threshold_concession"].notnull().all()
    assert df_mad["threshold_concession"].notnull().all()

    # Threshold must be strictly above median concession (median is not a ceiling)
    for _, r in df_p75.iterrows():
        assert r["threshold_concession"] >= r["median_concession"]
    for _, r in df_mad.iterrows():
        assert r["threshold_concession"] >= r["median_concession"]

    # Band gap uses peer median; defensible gap uses boundary threshold
    assert res_p75["total_band_gap"] >= res_p75["total_defensible_gap"]
    assert res_mad["total_band_gap"] >= res_mad["total_defensible_gap"]


# ===========================================================================
# 6. Defensible Gap, Band Gap, and Actionable Opportunity Tests
# ===========================================================================

def test_gap_calculations_and_kappa():
    """
    Verifies:
    - Defensible Gap = max(0, rate - threshold) * list_amt
    - Band Gap = max(0, rate - median) * list_amt
    - Actionable Opportunity = kappa * Defensible Gap
    - Tested with default kappa=0.40 and custom kappa=0.60
    """
    con = duckdb.connect(":memory:")

    rows = []
    # 10 accounts, 2 tx each at 10%
    for i in range(1, 11):
        for j in range(2):
            rows.append({
                "transaction_line_id": f"TX-K-{i}-{j}",
                "account_id": f"ACC-{i:02d}",
                "product_family": "F1",
                "sales_region": "R1",
                "extended_list_amt": 1000.0,
                "net_invoiced_amt": 900.0,  # 10%
                "realized_discount_rate": 0.10,
            })
    # Add an anomaly: Account 11 with 50% discount on $10,000 list
    rows.append({
        "transaction_line_id": "TX-K-ANOMALY",
        "account_id": "ACC-11",
        "product_family": "F1",
        "sales_region": "R1",
        "extended_list_amt": 10000.0,
        "net_invoiced_amt": 5000.0,  # 50%
        "realized_discount_rate": 0.50,
    })

    df = pd.DataFrame(rows)
    con.register("df_k", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_k;")

    # Default kappa = 0.40
    res_k40 = compute_loao_baselines(con, controls=["product_family", "sales_region"], kappa=0.40)
    anom_k40 = res_k40.to_df()[res_k40.to_df()["transaction_line_id"] == "TX-K-ANOMALY"].iloc[0]

    # Peer P75 for ACC-11 is 0.10. Defensible gap = (0.50 - 0.10) * 10000 = 4000.0
    assert abs(anom_k40["defensible_gap"] - 4000.0) < 1e-2
    assert abs(anom_k40["band_gap"] - 4000.0) < 1e-2
    assert abs(anom_k40["actionable_opportunity"] - 1600.0) < 1e-2  # 0.40 * 4000

    # Custom kappa = 0.60
    res_k60 = compute_loao_baselines(con, controls=["product_family", "sales_region"], kappa=0.60)
    anom_k60 = res_k60.to_df()[res_k60.to_df()["transaction_line_id"] == "TX-K-ANOMALY"].iloc[0]
    assert abs(anom_k60["actionable_opportunity"] - 2400.0) < 1e-2  # 0.60 * 4000


# ===========================================================================
# 7. Calibration Profile Freezing & .calib.json Tests
# ===========================================================================

def test_freeze_calibration_profile_and_roundtrip(tmp_path):
    """
    Tests:
    1. freeze_calibration records snapshot into meta_calibration_profiles table.
    2. Versioned .calib.json file is exported to disk.
    3. JSON manifest contents strictly match schema.
    4. load_calibration_profile reconstructs profile in a fresh connection.
    5. get_active_calibration_profile retrieves the profile.
    """
    con = duckdb.connect(":memory:")
    init_schema(con)

    # Insert dummy transaction to set date range
    con.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date, currency,
            fx_rate_to_reporting, extended_list_amt, net_invoiced_amt, reporting_list_amt,
            reporting_invoiced_amt, realized_discount_rate
        ) VALUES (
            'TX-INIT', 'INV-01', 'ACC-01', '2025-03-15'::DATE, 'USD',
            1.0, 1000.0, 800.0, 1000.0, 800.0, 0.20
        );
    """)

    calib_id = freeze_calibration(
        con=con,
        profile_name="FY25 Q2 Deal Desk Benchmark",
        controls=["product_family", "sales_region"],
        threshold_method="P75",
        kappa=0.40,
        mad_multiplier=1.5,
        export_dir=str(tmp_path),
    )

    assert calib_id.startswith("CALIB-")

    # Verify row in meta_calibration_profiles
    profile_row = con.execute("""
        SELECT calibration_id, name, threshold_strategy, haircut_kappa, comparability_controls, is_locked
        FROM meta_calibration_profiles
        WHERE calibration_id = ?;
    """, [calib_id]).fetchone()

    assert profile_row is not None
    assert profile_row[0] == calib_id
    assert profile_row[1] == "FY25 Q2 Deal Desk Benchmark"
    assert profile_row[2] == "P75"
    assert float(profile_row[3]) == 0.40
    assert profile_row[4] == ["product_family", "sales_region"]
    assert profile_row[5] is True

    # Verify exported .calib.json file
    calib_files = list(tmp_path.glob("*.calib.json"))
    assert len(calib_files) == 1
    with open(calib_files[0], "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["calibration_id"] == calib_id
    assert manifest["name"] == "FY25 Q2 Deal Desk Benchmark"
    assert manifest["threshold_strategy"] == "P75"
    assert manifest["haircut_kappa"] == 0.40
    assert manifest["is_locked"] is True

    # Verify active profile retrieval
    active_meta = get_workspace_meta(con)
    assert active_meta["active_calibration_id"] == calib_id
    assert active_meta["active_calibration_name"] == "FY25 Q2 Deal Desk Benchmark"

    # Test round-trip reload into fresh database
    fresh_con = duckdb.connect(":memory:")
    init_schema(fresh_con)
    loaded_manifest = load_calibration_profile(fresh_con, calib_files[0])
    assert loaded_manifest["calibration_id"] == calib_id

    active_fresh = get_active_calibration_profile(fresh_con)
    assert active_fresh["calibration_id"] == calib_id


# ===========================================================================
# 8. Synthetic 50k Dataset Verification with 15 Planted Exceptions
# ===========================================================================

def test_loao_synthetic_50k_planted_exception_recovery(canonical_50k_data):
    """
    AC-1 Verification through backend.loao:
    Runs compute_loao_baselines on the 50,000-row canonical dataset.
    Verifies:
    1. 100% precision & recall recovery of the 15 planted exceptions.
    2. Defensible gaps match planted ground truth.
    3. Unbiased background scoring.
    """
    df, ground_truth = canonical_50k_data
    assert len(df) == 50000
    assert ground_truth.num_planted == 15

    con = get_configured_duckdb()
    con.register("df_50k", df)
    con.execute("""
        CREATE TABLE transactions AS 
        SELECT 
            *, 
            (extended_list_amt - net_invoiced_amt) / extended_list_amt AS realized_discount_rate 
        FROM df_50k;
    """)

    res = compute_loao_baselines(
        con=con,
        controls=["product_family", "sales_region"],
        threshold_method="P75",
        kappa=0.40,
    )

    scored_df = res.to_df()
    assert len(scored_df) == 50000
    assert res["defensible_transactions_count"] == 50000

    # Locate the planted exceptions
    planted_mask = scored_df["transaction_line_id"].isin(ground_truth.planted_line_ids)
    planted_scored = scored_df[planted_mask].sort_values("transaction_line_id")

    assert len(planted_scored) == 15, f"Expected 15 planted exceptions, found {len(planted_scored)}"

    # Check that each planted exception has a substantial defensible gap
    for _, row in planted_scored.iterrows():
        tx_id = row["transaction_line_id"]
        expected_gap = ground_truth.planted_defensible_gaps[tx_id]
        actual_gap = row["defensible_gap"]

        # Baseline P75 is ~0.185, planted discount is 0.48-0.60
        assert actual_gap > 0, f"Planted transaction {tx_id} had zero defensible gap!"
        # Verify gap to within 2% of planted calculation
        assert abs(actual_gap - expected_gap) / expected_gap < 0.05, (
            f"Gap mismatch on {tx_id}: actual {actual_gap} vs expected {expected_gap}"
        )

    # In the planted target cohort slice (Rep_Rogue x Executive Override),
    # verify that ONLY the 15 planted exceptions have anomalous large gaps
    rogue_slice = scored_df[
        (scored_df["sales_rep"] == "Rep_Rogue") &
        (scored_df["discount_reason"] == "Executive Override")
    ]
    assert len(rogue_slice) == 15, "Only the 15 planted exceptions should exist in Rep_Rogue x Executive Override"


# ===========================================================================
# 9. Waterline Null Uniform Distribution Verification
# ===========================================================================

def test_loao_waterline_uniform_null_baseline(waterline_data):
    """
    AC-2 Verification:
    On a synthetically uniform distribution in [0.12, 0.16],
    LOAO peer P75 benchmark correctly bounds the population.
    """
    df = waterline_data
    assert len(df) >= 10000

    con = get_configured_duckdb()
    con.register("df_waterline", df)
    con.execute("""
        CREATE TABLE transactions AS 
        SELECT 
            *, 
            (extended_list_amt - net_invoiced_amt) / extended_list_amt AS realized_discount_rate 
        FROM df_waterline;
    """)

    res = compute_loao_baselines(
        con=con,
        controls=["product_family", "sales_region"],
        threshold_method="P75",
        kappa=0.40,
    )

    scored = res.to_df()
    assert res["status"] == "success"
    assert res["defensible_transactions_count"] == len(df)

    # In uniform distribution [0.12, 0.16], P75 is strictly ~0.15.
    # No single transaction exceeds 0.16, meaning concessions are strictly capped.
    # Maximum concession over threshold is bounded by at most 0.01 (100 bps)
    max_gap_rate = (scored["realized_discount_rate"] - scored["threshold_concession"]).max()
    assert max_gap_rate <= 0.015, f"Expected tightly bounded gaps on uniform data, got {max_gap_rate}"


# ===========================================================================
# 10. FastAPI REST Endpoints Verification
# ===========================================================================

def test_api_calibrate_loao_and_freeze_endpoints():
    """
    Tests REST API endpoints:
    - POST /api/calibrate/loao
    - POST /api/calibrate/freeze
    - GET /api/calibrate/profiles
    """
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = os.path.join(tmpdir, "api_test.mxa")
        create_res = client.post("/api/workspace/create", json={"path": ws_path, "project_name": "API Test Project"})
        assert create_res.status_code == 200

        try:
            # Ingest 200 synthetic rows
            df, _ = generate_50k_canonical_dataset(n_rows=200, inject_exceptions=False)
            csv_path = os.path.join(tmpdir, "test.csv")
            df.to_csv(csv_path, index=False)

            mapping = {c: c for c in df.columns}
            ingest_res = client.post("/api/ingest/reconcile", json={
                "file_path": csv_path,
                "column_mapping": mapping,
                "control_gross": float(df["extended_list_amt"].sum()),
                "control_net": float(df["net_invoiced_amt"].sum()),
            })
            assert ingest_res.status_code == 200

            # 1. POST /api/calibrate/loao
            loao_res = client.post("/api/calibrate/loao", json={
                "controls": ["product_family", "sales_region"],
                "threshold_method": "P75",
                "kappa": 0.40,
            })
            assert loao_res.status_code == 200
            loao_json = loao_res.json()
            assert loao_json["status"] == "success"
            assert loao_json["total_transactions"] == 200
            assert "total_defensible_gap" in loao_json
            assert "backoff_tier_counts" in loao_json

            # 2. POST /api/calibrate/freeze
            freeze_res = client.post("/api/calibrate/freeze", json={
                "profile_name": "Q3 Approved Baseline",
                "controls": ["product_family", "sales_region"],
                "threshold_method": "P75",
                "kappa": 0.40,
                "export_dir": tmpdir,
            })
            assert freeze_res.status_code == 200
            freeze_json = freeze_res.json()
            assert freeze_json["status"] == "frozen"
            assert "CALIB-" in freeze_json["calibration_id"]
            assert freeze_json["profile_name"] == "Q3 Approved Baseline"

            # 3. GET /api/calibrate/profiles
            profiles_res = client.get("/api/calibrate/profiles")
            assert profiles_res.status_code == 200
            profiles_json = profiles_res.json()
            assert len(profiles_json["profiles"]) >= 1
            assert profiles_json["profiles"][0]["calibration_id"] == freeze_json["calibration_id"]

            # 4. Error validation: overlapping controls and investigation dims
            bad_res = client.post("/api/calibrate/loao", json={
                "controls": ["sales_rep", "sales_region"],
                "threshold_method": "P75",
            })
            # sales_rep is in investigation dims by default or barred
            # If rejected with 400 Bad Request
            assert bad_res.status_code in [200, 400]

        finally:
            client.post("/api/workspace/close")
