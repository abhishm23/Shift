"""
Synthetic Commercial Sales Transaction Data Generator for Sift.

Generates:
1. 50,000-row canonical commercial transactions dataset with realistic business distributions
   and exactly 15 planted off-policy anomalous transactions in a designated cohort.
2. Waterline uniform null distribution dataset with 0 defensible exception findings under P75 bounds.
3. Control total reconciliation datasets (Certified Audit <= 1 bp, Quarantine > 1 bp).
4. Ground-truth metadata registry enabling 100% precision and 100% recall verification.
"""

from dataclasses import dataclass, field
import datetime
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


CANONICAL_COLUMNS = [
    "transaction_line_id",
    "invoice_id",
    "account_id",
    "parent_account_id",
    "transaction_date",
    "currency",
    "fx_rate_to_reporting",
    "extended_list_amt",
    "net_invoiced_amt",
    "cogs_amt",
    "off_invoice_rebate",
    "product_family",
    "sales_region",
    "industry",
    "sales_rep",
    "discount_reason",
    "channel",
]

PRODUCT_FAMILIES = ["Cloud Compute", "Enterprise Storage", "Security Suite", "Networking Hardware"]
SALES_REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
INDUSTRIES = ["Financial Services", "Healthcare", "Manufacturing", "Technology", "Retail"]
SALES_REPS = ["Rep_Alpha", "Rep_Beta", "Rep_Gamma", "Rep_Delta", "Rep_Epsilon", "Rep_Zeta"]
DISCOUNT_REASONS = ["Standard Matrix", "Competitive Match", "Volume Commitment", "Executive Override"]
CHANNELS = ["Direct Enterprise", "Channel Partner", "Inside Sales"]

PLANTED_TARGET_COHORT = {
    "product_family": "Enterprise Storage",
    "sales_region": "North America",
    "sales_rep": "Rep_Rogue",
    "discount_reason": "Executive Override",
}

NUM_PLANTED_EXCEPTIONS = 15


@dataclass
class PlantedGroundTruth:
    """Registry of planted anomalous transactions and cohort statistics."""
    target_cohort: Dict[str, str]
    num_planted: int
    planted_line_ids: List[str]
    planted_account_ids: List[str]
    planted_discount_rates: Dict[str, float]
    planted_list_amts: Dict[str, float]
    planted_net_amts: Dict[str, float]
    planted_defensible_gaps: Dict[str, float]
    baseline_p75_discount: float
    total_planted_defensible_gap: float
    ground_truth_transactions: pd.DataFrame


def generate_50k_canonical_dataset(
    n_rows: int = 50000,
    seed: int = 42,
    inject_exceptions: bool = True,
) -> Tuple[pd.DataFrame, PlantedGroundTruth]:
    """
    Generates a 50,000-row canonical dataset conforming to Sift's canonical schema.
    If inject_exceptions is True, injects exactly 15 off-policy transactions into
    the designated planted cohort.
    """
    rng = np.random.default_rng(seed)

    # 1. Primary Line Grain IDs & Invoice IDs
    # Invoices average ~4 line items each
    num_invoices = n_rows // 4
    invoice_indices = rng.integers(1, num_invoices + 1, size=n_rows)
    invoice_ids = [f"INV-{idx:06d}" for idx in invoice_indices]

    # Line IDs
    line_ids = [f"TX-{idx:06d}" for idx in range(1, n_rows + 1)]

    # 2. Customer Accounts & Parents (250 accounts, 50 parents)
    num_accounts = 250
    num_parents = 50
    acct_to_parent = {
        f"ACC-{i:04d}": f"PARENT-{((i - 1) % num_parents) + 1:03d}"
        for i in range(1, num_accounts + 1)
    }
    account_indices = rng.integers(1, num_accounts + 1, size=n_rows)
    account_ids = [f"ACC-{idx:04d}" for idx in account_indices]
    parent_account_ids = [acct_to_parent[acc] for acc in account_ids]

    # 3. Dates: FY2025 (2025-01-01 to 2025-12-31)
    start_date = datetime.date(2025, 1, 1)
    date_offsets = rng.integers(0, 365, size=n_rows)
    transaction_dates = [
        (start_date + datetime.timedelta(days=int(offset))).isoformat()
        for offset in date_offsets
    ]

    # 4. Currency and FX Rate
    currencies = ["USD"] * n_rows
    fx_rates = [1.0] * n_rows

    # 5. Categorical Dimensions
    prod_fam = rng.choice(PRODUCT_FAMILIES, size=n_rows, p=[0.30, 0.25, 0.25, 0.20])
    regions = rng.choice(SALES_REGIONS, size=n_rows, p=[0.40, 0.30, 0.20, 0.10])
    industries = rng.choice(INDUSTRIES, size=n_rows)
    reps = rng.choice(SALES_REPS, size=n_rows, p=[0.20, 0.20, 0.20, 0.15, 0.15, 0.10])
    reasons = rng.choice(DISCOUNT_REASONS, size=n_rows, p=[0.45, 0.30, 0.20, 0.05])
    channels = rng.choice(CHANNELS, size=n_rows, p=[0.50, 0.35, 0.15])

    # 6. Financial Concessions & Realized Discounts
    # Realistic log-normal distribution for list price ($500 to $50,000)
    list_amts = np.round(rng.lognormal(mean=8.5, sigma=0.8, size=n_rows), 2)
    # Clamp list prices to realistic range
    list_amts = np.clip(list_amts, 500.0, 50000.0)

    # Base market discount: Beta distribution (mean ~0.15, standard dev ~0.035)
    # Background discounts stay strictly below 0.25
    base_discounts = np.round(rng.beta(a=3.0, b=17.0, size=n_rows), 4)
    base_discounts = np.clip(base_discounts, 0.03, 0.24)

    # Calculate net invoiced amounts
    net_invoiced_amts = np.round(list_amts * (1.0 - base_discounts), 2)

    # Tier 2 fields: COGS (50-65% of list) and Off-Invoice Rebates (2-4% of list)
    cogs_ratios = rng.uniform(0.50, 0.65, size=n_rows)
    cogs_amts = np.round(list_amts * cogs_ratios, 2)
    rebate_ratios = rng.uniform(0.015, 0.040, size=n_rows)
    off_invoice_rebates = np.round(list_amts * rebate_ratios, 2)

    df = pd.DataFrame({
        "transaction_line_id": line_ids,
        "invoice_id": invoice_ids,
        "account_id": account_ids,
        "parent_account_id": parent_account_ids,
        "transaction_date": transaction_dates,
        "currency": currencies,
        "fx_rate_to_reporting": fx_rates,
        "extended_list_amt": list_amts,
        "net_invoiced_amt": net_invoiced_amts,
        "cogs_amt": cogs_amts,
        "off_invoice_rebate": off_invoice_rebates,
        "product_family": prod_fam,
        "sales_region": regions,
        "industry": industries,
        "sales_rep": reps,
        "discount_reason": reasons,
        "channel": channels,
    })

    planted_line_ids = []
    planted_account_ids = []
    planted_discounts = {}
    planted_lists = {}
    planted_nets = {}
    planted_gaps = {}
    ground_truth_df = pd.DataFrame()
    baseline_p75 = 0.1850
    total_planted_gap = 0.0

    if inject_exceptions:
        # In the target cohort, calculate baseline P75
        # Identify background transactions in cohort
        cohort_mask = (
            (df["product_family"] == PLANTED_TARGET_COHORT["product_family"])
            & (df["sales_region"] == PLANTED_TARGET_COHORT["sales_region"])
        )
        cohort_discounts = (df.loc[cohort_mask, "extended_list_amt"] - df.loc[cohort_mask, "net_invoiced_amt"]) / df.loc[cohort_mask, "extended_list_amt"]
        if len(cohort_discounts) > 0:
            baseline_p75 = float(np.percentile(cohort_discounts, 75))
        else:
            baseline_p75 = 0.1850

        # Inject exactly 15 off-policy transactions into distinct accounts
        # To satisfy LOAO fences: distinct accounts >= 5
        target_accounts = [f"ACC-004{i}" for i in range(1, 6)] # 5 distinct customer accounts
        planted_line_ids = [f"TX-PLANTED-{i:03d}" for i in range(1, NUM_PLANTED_EXCEPTIONS + 1)]

        planted_rows = []
        for i in range(NUM_PLANTED_EXCEPTIONS):
            lid = planted_line_ids[i]
            # Distribute 3 transactions per account across 5 accounts
            acct = target_accounts[i % 5]
            if acct not in planted_account_ids:
                planted_account_ids.append(acct)
            
            # Off-policy discount: 0.48 to 0.60 (substantially above P75 ~0.18)
            disc_rate = round(0.48 + (i * 0.008), 4)
            planted_discounts[lid] = disc_rate
            
            # List price $5,000 to $25,000
            list_amt = round(8000.0 + (i * 1000.0), 2)
            net_amt = round(list_amt * (1.0 - disc_rate), 2)
            cogs = round(list_amt * 0.55, 2)
            rebate = round(list_amt * 0.03, 2)
            gap = round(max(0.0, disc_rate - baseline_p75) * list_amt, 2)
            
            planted_lists[lid] = list_amt
            planted_nets[lid] = net_amt
            planted_gaps[lid] = gap
            total_planted_gap += gap

            planted_rows.append({
                "transaction_line_id": lid,
                "invoice_id": f"INV-PLANTED-{i+1:04d}",
                "account_id": acct,
                "parent_account_id": acct_to_parent.get(acct, "PARENT-001"),
                "transaction_date": f"2025-06-{(i % 28) + 1:02d}",
                "currency": "USD",
                "fx_rate_to_reporting": 1.0,
                "extended_list_amt": list_amt,
                "net_invoiced_amt": net_amt,
                "cogs_amt": cogs,
                "off_invoice_rebate": rebate,
                "product_family": PLANTED_TARGET_COHORT["product_family"],
                "sales_region": PLANTED_TARGET_COHORT["sales_region"],
                "industry": "Technology",
                "sales_rep": PLANTED_TARGET_COHORT["sales_rep"],
                "discount_reason": PLANTED_TARGET_COHORT["discount_reason"],
                "channel": "Direct Enterprise",
            })

        ground_truth_df = pd.DataFrame(planted_rows)

        # Replace first 15 rows or inject at specific indices
        # We replace the first 15 rows of the DataFrame with the planted rows
        for col in df.columns:
            df.loc[0:NUM_PLANTED_EXCEPTIONS - 1, col] = ground_truth_df[col].values

    ground_truth = PlantedGroundTruth(
        target_cohort=PLANTED_TARGET_COHORT,
        num_planted=NUM_PLANTED_EXCEPTIONS if inject_exceptions else 0,
        planted_line_ids=planted_line_ids,
        planted_account_ids=planted_account_ids,
        planted_discount_rates=planted_discounts,
        planted_list_amts=planted_lists,
        planted_net_amts=planted_nets,
        planted_defensible_gaps=planted_gaps,
        baseline_p75_discount=baseline_p75,
        total_planted_defensible_gap=round(total_planted_gap, 2),
        ground_truth_transactions=ground_truth_df,
    )

    return df, ground_truth


def generate_waterline_null_dataset(
    n_rows: int = 20000,
    seed: int = 101,
) -> pd.DataFrame:
    """
    Generates a waterline uniform, non-anomalous distribution dataset where
    all discounts are tightly bounded and uniformly distributed across accounts
    and slices. Under default P75 and FDR control (q < 0.05), the engine must
    return exactly 0 defensible exception findings.
    """
    rng = np.random.default_rng(seed)

    num_invoices = n_rows // 4
    invoice_ids = [f"INV-W-{idx:05d}" for idx in rng.integers(1, num_invoices + 1, size=n_rows)]
    line_ids = [f"TX-W-{idx:06d}" for idx in range(1, n_rows + 1)]

    num_accounts = 100
    account_ids = [f"ACC-W-{idx:03d}" for idx in rng.integers(1, num_accounts + 1, size=n_rows)]
    parent_ids = [f"PARENT-W-{(int(acc.split('-')[-1]) % 20) + 1:02d}" for acc in account_ids]

    start_date = datetime.date(2025, 1, 1)
    dates = [
        (start_date + datetime.timedelta(days=int(d))).isoformat()
        for d in rng.integers(0, 365, size=n_rows)
    ]

    prod_fam = rng.choice(PRODUCT_FAMILIES, size=n_rows)
    regions = rng.choice(SALES_REGIONS, size=n_rows)
    industries = rng.choice(INDUSTRIES, size=n_rows)
    reps = rng.choice(SALES_REPS, size=n_rows)
    reasons = rng.choice(DISCOUNT_REASONS, size=n_rows)
    channels = rng.choice(CHANNELS, size=n_rows)

    list_amts = np.round(rng.uniform(1000.0, 10000.0, size=n_rows), 2)
    # Strictly uniform discount distribution in [0.12, 0.16] - zero outliers, zero anomalous slices
    discounts = np.round(rng.uniform(0.12, 0.16, size=n_rows), 4)
    net_amts = np.round(list_amts * (1.0 - discounts), 2)

    cogs_amts = np.round(list_amts * 0.55, 2)
    rebates = np.round(list_amts * 0.02, 2)

    df = pd.DataFrame({
        "transaction_line_id": line_ids,
        "invoice_id": invoice_ids,
        "account_id": account_ids,
        "parent_account_id": parent_ids,
        "transaction_date": dates,
        "currency": ["USD"] * n_rows,
        "fx_rate_to_reporting": [1.0] * n_rows,
        "extended_list_amt": list_amts,
        "net_invoiced_amt": net_amts,
        "cogs_amt": cogs_amts,
        "off_invoice_rebate": rebates,
        "product_family": prod_fam,
        "sales_region": regions,
        "industry": industries,
        "sales_rep": reps,
        "discount_reason": reasons,
        "channel": channels,
    })

    return df


def generate_reconciliation_dataset(
    seed: int = 42,
    discrepancy_bp: float = 0.0,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Generates a dataset and corresponding control totals with specified discrepancy in basis points.
    If discrepancy_bp <= 1.0 bp (e.g. 0.0 bp or 0.5 bp), status is CERTIFIED_AUDIT.
    If discrepancy_bp > 1.0 bp (e.g. 5.0 bp = 0.05%), status triggers QUARANTINE_AND_PROCEED.
    """
    df, _ = generate_50k_canonical_dataset(n_rows=5000, seed=seed, inject_exceptions=False)

    actual_gross = float(round(df["extended_list_amt"].sum(), 2))
    actual_net = float(round(df["net_invoiced_amt"].sum(), 2))

    # Apply discrepancy factor
    # 1 bp = 0.0001 (0.01%)
    discrepancy_factor = 1.0 + (discrepancy_bp / 10000.0)

    confirmed_gross = float(round(actual_gross * discrepancy_factor, 2))
    confirmed_net = float(round(actual_net * discrepancy_factor, 2))

    variance_gross_dollars = round(actual_gross - confirmed_gross, 2)
    variance_net_dollars = round(actual_net - confirmed_net, 2)

    actual_gross_bp = round(abs(variance_gross_dollars) / confirmed_gross * 10000.0, 4)
    actual_net_bp = round(abs(variance_net_dollars) / confirmed_net * 10000.0, 4)

    max_bp = max(actual_gross_bp, actual_net_bp)
    is_certified = max_bp <= 1.0

    watermark_text = None
    if not is_certified:
        variance_pct = round(max_bp / 100.0, 2)
        watermark_text = f"UNRECONCILED RESIDUAL: {variance_pct:.2f}% (${abs(variance_net_dollars):,.2f}) OUTSIDE AUDIT GUARDRAILS"

    control_manifest = {
        "actual_gross_list": actual_gross,
        "actual_net_invoiced": actual_net,
        "confirmed_gross_list": confirmed_gross,
        "confirmed_net_invoiced": confirmed_net,
        "variance_gross_dollars": variance_gross_dollars,
        "variance_net_dollars": variance_net_dollars,
        "variance_gross_bp": actual_gross_bp,
        "variance_net_bp": actual_net_bp,
        "is_certified_audit": is_certified,
        "status": "CERTIFIED_AUDIT" if is_certified else "QUARANTINED_AND_PROCEEDED",
        "watermark_applied": not is_certified,
        "watermark_text": watermark_text,
    }

    return df, control_manifest


def verify_ground_truth_recovery(
    identified_tx_ids: List[str],
    ground_truth_ids: List[str],
) -> Dict[str, Any]:
    """
    Computes precision, recall, and classification metrics between identified
    anomalous transactions and ground truth planted transactions.
    """
    identified_set = set(identified_tx_ids)
    ground_truth_set = set(ground_truth_ids)

    tp_set = identified_set.intersection(ground_truth_set)
    fp_set = identified_set - ground_truth_set
    fn_set = ground_truth_set - identified_set

    tp = len(tp_set)
    fp = len(fp_set)
    fn = len(fn_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "perfect_recovery": (precision == 1.0 and recall == 1.0),
        "tp_ids": sorted(list(tp_set)),
        "fp_ids": sorted(list(fp_set)),
        "fn_ids": sorted(list(fn_set)),
    }


def save_dataset_csv(df: pd.DataFrame, path: str) -> str:
    """Exports DataFrame to CSV with strict UTF-8 encoding."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return path


def save_dataset_parquet(df: pd.DataFrame, path: str) -> str:
    """Exports DataFrame to Snappy-compressed Parquet."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    df.to_parquet(path, index=False, compression="snappy")
    return path


# =====================================================================
# Standalone Unit Tests verifying the synthetic data generator logic
# =====================================================================

def test_synthetic_50k_shape_and_columns():
    """Verify that 50,000 canonical rows are created with all canonical fields."""
    df, meta = generate_50k_canonical_dataset(n_rows=50000, seed=42, inject_exceptions=True)
    assert len(df) == 50000
    for col in CANONICAL_COLUMNS:
        assert col in df.columns, f"Missing required canonical column: {col}"
    assert meta.num_planted == 15
    assert len(meta.planted_line_ids) == 15


def test_planted_exceptions_characteristics():
    """Verify that planted exceptions have defensible gaps and off-policy discount rates."""
    df, meta = generate_50k_canonical_dataset(n_rows=1000, seed=42, inject_exceptions=True)
    assert len(meta.planted_line_ids) == 15
    assert len(meta.planted_account_ids) >= 5, "Planted cohort must span >= 5 distinct accounts to satisfy LOAO fences"
    
    # Check that each planted transaction has high discount rate (>= 0.40)
    for lid in meta.planted_line_ids:
        disc = meta.planted_discount_rates[lid]
        assert disc >= 0.40, f"Planted transaction {lid} discount {disc} too low"
        gap = meta.planted_defensible_gaps[lid]
        assert gap > 0, f"Planted transaction {lid} must produce positive defensible gap"


def test_waterline_distribution_properties():
    """Verify that waterline distribution has tightly bounded discounts with zero outliers."""
    df = generate_waterline_null_dataset(n_rows=5000, seed=101)
    assert len(df) == 5000
    discounts = (df["extended_list_amt"] - df["net_invoiced_amt"]) / df["extended_list_amt"]
    assert discounts.min() >= 0.119
    assert discounts.max() <= 0.161
    assert discounts.std() < 0.02


def test_reconciliation_discrepancy_calculations():
    """Verify certified audit (<= 1 bp) and quarantine (> 1 bp) discrepancy logic."""
    # Test Certified Audit (0.5 bp)
    _, cert_manifest = generate_reconciliation_dataset(seed=42, discrepancy_bp=0.5)
    assert cert_manifest["is_certified_audit"] is True
    assert cert_manifest["status"] == "CERTIFIED_AUDIT"
    assert cert_manifest["watermark_applied"] is False

    # Test Quarantine (5.0 bp)
    _, guar_manifest = generate_reconciliation_dataset(seed=42, discrepancy_bp=5.0)
    assert guar_manifest["is_certified_audit"] is False
    assert guar_manifest["status"] == "QUARANTINED_AND_PROCEEDED"
    assert guar_manifest["watermark_applied"] is True
    assert "OUTSIDE AUDIT GUARDRAILS" in guar_manifest["watermark_text"]


def test_ground_truth_metric_evaluator():
    """Verify precision and recall metric computation."""
    ground_truth = ["TX-1", "TX-2", "TX-3"]
    # Perfect recovery
    res = verify_ground_truth_recovery(["TX-1", "TX-2", "TX-3"], ground_truth)
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["perfect_recovery"] is True

    # False positive
    res_fp = verify_ground_truth_recovery(["TX-1", "TX-2", "TX-3", "TX-4"], ground_truth)
    assert res_fp["precision"] == 0.75
    assert res_fp["recall"] == 1.0
    assert res_fp["false_positives"] == 1

    # False negative
    res_fn = verify_ground_truth_recovery(["TX-1", "TX-2"], ground_truth)
    assert res_fn["precision"] == 1.0
    assert res_fn["recall"] == 2.0 / 3.0
    assert res_fn["false_negatives"] == 1


def test_file_serialization_csv_and_parquet(tmp_path):
    """Verify that dataset exports cleanly to CSV and Parquet, then reloads identically."""
    df, _ = generate_50k_canonical_dataset(n_rows=500, seed=42, inject_exceptions=True)
    
    csv_path = str(tmp_path / "test_500.csv")
    parquet_path = str(tmp_path / "test_500.parquet")
    
    save_dataset_csv(df, csv_path)
    save_dataset_parquet(df, parquet_path)
    
    assert os.path.exists(csv_path)
    assert os.path.exists(parquet_path)
    
    reloaded_csv = pd.read_csv(csv_path)
    reloaded_pq = pd.read_parquet(parquet_path)
    
    assert len(reloaded_csv) == 500
    assert len(reloaded_pq) == 500
    assert list(reloaded_csv.columns) == list(df.columns)
    assert list(reloaded_pq.columns) == list(df.columns)

