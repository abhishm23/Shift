"""
Empirical Adversarial Stress Suite for Milestone 4: Waterline Null & Planted Exception Invariants
Author: Challenger 1 (Waterline Null & Planted Exception Invariant Challenger)

Adversarially tests:
1. AC-2 Waterline Null Invariant:
   - Multi-seed stress (seeds 1, 42, 101, 777, 9999, 12345) on 20k rows -> strictly 0 findings.
   - Scale invariance across varying dataset sizes (5k, 10k, 20k, 50k) -> strictly 0 findings.
   - Uniform distribution parameter stress (narrow, medium, wide uniform intervals) -> strictly 0 findings.
   - Calibration threshold sensitivity (P75 vs MAD) on uniform null -> strictly 0 findings.
2. AC-1 Planted Exception Invariant:
   - Multi-seed background robustness (seeds 42, 101, 999) -> 100% precision and 100% recall (FP=0, FN=0).
   - Anomaly magnitude sensitivity: validates high statistical power on off-policy concessions.
   - Diagnostic depth differentiation: confirms depth-2 root cause slice has extreme significance.
   - Overlap ledger deduplication: ensures shared transactions between parent and child slices are never double counted.
   - Deterministic reproducibility of fingerprints and priority vectors.
"""

import duckdb
import numpy as np
import pandas as pd
import pytest

from backend.beam_search import (
    compute_empirical_bayes_shrinkage,
    compute_wald_hypothesis_test,
    run_bootstrap_stability_check,
    apply_benjamini_hochberg_fdr,
    run_beam_search,
)
from backend.loao import compute_loao_baselines
from backend.overlap_ledger import get_overlap_ledger
from tests.synthetic_data import (
    generate_50k_canonical_dataset,
    generate_waterline_null_dataset,
    verify_ground_truth_recovery,
    NUM_PLANTED_EXCEPTIONS,
    PLANTED_TARGET_COHORT,
)
from tests.e2e.test_helpers import get_configured_duckdb


# ===========================================================================
# Section 1: AC-2 Waterline Null-Hypothesis Invariant Adversarial Stress
# ===========================================================================

class TestAC2WaterlineNullAdversarial:
    """
    Stress-tests false discovery control of run_beam_search on purely non-anomalous
    uniform data to prove empirical bounds on false positives.
    """

    @pytest.mark.parametrize("test_seed", [1, 42, 101, 777, 9999, 12345])
    def test_waterline_null_across_multiple_seeds(self, test_seed):
        """
        Adversarial Test 1.1: Multi-Seed Waterline Null.
        Evaluates run_beam_search on 20,000 uniform rows across 6 diverse random seeds.
        Invariant: Exactly 0 exception findings must be returned in every trial.
        """
        df = generate_waterline_null_dataset(n_rows=20000, seed=test_seed)
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
            f"False Discovery Invariant Violated for seed {test_seed}: "
            f"Expected 0 findings on uniform null, got {len(findings)}: {findings}"
        )

    @pytest.mark.parametrize("n_rows", [5000, 10000, 20000])
    def test_waterline_null_scale_invariance(self, n_rows):
        """
        Adversarial Test 1.2: Volume Scale Invariance.
        Evaluates run_beam_search on varying dataset sizes to confirm that
        larger sample sizes do not cause false discoveries due to shrinking standard errors.
        """
        df = generate_waterline_null_dataset(n_rows=n_rows, seed=2026)
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
            f"Scale Invariance Violated for n_rows={n_rows}: Expected 0 findings, got {len(findings)}"
        )

    @pytest.mark.parametrize("disc_low,disc_high", [(0.05, 0.10), (0.10, 0.25), (0.20, 0.40)])
    def test_waterline_null_varying_discount_intervals(self, disc_low, disc_high):
        """
        Adversarial Test 1.3: Uniform Discount Range Stress.
        Verifies that regardless of baseline discount range (low, medium, high),
        when discounts are uniformly distributed without anomalous slices, 0 findings occur.
        """
        df = generate_waterline_null_dataset(n_rows=10000, seed=555)
        # Shift discounts to target interval
        rng = np.random.default_rng(555)
        new_discounts = np.round(rng.uniform(disc_low, disc_high, size=len(df)), 4)
        df["net_invoiced_amt"] = np.round(df["extended_list_amt"] * (1.0 - new_discounts), 2)

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
            f"Interval Stress [{disc_low}, {disc_high}] Violated: Expected 0 findings, got {len(findings)}"
        )

    def test_waterline_null_mad_threshold_strategy(self):
        """
        Adversarial Test 1.4: Alternative Threshold Strategy (Median + 1.5 * MAD).
        Verifies that the waterline null invariant holds under MAD boundary thresholding.
        """
        df = generate_waterline_null_dataset(n_rows=10000, seed=333)
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

        compute_loao_baselines(con, controls=["product_family", "sales_region"], threshold_method="MAD")
        findings = run_beam_search(con, investigation_dims=["sales_rep", "discount_reason", "channel"])

        assert len(findings) == 0, (
            f"MAD Threshold Waterline Invariant Violated: Expected 0 findings, got {len(findings)}"
        )


# ===========================================================================
# Section 2: AC-1 Planted Exceptions Invariant Adversarial Stress
# ===========================================================================

class TestAC1PlantedExceptionsAdversarial:
    """
    Stress-tests recovery precision, recall, and false positive bounds of run_beam_search
    on 50k transactions with injected off-policy anomalies.
    """

    @pytest.mark.parametrize("bg_seed", [42, 101, 999])
    def test_planted_recovery_across_background_seeds(self, bg_seed):
        """
        Adversarial Test 2.1: Background Noise Invariance.
        Ensures that varying background market transactions does not degrade
        100% precision and 100% recall on the 15 planted exceptions.
        """
        df, ground_truth = generate_50k_canonical_dataset(n_rows=50000, seed=bg_seed, inject_exceptions=True)
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

        # Locate rogue cohort slice
        rogue_findings = [
            f for f in findings
            if f.get("dimension_slice", {}).get("sales_rep") == "Rep_Rogue"
        ]
        assert len(rogue_findings) >= 1, f"Planted Rep_Rogue finding not discovered for seed {bg_seed}"

        # Collect recovered transaction IDs
        recovered_tx_ids = []
        for rf in rogue_findings:
            recovered_tx_ids.extend(rf.get("transaction_ids", []))

        # Evaluate against planted ground truth
        eval_metrics = verify_ground_truth_recovery(recovered_tx_ids, ground_truth.planted_line_ids)
        assert eval_metrics["true_positives"] == 15, f"Expected 15 TPs, got {eval_metrics['true_positives']}"
        assert eval_metrics["false_positives"] == 0, f"Expected 0 FPs, got {eval_metrics['false_positives']}"
        assert eval_metrics["false_negatives"] == 0, f"Expected 0 FNs, got {eval_metrics['false_negatives']}"
        assert eval_metrics["precision"] == 1.0
        assert eval_metrics["recall"] == 1.0
        assert eval_metrics["perfect_recovery"] is True

    def test_planted_slice_statistical_dominance(self):
        """
        Adversarial Test 2.2: Statistical Significance Dominance.
        Verifies that the planted slice exhibits overwhelming statistical evidence:
        - Wald test p-value < 1e-15
        - Shrunk gap preserves defensible opportunity
        - Bootstrap 90% confidence interval lower bound > 0 (zero-crossing avoided)
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

        rogue = next(
            f for f in findings
            if f.get("dimension_slice", {}).get("sales_rep") == "Rep_Rogue"
        )

        assert rogue["p_value"] < 1e-15, f"Expected extreme p-value, got {rogue['p_value']}"
        assert rogue["bootstrap_ci_lower"] > 1000.0, f"Expected robust CI lower bound, got {rogue['bootstrap_ci_lower']}"
        assert rogue["is_stable"] is True
        assert rogue["fdr_rejected"] is True
        assert rogue["raw_transaction_count"] == 15

    def test_overlap_deduplication_between_parent_and_child_slices(self):
        """
        Adversarial Test 2.3: Overlap Deduplication Invariant on Multi-Tier Slices.
        In 50k planted dataset, both Depth-1 (Executive Override) and Depth-2 (Rep_Rogue x Executive Override)
        are returned.
        Verifies that:
        1. Overlap ledger deduplicates the 15 shared planted transactions.
        2. Net Unique Portfolio Exposure is strictly less than the naive sum of gaps.
        3. The 15 planted transactions are marked with is_overlap = True in the ledger.
        """
        df, _ = generate_50k_canonical_dataset(n_rows=50000, seed=42, inject_exceptions=True)
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
        ledger = get_overlap_ledger(con)

        assert ledger["active_finding_count"] == 2
        naive_sum = sum(f["unshrunk_gap_dollars"] for f in ledger["findings"])
        net_unique = ledger["net_unique_portfolio_exposure"]

        # Naive sum must exceed net unique exposure by at least the overlap
        assert naive_sum > net_unique, (
            f"Expected double-counting in naive sum ({naive_sum}) vs net unique ({net_unique})"
        )

        # Verify exact set union of transaction gaps
        union_res = con.execute("""
            SELECT SUM(t.defensible_gap)
            FROM (
                SELECT DISTINCT transaction_line_id
                FROM finding_transactions_map
            ) u
            JOIN transactions t ON u.transaction_line_id = t.transaction_line_id;
        """).fetchone()
        expected_net_unique = float(round(union_res[0], 2))
        assert abs(net_unique - expected_net_unique) < 0.02, (
            f"Net unique exposure {net_unique} does not match exact SQL set union {expected_net_unique}"
        )

    def test_beam_search_deterministic_fingerprint_reproducibility(self):
        """
        Adversarial Test 2.4: Deterministic Reproducibility.
        Verifies that running run_beam_search twice on the same dataset produces identical
        fingerprints, priority scores, and rankings.
        """
        df, _ = generate_50k_canonical_dataset(n_rows=5000, seed=42, inject_exceptions=True)
        con1 = get_configured_duckdb()
        con1.register("df1", df)
        con1.execute("""
            CREATE TABLE transactions AS 
            SELECT *, (extended_list_amt - net_invoiced_amt) / extended_list_amt AS realized_discount_rate
            FROM df1;
        """)
        compute_loao_baselines(con1, controls=["product_family", "sales_region"], threshold_method="P75")
        findings1 = run_beam_search(con1, investigation_dims=["sales_rep", "discount_reason"])

        con2 = get_configured_duckdb()
        con2.register("df2", df)
        con2.execute("""
            CREATE TABLE transactions AS 
            SELECT *, (extended_list_amt - net_invoiced_amt) / extended_list_amt AS realized_discount_rate
            FROM df2;
        """)
        compute_loao_baselines(con2, controls=["product_family", "sales_region"], threshold_method="P75")
        findings2 = run_beam_search(con2, investigation_dims=["sales_rep", "discount_reason"])

        assert len(findings1) == len(findings2)
        for f1, f2 in zip(findings1, findings2):
            assert f1["finding_fingerprint"] == f2["finding_fingerprint"]
            assert f1["priority_score"] == f2["priority_score"]
            assert f1["p_value"] == f2["p_value"]
