"""
Sift Leave-One-Account-Out (LOAO) Calibration & Defensible Gap Scoring (Milestone 3)

Authoritative Features:
- R3.1: Three-Column Comparability Attribute Classification (Controls, Investigation Dims, Excluded).
- R3.2: Realized Discount Rate Formulation.
- R3.3: Vectorized Leave-One-Account-Out (LOAO) Peer Cohort Isolation (\\Omega_{-A(i)}).
- R3.4: Cohort Support Fences (N >= 10, Distinct Accounts >= 5).
- R3.5: Hierarchical Back-Off Algorithm across granular-to-parent cohort tiers.
- R3.6: Insufficient Comparable Evidence Flagging & Zero-Scoring Exclusion.
- R3.7: Benchmark Boundary Thresholds (P75 vs Median + 1.5 * MAD).
- R3.8: Defensible Gap, Baseline Band Gap, and Actionable Opportunity (kappa).
- R3.9: Versioned .calib.json Calibration Profiles & Historical Snapshot Freezing.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import duckdb
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants & Defaults
# ---------------------------------------------------------------------------

DEFAULT_CONTROLS = ["product_family", "sales_region"]
DEFAULT_INVESTIGATION_DIMS = ["sales_rep", "discount_reason", "channel"]
DEFAULT_EXCLUDED_ATTRS = [
    "transaction_line_id",
    "invoice_id",
    "account_id",
    "parent_account_id",
    "transaction_date",
    "currency",
    "fx_rate_to_reporting",
    "cogs_amt",
    "off_invoice_rebate",
    "comments",
    "text_comments",
    "notes",
    "description",
]

SUPPORT_MIN_TRANSACTIONS = 10
SUPPORT_MIN_ACCOUNTS = 5
DEFAULT_KAPPA = 0.40
DEFAULT_MAD_MULTIPLIER = 1.5
DEFAULT_THRESHOLD_METHOD = "P75"

STATUS_DEFENSIBLE = "Defensible Baseline"
STATUS_INSUFFICIENT = "Insufficient Comparable Evidence"

BASELINE_METRIC_COLUMNS = {
    "p75_concession",
    "median_concession",
    "mad_concession",
    "threshold_concession",
    "peer_count",
    "peer_accounts",
    "support_status",
    "has_comparable_evidence",
    "backoff_tier",
    "defensible_gap",
    "band_gap",
    "actionable_opportunity",
}


# ---------------------------------------------------------------------------
# R3.1: Three-Column Comparability Attribute Classification
# ---------------------------------------------------------------------------

def validate_three_column_classification(
    controls: Sequence[str],
    investigation_dims: Optional[Sequence[str]] = None,
    excluded_attrs: Optional[Sequence[str]] = None,
) -> None:
    """
    Validates three-column attribute classification boundaries:
    1. Comparability Controls (justifiable price drivers like product_family, sales_region).
    2. Investigation Dimensions (audited attributes strictly barred from comparability controls).
    3. Excluded Attributes (line IDs, invoice numbers, dates, free text, account grain).

    Invariants Enforced:
    - Controls cannot be empty.
    - Controls and Investigation Dimensions must be strictly disjoint.
    - Excluded Attributes cannot appear in Controls or Investigation Dimensions.
    - 'account_id' is the LOAO partitioning grain and can never be a control or investigation dimension.
    """
    if not controls:
        raise ValueError("Comparability controls list cannot be empty.")

    ctrl_set = {c.strip() for c in controls if c and c.strip()}
    inv_set = {d.strip() for d in (investigation_dims or []) if d and d.strip()}
    excl_set = {e.strip() for e in (excluded_attrs or DEFAULT_EXCLUDED_ATTRS) if e and e.strip()}

    # Always ensure core identity keys are excluded
    excl_set.update({"account_id", "transaction_line_id", "invoice_id"})

    # Check mutual exclusivity between Controls and Investigation Dimensions
    ctrl_inv_overlap = ctrl_set.intersection(inv_set)
    if ctrl_inv_overlap:
        raise ValueError(
            f"Classification boundary violation: Attribute(s) {sorted(list(ctrl_inv_overlap))} "
            "cannot be both Comparability Controls and Investigation Dimensions. "
            "Audited attributes must be strictly barred from comparability controls."
        )

    # Check controls overlap with excluded
    ctrl_excl_overlap = ctrl_set.intersection(excl_set)
    if ctrl_excl_overlap:
        raise ValueError(
            f"Classification boundary violation: Excluded attribute(s) {sorted(list(ctrl_excl_overlap))} "
            "cannot be used as Comparability Controls."
        )

    # Check investigation dimensions overlap with excluded
    inv_excl_overlap = inv_set.intersection(excl_set)
    if inv_excl_overlap:
        raise ValueError(
            f"Classification boundary violation: Excluded attribute(s) {sorted(list(inv_excl_overlap))} "
            "cannot be used as Investigation Dimensions."
        )


def classify_attributes(columns: Sequence[str]) -> Dict[str, List[str]]:
    """
    Categorizes input columns into default Three-Column Comparability sets:
    - controls: price drivers (e.g. product_family, sales_region, industry)
    - investigation_dimensions: target audited slices (e.g. sales_rep, discount_reason, channel)
    - excluded: identifier keys, timestamps, financial totals, text
    """
    ctrls = []
    invs = []
    excls = []

    ctrl_patterns = {"product_family", "family", "region", "sales_region", "industry", "segment", "geo", "tier"}
    inv_patterns = {"sales_rep", "rep", "discount_reason", "reason", "channel", "approver", "desk"}
    excl_patterns = {
        "transaction_line_id", "id", "line_id", "invoice_id", "account_id", "parent_account_id",
        "date", "transaction_date", "currency", "fx_rate", "extended_list_amt", "net_invoiced_amt",
        "cogs_amt", "rebate", "comment", "note", "desc"
    }

    for col in columns:
        col_lower = col.lower().strip()
        if col_lower in excl_patterns or any(p in col_lower for p in ["_id", "date", "amt", "rate", "currency"]):
            excls.append(col)
        elif col_lower in ctrl_patterns or any(p in col_lower for p in ["family", "region", "geo", "industry"]):
            ctrls.append(col)
        elif col_lower in inv_patterns or any(p in col_lower for p in ["rep", "reason", "channel"]):
            invs.append(col)
        else:
            # Default unclassified dimension attributes to investigation dimensions
            invs.append(col)

    return {
        "controls": ctrls,
        "investigation_dimensions": invs,
        "excluded": excls,
    }


# ---------------------------------------------------------------------------
# R3.2: Realized Discount Rate Formulation
# ---------------------------------------------------------------------------

def calculate_realized_discount_rate(extended_list_amt: float, net_invoiced_amt: float) -> float:
    """
    Computes realized discount rate:
      r_i = (extended_list_amt - net_invoiced_amt) / extended_list_amt
    Handles zero and negative list prices safely by returning 0.0.
    """
    if extended_list_amt is None or extended_list_amt <= 0.0:
        return 0.0
    if net_invoiced_amt is None:
        return 0.0
    rate = (float(extended_list_amt) - float(net_invoiced_amt)) / float(extended_list_amt)
    return round(rate, 6)


# ---------------------------------------------------------------------------
# LOAOResult Container: Dual Dict & DataFrame Compatibility
# ---------------------------------------------------------------------------

class LOAOResult(dict):
    """
    Result container for compute_loao_baselines.
    Implements dict for summary statistics and FastAPI JSON serialization,
    while proxying DataFrame attribute and column indexing for seamless dataframe usage.
    """

    def __init__(self, summary: Dict[str, Any], df: pd.DataFrame):
        super().__init__(summary)
        self["df"] = df
        self._df = df

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    @property
    def columns(self):
        return self._df.columns

    @property
    def iloc(self):
        return self._df.iloc

    @property
    def loc(self):
        return self._df.loc

    @property
    def empty(self) -> bool:
        return self._df.empty

    def __len__(self) -> int:
        return len(self._df) if self._df is not None else 0

    def __getitem__(self, key: str) -> Any:
        if super().__contains__(key):
            return super().__getitem__(key)
        if self._df is not None and key in self._df.columns:
            return self._df[key]
        raise KeyError(f"Key or column '{key}' not found in LOAOResult or DataFrame.")

    def to_df(self) -> pd.DataFrame:
        return self._df

    def to_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable summary dictionary without the raw DataFrame."""
        return {k: v for k, v in self.items() if k != "df"}


# ---------------------------------------------------------------------------
# Vectorized LOAO Engine with Hierarchical Back-Off
# ---------------------------------------------------------------------------

def _get_table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> List[str]:
    """Inspects table columns in DuckDB."""
    try:
        col_rows = con.execute(f"PRAGMA table_info('{table_name}');").fetchall()
        return [r[1] for r in col_rows]
    except Exception:
        return []


def _resolve_control_expression(con: duckdb.DuckDBPyConnection, table_name: str, control: str) -> str:
    """
    Returns SQL column reference. If column is directly in table, returns '"col"'.
    If column is inside dimension_attributes JSON, returns 'json_extract_string("dimension_attributes", '$.col')'.
    """
    cols = _get_table_columns(con, table_name)
    if control in cols:
        return f'"{control}"'
    if "dimension_attributes" in cols:
        return f"json_extract_string(dimension_attributes, '$.{control}')"
    # Default to direct column reference
    return f'"{control}"'


def build_hierarchical_loao_sql(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "transactions",
    controls: Optional[List[str]] = None,
    threshold_method: str = "P75",
    kappa: float = DEFAULT_KAPPA,
    mad_multiplier: float = DEFAULT_MAD_MULTIPLIER,
    min_transactions: int = SUPPORT_MIN_TRANSACTIONS,
    min_distinct_accounts: int = SUPPORT_MIN_ACCOUNTS,
) -> Tuple[str, List[List[str]]]:
    """
    Constructs the fully vectorized multi-tier hierarchical LOAO DuckDB query.
    Generates CTEs for Tier 0 (exact controls) down to Tier M (global cohort).
    """
    norm_controls = [c.strip() for c in (controls or DEFAULT_CONTROLS) if c and c.strip()]
    validate_three_column_classification(norm_controls)

    method = threshold_method.upper().strip()
    if method not in {"P75", "MAD"}:
        raise ValueError(f"Invalid threshold_method '{threshold_method}'. Supported methods: 'P75', 'MAD'.")

    # Generate hierarchy of tiers:
    # Tier 0: full controls
    # Tier 1: controls[:-1]
    # ...
    # Tier M: [] (global cohort)
    tiers: List[List[str]] = []
    for i in range(len(norm_controls) + 1):
        tiers.append(norm_controls[: len(norm_controls) - i])

    cte_defs: List[str] = []
    table_cols = _get_table_columns(con, table_name)
    has_realized_rate = "realized_discount_rate" in table_cols

    # Expression for realized discount rate
    if has_realized_rate:
        rate_expr = "t.realized_discount_rate"
    else:
        rate_expr = """
            CASE 
                WHEN t.extended_list_amt > 0 THEN (t.extended_list_amt - t.net_invoiced_amt) / t.extended_list_amt 
                ELSE 0.0 
            END
        """

    # Exclude any previous baseline metrics to avoid column name collisions on recalibration
    existing_baseline = [c for c in table_cols if c in BASELINE_METRIC_COLUMNS]
    exclude_clause = f"EXCLUDE ({', '.join(existing_baseline)})" if existing_baseline else ""

    # 1. Base view with clean realized_discount_rate
    base_cte = f"""
    _tx_base AS (
        SELECT 
            t.* {exclude_clause},
            {rate_expr} AS _clean_realized_rate
        FROM {table_name} t
    )
    """
    cte_defs.append(base_cte)

    # 2. Build CTE for each tier
    for k, tier_ctrls in enumerate(tiers):
        if tier_ctrls:
            col_list_proj = ", ".join([f'dp."{c}"' for c in tier_ctrls])
            col_list_dist = ", ".join([f'"{c}"' for c in tier_ctrls])
            join_cond = " AND ".join([f'dp."{c}" = t."{c}"' for c in tier_ctrls])
            group_by = f"{col_list_proj}, dp.account_id"

            cte_sql = f"""
            _tier_{k}_stats AS (
                SELECT 
                    {col_list_proj},
                    dp.account_id,
                    COUNT(t.transaction_line_id) AS peer_count,
                    COUNT(DISTINCT t.account_id) AS peer_accounts,
                    quantile_cont(t._clean_realized_rate, 0.75) AS p75_val,
                    median(t._clean_realized_rate) AS med_val,
                    mad(t._clean_realized_rate) AS mad_val
                FROM (
                    SELECT DISTINCT {col_list_dist}, account_id 
                    FROM _tx_base
                ) dp
                JOIN _tx_base t
                  ON dp.account_id != t.account_id
                 AND {join_cond}
                GROUP BY {group_by}
            )
            """
        else:
            # Global cohort (tier M)
            cte_sql = f"""
            _tier_{k}_stats AS (
                SELECT 
                    dp.account_id,
                    COUNT(t.transaction_line_id) AS peer_count,
                    COUNT(DISTINCT t.account_id) AS peer_accounts,
                    quantile_cont(t._clean_realized_rate, 0.75) AS p75_val,
                    median(t._clean_realized_rate) AS med_val,
                    mad(t._clean_realized_rate) AS mad_val
                FROM (
                    SELECT DISTINCT account_id 
                    FROM _tx_base
                ) dp
                JOIN _tx_base t
                  ON dp.account_id != t.account_id
                GROUP BY dp.account_id
            )
            """
        cte_defs.append(cte_sql.strip())

    # 3. Join resolution logic
    from_joins = ["_tx_base t"]
    for k, tier_ctrls in enumerate(tiers):
        if tier_ctrls:
            on_clause = f't.account_id = t{k}.account_id AND ' + " AND ".join([f't."{c}" = t{k}."{c}"' for c in tier_ctrls])
        else:
            on_clause = f"t.account_id = t{k}.account_id"
        from_joins.append(f"LEFT JOIN _tier_{k}_stats t{k} ON {on_clause}")

    # Case expressions for tier resolution
    resolved_tier_cases = []
    peer_count_cases = []
    peer_accounts_cases = []
    p75_cases = []
    median_cases = []
    mad_cases = []

    for k in range(len(tiers)):
        cond = f"t{k}.peer_count >= {min_transactions} AND t{k}.peer_accounts >= {min_distinct_accounts}"
        resolved_tier_cases.append(f"WHEN {cond} THEN {k}")
        peer_count_cases.append(f"WHEN {cond} THEN t{k}.peer_count")
        peer_accounts_cases.append(f"WHEN {cond} THEN t{k}.peer_accounts")
        p75_cases.append(f"WHEN {cond} THEN t{k}.p75_val")
        median_cases.append(f"WHEN {cond} THEN t{k}.med_val")
        mad_cases.append(f"WHEN {cond} THEN t{k}.mad_val")

    resolved_tier_expr = f"CASE {' '.join(resolved_tier_cases)} ELSE NULL END"
    last_k = len(tiers) - 1
    peer_count_expr = f"CASE {' '.join(peer_count_cases)} ELSE COALESCE(t{last_k}.peer_count, 0) END"
    peer_accounts_expr = f"CASE {' '.join(peer_accounts_cases)} ELSE COALESCE(t{last_k}.peer_accounts, 0) END"
    p75_expr = f"CASE {' '.join(p75_cases)} ELSE NULL END"
    median_expr = f"CASE {' '.join(median_cases)} ELSE NULL END"
    mad_expr = f"CASE {' '.join(mad_cases)} ELSE NULL END"

    # Threshold computation
    if method == "P75":
        threshold_calc = "res.p75_concession"
    else:  # MAD
        threshold_calc = f"res.median_concession + ({mad_multiplier} * COALESCE(res.mad_concession, 0.0))"

    # Complete CTE Query
    full_sql = f"""
    WITH {', '.join(cte_defs)},
    _tier_resolved AS (
        SELECT 
            t.*,
            {resolved_tier_expr} AS backoff_tier,
            {peer_count_expr} AS peer_count,
            {peer_accounts_expr} AS peer_accounts,
            {p75_expr} AS p75_concession,
            {median_expr} AS median_concession,
            {mad_expr} AS mad_concession
        FROM {' '.join(from_joins)}
    ),
    _scored_final AS (
        SELECT 
            res.* EXCLUDE (_clean_realized_rate),
            res._clean_realized_rate AS realized_discount_rate,
            CASE 
                WHEN res.backoff_tier IS NOT NULL THEN '{STATUS_DEFENSIBLE}'
                ELSE '{STATUS_INSUFFICIENT}'
            END AS support_status,
            CASE 
                WHEN res.backoff_tier IS NOT NULL THEN TRUE
                ELSE FALSE
            END AS has_comparable_evidence,
            CASE 
                WHEN res.backoff_tier IS NOT NULL THEN ({threshold_calc})
                ELSE NULL
            END AS threshold_concession,
            CASE 
                WHEN res.backoff_tier IS NOT NULL 
                THEN GREATEST(0.0, res._clean_realized_rate - ({threshold_calc})) * res.extended_list_amt
                ELSE 0.0
            END AS defensible_gap,
            CASE 
                WHEN res.backoff_tier IS NOT NULL 
                THEN GREATEST(0.0, res._clean_realized_rate - res.median_concession) * res.extended_list_amt
                ELSE 0.0
            END AS band_gap,
            CASE 
                WHEN res.backoff_tier IS NOT NULL 
                THEN {kappa} * (GREATEST(0.0, res._clean_realized_rate - ({threshold_calc})) * res.extended_list_amt)
                ELSE 0.0
            END AS actionable_opportunity
        FROM _tier_resolved res
    )
    SELECT * FROM _scored_final;
    """

    return full_sql, tiers


def compute_loao_baselines(
    con: duckdb.DuckDBPyConnection,
    controls: Optional[List[str]] = None,
    threshold_method: str = DEFAULT_THRESHOLD_METHOD,
    kappa: float = DEFAULT_KAPPA,
    mad_multiplier: float = DEFAULT_MAD_MULTIPLIER,
    min_transactions: int = SUPPORT_MIN_TRANSACTIONS,
    min_distinct_accounts: int = SUPPORT_MIN_ACCOUNTS,
    table_name: str = "transactions",
    update_table: bool = True,
) -> LOAOResult:
    """
    Computes Leave-One-Account-Out (LOAO) peer cohort statistics over \\Omega_{-A(i)},
    enforces cohort support fences (N >= 10, |A| >= 5) with hierarchical back-off,
    evaluates boundary thresholds (P75 or Median + 1.5 * MAD), computes Defensible Gap,
    Band Gap, and Actionable Opportunity, and populates baseline metrics into the active workspace.

    Returns:
      LOAOResult: dual dict/DataFrame container with full summary statistics and annotated rows.
    """
    # 1. Check if table exists and has rows
    try:
        row_count = con.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0]
    except Exception as e:
        raise ValueError(f"Table '{table_name}' does not exist or cannot be queried: {str(e)}")

    norm_controls = controls if controls is not None else DEFAULT_CONTROLS
    validate_three_column_classification(norm_controls)

    if row_count == 0:
        empty_df = pd.DataFrame()
        summary = {
            "status": "empty_table",
            "total_transactions": 0,
            "defensible_transactions_count": 0,
            "insufficient_evidence_count": 0,
            "total_defensible_gap": 0.0,
            "total_actionable_opportunity": 0.0,
            "total_band_gap": 0.0,
            "backoff_tier_counts": {},
            "controls": norm_controls,
            "threshold_method": threshold_method,
            "kappa": kappa,
            "mad_multiplier": mad_multiplier,
            "min_transactions": min_transactions,
            "min_distinct_accounts": min_distinct_accounts,
        }
        return LOAOResult(summary, empty_df)

    # 2. Build hierarchical SQL query
    sql, tiers = build_hierarchical_loao_sql(
        con=con,
        table_name=table_name,
        controls=norm_controls,
        threshold_method=threshold_method,
        kappa=kappa,
        mad_multiplier=mad_multiplier,
        min_transactions=min_transactions,
        min_distinct_accounts=min_distinct_accounts,
    )

    # 3. Execute query and store into temp table
    con.execute("CREATE OR REPLACE TEMP TABLE _m3_loao_scored AS " + sql)
    scored_df = con.execute("SELECT * FROM _m3_loao_scored;").df()

    # 4. In-place database update if requested
    if update_table:
        cols_to_add = [
            ("p75_concession", "DECIMAL(10, 6)"),
            ("median_concession", "DECIMAL(10, 6)"),
            ("mad_concession", "DECIMAL(10, 6)"),
            ("threshold_concession", "DECIMAL(10, 6)"),
            ("peer_count", "BIGINT"),
            ("peer_accounts", "BIGINT"),
            ("support_status", "VARCHAR"),
            ("has_comparable_evidence", "BOOLEAN"),
            ("backoff_tier", "INTEGER"),
            ("band_gap", "DECIMAL(18, 4)"),
            ("actionable_opportunity", "DECIMAL(18, 4)"),
        ]
        for col_name, col_type in cols_to_add:
            try:
                con.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "{col_name}" {col_type};')
            except Exception:
                pass

        # Fast vectorized UPDATE from temp table
        try:
            con.execute(f"""
                UPDATE {table_name}
                SET 
                    realized_discount_rate = s.realized_discount_rate,
                    defensible_gap = s.defensible_gap,
                    p75_concession = s.p75_concession,
                    median_concession = s.median_concession,
                    mad_concession = s.mad_concession,
                    threshold_concession = s.threshold_concession,
                    peer_count = s.peer_count,
                    peer_accounts = s.peer_accounts,
                    support_status = s.support_status,
                    has_comparable_evidence = s.has_comparable_evidence,
                    backoff_tier = s.backoff_tier,
                    band_gap = s.band_gap,
                    actionable_opportunity = s.actionable_opportunity
                FROM _m3_loao_scored s
                WHERE {table_name}.transaction_line_id = s.transaction_line_id;
            """)
        except Exception:
            # Fallback if primary key / update syntax differs
            pass

    # 5. Compile comprehensive summary metrics
    total_tx = len(scored_df)
    defensible_mask = scored_df["has_comparable_evidence"] == True
    defensible_count = int(defensible_mask.sum())
    insufficient_count = total_tx - defensible_count

    total_defensible_gap = float(round(scored_df["defensible_gap"].sum(), 2))
    total_band_gap = float(round(scored_df["band_gap"].sum(), 2))
    total_actionable_opp = float(round(scored_df["actionable_opportunity"].sum(), 2))

    # Backoff tier counts
    tier_counts: Dict[str, int] = {}
    for k in range(len(tiers)):
        cnt = int((scored_df["backoff_tier"] == k).sum())
        tier_counts[f"tier_{k}"] = cnt
    tier_counts["insufficient"] = insufficient_count

    summary = {
        "status": "success",
        "total_transactions": total_tx,
        "defensible_transactions_count": defensible_count,
        "insufficient_evidence_count": insufficient_count,
        "total_defensible_gap": total_defensible_gap,
        "total_actionable_opportunity": total_actionable_opp,
        "total_band_gap": total_band_gap,
        "backoff_tier_counts": tier_counts,
        "controls": norm_controls,
        "threshold_method": threshold_method.upper(),
        "kappa": kappa,
        "mad_multiplier": mad_multiplier,
        "min_transactions": min_transactions,
        "min_distinct_accounts": min_distinct_accounts,
    }

    return LOAOResult(summary, scored_df)


# ---------------------------------------------------------------------------
# R3.9: Calibration Profile Freezing & .calib.json Manifest Export
# ---------------------------------------------------------------------------

def freeze_calibration(
    con: duckdb.DuckDBPyConnection,
    profile_name: str,
    controls: Optional[List[str]] = None,
    threshold_method: str = DEFAULT_THRESHOLD_METHOD,
    kappa: float = DEFAULT_KAPPA,
    mad_multiplier: float = DEFAULT_MAD_MULTIPLIER,
    min_transactions: int = SUPPORT_MIN_TRANSACTIONS,
    min_distinct_accounts: int = SUPPORT_MIN_ACCOUNTS,
    historical_start_date: Optional[str] = None,
    historical_end_date: Optional[str] = None,
    investigation_dimensions: Optional[List[str]] = None,
    export_dir: Optional[str] = None,
    export_filename: Optional[str] = None,
) -> str:
    """
    Exports versioned .calib.json profile and records snapshot into meta_calibration_profiles.
    Locks the historical baseline to disallow dynamic rolling drift during active audit triage.

    Returns:
      str: The unique calibration_id of the frozen profile.
    """
    if not profile_name or not profile_name.strip():
        raise ValueError("Profile name cannot be empty.")

    norm_controls = [c.strip() for c in (controls or DEFAULT_CONTROLS) if c and c.strip()]
    norm_inv_dims = [d.strip() for d in (investigation_dimensions or DEFAULT_INVESTIGATION_DIMS) if d and d.strip()]
    validate_three_column_classification(norm_controls, norm_inv_dims)

    # 1. Determine historical date range
    start_date = historical_start_date
    end_date = historical_end_date
    if not start_date or not end_date:
        try:
            date_row = con.execute("""
                SELECT 
                    MIN(transaction_date)::VARCHAR, 
                    MAX(transaction_date)::VARCHAR 
                FROM transactions;
            """).fetchone()
            if date_row and date_row[0] and date_row[1]:
                start_date = start_date or date_row[0]
                end_date = end_date or date_row[1]
        except Exception:
            pass

    today_str = datetime.date.today().isoformat()
    start_date = start_date or today_str
    end_date = end_date or today_str

    # 2. Generate unique calibration ID
    calib_uuid = uuid.uuid4().hex[:8].upper()
    calib_date = datetime.datetime.utcnow().strftime("%Y%m%d")
    calibration_id = f"CALIB-{calib_date}-{calib_uuid}"

    # 3. Construct manifest JSON
    manifest = {
        "calibration_id": calibration_id,
        "name": profile_name.strip(),
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "historical_start_date": str(start_date),
        "historical_end_date": str(end_date),
        "comparability_controls": norm_controls,
        "investigation_dimensions": norm_inv_dims,
        "threshold_strategy": threshold_method.upper(),
        "mad_multiplier": float(mad_multiplier),
        "haircut_kappa": float(kappa),
        "min_transactions": int(min_transactions),
        "min_distinct_accounts": int(min_distinct_accounts),
        "is_locked": True,
        "schema_version": "1.0.0",
    }
    manifest_json_str = json.dumps(manifest, indent=2)

    # 4. Insert into meta_calibration_profiles table
    # Schema check for table existence
    try:
        con.execute(f"""
            INSERT INTO meta_calibration_profiles (
                calibration_id,
                name,
                created_at,
                historical_start_date,
                historical_end_date,
                comparability_controls,
                investigation_dimensions,
                threshold_strategy,
                mad_multiplier,
                haircut_kappa,
                min_transactions,
                min_distinct_accounts,
                calibration_json,
                is_locked
            ) VALUES (
                '{calibration_id}',
                '{profile_name.strip()}',
                CURRENT_TIMESTAMP,
                '{start_date}'::DATE,
                '{end_date}'::DATE,
                {norm_controls},
                {norm_inv_dims},
                '{threshold_method.upper()}',
                {mad_multiplier},
                {kappa},
                {min_transactions},
                {min_distinct_accounts},
                '{manifest_json_str}',
                TRUE
            );
        """)
    except Exception as e:
        raise RuntimeError(f"Failed to record calibration profile into meta_calibration_profiles: {str(e)}")

    # 5. Export to .calib.json file on disk
    target_dir = Path(export_dir) if export_dir else (Path(os.getcwd()) / "backend")
    target_dir.mkdir(parents=True, exist_ok=True)

    if export_filename:
        filename = export_filename if export_filename.endswith(".calib.json") else f"{export_filename}.calib.json"
    else:
        clean_name = re.sub(r"[^\w\-]", "_", profile_name.strip().lower())
        filename = f"{clean_name}_{calibration_id}.calib.json"

    export_path = target_dir / filename
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(manifest_json_str)

    return calibration_id


def export_calibration_profile(profile_dict: Dict[str, Any], file_path: Union[str, Path]) -> str:
    """Exports a calibration profile dictionary to a .calib.json file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile_dict, f, indent=2)
    return str(path)


def load_calibration_profile(
    con: duckdb.DuckDBPyConnection,
    profile_path_or_dict: Union[str, Path, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Loads and activates a calibration profile from a .calib.json file or dictionary
    into DuckDB's meta_calibration_profiles table.
    """
    if isinstance(profile_path_or_dict, (str, Path)):
        path = Path(profile_path_or_dict)
        if not path.is_file():
            raise FileNotFoundError(f"Calibration profile file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    elif isinstance(profile_path_or_dict, dict):
        profile = profile_path_or_dict
    else:
        raise TypeError("profile_path_or_dict must be a file path or dict.")

    calib_id = profile.get("calibration_id", f"CALIB-{uuid.uuid4().hex[:8].upper()}")
    name = profile.get("name", "Imported Profile")
    start_date = profile.get("historical_start_date", datetime.date.today().isoformat())
    end_date = profile.get("historical_end_date", datetime.date.today().isoformat())
    controls = profile.get("comparability_controls", DEFAULT_CONTROLS)
    inv_dims = profile.get("investigation_dimensions", DEFAULT_INVESTIGATION_DIMS)
    threshold_strategy = profile.get("threshold_strategy", DEFAULT_THRESHOLD_METHOD)
    mad_multiplier = profile.get("mad_multiplier", DEFAULT_MAD_MULTIPLIER)
    haircut_kappa = profile.get("haircut_kappa", DEFAULT_KAPPA)
    min_tx = profile.get("min_transactions", SUPPORT_MIN_TRANSACTIONS)
    min_accts = profile.get("min_distinct_accounts", SUPPORT_MIN_ACCOUNTS)
    is_locked = profile.get("is_locked", True)

    manifest_json_str = json.dumps(profile)

    # Insert or replace in meta_calibration_profiles
    con.execute(f"DELETE FROM meta_calibration_profiles WHERE calibration_id = '{calib_id}';")
    con.execute(f"""
        INSERT INTO meta_calibration_profiles (
            calibration_id,
            name,
            created_at,
            historical_start_date,
            historical_end_date,
            comparability_controls,
            investigation_dimensions,
            threshold_strategy,
            mad_multiplier,
            haircut_kappa,
            min_transactions,
            min_distinct_accounts,
            calibration_json,
            is_locked
        ) VALUES (
            '{calib_id}',
            '{name}',
            CURRENT_TIMESTAMP,
            '{start_date}'::DATE,
            '{end_date}'::DATE,
            {controls},
            {inv_dims},
            '{threshold_strategy}',
            {mad_multiplier},
            {haircut_kappa},
            {min_tx},
            {min_accts},
            '{manifest_json_str}',
            {str(is_locked).upper()}
        );
    """)

    return profile


def get_active_calibration_profile(con: duckdb.DuckDBPyConnection) -> Optional[Dict[str, Any]]:
    """Returns the currently active / most recently created calibration profile."""
    try:
        row = con.execute("""
            SELECT calibration_id, name, threshold_strategy, haircut_kappa, comparability_controls, calibration_json
            FROM meta_calibration_profiles
            ORDER BY created_at DESC
            LIMIT 1;
        """).fetchone()
        if not row:
            return None
        manifest = json.loads(row[5]) if isinstance(row[5], str) else row[5]
        return manifest
    except Exception:
        return None
