"""
Sift Bounded Diagnostic Beam Search Traversal & Statistical Triage (Milestone 4)

Authoritative Requirements & Features:
- R4.1: Empirical Bayes shrinkage pulling slice gaps toward parent cohort mean
        based on sample volume and variance.
- R4.2: 200-iteration bootstrap stability checks (flagging findings where 90% CI crosses zero).
- R4.3: Benjamini-Hochberg False Discovery Rate (FDR q < 0.05) control.
- R4.4: Bounded beam search traversal (width: 3, max depth: 3).
- R4.5: Multi-signal priority vector (Dollar Gap, Concentration Ratio, Bootstrap Stability,
        Incremental Coverage).
- R4.6 & R4.7: Inverted transaction gap ledger tracking multi-finding memberships
               and deduplicated Net Unique Portfolio Exposure.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb
import numpy as np
import pandas as pd

from backend.overlap_ledger import (
    compute_net_unique_portfolio_exposure,
    get_finding_transactions,
    get_overlap_ledger,
    record_findings_to_db,
)


# ---------------------------------------------------------------------------
# 1. Deterministic SHA-256 Fingerprinting
# ---------------------------------------------------------------------------

def compute_finding_fingerprint(
    dimension_slice: Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
    calib_id: str = "CALIB-DEFAULT",
) -> str:
    """
    Computes a deterministic 64-character SHA-256 fingerprint for a slice finding.
    Formula: SHA256(canonical_json(dimension_slice) + '|' + canonical_json(filters) + '|' + calib_id)
    """
    norm_dims = {str(k): str(v) for k, v in sorted(dimension_slice.items())}
    norm_filters = {str(k): str(v) for k, v in sorted((filters or {}).items())}
    dims_json = json.dumps(norm_dims, sort_keys=True)
    filters_json = json.dumps(norm_filters, sort_keys=True)
    payload = f"{dims_json}|{filters_json}|{calib_id.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 2. Statistical Primitives: Empirical Bayes Shrinkage
# ---------------------------------------------------------------------------

def compute_empirical_bayes_shrinkage(
    sample_mean: float,
    sample_var: float,
    n: int,
    prior_mean: float,
    prior_var: float,
) -> Tuple[float, float, float]:
    """
    Computes Empirical Bayes shrinkage pulling slice gap estimate toward parent prior mean.

    Equations:
        lambda = prior_var / (prior_var + (sample_var / n))
        shrunk_mean = (lambda * sample_mean) + ((1.0 - lambda) * prior_mean)
        total_shrunk_gap = shrunk_mean * n

    Returns:
        (shrunk_mean, shrinkage_lambda, total_shrunk_gap)
    """
    if n <= 0:
        return prior_mean, 0.0, 0.0

    p_var = max(float(prior_var), 1e-6)
    s_var = max(float(sample_var), 1e-6)

    variance_ratio = s_var / n
    shrinkage_lambda = p_var / (p_var + variance_ratio)
    shrinkage_lambda = max(0.0, min(1.0, float(shrinkage_lambda)))

    shrunk_mean = (shrinkage_lambda * sample_mean) + ((1.0 - shrinkage_lambda) * prior_mean)
    total_shrunk_gap = float(shrunk_mean * n)

    return float(shrunk_mean), float(shrinkage_lambda), float(total_shrunk_gap)


# ---------------------------------------------------------------------------
# 3. Statistical Primitives: Hypothesis Testing & FDR Control
# ---------------------------------------------------------------------------

def compute_wald_hypothesis_test(
    sample_mean: float,
    sample_var: float,
    n: int,
    prior_mean: float,
    prior_var: float,
    total_population_n: int,
) -> Tuple[float, float]:
    """
    Right-tailed test for excess concession above parent cohort mean:
        H0: slice_mean <= prior_mean
        H1: slice_mean > prior_mean

    Equations:
        diff_mean = sample_mean - prior_mean
        SE = sqrt((sample_var / n) + (prior_var / total_population_n))
        Z = diff_mean / SE
        p_val = 0.5 * erfc(Z / sqrt(2))

    Returns:
        (z_score, p_value)
    """
    diff_mean = sample_mean - prior_mean
    p_var = max(float(prior_var), 1e-6)
    s_var = max(float(sample_var), 1e-6)
    pop_n = max(int(total_population_n), 1)

    se = math.sqrt((s_var / n) + (p_var / pop_n))
    if se <= 0.0:
        return 0.0, 0.5

    z_score = diff_mean / se
    p_val = 0.5 * math.erfc(z_score / math.sqrt(2.0))
    p_val = max(0.0, min(1.0, float(p_val)))

    return float(z_score), float(p_val)


def run_bootstrap_stability_check(
    gaps: np.ndarray,
    prior_mean: float,
    n_boot: int = 200,
    ci_percentile: float = 90.0,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Executes a 200-iteration non-parametric bootstrap resampling on candidate slice gaps.
    Evaluates whether the 90% confidence interval of excess gap (resample.mean() - prior_mean)
    crosses zero.

    Returns dict with keys:
        - ci_lower: float (5th percentile for 90% CI)
        - ci_upper: float (95th percentile for 90% CI)
        - is_stable: bool (ci_lower > 0.0)
        - stability_score: float (proportion of resamples with excess > 0.0)
    """
    gaps_arr = np.asarray(gaps, dtype=np.float64)
    n = len(gaps_arr)
    if n == 0:
        return {
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "is_stable": False,
            "stability_score": 0.0,
        }

    alpha = (100.0 - ci_percentile) / 2.0  # 5.0% for 90% CI
    upper_pct = 100.0 - alpha              # 95.0% for 90% CI

    rng = np.random.default_rng(seed)
    # Vectorized 2D matrix resampling: (n_boot, n)
    resamples = rng.choice(gaps_arr, size=(n_boot, n), replace=True)
    resample_means = np.mean(resamples, axis=1)
    resample_excess = resample_means - prior_mean

    ci_lower = float(np.percentile(resample_excess, alpha))
    ci_upper = float(np.percentile(resample_excess, upper_pct))
    is_stable = bool(ci_lower > 0.0)
    stability_score = float(np.mean(resample_excess > 0.0))

    return {
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "is_stable": is_stable,
        "stability_score": round(stability_score, 4),
    }


def apply_benjamini_hochberg_fdr(
    candidates: List[Dict[str, Any]],
    fdr_q: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    Applies Benjamini-Hochberg False Discovery Rate control (q < 0.05).
    Sets 'fdr_rejected', 'fdr_q_value', 'bh_threshold', and 'is_exception_finding'.
    """
    if not candidates:
        return []

    # Sort candidates ascending by p_value
    sorted_candidates = sorted(candidates, key=lambda c: c["p_value"])
    m = len(sorted_candidates)

    # 1. Step-up BH critical value: p_(k) <= (k / m) * fdr_q
    # Find largest k satisfying the threshold
    k_star = 0
    for i, c in enumerate(sorted_candidates):
        rank = i + 1
        threshold = (rank / m) * fdr_q
        c["bh_threshold"] = round(threshold, 6)
        if c["p_value"] <= threshold:
            k_star = rank

    # 2. Step-down adjusted q-values:
    # q_(m) = p_(m)
    # q_(k) = min(1.0, min(q_(k+1), (m / k) * p_(k)))
    q_vals = [0.0] * m
    q_vals[-1] = min(1.0, sorted_candidates[-1]["p_value"])
    for i in range(m - 2, -1, -1):
        rank = i + 1
        raw_q = (m / rank) * sorted_candidates[i]["p_value"]
        q_vals[i] = min(1.0, min(q_vals[i + 1], raw_q))

    for i, c in enumerate(sorted_candidates):
        rank = i + 1
        c["fdr_q_value"] = round(q_vals[i], 6)
        c["fdr_rejected"] = bool(rank <= k_star and c["fdr_q_value"] <= fdr_q)
        # Final qualification predicate
        c["is_exception_finding"] = bool(
            c["fdr_rejected"] and c.get("is_stable", False) and (c.get("diff_mean", 0.0) > 0.0)
        )

    return sorted_candidates


# ---------------------------------------------------------------------------
# 4. Multi-Signal Priority Vector Ranking
# ---------------------------------------------------------------------------

def rank_candidates_by_priority_vector(
    candidates: List[Dict[str, Any]],
    covered_tx_ids: Set[str],
    weights: Tuple[float, float, float, float] = (0.35, 0.25, 0.20, 0.20),
) -> List[Dict[str, Any]]:
    """
    Ranks candidate slices via multi-signal priority vector:
    1. Absolute Dollar Gap (shrunk_gap_dollars)
    2. Relative Concentration Ratio (raw_total_gap / gross_list_volume)
    3. Bootstrap Stability (stability_score)
    4. Incremental Coverage (unique_incremental_gap / raw_total_gap)

    Weights: (0.35, 0.25, 0.20, 0.20)
    Returns sorted candidates descending by (is_exception_finding, priority_score).
    """
    if not candidates:
        return []

    w_gap, w_conc, w_boot, w_cov = weights

    # Compute incremental coverage for each candidate
    for c in candidates:
        tx_ids = c.get("tx_ids", [])
        gap_values = c.get("gap_values", [])
        raw_gap = float(c.get("unshrunk_gap_dollars", c.get("raw_total_gap", 0.0)))

        # Find transactions not yet covered by previously selected findings
        unique_tids = set(tx_ids) - covered_tx_ids
        if len(unique_tids) == len(tx_ids):
            inc_gap = raw_gap
        elif len(unique_tids) == 0:
            inc_gap = 0.0
        else:
            inc_gap = sum(
                gap_values[i] for i, tid in enumerate(tx_ids) if tid in unique_tids
            )

        c["unique_incremental_gap"] = max(0.0, float(inc_gap))
        cov_ratio = (inc_gap / (raw_gap + 1e-9)) if raw_gap > 0 else 0.0
        c["coverage_ratio"] = max(0.0, min(1.0, float(cov_ratio)))

    # Min-max normalization helper
    def _normalize(values: List[float]) -> List[float]:
        if not values:
            return []
        v_min, v_max = min(values), max(values)
        spread = v_max - v_min
        if spread <= 1e-9:
            return [1.0 if v_max > 0 else 0.0 for _ in values]
        return [(v - v_min) / spread for v in values]

    gap_norm = _normalize([float(c.get("shrunk_gap_dollars", 0.0)) for c in candidates])
    conc_norm = _normalize([float(c.get("concentration_ratio", 0.0)) for c in candidates])
    boot_norm = [float(c.get("bootstrap_stability_score", 0.0)) for c in candidates]
    cov_norm = [float(c.get("coverage_ratio", 1.0)) for c in candidates]

    for i, c in enumerate(candidates):
        score = 100.0 * (
            (w_gap * gap_norm[i]) +
            (w_conc * conc_norm[i]) +
            (w_boot * boot_norm[i]) +
            (w_cov * cov_norm[i])
        )
        c["priority_score"] = round(float(score), 2)

    # Sort descending: exception findings first, then by priority score
    candidates.sort(
        key=lambda c: (
            1 if c.get("is_exception_finding", False) else 0,
            c.get("priority_score", 0.0),
            c.get("shrunk_gap_dollars", 0.0),
        ),
        reverse=True,
    )

    return candidates


# ---------------------------------------------------------------------------
# 5. Helper: Database Initialization & Fallbacks
# ---------------------------------------------------------------------------

def _ensure_schema_exists(con: duckdb.DuckDBPyConnection) -> None:
    """Ensures finding_records and finding_transactions_map tables exist."""
    tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
    if "meta_calibration_profiles" not in tables:
        con.execute("""
            CREATE TABLE IF NOT EXISTS meta_calibration_profiles (
                calibration_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                historical_start_date DATE NOT NULL,
                historical_end_date DATE NOT NULL,
                comparability_controls VARCHAR[] NOT NULL,
                investigation_dimensions VARCHAR[] NOT NULL,
                threshold_strategy VARCHAR NOT NULL,
                haircut_kappa DECIMAL(5, 4) NOT NULL DEFAULT 0.4000,
                calibration_json JSON NOT NULL,
                is_locked BOOLEAN NOT NULL DEFAULT TRUE
            );
        """)

    if "finding_records" not in tables:
        con.execute("""
            CREATE TABLE IF NOT EXISTS finding_records (
                finding_fingerprint VARCHAR(64) PRIMARY KEY,
                calibration_id VARCHAR,
                depth INTEGER NOT NULL,
                dimension_slice_json JSON NOT NULL,
                raw_transaction_count BIGINT NOT NULL,
                distinct_account_count BIGINT NOT NULL,
                gross_list_volume DECIMAL(18, 4) NOT NULL,
                unshrunk_gap_dollars DECIMAL(18, 4) NOT NULL,
                shrunk_gap_dollars DECIMAL(18, 4) NOT NULL,
                concentration_ratio DECIMAL(10, 6) NOT NULL,
                bootstrap_stability_score DECIMAL(6, 4) NOT NULL,
                bootstrap_ci_lower DECIMAL(18, 4) NOT NULL,
                bootstrap_ci_upper DECIMAL(18, 4) NOT NULL,
                fdr_p_value DOUBLE NOT NULL,
                fdr_q_value DOUBLE NOT NULL,
                fdr_rejected BOOLEAN NOT NULL,
                unique_incremental_gap DECIMAL(18, 4) NOT NULL,
                lifecycle_status VARCHAR NOT NULL DEFAULT 'New',
                assigned_owner VARCHAR,
                dismissal_category VARCHAR,
                dismissal_snooze_date DATE,
                action_target_recovery DECIMAL(18, 4),
                evidence_tier VARCHAR NOT NULL DEFAULT 'Tier 1',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

    if "finding_transactions_map" not in tables:
        con.execute("""
            CREATE TABLE IF NOT EXISTS finding_transactions_map (
                finding_fingerprint VARCHAR(64) NOT NULL,
                transaction_line_id VARCHAR NOT NULL,
                allocated_defensible_gap DECIMAL(18, 4) NOT NULL,
                PRIMARY KEY (finding_fingerprint, transaction_line_id)
            );
        """)


def _get_or_create_calibration_id(con: duckdb.DuckDBPyConnection) -> str:
    """Retrieves the active calibration profile ID, or registers an auto profile."""
    _ensure_schema_exists(con)
    try:
        row = con.execute(
            "SELECT calibration_id FROM meta_calibration_profiles ORDER BY created_at DESC LIMIT 1;"
        ).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass

    calib_id = "CALIB-AUTO-BASELINE"
    try:
        con.execute("""
            INSERT OR IGNORE INTO meta_calibration_profiles (
                calibration_id, name, historical_start_date, historical_end_date,
                comparability_controls, investigation_dimensions, threshold_strategy,
                calibration_json, is_locked
            ) VALUES (
                'CALIB-AUTO-BASELINE', 'Auto Baseline', CURRENT_DATE, CURRENT_DATE,
                ['product_family', 'sales_region'], ['sales_rep', 'discount_reason'],
                'P75', '{}', TRUE
            );
        """)
    except Exception:
        pass
    return calib_id


# ---------------------------------------------------------------------------
# 6. Core Bounded Beam Search Traversal Engine
# ---------------------------------------------------------------------------

def run_beam_search(
    con: duckdb.DuckDBPyConnection,
    investigation_dims: Optional[List[str]] = None,
    width: int = 3,
    depth: int = 3,
    fdr_q: float = 0.05,
    min_slice_size: int = 5,
    table_name: str = "transactions",
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Executes bounded beam search traversal (width <= 3, depth <= 3) over investigation
    dimensions, applying Empirical Bayes shrinkage, 200-iteration bootstrap stability checks,
    Benjamini-Hochberg FDR control (q < 0.05), and multi-signal priority ranking.

    Persists qualified findings into finding_records and finding_transactions_map.
    Returns list of qualified exception finding dictionaries.
    """
    _ensure_schema_exists(con)
    calib_id = _get_or_create_calibration_id(con)

    # Validate table and columns
    tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
    if table_name not in tables:
        return []

    table_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]
    if "defensible_gap" not in table_cols:
        try:
            temp_tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
            if "_m3_loao_scored" in temp_tables:
                con.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS defensible_gap DECIMAL(18, 4);')
                con.execute(f"""
                    UPDATE {table_name}
                    SET defensible_gap = s.defensible_gap
                    FROM _m3_loao_scored s
                    WHERE {table_name}.transaction_line_id = s.transaction_line_id;
                """)
                table_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]
        except Exception:
            pass

    if "defensible_gap" not in table_cols:
        raise ValueError(
            f"Table '{table_name}' lacks 'defensible_gap' column. "
            "Please execute compute_loao_baselines before running beam search."
        )

    # Dynamic column resolver (direct column vs JSON attribute)
    def col_sql(col_name: str) -> str:
        if col_name in table_cols:
            return f'"{col_name}"'
        elif "dimension_attributes" in table_cols:
            return f"json_extract_string(dimension_attributes, '$.{col_name}')"
        else:
            return f'"{col_name}"'

    # Filter investigation dimensions to those existing in schema or dimension_attributes
    default_dims = ["sales_rep", "discount_reason", "channel"]
    raw_dims = investigation_dims or default_dims
    valid_dims = []
    for d in raw_dims:
        d_clean = d.strip()
        if d_clean in table_cols:
            valid_dims.append(d_clean)
        elif "dimension_attributes" in table_cols:
            try:
                has_attr = con.execute(f"SELECT COUNT(*) FROM {table_name} WHERE json_extract_string(dimension_attributes, '$.{d_clean}') IS NOT NULL AND json_extract_string(dimension_attributes, '$.{d_clean}') != '';").fetchone()[0]
                if has_attr > 0:
                    valid_dims.append(d_clean)
            except Exception:
                pass

    if not valid_dims:
        # Dynamically discover categorical dimension columns from table
        excluded_suffixes = ("_amt", "_pct", "_rate", "_price", "_id", "_date", "_rn", "_val", "_dollars")
        reserved_set = {
            "transaction_line_id", "invoice_id", "account_id", "parent_account_id",
            "transaction_date", "currency", "fx_rate_to_reporting", "extended_list_amt",
            "net_invoiced_amt", "cogs_amt", "off_invoice_rebate", "reporting_list_amt",
            "reporting_invoiced_amt", "reporting_cogs_amt", "reporting_rebate_amt",
            "gross_invoiced_amt", "discount_amt", "realized_discount_rate", "defensible_gap",
            "pocket_margin_amt", "pocket_margin_pct", "is_credit_reversal", "dimension_attributes",
            "_raw_pocket_margin_amt", "_grain_rn"
        }
        candidate_cols = [
            c for c in table_cols
            if c not in reserved_set and not c.startswith("_") and not any(c.lower().endswith(s) for s in excluded_suffixes)
        ]
        valid_dims = candidate_cols[:10]

    if not valid_dims:
        return []

    # Maximum depth bounded by number of dimensions and depth parameter (up to 3)
    max_depth = min(depth, len(valid_dims), 3)

    # 1. Global Parent Population Prior Parameters (computed across table)
    prior_row = con.execute(f"""
        SELECT 
            COALESCE(AVG(defensible_gap), 0.0) AS prior_mean,
            COALESCE(VAR_SAMP(defensible_gap), 0.0) AS prior_var,
            COUNT(transaction_line_id) AS total_count
        FROM {table_name}
        WHERE defensible_gap IS NOT NULL;
    """).fetchone()

    prior_mean = float(prior_row[0] or 0.0)
    prior_var = max(float(prior_row[1] or 0.0), 1e-6)
    total_population_n = max(int(prior_row[2] or 0), 1)

    visited_states: Set[Tuple[Tuple[str, str], ...]] = set()
    covered_tx_ids: Set[str] = set()
    accepted_findings: List[Dict[str, Any]] = []

    # Active beam frontier for expansion
    current_beam: List[Dict[str, Any]] = []

    # =======================================================================
    # DEPTH 1: Single-Dimension Slices
    # =======================================================================
    d1_candidates = []
    for dim in valid_dims:
        sql = f"""
            SELECT 
                CAST({col_sql(dim)} AS VARCHAR) AS val,
                COUNT(transaction_line_id) AS sample_size,
                COUNT(DISTINCT account_id) AS distinct_accounts,
                SUM(extended_list_amt) AS gross_list_volume,
                SUM(defensible_gap) AS raw_total_gap,
                AVG(defensible_gap) AS sample_mean,
                COALESCE(VAR_SAMP(defensible_gap), 0.0) AS sample_var,
                LIST(defensible_gap) AS gap_values,
                LIST(transaction_line_id) AS tx_ids
            FROM {table_name}
            WHERE {col_sql(dim)} IS NOT NULL AND defensible_gap IS NOT NULL
            GROUP BY {col_sql(dim)}
            HAVING COUNT(transaction_line_id) >= {min_slice_size} AND SUM(defensible_gap) > 0;
        """
        rows = con.execute(sql).fetchall()
        for r in rows:
            val_str = str(r[0])
            state_key = ((dim, val_str),)
            if state_key in visited_states:
                continue
            visited_states.add(state_key)

            n = int(r[1])
            sample_mean = float(r[5] or 0.0)
            sample_var = max(float(r[6] or 0.0), 1e-6)
            raw_gap = float(r[4] or 0.0)
            gross_vol = max(float(r[3] or 0.0), 1e-6)
            gap_vals = np.array(r[7], dtype=np.float64)
            tx_ids = [str(tid) for tid in r[8]]

            # EB Shrinkage
            shrunk_mean, shrinkage_lambda, total_shrunk_gap = compute_empirical_bayes_shrinkage(
                sample_mean=sample_mean,
                sample_var=sample_var,
                n=n,
                prior_mean=prior_mean,
                prior_var=prior_var,
            )

            # Wald Z-Test
            z_score, p_val = compute_wald_hypothesis_test(
                sample_mean=sample_mean,
                sample_var=sample_var,
                n=n,
                prior_mean=prior_mean,
                prior_var=prior_var,
                total_population_n=total_population_n,
            )

            # 200-Iteration Bootstrap Check
            boot_res = run_bootstrap_stability_check(
                gaps=gap_vals,
                prior_mean=prior_mean,
                n_boot=200,
                seed=seed,
            )

            d1_candidates.append({
                "dimension_slice": {dim: val_str},
                "depth": 1,
                "sample_size": n,
                "raw_transaction_count": n,
                "distinct_accounts": int(r[2]),
                "distinct_account_count": int(r[2]),
                "gross_list_volume": gross_vol,
                "raw_total_gap": raw_gap,
                "unshrunk_gap_dollars": raw_gap,
                "sample_mean": sample_mean,
                "sample_var": sample_var,
                "shrinkage_lambda": shrinkage_lambda,
                "shrunk_mean": shrunk_mean,
                "shrunk_gap_dollars": total_shrunk_gap,
                "diff_mean": sample_mean - prior_mean,
                "z_score": z_score,
                "p_value": p_val,
                "fdr_p_value": p_val,
                "bootstrap_ci_lower": boot_res["ci_lower"],
                "bootstrap_ci_upper": boot_res["ci_upper"],
                "bootstrap_stability_score": boot_res["stability_score"],
                "is_stable": boot_res["is_stable"],
                "concentration_ratio": raw_gap / gross_vol,
                "tx_ids": tx_ids,
                "transaction_ids": tx_ids,
                "gap_values": gap_vals.tolist(),
            })

    if d1_candidates:
        # Multiple testing correction
        d1_candidates = apply_benjamini_hochberg_fdr(d1_candidates, fdr_q=fdr_q)
        # Multi-signal priority scoring
        d1_candidates = rank_candidates_by_priority_vector(d1_candidates, covered_tx_ids)

        # Beam selection: top 'width' candidates
        current_beam = d1_candidates[:width]
        for cand in current_beam:
            if cand.get("is_exception_finding", False):
                accepted_findings.append(cand)
                covered_tx_ids.update(cand["tx_ids"])

    # =======================================================================
    # DEPTH 2 & DEPTH 3 Traversal
    # =======================================================================
    for curr_depth in range(2, max_depth + 1):
        if not current_beam:
            break

        next_candidates = []
        for parent in current_beam:
            parent_slice = parent["dimension_slice"]
            parent_dims = set(parent_slice.keys())
            unused_dims = [d for d in valid_dims if d not in parent_dims]
            if not unused_dims:
                continue

            where_clauses = []
            for k, v in parent_slice.items():
                escaped_v = str(v).replace("'", "''")
                where_clauses.append(f"{col_sql(k)} = '{escaped_v}'")
            where_sql = " AND ".join(where_clauses)

            for child_dim in unused_dims:
                sql = f"""
                    SELECT 
                        CAST({col_sql(child_dim)} AS VARCHAR) AS val,
                        COUNT(transaction_line_id) AS sample_size,
                        COUNT(DISTINCT account_id) AS distinct_accounts,
                        SUM(extended_list_amt) AS gross_list_volume,
                        SUM(defensible_gap) AS raw_total_gap,
                        AVG(defensible_gap) AS sample_mean,
                        COALESCE(VAR_SAMP(defensible_gap), 0.0) AS sample_var,
                        LIST(defensible_gap) AS gap_values,
                        LIST(transaction_line_id) AS tx_ids
                    FROM {table_name}
                    WHERE {where_sql} AND {col_sql(child_dim)} IS NOT NULL AND defensible_gap IS NOT NULL
                    GROUP BY {col_sql(child_dim)}
                    HAVING COUNT(transaction_line_id) >= {min_slice_size} AND SUM(defensible_gap) > 0;
                """
                rows = con.execute(sql).fetchall()
                for r in rows:
                    val_str = str(r[0])
                    new_slice = dict(parent_slice)
                    new_slice[child_dim] = val_str
                    state_key = tuple(sorted([(k, str(v)) for k, v in new_slice.items()]))
                    if state_key in visited_states:
                        continue
                    visited_states.add(state_key)

                    n = int(r[1])
                    sample_mean = float(r[5] or 0.0)
                    sample_var = max(float(r[6] or 0.0), 1e-6)
                    raw_gap = float(r[4] or 0.0)
                    gross_vol = max(float(r[3] or 0.0), 1e-6)
                    gap_vals = np.array(r[7], dtype=np.float64)
                    tx_ids = [str(tid) for tid in r[8]]

                    # EB Shrinkage
                    shrunk_mean, shrinkage_lambda, total_shrunk_gap = compute_empirical_bayes_shrinkage(
                        sample_mean=sample_mean,
                        sample_var=sample_var,
                        n=n,
                        prior_mean=prior_mean,
                        prior_var=prior_var,
                    )

                    # Wald Z-Test
                    z_score, p_val = compute_wald_hypothesis_test(
                        sample_mean=sample_mean,
                        sample_var=sample_var,
                        n=n,
                        prior_mean=prior_mean,
                        prior_var=prior_var,
                        total_population_n=total_population_n,
                    )

                    # 200-Iteration Bootstrap Check
                    boot_res = run_bootstrap_stability_check(
                        gaps=gap_vals,
                        prior_mean=prior_mean,
                        n_boot=200,
                        seed=seed + curr_depth,
                    )

                    next_candidates.append({
                        "dimension_slice": new_slice,
                        "depth": curr_depth,
                        "sample_size": n,
                        "raw_transaction_count": n,
                        "distinct_accounts": int(r[2]),
                        "distinct_account_count": int(r[2]),
                        "gross_list_volume": gross_vol,
                        "raw_total_gap": raw_gap,
                        "unshrunk_gap_dollars": raw_gap,
                        "sample_mean": sample_mean,
                        "sample_var": sample_var,
                        "shrinkage_lambda": shrinkage_lambda,
                        "shrunk_mean": shrunk_mean,
                        "shrunk_gap_dollars": total_shrunk_gap,
                        "diff_mean": sample_mean - prior_mean,
                        "z_score": z_score,
                        "p_value": p_val,
                        "fdr_p_value": p_val,
                        "bootstrap_ci_lower": boot_res["ci_lower"],
                        "bootstrap_ci_upper": boot_res["ci_upper"],
                        "bootstrap_stability_score": boot_res["stability_score"],
                        "is_stable": boot_res["is_stable"],
                        "concentration_ratio": raw_gap / gross_vol,
                        "tx_ids": tx_ids,
                        "transaction_ids": tx_ids,
                        "gap_values": gap_vals.tolist(),
                    })

        if not next_candidates:
            break

        next_candidates = apply_benjamini_hochberg_fdr(next_candidates, fdr_q=fdr_q)
        next_candidates = rank_candidates_by_priority_vector(next_candidates, covered_tx_ids)

        current_beam = next_candidates[:width]
        for cand in current_beam:
            if cand.get("is_exception_finding", False):
                accepted_findings.append(cand)
                covered_tx_ids.update(cand["tx_ids"])

    # =======================================================================
    # Deduplicate & Prune Strict Transaction Duplicates
    # =======================================================================
    # If a deeper finding covers the exact same transactions as a shallower finding,
    # keep the deeper (more diagnostic) finding to avoid duplicate presentations.
    final_findings: List[Dict[str, Any]] = []
    # Sort by depth descending so deeper findings are evaluated first
    sorted_accepted = sorted(accepted_findings, key=lambda f: f["depth"], reverse=True)
    seen_tx_sets: List[Set[str]] = []

    for f in sorted_accepted:
        tx_set = set(f["tx_ids"])
        # Check if identical tx_set already added by a deeper finding
        is_exact_dup = any(tx_set == prev_set for prev_set in seen_tx_sets)
        if not is_exact_dup:
            seen_tx_sets.append(tx_set)
            final_findings.append(f)

    # Sort final findings by priority score descending
    final_findings.sort(key=lambda f: f.get("priority_score", 0.0), reverse=True)

    # Generate fingerprints and enrich dictionary
    for f in final_findings:
        fp = compute_finding_fingerprint(f["dimension_slice"], calib_id=calib_id)
        f["finding_fingerprint"] = fp
        f["id"] = fp[:16]
        f["sha256"] = fp
        title_parts = [f"{k}: {v}" for k, v in f["dimension_slice"].items()]
        f["title"] = " & ".join(title_parts)
        f["defensibleGap"] = round(f["unshrunk_gap_dollars"], 2)
        f["actionableOpportunity"] = round(f["shrunk_gap_dollars"] * 0.40, 2)
        f["transactionCount"] = f["raw_transaction_count"]
        f["concentrationRatio"] = round(f["concentration_ratio"], 4)
        f["bootstrapStable"] = f["is_stable"]
        f["priorityScore"] = f["priority_score"]
        f["fdrQ"] = f.get("fdr_q_value", f["p_value"])
        f["status"] = "New"
        f["lifecycle_status"] = "New"

    # Persist to database
    record_findings_to_db(
        con=con,
        findings=final_findings,
        calibration_id=calib_id,
        table_name=table_name,
    )

    return final_findings
