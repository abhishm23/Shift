"""
AC-3: Reconciliation Invariant Test.

Authoritative Requirement:
Aggregate portfolio net variance strictly matches the sum of Gross Unfavorable
Gap and Favorable Variance to the exact cent across all test datasets.
(ORIGINAL_REQUEST.md § Acceptance Criteria, PROJECT.md R2/R3, spec_report.md AC-3).
"""

import numpy as np
import pandas as pd
import pytest

from tests.synthetic_data import (
    generate_50k_canonical_dataset,
    generate_waterline_null_dataset,
)


def compute_portfolio_reconciliation(
    df: pd.DataFrame,
    benchmark_threshold_col: str = "benchmark_tau",
) -> dict:
    """
    Computes portfolio reconciliation metrics:
    - Line variance: Delta_i = (realized_discount_i - tau_i) * extended_list_amt_i
    - Gross Unfavorable Gap = sum(max(0, Delta_i))
    - Favorable Variance = sum(min(0, Delta_i))
    - Net Portfolio Variance = sum(Delta_i)
    Verifies that Net Portfolio Variance == Gross Unfavorable Gap + Favorable Variance.
    """
    list_amt = df["extended_list_amt"].values
    net_amt = df["net_invoiced_amt"].values
    tau = df[benchmark_threshold_col].values

    # Realized discount rate
    realized_rate = (list_amt - net_amt) / list_amt

    # Line-level commercial variance relative to benchmark
    delta = (realized_rate - tau) * list_amt

    # Decompose into unfavorable (rate > tau) and favorable (rate <= tau)
    unfavorable_gap = np.where(delta > 0.0, delta, 0.0)
    favorable_variance = np.where(delta < 0.0, delta, 0.0)

    sum_net_variance = round(float(np.sum(delta)), 2)
    sum_gross_unfavorable = round(float(np.sum(unfavorable_gap)), 2)
    sum_favorable = round(float(np.sum(favorable_variance)), 2)
    sum_decomposed = round(sum_gross_unfavorable + sum_favorable, 2)

    penny_discrepancy = round(abs(sum_net_variance - sum_decomposed), 4)

    return {
        "net_variance": sum_net_variance,
        "gross_unfavorable_gap": sum_gross_unfavorable,
        "favorable_variance": sum_favorable,
        "sum_decomposed": sum_decomposed,
        "penny_discrepancy": penny_discrepancy,
    }


def test_reconciliation_invariant_on_50k_dataset(canonical_50k_data):
    """AC-3: Invariant holds to the cent on 50,000-row canonical dataset."""
    df, _ = canonical_50k_data
    # Set benchmark threshold at P75 = 0.185
    df_copy = df.copy()
    df_copy["benchmark_tau"] = 0.1850

    recon = compute_portfolio_reconciliation(df_copy)
    assert recon["penny_discrepancy"] == 0.0, (
        f"Reconciliation invariant failed: Net {recon['net_variance']} != "
        f"Unfavorable {recon['gross_unfavorable_gap']} + Favorable {recon['favorable_variance']}"
    )


def test_reconciliation_invariant_on_waterline_null(waterline_data):
    """AC-3: Invariant holds to the cent on waterline uniform dataset."""
    df_copy = waterline_data.copy()
    df_copy["benchmark_tau"] = 0.1400

    recon = compute_portfolio_reconciliation(df_copy)
    assert recon["penny_discrepancy"] == 0.0, (
        f"Reconciliation invariant failed on waterline dataset: "
        f"Discrepancy of ${recon['penny_discrepancy']}"
    )


def test_reconciliation_invariant_extreme_boundary_cases():
    """
    AC-3: Tests invariant across edge conditions:
    1. All transactions are unfavorable (rates > tau) -> Favorable = 0.0
    2. All transactions are favorable (rates < tau) -> Unfavorable = 0.0
    3. Exactly on threshold (rate == tau) -> Variance = 0.0
    """
    # 1. All unfavorable
    df_unfav = pd.DataFrame({
        "extended_list_amt": [10000.0, 20000.0, 50000.0],
        "net_invoiced_amt": [6000.0, 12000.0, 30000.0], # 40% discount
        "benchmark_tau": [0.20, 0.20, 0.20],
    })
    recon_unfav = compute_portfolio_reconciliation(df_unfav)
    assert recon_unfav["penny_discrepancy"] == 0.0
    assert recon_unfav["favorable_variance"] == 0.0
    assert recon_unfav["net_variance"] == recon_unfav["gross_unfavorable_gap"]

    # 2. All favorable
    df_fav = pd.DataFrame({
        "extended_list_amt": [10000.0, 20000.0, 50000.0],
        "net_invoiced_amt": [9500.0, 19000.0, 48000.0], # 5% discount
        "benchmark_tau": [0.20, 0.20, 0.20],
    })
    recon_fav = compute_portfolio_reconciliation(df_fav)
    assert recon_fav["penny_discrepancy"] == 0.0
    assert recon_fav["gross_unfavorable_gap"] == 0.0
    assert recon_fav["net_variance"] == recon_fav["favorable_variance"]

    # 3. Exactly on threshold
    df_exact = pd.DataFrame({
        "extended_list_amt": [10000.0, 20000.0],
        "net_invoiced_amt": [8000.0, 16000.0], # 20% discount
        "benchmark_tau": [0.20, 0.20],
    })
    recon_exact = compute_portfolio_reconciliation(df_exact)
    assert recon_exact["penny_discrepancy"] == 0.0
    assert recon_exact["net_variance"] == 0.0
    assert recon_exact["gross_unfavorable_gap"] == 0.0
    assert recon_exact["favorable_variance"] == 0.0
