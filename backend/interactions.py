"""
backend/interactions.py
Milestone 5 (M5.1): Interaction Detection, Compound Stacking, Contractual Cap Evaluation & Programmatic Tone Guard.

Implements:
1. ToneGuard programmatic enforcement strictly blocking 'Policy Violation' in statistical mode,
   and enforcing the mandatory canonical label for anomalous joint concessions.
2. Tier 3 rule-based compound concession stacking audits against contractual caps
   (Additive vs Multiplicative stacking models).
3. Statistical exploratory pairwise interaction testing:
   r_hat_AB = r_A + r_B - r_global
   I_rate = r_AB - r_hat_AB
   Wald Z-score, sample variances, one-tailed p-values, and Benjamini-Hochberg FDR control.
"""

import math
import re
import json
from typing import Optional, Dict, Any, List, Union
import duckdb


# ===========================================================================
# 1. Programmatic Tone Guard (R5.3)
# ===========================================================================

class ToneGuardViolationError(ValueError):
    """Raised when a blacklisted punitive phrase is attempted in statistical exploratory mode."""
    pass


class ToneGuard:
    """
    Tone Guard Programmatic Enforcer (R5.3).
    Enforces approved commercial auditing taxonomy and strictly blocks punitive terminology
    such as 'Policy Violation', 'Unauthorized Deal', etc. in statistical exploratory mode.
    """

    FORBIDDEN_TERMS = [
        "policy violation",
        "policy_violation",
        "policy-violation",
        "policyviolation",
        "unapproved concession",
        "unauthorized deal",
        "breach of policy",
        "off-policy deal",
        "off policy deal",
    ]

    MANDATORY_INTERACTION_LABEL = (
        "Anomalous Joint Concession: Pairwise combination exhibits a larger-than-expected concession gap. Review contract terms."
    )

    @classmethod
    def is_safe(cls, text: str, mode: str = "statistical") -> bool:
        """Checks if text contains any forbidden punitive phrases in statistical mode."""
        if mode.lower() != "statistical":
            return True
        if not text:
            return True
        
        low = text.lower()
        norm_space = re.sub(r"[\s_\-]+", " ", low).strip()
        norm_dense = re.sub(r"[^a-z0-9]", "", low)

        for term in cls.FORBIDDEN_TERMS:
            term_norm = re.sub(r"[\s_\-]+", " ", term.lower()).strip()
            term_dense = re.sub(r"[^a-z0-9]", "", term.lower())
            if term_norm in norm_space or term_dense in norm_dense:
                return False
        return True

    @classmethod
    def validate(cls, text: str, mode: str = "statistical") -> None:
        """
        Validates text against Tone Guard rules.
        Raises ToneGuardViolationError if a forbidden punitive term is found in statistical mode.
        """
        if not cls.is_safe(text, mode=mode):
            raise ToneGuardViolationError(
                f"ToneGuard Violation: Punitive phrase detected in text '{text}' under mode '{mode}'. "
                "The term 'Policy Violation' and related punitive codes are programmatically barred in statistical exploratory mode. "
                f"Mandatory approved label: '{cls.MANDATORY_INTERACTION_LABEL}'"
            )

    @classmethod
    def sanitize(cls, text: str, mode: str = "statistical") -> str:
        """
        Replaces forbidden punitive phrases with approved commercial taxonomy.
        """
        if mode.lower() != "statistical" or not text:
            return text

        replacements = [
            (r"(?i)\bpolicy[_\s\-]*violation\b", "Statistical Interaction Anomaly"),
            (r"(?i)\bunapproved[_\s\-]*concession\b", "Anomalous Joint Concession"),
            (r"(?i)\bunauthorized[_\s\-]*deal\b", "Commercial Review Required"),
            (r"(?i)\bbreach[_\s\-]*of[_\s\-]*policy\b", "Statistical Variance Departure"),
            (r"(?i)\boff[_\s\-]*policy[_\s\-]*deal\b", "Anomalous Concession Pattern"),
        ]

        sanitized = text
        for pat, repl in replacements:
            sanitized = re.sub(pat, repl, sanitized)
        return sanitized

    @classmethod
    def get_interaction_label(cls, is_significant: bool, i_rate: float) -> str:
        """
        Returns the mandatory canonical commercial label for an interaction result.
        """
        if is_significant and i_rate > 0:
            return cls.MANDATORY_INTERACTION_LABEL
        elif i_rate > 0:
            return "Positive Interaction Trend: Pairwise combination exhibits higher concession than independent expectation, but does not meet significance fence."
        elif i_rate < 0:
            return "Sub-additive Concession: Pairwise combination receives lower concessions than expected."
        else:
            return "Additive Concession: Pairwise combination is within expected baseline variance."


# ===========================================================================
# 2. Tier 3 Rule-Based Compound Concession Stacking (R5.1)
# ===========================================================================

def evaluate_contractual_cap_stacking(
    con: duckdb.DuckDBPyConnection,
    cap_rate: float,
    stacking_mode: str = "additive",
    group_by: Optional[List[str]] = None,
    table_name: str = "transactions",
) -> Dict[str, Any]:
    """
    Evaluates Tier 3 rule-based compound concession stacking against a contractual cap.

    Supports:
      - 'additive': r_compound = r_inv + r_reb
      - 'multiplicative': r_compound = 1 - (1 - r_inv) * (1 - r_reb)

    Mathematical invariant:
      For positive concession rates, r_compound(additive) >= r_compound(multiplicative).

    Transactions exceeding cap_rate are classified as Tier 3 'Rule-Confirmed Exception'.
    """
    norm_mode = stacking_mode.strip().lower()
    if norm_mode not in ("additive", "multiplicative"):
        raise ValueError(f"Unknown stacking mode '{stacking_mode}'. Must be 'additive' or 'multiplicative'.")

    table_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]

    rebate_col_expr = (
        "COALESCE(reporting_rebate_amt, off_invoice_rebate * COALESCE(fx_rate_to_reporting, 1.0), 0.0)"
        if "reporting_rebate_amt" in table_cols
        else (
            "COALESCE(off_invoice_rebate * COALESCE(fx_rate_to_reporting, 1.0), 0.0)"
            if "off_invoice_rebate" in table_cols
            else "0.0"
        )
    )

    is_credit_expr = "is_credit_reversal = FALSE" if "is_credit_reversal" in table_cols else "1=1"

    # Compound rate calculation in SQL
    if norm_mode == "additive":
        compound_rate_sql = f"""
            (
                CASE WHEN extended_list_amt > 0 THEN 
                    (extended_list_amt - net_invoiced_amt) / extended_list_amt 
                ELSE 0.0 END
                +
                CASE WHEN extended_list_amt > 0 THEN 
                    ({rebate_col_expr}) / extended_list_amt 
                ELSE 0.0 END
            )
        """
    else:  # multiplicative
        compound_rate_sql = f"""
            (
                1.0 - (
                    (1.0 - CASE WHEN extended_list_amt > 0 THEN 
                        (extended_list_amt - net_invoiced_amt) / extended_list_amt 
                    ELSE 0.0 END)
                    *
                    (1.0 - CASE WHEN extended_list_amt > 0 THEN 
                        ({rebate_col_expr}) / extended_list_amt 
                    ELSE 0.0 END)
                )
            )
        """

    query = f"""
        WITH calculated AS (
            SELECT
                transaction_line_id,
                account_id,
                extended_list_amt,
                net_invoiced_amt,
                {rebate_col_expr} AS rebate_amt,
                CASE WHEN extended_list_amt > 0 THEN 
                    (extended_list_amt - net_invoiced_amt) / extended_list_amt 
                ELSE 0.0 END AS on_invoice_discount_rate,
                CASE WHEN extended_list_amt > 0 THEN 
                    ({rebate_col_expr}) / extended_list_amt 
                ELSE 0.0 END AS off_invoice_rebate_rate,
                {compound_rate_sql} AS compound_rate
            FROM {table_name}
            WHERE {is_credit_expr} AND extended_list_amt > 0
        )
        SELECT
            transaction_line_id,
            account_id,
            extended_list_amt,
            net_invoiced_amt,
            rebate_amt,
            on_invoice_discount_rate,
            off_invoice_rebate_rate,
            compound_rate,
            GREATEST(0.0, compound_rate - {float(cap_rate)}) AS excess_rate,
            GREATEST(0.0, compound_rate - {float(cap_rate)}) * extended_list_amt AS breach_exposure,
            CASE WHEN compound_rate > {float(cap_rate)} THEN TRUE ELSE FALSE END AS is_breach
        FROM calculated;
    """

    rows = con.execute(query).fetchall()

    total_evaluated = len(rows)
    breached_records = []
    total_breach_exposure = 0.0
    total_list_volume = 0.0

    for r in rows:
        (
            tx_id,
            acct_id,
            list_amt,
            net_amt,
            reb_amt,
            inv_rate,
            reb_rate,
            comp_rate,
            excess_rate,
            exposure,
            is_breach,
        ) = r
        total_list_volume += float(list_amt)

        if is_breach:
            total_breach_exposure += float(exposure)
            breached_records.append({
                "transaction_line_id": str(tx_id),
                "account_id": str(acct_id),
                "extended_list_amt": round(float(list_amt), 4),
                "net_invoiced_amt": round(float(net_amt), 4),
                "off_invoice_rebate": round(float(reb_amt), 4),
                "on_invoice_discount_rate": round(float(inv_rate), 6),
                "off_invoice_rebate_rate": round(float(reb_rate), 6),
                "compound_concession_rate": round(float(comp_rate), 6),
                "contract_cap": float(cap_rate),
                "excess_rate": round(float(excess_rate), 6),
                "breach_exposure_dollars": round(float(exposure), 4),
                "evidence_tier": "Tier 3",
                "classification": "Rule-Confirmed Exception",
                "governance_status": "Contractual Cap Breach",
                "stacking_mode": norm_mode,
            })

    breach_count = len(breached_records)
    breach_rate = (breach_count / total_evaluated) if total_evaluated > 0 else 0.0

    return {
        "status": "success",
        "stacking_mode": norm_mode,
        "contract_cap": float(cap_rate),
        "total_evaluated_transactions": total_evaluated,
        "total_list_volume": round(total_list_volume, 2),
        "breach_count": breach_count,
        "breach_rate": round(breach_rate, 4),
        "total_breached_exposure": round(total_breach_exposure, 2),
        "evidence_tier": "Tier 3",
        "classification": "Rule-Confirmed Exception",
        "breached_records": breached_records,
    }


# ===========================================================================
# 3. Statistical Exploratory Pairwise Interaction Analysis (R5.2)
# ===========================================================================

def evaluate_interactions(
    con: duckdb.DuckDBPyConnection,
    dim_a: str,
    dim_b: str,
    min_support_tx: int = 5,
    min_support_accts: int = 3,
    fdr_q: float = 0.05,
    mode: str = "statistical",
    table_name: str = "transactions",
) -> List[Dict[str, Any]]:
    """
    Evaluates statistical exploratory pairwise interaction between two dimensions.

    Formulation:
      r_hat_AB = r_A + r_B - r_global
      I_rate = r_AB - r_hat_AB = r_AB - r_A - r_B + r_global

    Hypothesis Testing:
      SE = sqrt( s_AB^2 / n_AB + s_A^2 / n_A + s_B^2 / n_B + s_global^2 / N )
      Z = I_rate / SE
      p = 0.5 * erfc(Z / sqrt(2)) (one-tailed super-additive test)
      Benjamini-Hochberg FDR control (q < 0.05).

    Tone Guard Enforcement:
      Programmatically blocks the term 'Policy Violation' in statistical mode.
      Enforces mandatory label when I_rate > 0 and statistically significant.
    """
    table_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]

    def col_sql(col_name: str) -> str:
        col_clean = col_name.strip()
        if col_clean in table_cols:
            return f'"{col_clean}"'
        elif "dimension_attributes" in table_cols:
            return f"json_extract_string(dimension_attributes, '$.{col_clean}')"
        else:
            return f'"{col_clean}"'

    col_a_sql = col_sql(dim_a)
    col_b_sql = col_sql(dim_b)

    is_credit_expr = "is_credit_reversal = FALSE" if "is_credit_reversal" in table_cols else "1=1"

    # Rate column resolver
    rate_expr = (
        "realized_discount_rate"
        if "realized_discount_rate" in table_cols
        else "CASE WHEN extended_list_amt > 0 THEN (extended_list_amt - net_invoiced_amt) / extended_list_amt ELSE 0.0 END"
    )

    # 1. Global Metrics
    global_row = con.execute(f"""
        SELECT 
            COALESCE(AVG({rate_expr}), 0.0) AS global_mean,
            COALESCE(VAR_SAMP({rate_expr}), 0.0) AS global_var,
            COUNT(*) AS global_n
        FROM {table_name}
        WHERE {is_credit_expr} AND extended_list_amt > 0 AND {rate_expr} IS NOT NULL;
    """).fetchone()

    if not global_row or global_row[2] == 0:
        return []

    global_mean = float(global_row[0] or 0.0)
    global_var = float(global_row[1] or 0.0)
    global_n = int(global_row[2] or 0)

    # 2. Marginal Metrics for dim_a
    sql_a = f"""
        SELECT 
            CAST({col_a_sql} AS VARCHAR) AS val_a,
            COALESCE(AVG({rate_expr}), 0.0) AS mean_a,
            COALESCE(VAR_SAMP({rate_expr}), 0.0) AS var_a,
            COUNT(*) AS n_a
        FROM {table_name}
        WHERE {is_credit_expr} AND extended_list_amt > 0 AND {col_a_sql} IS NOT NULL
        GROUP BY 1;
    """
    marginal_a = {
        row[0]: {"mean": float(row[1] or 0.0), "var": float(row[2] or 0.0), "n": int(row[3])}
        for row in con.execute(sql_a).fetchall()
        if row[0] is not None
    }

    # 3. Marginal Metrics for dim_b
    sql_b = f"""
        SELECT 
            CAST({col_b_sql} AS VARCHAR) AS val_b,
            COALESCE(AVG({rate_expr}), 0.0) AS mean_b,
            COALESCE(VAR_SAMP({rate_expr}), 0.0) AS var_b,
            COUNT(*) AS n_b
        FROM {table_name}
        WHERE {is_credit_expr} AND extended_list_amt > 0 AND {col_b_sql} IS NOT NULL
        GROUP BY 1;
    """
    marginal_b = {
        row[0]: {"mean": float(row[1] or 0.0), "var": float(row[2] or 0.0), "n": int(row[3])}
        for row in con.execute(sql_b).fetchall()
        if row[0] is not None
    }

    # 4. Joint Cell Metrics
    sql_cells = f"""
        SELECT 
            CAST({col_a_sql} AS VARCHAR) AS val_a,
            CAST({col_b_sql} AS VARCHAR) AS val_b,
            COUNT(*) AS cell_n,
            COUNT(DISTINCT account_id) AS cell_accts,
            COALESCE(SUM(extended_list_amt), 0.0) AS cell_list_vol,
            COALESCE(SUM(net_invoiced_amt), 0.0) AS cell_net_vol,
            COALESCE(AVG({rate_expr}), 0.0) AS observed_rate,
            COALESCE(VAR_SAMP({rate_expr}), 0.0) AS cell_var
        FROM {table_name}
        WHERE {is_credit_expr} AND extended_list_amt > 0 
          AND {col_a_sql} IS NOT NULL AND {col_b_sql} IS NOT NULL
        GROUP BY 1, 2;
    """
    cell_rows = con.execute(sql_cells).fetchall()

    candidate_records = []
    unsupported_records = []

    for r in cell_rows:
        val_a, val_b, cell_n, cell_accts, list_vol, net_vol, obs_rate, cell_var = r
        if val_a is None or val_b is None:
            continue

        meta_a = marginal_a.get(val_a, {"mean": global_mean, "var": global_var, "n": 1})
        meta_b = marginal_b.get(val_b, {"mean": global_mean, "var": global_var, "n": 1})

        mean_a = meta_a["mean"]
        var_a = meta_a["var"]
        n_a = meta_a["n"]

        mean_b = meta_b["mean"]
        var_b = meta_b["var"]
        n_b = meta_b["n"]

        expected_rate = mean_a + mean_b - global_mean
        i_rate = obs_rate - expected_rate

        # Support check
        has_support = (cell_n >= min_support_tx) and (cell_accts >= min_support_accts)

        # Standard error of estimator
        safe_cell_var = max(float(cell_var or 0.0), 1e-6)
        safe_var_a = max(var_a, 1e-6)
        safe_var_b = max(var_b, 1e-6)
        safe_global_var = max(global_var, 1e-6)

        se = math.sqrt(
            (safe_cell_var / max(cell_n, 1))
            + (safe_var_a / max(n_a, 1))
            + (safe_var_b / max(n_b, 1))
            + (safe_global_var / max(global_n, 1))
        )
        se = max(se, 1e-6)

        z_score = i_rate / se

        # One-tailed p-value for super-additive excess (I_rate > 0)
        p_value = 0.5 * math.erfc(z_score / math.sqrt(2.0))
        p_value = max(0.0, min(1.0, p_value))

        dollar_gap = max(0.0, i_rate) * float(list_vol)

        record = {
            "interaction_id": f"INT-{dim_a}_{val_a}-{dim_b}_{val_b}".replace(" ", "_"),
            "dim_a": dim_a,
            "val_a": val_a,
            "dim_b": dim_b,
            "val_b": val_b,
            "cell_count": int(cell_n),
            "distinct_accounts": int(cell_accts),
            "gross_list_volume": round(float(list_vol), 2),
            "net_invoiced_volume": round(float(net_vol), 2),
            "observed_rate": round(float(obs_rate), 6),
            "marginal_rate_a": round(float(mean_a), 6),
            "marginal_rate_b": round(float(mean_b), 6),
            "global_rate": round(float(global_mean), 6),
            "expected_rate": round(float(expected_rate), 6),
            "interaction_rate": round(float(i_rate), 6),
            "interaction_dollar_gap": round(float(dollar_gap), 2),
            "standard_error": round(float(se), 6),
            "z_score": round(float(z_score), 4),
            "p_value": round(float(p_value), 6),
            "has_support": has_support,
            "evidence_tier": "Tier 1",
            "tone_guard_status": "PASSED",
        }

        if has_support:
            candidate_records.append(record)
        else:
            record["is_significant"] = False
            record["fdr_q_value"] = 1.0
            record["label"] = "Insufficient Support: Cell sample size or distinct accounts below threshold."
            unsupported_records.append(record)

    # 5. Benjamini-Hochberg FDR Control on supported candidates
    if candidate_records:
        candidate_records.sort(key=lambda x: x["p_value"])
        m = len(candidate_records)
        raw_adj = []
        for rank, cand in enumerate(candidate_records, start=1):
            crit = (rank / m) * fdr_q
            adj_p = min(1.0, cand["p_value"] * (m / rank))
            raw_adj.append(adj_p)

        # Monotonicity adjustment from right to left
        cum_min = 1.0
        q_vals = [1.0] * m
        for i in range(m - 1, -1, -1):
            cum_min = min(cum_min, raw_adj[i])
            q_vals[i] = cum_min

        for i, cand in enumerate(candidate_records):
            q_val = q_vals[i]
            cand["fdr_q_value"] = round(q_val, 6)
            is_sig = bool((q_val <= fdr_q) and (cand["z_score"] > 0) and (cand["interaction_rate"] > 0))
            cand["is_significant"] = is_sig
            cand["label"] = ToneGuard.get_interaction_label(is_sig, cand["interaction_rate"])

    # Combine candidates and sort descending by interaction dollar gap, then z-score
    all_results = candidate_records + unsupported_records
    all_results.sort(key=lambda x: (x["interaction_dollar_gap"], x["z_score"]), reverse=True)

    # Strict ToneGuard validation across all output records in statistical mode
    for rec in all_results:
        ToneGuard.validate(rec["label"], mode=mode)
        # Verify no punitive substrings exist in any field
        assert ToneGuard.is_safe(json.dumps(rec), mode=mode), "ToneGuard invariant violated in output record"

    return all_results
