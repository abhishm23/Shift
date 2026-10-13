"""
Shared reference algorithms and test oracle helpers for Sift E2E verification.

Provides authoritative mathematical implementations of:
1. LOAO Cohort Partitioning & P75 Benchmark Scoring in DuckDB.
2. Empirical Bayes Shrinkage & Benjamini-Hochberg FDR Control.
3. Deduplicated Overlap Ledger calculation.
4. Two-phase CSV Formula Injection Defense (preserving negative numbers).
5. Gated Lifecycle State Machine transition rules with punitive code lockout.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb
import numpy as np
import pandas as pd


NUMERIC_REGEX = re.compile(r'^[+-]?((\d+(\.\d*)?)|(\.\d+))([eE][+-]?\d+)?$')
DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

PUNITIVE_DISPOSITION_CODES = {"Unapproved Concession", "Unauthorized Deal"}
VALID_DISMISSAL_CATEGORIES = {
    "Statistical Anomaly",
    "Market Alignment",
    "Customer Volume Justified",
    "Legacy Contract Terms",
    "Pre-Approved Override",
}


def get_configured_duckdb(db_path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    """Returns a DuckDB connection configured with 4GB memory ceiling."""
    con = duckdb.connect(db_path)
    con.execute("PRAGMA threads = 4;")
    con.execute("PRAGMA max_memory = '4GB';")
    return con


def sanitize_csv_cell(value: Any) -> str:
    """
    Two-step formula injection defense algorithm:
    Phase 1: Pure numeric preservation (preserves valid negative values like -1450.50).
    Phase 2: Neutralize dangerous prefixes (=, +, -, @, \\t, \\r) on non-numeric text.
    """
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    # Phase 1: Pure Numeric Preservation
    if NUMERIC_REGEX.match(s.strip()):
        return s.strip()
    # Phase 2: Formula Injection Neutralization
    if s[0] in DANGEROUS_PREFIXES:
        return "'" + s
    return s


def validate_finding_transition(
    evidence_tier: str,
    new_state: str,
    disposition_code: Optional[str] = None,
    dismissal_category: Optional[str] = None,
    snooze_date: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validates finding lifecycle state transitions according to R6.41 and AC-9.
    Blocks punitive disposition codes unless evidence_tier == 'Tier 3'.
    Requires mandatory category and snooze date for dismissals.
    """
    valid_states = {"New", "Assigned", "In Review", "Dismissed", "Actioned"}
    if new_state not in valid_states:
        return False, f"Invalid target state: {new_state}"

    # Punitive Disposition Lockdown Invariant (AC-9)
    if disposition_code in PUNITIVE_DISPOSITION_CODES:
        if evidence_tier != "Tier 3" and evidence_tier != "Tier 3 (Rule-Confirmed Exception)":
            return False, (
                f"Punitive disposition code '{disposition_code}' is locked for {evidence_tier}. "
                "Only permitted for Tier 3 Rule-Confirmed Exceptions."
            )

    # Dismissal Governance Invariant
    if new_state == "Dismissed":
        if not dismissal_category or dismissal_category not in VALID_DISMISSAL_CATEGORIES:
            return False, f"Mandatory valid dismissal category required. Got: {dismissal_category}"
        if not snooze_date:
            return False, "Mandatory snooze/expiry date required for dismissal."

    return True, "Valid transition"


def compute_reference_loao_p75(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "transactions",
    min_tx: int = 10,
    min_accounts: int = 5,
) -> pd.DataFrame:
    """
    Vectorized LOAO reference computation in DuckDB:
    For each (product_family, sales_region, account_id), computes the peer cohort P75
    excluding that account, then scores all transactions for defensible gap.
    """
    query = f"""
    WITH peer_stats AS (
        SELECT 
            dp.product_family,
            dp.sales_region,
            dp.account_id,
            COUNT(t.transaction_line_id) AS peer_count,
            COUNT(DISTINCT t.account_id) AS peer_accounts,
            quantile_cont(t.realized_discount_rate, 0.75) AS p75_concession,
            median(t.realized_discount_rate) AS median_concession
        FROM (
            SELECT DISTINCT product_family, sales_region, account_id 
            FROM {table_name}
        ) dp
        JOIN {table_name} t
          ON dp.product_family = t.product_family
         AND dp.sales_region = t.sales_region
         AND dp.account_id != t.account_id
        GROUP BY dp.product_family, dp.sales_region, dp.account_id
    )
    SELECT 
        t.transaction_line_id,
        t.account_id,
        t.product_family,
        t.sales_region,
        t.sales_rep,
        t.discount_reason,
        t.extended_list_amt,
        t.net_invoiced_amt,
        t.realized_discount_rate,
        ps.peer_count,
        ps.peer_accounts,
        ps.p75_concession,
        CASE 
            WHEN ps.peer_count < {min_tx} OR ps.peer_accounts < {min_accounts} 
            THEN 'Insufficient Comparable Evidence'
            ELSE 'Defensible Baseline'
        END AS support_status,
        CASE 
            WHEN ps.peer_count >= {min_tx} AND ps.peer_accounts >= {min_accounts} 
            THEN GREATEST(0.0, t.realized_discount_rate - ps.p75_concession) * t.extended_list_amt
            ELSE 0.0
        END AS defensible_gap
    FROM {table_name} t
    LEFT JOIN peer_stats ps
      ON t.product_family = ps.product_family
     AND t.sales_region = ps.sales_region
     AND t.account_id = ps.account_id;
    """
    return con.execute(query).df()


def apply_empirical_bayes_and_fdr(
    scored_df: pd.DataFrame,
    group_cols: List[str],
    fdr_q: float = 0.05,
) -> pd.DataFrame:
    """
    Computes candidate slices, applies Empirical Bayes shrinkage toward the parent mean,
    runs bootstrap stability check, and applies Benjamini-Hochberg FDR control.
    """
    slices = []
    # Parent cohort prior parameters
    prior_mean = scored_df["defensible_gap"].mean()
    prior_var = max(scored_df["defensible_gap"].var(), 1e-6)

    grouped = scored_df.groupby(group_cols)
    for name, group in grouped:
        n = len(group)
        if n < 5:
            continue
        sample_mean = group["defensible_gap"].mean()
        sample_var = max(group["defensible_gap"].var(), 1e-6)
        
        # Empirical Bayes shrinkage factor
        # lambda = prior_var / (prior_var + sample_var / n)
        shrinkage_lambda = prior_var / (prior_var + (sample_var / n))
        shrunk_mean = (shrinkage_lambda * sample_mean) + ((1.0 - shrinkage_lambda) * prior_mean)
        total_shrunk_gap = shrunk_mean * n

        # Test whether slice excess gap above parent cohort is statistically significant
        # H0: slice_mean <= prior_mean
        diff_mean = sample_mean - prior_mean
        se = math.sqrt((sample_var / n) + (prior_var / len(scored_df)))
        z_score = diff_mean / se if se > 0 else 0.0
        # Right-tailed p-value for excess concession
        p_val = 0.5 * math.erfc(z_score / math.sqrt(2.0))

        # 200-iteration bootstrap check on excess gap
        resample_excess = []
        gaps_arr = group["defensible_gap"].values
        rng = np.random.default_rng(42)
        for _ in range(200):
            resample = rng.choice(gaps_arr, size=n, replace=True)
            resample_excess.append(resample.mean() - prior_mean)
        ci_lower = float(np.percentile(resample_excess, 5))
        ci_upper = float(np.percentile(resample_excess, 95))
        # 90% CI must be strictly positive (does not cross zero)
        is_stable = ci_lower > 0.0

        slice_dict = {
            "group_keys": dict(zip(group_cols, name if isinstance(name, tuple) else [name])),
            "sample_size": n,
            "distinct_accounts": group["account_id"].nunique(),
            "raw_total_gap": float(group["defensible_gap"].sum()),
            "shrunk_total_gap": float(total_shrunk_gap),
            "diff_mean": float(diff_mean),
            "p_value": float(p_val),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "is_stable": is_stable,
            "tx_ids": group["transaction_line_id"].tolist(),
        }
        slices.append(slice_dict)

    if not slices:
        return pd.DataFrame()

    res_df = pd.DataFrame(slices)
    # Benjamini-Hochberg FDR
    res_df = res_df.sort_values("p_value").reset_index(drop=True)
    m = len(res_df)
    res_df["bh_threshold"] = [(i + 1) / m * fdr_q for i in range(m)]
    res_df["fdr_reject"] = res_df["p_value"] <= res_df["bh_threshold"]

    # Filter for significant & stable findings with positive excess gap
    res_df["is_exception_finding"] = res_df["fdr_reject"] & res_df["is_stable"] & (res_df["diff_mean"] > 0)
    return res_df
