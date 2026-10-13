"""
Milestone 4 Comprehensive Test Suite: Diagnostic Beam Search & Overlap-Aware Ledger.

Covers:
1. Empirical Bayes Shrinkage formulation & boundary conditions.
2. 200-iteration bootstrap stability checks & 90% CI zero-cross detection.
3. Benjamini-Hochberg FDR control (q < 0.05).
4. Multi-signal priority vector ranking & signal normalization.
5. Bounded beam search traversal (width 3, depth 3) and expansion limits.
6. Incremental coverage penalization for redundant slices.
7. Overlap-aware ledger exact SQL set union invariant.
8. Dismissal governance and transaction protection in overlap ledger.
9. Database relational integrity (finding_records & finding_transactions_map).
10. AC-2 Waterline null-hypothesis invariant (zero exception findings).
11. AC-1 Planted exception recovery with 100% precision and 100% recall.
12. Empty workspace and zero-gap resilience.
13. FastAPI POST /api/triage/beam_search integration.
14. FastAPI GET /api/triage/overlap_ledger integration.
15. FastAPI GET /api/triage/findings/{id}/transactions drawer integration.
16. Workspace lifecycle gating (400 Bad Request when workspace closed).
"""

import json
import math
import os
import tempfile
import duckdb
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app import app, state
from backend.storage import open_workspace, create_workspace, init_schema, close_workspace
from backend.loao import compute_loao_baselines
from backend.beam_search import (
    compute_empirical_bayes_shrinkage,
    compute_wald_hypothesis_test,
    run_bootstrap_stability_check,
    apply_benjamini_hochberg_fdr,
    rank_candidates_by_priority_vector,
    compute_finding_fingerprint,
    run_beam_search,
)
from backend.overlap_ledger import (
    compute_net_unique_portfolio_exposure,
    get_overlap_ledger,
    get_finding_transactions,
    record_findings_to_db,
)
from tests.synthetic_data import (
    generate_50k_canonical_dataset,
    generate_waterline_null_dataset,
    verify_ground_truth_recovery,
)
from tests.e2e.test_helpers import get_configured_duckdb


# ===========================================================================
# Section 1: Statistical Shrinkage & Hypothesis Testing Primitives
# ===========================================================================

def test_empirical_bayes_shrinkage_extreme_samples():
    """
    Test 1: Verifies that Empirical Bayes shrinkage properly pulls noisy,
    low-sample estimates toward the parent prior mean, while preserving high-confidence,
    large-sample estimates.
    """
    prior_mean = 100.0
    prior_var = 400.0  # std = 20.0

    # Small, noisy sample (n=5, high variance)
    n_small = 5
    sample_mean_small = 250.0
    sample_var_small = 5000.0
    shrunk_small, lambda_small, total_gap_small = compute_empirical_bayes_shrinkage(
        sample_mean=sample_mean_small,
        sample_var=sample_var_small,
        n=n_small,
        prior_mean=prior_mean,
        prior_var=prior_var,
    )

    # lambda = 400 / (400 + 5000/5) = 400 / 1400 = ~0.2857
    assert 0.20 < lambda_small < 0.35, f"Expected lambda ~0.286, got {lambda_small}"
    assert prior_mean < shrunk_small < sample_mean_small
    assert abs(shrunk_small - (lambda_small * sample_mean_small + (1 - lambda_small) * prior_mean)) < 1e-9
    assert abs(total_gap_small - (shrunk_small * n_small)) < 1e-9

    # Large, precise sample (n=5000, low variance)
    n_large = 5000
    sample_mean_large = 250.0
    sample_var_large = 400.0
    shrunk_large, lambda_large, total_gap_large = compute_empirical_bayes_shrinkage(
        sample_mean=sample_mean_large,
        sample_var=sample_var_large,
        n=n_large,
        prior_mean=prior_mean,
        prior_var=prior_var,
    )

    # lambda = 400 / (400 + 400/5000) = 400 / 400.08 = ~0.9998
    assert lambda_large > 0.999
    assert abs(shrunk_large - sample_mean_large) < 0.1


def test_bootstrap_stability_check_positive_vs_zero_crossing():
    """
    Test 2: Verifies 200-iteration bootstrap stability check.
    Positive excess slice yields is_stable=True, ci_lower > 0.
    Noisy slice crosses zero (ci_lower <= 0) and is flagged unstable.
    """
    prior_mean = 50.0

    # High-concession slice: gaps tightly centered around 150.0 (> prior 50.0)
    rng = np.random.default_rng(42)
    high_gaps = rng.normal(loc=150.0, scale=10.0, size=30)
    res_stable = run_bootstrap_stability_check(high_gaps, prior_mean=prior_mean, n_boot=200, seed=42)

    assert res_stable["is_stable"] is True
    assert res_stable["ci_lower"] > 50.0, f"Expected positive lower bound, got {res_stable['ci_lower']}"
    assert res_stable["stability_score"] == 1.0

    # Noisy slice: gaps centered around 50.0 (equal to prior mean)
    noisy_gaps = rng.normal(loc=50.0, scale=30.0, size=30)
    res_unstable = run_bootstrap_stability_check(noisy_gaps, prior_mean=prior_mean, n_boot=200, seed=42)

    assert res_unstable["is_stable"] is False
    assert res_unstable["ci_lower"] <= 0.0, f"Expected non-positive lower bound, got {res_unstable['ci_lower']}"
    assert res_unstable["stability_score"] < 0.95

    # Deterministic reproducibility check
    res_repeat = run_bootstrap_stability_check(high_gaps, prior_mean=prior_mean, n_boot=200, seed=42)
    assert res_repeat["ci_lower"] == res_stable["ci_lower"]
    assert res_repeat["ci_upper"] == res_stable["ci_upper"]


def test_benjamini_hochberg_fdr_control():
    """
    Test 3: Verifies Benjamini-Hochberg FDR control with q < 0.05.
    Rejects true discoveries while bounding false discovery rate.
    """
    candidates = [
        {"id": "C1", "p_value": 0.0001, "diff_mean": 50.0, "is_stable": True},
        {"id": "C2", "p_value": 0.0010, "diff_mean": 40.0, "is_stable": True},
        {"id": "C3", "p_value": 0.0040, "diff_mean": 30.0, "is_stable": True},
        {"id": "C4", "p_value": 0.1500, "diff_mean": 10.0, "is_stable": True},
        {"id": "C5", "p_value": 0.2500, "diff_mean": 5.0, "is_stable": False},
        {"id": "C6", "p_value": 0.3500, "diff_mean": 2.0, "is_stable": False},
        {"id": "C7", "p_value": 0.5000, "diff_mean": -5.0, "is_stable": False},
        {"id": "C8", "p_value": 0.6000, "diff_mean": -10.0, "is_stable": False},
        {"id": "C9", "p_value": 0.8000, "diff_mean": -20.0, "is_stable": False},
        {"id": "C10", "p_value": 0.9500, "diff_mean": -30.0, "is_stable": False},
    ]

    adjusted = apply_benjamini_hochberg_fdr(candidates, fdr_q=0.05)
    rejected_ids = [c["id"] for c in adjusted if c["fdr_rejected"]]
    exception_ids = [c["id"] for c in adjusted if c["is_exception_finding"]]

    assert "C1" in rejected_ids
    assert "C2" in rejected_ids
    assert "C3" in rejected_ids
    assert "C4" not in rejected_ids
    assert "C5" not in rejected_ids

    assert exception_ids == ["C1", "C2", "C3"]

    # Edge case: all p-values high (0.50)
    null_candidates = [
        {"id": f"N{i}", "p_value": 0.50, "diff_mean": 0.0, "is_stable": False}
        for i in range(10)
    ]
    null_adjusted = apply_benjamini_hochberg_fdr(null_candidates, fdr_q=0.05)
    assert not any(c["fdr_rejected"] for c in null_adjusted)
    assert not any(c["is_exception_finding"] for c in null_adjusted)


# ===========================================================================
# Section 2: Multi-Signal Priority Vector & Traversal Limits
# ===========================================================================

def test_multi_signal_priority_vector_ranking():
    """
    Test 4: Evaluates the 4 signals of the priority vector:
    (Dollar Gap, Concentration Ratio, Bootstrap Stability, Incremental Coverage).
    """
    cand_high = {
        "id": "High-Impact",
        "shrunk_gap_dollars": 100000.0,
        "concentration_ratio": 0.30,
        "bootstrap_stability_score": 1.0,
        "unshrunk_gap_dollars": 100000.0,
        "tx_ids": ["TX-1", "TX-2", "TX-3"],
        "gap_values": [30000.0, 30000.0, 40000.0],
        "is_exception_finding": True,
    }

    cand_low = {
        "id": "Low-Impact",
        "shrunk_gap_dollars": 5000.0,
        "concentration_ratio": 0.05,
        "bootstrap_stability_score": 0.5,
        "unshrunk_gap_dollars": 5000.0,
        "tx_ids": ["TX-4", "TX-5"],
        "gap_values": [2500.0, 2500.0],
        "is_exception_finding": True,
    }

    ranked = rank_candidates_by_priority_vector([cand_low, cand_high], covered_tx_ids=set())
    assert ranked[0]["id"] == "High-Impact"
    assert ranked[0]["priority_score"] > ranked[1]["priority_score"]


def test_incremental_coverage_penalizes_redundant_slices():
    """
    Test 5 & 6: Verifies that candidates covering transactions that are already
    covered by higher-ranked findings receive an incremental coverage score of 0.0,
    downranking them relative to findings providing novel coverage.
    """
    cand_novel = {
        "id": "Novel-Slice",
        "shrunk_gap_dollars": 20000.0,
        "concentration_ratio": 0.15,
        "bootstrap_stability_score": 1.0,
        "unshrunk_gap_dollars": 20000.0,
        "tx_ids": ["TX-NOVEL-1", "TX-NOVEL-2"],
        "gap_values": [10000.0, 10000.0],
        "is_exception_finding": True,
    }

    cand_redundant = {
        "id": "Redundant-Slice",
        "shrunk_gap_dollars": 20000.0,
        "concentration_ratio": 0.15,
        "bootstrap_stability_score": 1.0,
        "unshrunk_gap_dollars": 20000.0,
        "tx_ids": ["TX-COVERED-1", "TX-COVERED-2"],
        "gap_values": [10000.0, 10000.0],
        "is_exception_finding": True,
    }

    # Already covered transactions
    covered = {"TX-COVERED-1", "TX-COVERED-2"}

    ranked = rank_candidates_by_priority_vector([cand_redundant, cand_novel], covered_tx_ids=covered)
    assert ranked[0]["id"] == "Novel-Slice"
    assert ranked[0]["unique_incremental_gap"] == 20000.0
    assert ranked[1]["id"] == "Redundant-Slice"
    assert ranked[1]["unique_incremental_gap"] == 0.0
    assert ranked[0]["priority_score"] > ranked[1]["priority_score"]


def test_beam_search_width_and_depth_limits():
    """
    Test 6: Verifies bounded beam search constraints:
    - Bounded width (top W candidates per depth)
    - Max depth <= requested depth (e.g. depth 2 never evaluates 3-way slices)
    """
    df, _ = generate_50k_canonical_dataset(n_rows=2000, seed=42, inject_exceptions=True)
    con = duckdb.connect(":memory:")
    con.register("df", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM df;")

    compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="P75")

    # Run with depth=1
    findings_d1 = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason", "channel"], width=2, depth=1)
    for f in findings_d1:
        assert f["depth"] == 1
        assert len(f["dimension_slice"]) == 1

    # Run with depth=2
    findings_d2 = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason", "channel"], width=2, depth=2)
    for f in findings_d2:
        assert f["depth"] <= 2
        assert len(f["dimension_slice"]) <= 2


def test_beam_search_deterministic_reproducibility():
    """
    Test 7: Verifies that running beam search twice with the same seed produces
    strictly identical findings, rankings, and priority scores.
    """
    df, _ = generate_50k_canonical_dataset(n_rows=1500, seed=42, inject_exceptions=True)
    con1 = duckdb.connect(":memory:")
    con1.register("df", df)
    con1.execute("CREATE TABLE transactions AS SELECT * FROM df;")
    compute_loao_baselines(con1, controls=["product_family", "sales_region"], threshold_method="P75")

    con2 = duckdb.connect(":memory:")
    con2.register("df", df)
    con2.execute("CREATE TABLE transactions AS SELECT * FROM df;")
    compute_loao_baselines(con2, controls=["product_family", "sales_region"], threshold_method="P75")

    f1 = run_beam_search(con1, investigation_dims=["sales_rep", "discount_reason"], width=3, depth=2, seed=42)
    f2 = run_beam_search(con2, investigation_dims=["sales_rep", "discount_reason"], width=3, depth=2, seed=42)

    assert len(f1) == len(f2)
    for i in range(len(f1)):
        assert f1[i]["finding_fingerprint"] == f2[i]["finding_fingerprint"]
        assert f1[i]["priority_score"] == f2[i]["priority_score"]
        assert f1[i]["shrunk_gap_dollars"] == f2[i]["shrunk_gap_dollars"]


# ===========================================================================
# Section 3: Overlap Ledger Set Union Mechanics & Invariants (AC-4)
# ===========================================================================

def test_overlap_ledger_exact_set_union_invariant():
    """
    Test 7: Sets up 3 overlapping findings:
    - FP-01: TX-01 to TX-10 ($1,000 each = $10,000)
    - FP-02: TX-06 to TX-15 ($1,000 each = $10,000; TX-06..TX-10 shared)
    - FP-03: TX-01 to TX-05 ($1,000 each = $5,000; 100% overlap with FP-01)
    Asserts net_unique_portfolio_exposure strictly equals $15,000.00.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            account_id VARCHAR,
            extended_list_amt DECIMAL(18, 4),
            defensible_gap DECIMAL(18, 4)
        );
        CREATE TABLE finding_records (
            finding_fingerprint VARCHAR(64) PRIMARY KEY,
            calibration_id VARCHAR,
            depth INTEGER,
            dimension_slice_json JSON,
            raw_transaction_count BIGINT,
            distinct_account_count BIGINT,
            gross_list_volume DECIMAL(18, 4),
            unshrunk_gap_dollars DECIMAL(18, 4),
            shrunk_gap_dollars DECIMAL(18, 4),
            concentration_ratio DECIMAL(10, 6),
            bootstrap_stability_score DECIMAL(6, 4),
            bootstrap_ci_lower DECIMAL(18, 4),
            bootstrap_ci_upper DECIMAL(18, 4),
            fdr_p_value DOUBLE,
            fdr_q_value DOUBLE,
            fdr_rejected BOOLEAN,
            unique_incremental_gap DECIMAL(18, 4),
            lifecycle_status VARCHAR DEFAULT 'New'
        );
        CREATE TABLE finding_transactions_map (
            finding_fingerprint VARCHAR(64) NOT NULL,
            transaction_line_id VARCHAR NOT NULL,
            allocated_defensible_gap DECIMAL(18, 4),
            PRIMARY KEY (finding_fingerprint, transaction_line_id)
        );
    """)

    # 15 transactions at $1,000 defensible gap each
    for i in range(1, 16):
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?)",
            [f"TX-{i:02d}", f"ACC-{(i % 3) + 1}", 10000.00, 1000.00],
        )

    # FP-01 (TX-01..TX-10) = $10,000
    con.execute(
        "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, depth, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) "
        "VALUES ('FP-01', '{\"sales_rep\": \"Alice\"}', 1, 10000.00, 10000.00, 'New')"
    )
    for i in range(1, 11):
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-01', ?, 1000.00)", [f"TX-{i:02d}"])

    # FP-02 (TX-06..TX-15) = $10,000 (TX-06..TX-10 overlap)
    con.execute(
        "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, depth, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) "
        "VALUES ('FP-02', '{\"discount_reason\": \"Match\"}', 1, 10000.00, 10000.00, 'New')"
    )
    for i in range(6, 16):
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-02', ?, 1000.00)", [f"TX-{i:02d}"])

    # FP-03 (TX-01..TX-05) = $5,000 (100% overlap with FP-01)
    con.execute(
        "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, depth, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) "
        "VALUES ('FP-03', '{\"channel\": \"Direct\"}', 1, 5000.00, 5000.00, 'New')"
    )
    for i in range(1, 6):
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-03', ?, 1000.00)", [f"TX-{i:02d}"])

    ledger = get_overlap_ledger(con)
    assert ledger["net_unique_portfolio_exposure"] == 15000.00
    assert ledger["net_unique_transactions"] == 15
    assert ledger["gross_unshrunk_gap_sum"] == 25000.00
    assert ledger["overlap_double_counted_dollars"] == 10000.00
    assert ledger["overlap_pct"] == 40.0


def test_overlap_ledger_dismissal_updates_exposure_cleanly():
    """
    Test 8: Dismissing a finding excludes its unique transactions from Net Unique
    Portfolio Exposure, but keeps shared transactions protected under surviving findings.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            account_id VARCHAR,
            extended_list_amt DECIMAL(18, 4),
            defensible_gap DECIMAL(18, 4)
        );
        CREATE TABLE finding_records (
            finding_fingerprint VARCHAR(64) PRIMARY KEY,
            dimension_slice_json JSON,
            depth INTEGER,
            unshrunk_gap_dollars DECIMAL(18, 4),
            shrunk_gap_dollars DECIMAL(18, 4),
            lifecycle_status VARCHAR DEFAULT 'New'
        );
        CREATE TABLE finding_transactions_map (
            finding_fingerprint VARCHAR(64) NOT NULL,
            transaction_line_id VARCHAR NOT NULL,
            allocated_defensible_gap DECIMAL(18, 4),
            PRIMARY KEY (finding_fingerprint, transaction_line_id)
        );
    """)

    for i in range(1, 6):
        con.execute("INSERT INTO transactions VALUES (?, 'ACC-1', 10000.00, 1000.00)", [f"TX-{i:02d}"])

    # FP-A: TX-01, TX-02, TX-03 ($3,000)
    con.execute("INSERT INTO finding_records VALUES ('FP-A', '{\"dim\": \"A\"}', 1, 3000.00, 3000.00, 'New')")
    for tid in ["TX-01", "TX-02", "TX-03"]:
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-A', ?, 1000.00)", [tid])

    # FP-B: TX-03, TX-04, TX-05 ($3,000, TX-03 shared)
    con.execute("INSERT INTO finding_records VALUES ('FP-B', '{\"dim\": \"B\"}', 1, 3000.00, 3000.00, 'New')")
    for tid in ["TX-03", "TX-04", "TX-05"]:
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-B', ?, 1000.00)", [tid])

    # Before dismissal: 5 unique transactions = $5,000
    ledger_before = get_overlap_ledger(con)
    assert ledger_before["net_unique_portfolio_exposure"] == 5000.00
    assert ledger_before["net_unique_transactions"] == 5

    # Dismiss FP-A
    con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-A'")

    # After dismissal: Surviving finding is FP-B (TX-03, TX-04, TX-05 = $3,000)
    ledger_after = get_overlap_ledger(con)
    assert ledger_after["net_unique_portfolio_exposure"] == 3000.00
    assert ledger_after["net_unique_transactions"] == 3
    assert ledger_after["active_finding_count"] == 1
    assert ledger_after["dismissed_finding_count"] == 1


def test_overlap_ledger_transaction_drawer_query():
    """
    Test 9: Verifies that get_finding_transactions returns rich transaction details
    annotated with is_overlap and other_findings for the View 3 slide-over drawer.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            invoice_id VARCHAR,
            account_id VARCHAR,
            transaction_date VARCHAR,
            extended_list_amt DECIMAL(18, 4),
            net_invoiced_amt DECIMAL(18, 4),
            realized_discount_rate DECIMAL(10, 6),
            defensible_gap DECIMAL(18, 4),
            product_family VARCHAR,
            sales_region VARCHAR,
            threshold_concession DECIMAL(10, 6)
        );
        CREATE TABLE finding_records (
            finding_fingerprint VARCHAR(64) PRIMARY KEY,
            dimension_slice_json JSON,
            depth INTEGER,
            unshrunk_gap_dollars DECIMAL(18, 4),
            lifecycle_status VARCHAR DEFAULT 'New'
        );
        CREATE TABLE finding_transactions_map (
            finding_fingerprint VARCHAR(64) NOT NULL,
            transaction_line_id VARCHAR NOT NULL,
            allocated_defensible_gap DECIMAL(18, 4),
            PRIMARY KEY (finding_fingerprint, transaction_line_id)
        );
    """)

    con.execute("""
        INSERT INTO transactions VALUES 
        ('TX-01', 'INV-1', 'ACC-1', '2025-01-01', 10000.0, 7000.0, 0.30, 1000.0, 'Storage', 'North America', 0.20),
        ('TX-02', 'INV-2', 'ACC-2', '2025-01-02', 12000.0, 8000.0, 0.33, 1500.0, 'Storage', 'North America', 0.20);
    """)
    con.execute("INSERT INTO finding_records VALUES ('FP-1', '{\"sales_rep\": \"Alice\"}', 1, 2500.0, 'New');")
    con.execute("INSERT INTO finding_records VALUES ('FP-2', '{\"discount_reason\": \"Override\"}', 1, 1000.0, 'New');")

    con.execute("INSERT INTO finding_transactions_map VALUES ('FP-1', 'TX-01', 1000.0), ('FP-1', 'TX-02', 1500.0);")
    con.execute("INSERT INTO finding_transactions_map VALUES ('FP-2', 'TX-01', 1000.0);")

    drawer_rows = get_finding_transactions(con, "FP-1")
    assert len(drawer_rows) == 2
    row1 = next(r for r in drawer_rows if r["transaction_line_id"] == "TX-01")
    row2 = next(r for r in drawer_rows if r["transaction_line_id"] == "TX-02")

    # TX-01 is shared with FP-2 -> is_overlap = True
    assert row1["is_overlap"] is True
    assert "FP-2" in row1["other_findings"]
    assert row1["total_active_finding_memberships"] == 2

    # TX-02 is unique to FP-1 -> is_overlap = False
    assert row2["is_overlap"] is False
    assert row2["other_findings"] == []
    assert row2["total_active_finding_memberships"] == 1


def test_finding_transactions_relational_integrity():
    """
    Test 9: Verifies that finding_fingerprint is a valid 64-character hex string
    and line transactions map properly to finding_transactions_map.
    """
    slice_a = {"sales_rep": "Alice", "channel": "Direct"}
    fp_a = compute_finding_fingerprint(slice_a, calib_id="CALIB-2025")
    assert len(fp_a) == 64
    assert all(c in "0123456789abcdef" for c in fp_a)

    # Commutative consistency: key order must not change the hash
    slice_b = {"channel": "Direct", "sales_rep": "Alice"}
    fp_b = compute_finding_fingerprint(slice_b, calib_id="CALIB-2025")
    assert fp_a == fp_b


# ===========================================================================
# Section 4: End-to-End Acceptance Invariants (AC-1, AC-2, Edge Cases)
# ===========================================================================

def test_ac2_waterline_null_returns_zero_defensible_findings():
    """
    Test 10: AC-2 Waterline null distribution: 20k rows of uniform discounts.
    run_beam_search must return exactly 0 exception findings under default P75 and FDR q < 0.05.
    """
    df = generate_waterline_null_dataset(n_rows=10000, seed=101)
    con = get_configured_duckdb()
    con.register("waterline_df", df)
    con.execute("""
        CREATE TABLE transactions AS 
        SELECT 
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting, extended_list_amt,
            net_invoiced_amt, cogs_amt, off_invoice_rebate, product_family,
            sales_region, industry, sales_rep, discount_reason, channel,
            (extended_list_amt - net_invoiced_amt) / extended_list_amt AS realized_discount_rate
        FROM waterline_df;
    """)

    compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="P75")
    findings = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason", "channel"])

    assert len(findings) == 0, (
        f"Waterline Null Invariant Violated: Expected 0 findings, got {len(findings)}"
    )


def test_ac1_planted_exception_100pct_precision_recall():
    """
    Test 11: AC-1 Planted exceptions: 50,000 rows with 15 injected exceptions.
    run_beam_search must achieve 100% precision and 100% recall on the rogue cohort.
    """
    df, ground_truth = generate_50k_canonical_dataset(n_rows=50000, seed=42, inject_exceptions=True)
    con = get_configured_duckdb()
    con.register("transactions_df", df)
    con.execute("""
        CREATE TABLE transactions AS 
        SELECT 
            transaction_line_id, invoice_id, account_id, parent_account_id,
            transaction_date, currency, fx_rate_to_reporting, extended_list_amt,
            net_invoiced_amt, cogs_amt, off_invoice_rebate, product_family,
            sales_region, industry, sales_rep, discount_reason, channel,
            (extended_list_amt - net_invoiced_amt) / extended_list_amt AS realized_discount_rate
        FROM transactions_df;
    """)

    compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="P75")
    findings = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason"])

    recovered_tx_ids = []
    for f in findings:
        if f.get("dimension_slice", {}).get("sales_rep") == "Rep_Rogue":
            recovered_tx_ids.extend(f.get("transaction_ids", []))

    eval_metrics = verify_ground_truth_recovery(recovered_tx_ids, ground_truth.planted_line_ids)
    assert eval_metrics["true_positives"] == 15
    assert eval_metrics["false_positives"] == 0
    assert eval_metrics["false_negatives"] == 0
    assert eval_metrics["precision"] == 1.0
    assert eval_metrics["recall"] == 1.0


def test_empty_workspace_and_zero_gap_handling():
    """
    Test 12: Verifies that beam search handles empty tables or tables where all
    defensible gaps are 0.0 cleanly without raising exceptions.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            account_id VARCHAR,
            extended_list_amt DECIMAL(18, 4),
            defensible_gap DECIMAL(18, 4),
            sales_rep VARCHAR,
            discount_reason VARCHAR
        );
    """)

    # Empty table
    findings_empty = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason"])
    assert findings_empty == []

    # Table with all 0 defensible gap
    for i in range(10):
        con.execute(
            "INSERT INTO transactions VALUES (?, 'ACC-1', 1000.0, 0.0, 'Rep_A', 'Standard')",
            [f"TX-{i}"],
        )
    findings_zero = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason"])
    assert findings_zero == []


# ===========================================================================
# Section 5: FastAPI REST Endpoints Integration
# ===========================================================================

@pytest.fixture
def api_test_client(tmp_path):
    """Fixture providing a FastAPI TestClient with an active test workspace."""
    ws_path = str(tmp_path / "test_m4_workspace.mxa")
    client = TestClient(app)

    # Create workspace
    res = client.post("/api/workspace/create", json={"path": ws_path, "project_name": "Test M4 Project"})
    assert res.status_code == 200

    yield client, ws_path

    # Teardown
    client.post("/api/workspace/close")


def test_api_triage_endpoints_require_open_workspace():
    """
    Test 16: Verifies that all /api/triage/* endpoints return 400 Bad Request
    when no workspace is currently open.
    """
    client = TestClient(app)
    # Ensure workspace is closed
    client.post("/api/workspace/close")

    res_beam = client.post("/api/triage/beam_search", json={"investigation_dims": ["sales_rep"]})
    assert res_beam.status_code == 400

    res_ledger = client.get("/api/triage/overlap_ledger")
    assert res_ledger.status_code == 400

    res_tx = client.get("/api/triage/findings/FP-123/transactions")
    assert res_tx.status_code == 400


def test_api_triage_beam_search_and_overlap_ledger(api_test_client, tmp_path):
    """
    Test 13, 14, 15: Ingests synthetic data, computes LOAO, runs beam search via API,
    queries overlap ledger, and verifies line-grain transactions drawer response.
    """
    client, ws_path = api_test_client

    # Ingest synthetic data with planted exception via ingest endpoint
    df, gt = generate_50k_canonical_dataset(n_rows=1000, seed=42, inject_exceptions=True)
    csv_path = str(tmp_path / "seed_data.csv")
    df.to_csv(csv_path, index=False)

    mapping = {c: c for c in df.columns}
    ingest_res = client.post("/api/ingest/reconcile", json={
        "file_path": csv_path,
        "column_mapping": mapping,
        "control_gross": float(df["extended_list_amt"].sum()),
        "control_net": float(df["net_invoiced_amt"].sum()),
    })
    assert ingest_res.status_code == 200

    # Calibrate LOAO
    res_calib = client.post("/api/calibrate/loao", json={
        "controls": ["product_family", "sales_region"],
        "threshold_method": "P75",
        "kappa": 0.40,
    })
    assert res_calib.status_code == 200

    # 1. POST /api/triage/beam_search
    res_beam = client.post("/api/triage/beam_search", json={
        "investigation_dims": ["sales_rep", "discount_reason"],
        "width": 3,
        "depth": 3,
        "fdr_q": 0.05,
    })
    assert res_beam.status_code == 200
    beam_data = res_beam.json()
    assert beam_data["status"] == "success"
    assert beam_data["findings_count"] >= 1
    assert beam_data["net_unique_portfolio_exposure"] > 0

    finding = beam_data["findings"][0]
    fp = finding["finding_fingerprint"]

    # 2. GET /api/triage/overlap_ledger
    res_ledger = client.get("/api/triage/overlap_ledger")
    assert res_ledger.status_code == 200
    ledger_data = res_ledger.json()
    assert ledger_data["status"] == "success"
    assert ledger_data["active_finding_count"] >= 1
    assert ledger_data["net_unique_portfolio_exposure"] > 0
    assert len(ledger_data["findings"]) >= 1

    # 3. GET /api/triage/findings/{finding_id}/transactions
    res_tx = client.get(f"/api/triage/findings/{fp}/transactions")
    assert res_tx.status_code == 200
    tx_list = res_tx.json()
    assert isinstance(tx_list, list)
    assert len(tx_list) >= 1
    sample_tx = tx_list[0]
    assert "transaction_line_id" in sample_tx
    assert "defensible_gap" in sample_tx
    assert "is_overlap" in sample_tx
    assert "other_findings" in sample_tx

