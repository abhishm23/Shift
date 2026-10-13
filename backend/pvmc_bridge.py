"""
backend/pvmc_bridge.py
Decoupled Engine B: Period-over-Period Macro PVMC Margin Bridge (R5.4 - R5.6)

Implements:
1. Period-over-period margin bridge decomposing Delta Margin into:
   Price Effect + Cost Effect + Volume Effect + Mix Effect + New & Discontinued Business turnover.
2. Volume Homogeneity Rule (R5.5):
   Automated detection of disparate Units of Measure (UoM).
   Segmentation by UoM with additive dollar aggregation.
3. Turnover Isolation (R5.6):
   Dedicated isolation for entries (Q0 = 0) and exits (Q1 = 0).
4. Exact penny reconciliation algebraic invariant:
   Delta Margin == Price + Cost + Volume + Mix + New + Discontinued.
"""

import re
from typing import Optional, Dict, Any, List, Union, Tuple
import duckdb


def parse_period_filter(filter_spec: Union[str, Dict[str, Any]], date_col: str = "transaction_date") -> str:
    """
    Translates period shorthand or expressions into a validated DuckDB SQL WHERE condition.

    Supported formats:
      - '2024-H1' -> 2024-01-01 to 2024-06-30
      - '2024-H2' -> 2024-07-01 to 2024-12-31
      - '2024-Q1' -> 2024-01-01 to 2024-03-31 (Q1..Q4)
      - '2024-FY' or '2024' -> 2024-01-01 to 2024-12-31
      - '2024-01-01:2024-06-30' or '2024-01-01 to 2024-06-30'
      - Dict: {'start': '2024-01-01', 'end': '2024-06-30'}
      - Direct SQL predicate (e.g. "transaction_date >= '2024-01-01'")
    """
    if not filter_spec:
        return "1=1"

    if isinstance(filter_spec, dict):
        start = filter_spec.get("start") or filter_spec.get("start_date") or filter_spec.get("from")
        end = filter_spec.get("end") or filter_spec.get("end_date") or filter_spec.get("to")
        clauses = []
        if start:
            clauses.append(f"{date_col} >= '{start}'")
        if end:
            clauses.append(f"{date_col} <= '{end}'")
        return " AND ".join(clauses) if clauses else "1=1"

    spec = str(filter_spec).strip()

    # Direct SQL expressions containing operators or keywords
    if any(k in spec.upper() for k in (" AND ", " OR ", ">=", "<=", " BETWEEN ", "LIKE ", "=")):
        return spec

    # Half-year: e.g. 2024-H1, 2025-H2
    m_h = re.match(r"^(\d{4})[-_]?[hH]([12])$", spec)
    if m_h:
        year, half = m_h.groups()
        if half == "1":
            return f"({date_col} >= '{year}-01-01' AND {date_col} <= '{year}-06-30')"
        else:
            return f"({date_col} >= '{year}-07-01' AND {date_col} <= '{year}-12-31')"

    # Quarter: e.g. 2024-Q1, 2024-Q3
    m_q = re.match(r"^(\d{4})[-_]?[qQ]([1-4])$", spec)
    if m_q:
        year, qtr = m_q.groups()
        q_map = {
            "1": ("01-01", "03-31"),
            "2": ("04-01", "06-30"),
            "3": ("07-01", "09-30"),
            "4": ("10-01", "12-31"),
        }
        start_d, end_d = q_map[qtr]
        return f"({date_col} >= '{year}-{start_d}' AND {date_col} <= '{year}-{end_d}')"

    # Full year: e.g. 2024-FY, 2024
    m_y = re.match(r"^(\d{4})([-_]?[fF][yY])?$", spec)
    if m_y:
        year = m_y.group(1)
        return f"({date_col} >= '{year}-01-01' AND {date_col} <= '{year}-12-31')"

    # Range separator: '2024-01-01:2024-06-30' or '2024-01-01 to 2024-06-30' or '2024-01-01..2024-06-30'
    m_range = re.split(r"\s*(?::|\.\.|to)\s*", spec, flags=re.IGNORECASE)
    if len(m_range) == 2 and len(m_range[0]) >= 4 and len(m_range[1]) >= 4:
        return f"({date_col} >= '{m_range[0].strip()}' AND {date_col} <= '{m_range[1].strip()}')"

    # Fallback to equality check on date or period
    return f"{date_col} = '{spec}'"


def resolve_schema_columns(
    con: duckdb.DuckDBPyConnection,
    product_col: Optional[str] = None,
    qty_col: Optional[str] = None,
    uom_col: Optional[str] = None,
    table_name: str = "transactions",
) -> Dict[str, str]:
    """
    Detects column references for product entity, quantity, and unit of measure (UoM),
    supporting canonical columns, physical source columns, and dimension_attributes JSON.
    """
    table_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]

    # 1. Product Identifier Resolver
    prod_sql = ""
    if product_col and product_col in table_cols:
        prod_sql = f'"{product_col}"'
    elif product_col and "dimension_attributes" in table_cols:
        prod_sql = f"COALESCE(json_extract_string(dimension_attributes, '$.{product_col}'), '{product_col}')"
    else:
        candidates = ["product_family", "product_id", "sku", "item_id", "account_id"]
        for cand in candidates:
            if cand in table_cols:
                prod_sql = f'"{cand}"'
                break
        if not prod_sql:
            if "dimension_attributes" in table_cols:
                prod_sql = "COALESCE(json_extract_string(dimension_attributes, '$.product_family'), json_extract_string(dimension_attributes, '$.product_id'), 'DEFAULT_PROD')"
            else:
                prod_sql = "'DEFAULT_PROD'"

    # 2. Quantity Resolver
    qty_sql = ""
    if qty_col and qty_col in table_cols:
        qty_sql = f'COALESCE(TRY_CAST("{qty_col}" AS DOUBLE), 1.0)'
    elif qty_col and "dimension_attributes" in table_cols:
        qty_sql = f"COALESCE(TRY_CAST(json_extract_string(dimension_attributes, '$.{qty_col}') AS DOUBLE), 1.0)"
    else:
        candidates = ["quantity", "qty", "units", "volume"]
        for cand in candidates:
            if cand in table_cols:
                qty_sql = f'COALESCE(TRY_CAST("{cand}" AS DOUBLE), 1.0)'
                break
        if not qty_sql:
            if "dimension_attributes" in table_cols:
                qty_sql = "COALESCE(TRY_CAST(json_extract_string(dimension_attributes, '$.quantity') AS DOUBLE), 1.0)"
            else:
                qty_sql = "1.0"

    # 3. Unit of Measure Resolver
    uom_sql = ""
    if uom_col and uom_col in table_cols:
        uom_sql = f'COALESCE("{uom_col}", \'EA\')'
    elif uom_col and "dimension_attributes" in table_cols:
        uom_sql = f"COALESCE(json_extract_string(dimension_attributes, '$.{uom_col}'), 'EA')"
    else:
        candidates = ["uom", "unit_of_measure", "unit"]
        for cand in candidates:
            if cand in table_cols:
                uom_sql = f'COALESCE("{cand}", \'EA\')'
                break
        if not uom_sql:
            if "dimension_attributes" in table_cols:
                uom_sql = "COALESCE(json_extract_string(dimension_attributes, '$.uom'), 'EA')"
            else:
                uom_sql = "'EA'"

    # 4. Reporting Amount Columns
    rev_sql = (
        "reporting_invoiced_amt"
        if "reporting_invoiced_amt" in table_cols
        else "net_invoiced_amt * COALESCE(fx_rate_to_reporting, 1.0)"
    )

    cogs_col = (
        "COALESCE(reporting_cogs_amt, cogs_amt * COALESCE(fx_rate_to_reporting, 1.0), 0.0)"
        if "reporting_cogs_amt" in table_cols
        else "COALESCE(cogs_amt * COALESCE(fx_rate_to_reporting, 1.0), 0.0)"
    )

    reb_col = (
        "COALESCE(reporting_rebate_amt, off_invoice_rebate * COALESCE(fx_rate_to_reporting, 1.0), 0.0)"
        if "reporting_rebate_amt" in table_cols
        else "COALESCE(off_invoice_rebate * COALESCE(fx_rate_to_reporting, 1.0), 0.0)"
    )

    cost_sql = f"({cogs_col} + {reb_col})"

    margin_sql = (
        "pocket_margin_amt"
        if "pocket_margin_amt" in table_cols
        else f"({rev_sql} - {cost_sql})"
    )

    return {
        "product_sql": prod_sql,
        "qty_sql": qty_sql,
        "uom_sql": uom_sql,
        "rev_sql": rev_sql,
        "cost_sql": cost_sql,
        "margin_sql": margin_sql,
    }


def compute_homogeneous_segment_pvmc(
    con: duckdb.DuckDBPyConnection,
    t0_where: str,
    t1_where: str,
    uom_val: str,
    schema_info: Dict[str, str],
    table_name: str = "transactions",
) -> Dict[str, Any]:
    """
    Computes exact PVMC decomposition for a single homogeneous UoM segment.
    """
    prod_sql = schema_info["product_sql"]
    qty_sql = schema_info["qty_sql"]
    uom_sql = schema_info["uom_sql"]
    rev_sql = schema_info["rev_sql"]
    cost_sql = schema_info["cost_sql"]
    margin_sql = schema_info["margin_sql"]

    # Table columns to check is_credit_reversal
    table_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]
    credit_rev_expr = (
        f"CASE WHEN is_credit_reversal AND ({qty_sql}) > 0 THEN -({qty_sql}) ELSE ({qty_sql}) END"
        if "is_credit_reversal" in table_cols
        else qty_sql
    )

    uom_filter_clause = f"AND ({uom_sql}) = '{uom_val}'" if uom_val != "*" else ""

    query = f"""
        WITH t0_data AS (
            SELECT
                CAST({prod_sql} AS VARCHAR) AS product_id,
                SUM({credit_rev_expr}) AS q0,
                SUM({rev_sql}) AS r0,
                SUM({cost_sql}) AS c0,
                SUM({margin_sql}) AS m0
            FROM {table_name}
            WHERE ({t0_where}) {uom_filter_clause}
            GROUP BY 1
        ),
        t1_data AS (
            SELECT
                CAST({prod_sql} AS VARCHAR) AS product_id,
                SUM({credit_rev_expr}) AS q1,
                SUM({rev_sql}) AS r1,
                SUM({cost_sql}) AS c1,
                SUM({margin_sql}) AS m1
            FROM {table_name}
            WHERE ({t1_where}) {uom_filter_clause}
            GROUP BY 1
        ),
        merged AS (
            SELECT
                COALESCE(t0.product_id, t1.product_id) AS product_id,
                COALESCE(t0.q0, 0.0) AS q0,
                COALESCE(t1.q1, 0.0) AS q1,
                COALESCE(t0.r0, 0.0) AS r0,
                COALESCE(t1.r1, 0.0) AS r1,
                COALESCE(t0.c0, 0.0) AS c0,
                COALESCE(t1.c1, 0.0) AS c1,
                COALESCE(t0.m0, 0.0) AS m0,
                COALESCE(t1.m1, 0.0) AS m1
            FROM t0_data t0
            FULL OUTER JOIN t1_data t1 ON t0.product_id = t1.product_id
        )
        SELECT * FROM merged;
    """

    rows = con.execute(query).fetchall()

    # Continuing items list
    continuing = []
    # Turnover
    new_business_turnover = 0.0
    disc_business_turnover = 0.0
    new_count = 0
    disc_count = 0

    base_margin_t0 = 0.0
    final_margin_t1 = 0.0

    for r in rows:
        prod_id, q0, q1, r0, r1, c0, c1, m0, m1 = r
        q0 = float(q0 or 0.0)
        q1 = float(q1 or 0.0)
        r0 = float(r0 or 0.0)
        r1 = float(r1 or 0.0)
        c0 = float(c0 or 0.0)
        c1 = float(c1 or 0.0)
        m0 = float(m0 or 0.0)
        m1 = float(m1 or 0.0)

        base_margin_t0 += m0
        final_margin_t1 += m1

        # Classify item status
        if q0 > 0 and q1 > 0:
            continuing.append({
                "product_id": prod_id,
                "q0": q0,
                "q1": q1,
                "r0": r0,
                "r1": r1,
                "c0": c0,
                "c1": c1,
                "m0": m0,
                "m1": m1,
                "p0": r0 / q0,
                "p1": r1 / q1,
                "cost0": c0 / q0,
                "cost1": c1 / q1,
                "unit_m0": m0 / q0,
                "unit_m1": m1 / q1,
            })
        elif q1 > 0 and q0 <= 0:
            new_business_turnover += m1
            new_count += 1
            if m0 != 0:
                disc_business_turnover -= m0  # Account for T0 return margin
        elif q0 > 0 and q1 <= 0:
            disc_business_turnover -= m0      # Lost margin is a negative effect
            disc_count += 1
            if m1 != 0:
                new_business_turnover += m1   # Account for T1 return margin
        else:
            # Inactive in volume, but if there's any non-volume residual margin
            if m1 != 0:
                new_business_turnover += m1
            if m0 != 0:
                disc_business_turnover -= m0

    continuing_count = len(continuing)

    price_effect = 0.0
    cost_effect = 0.0
    volume_effect = 0.0
    mix_effect = 0.0

    if continuing_count > 0:
        total_q0 = sum(item["q0"] for item in continuing)
        total_q1 = sum(item["q1"] for item in continuing)
        total_m0_cont = sum(item["m0"] for item in continuing)

        avg_unit_m0 = (total_m0_cont / total_q0) if total_q0 > 0 else 0.0

        for item in continuing:
            # Price Effect: Q1 * (P1 - P0)
            price_effect += item["q1"] * (item["p1"] - item["p0"])
            # Cost Effect: Q1 * (Cost0 - Cost1)
            cost_effect += item["q1"] * (item["cost0"] - item["cost1"])

        # Volume Effect: (Q1 - Q0) * avg_unit_m0
        volume_effect = (total_q1 - total_q0) * avg_unit_m0

        # Mix Effect: sum(Q1_i * unit_m0_i) - Q1 * avg_unit_m0
        # which identically equals Q1 * sum( (s1_i - s0_i) * unit_m0_i )
        sum_q1_m0 = sum(item["q1"] * item["unit_m0"] for item in continuing)
        mix_effect = sum_q1_m0 - (total_q1 * avg_unit_m0)

    delta_margin = final_margin_t1 - base_margin_t0
    turnover_total = new_business_turnover + disc_business_turnover

    return {
        "uom": uom_val,
        "base_margin_t0": base_margin_t0,
        "final_margin_t1": final_margin_t1,
        "delta_margin": delta_margin,
        "price_effect": price_effect,
        "cost_effect": cost_effect,
        "volume_effect": volume_effect,
        "mix_effect": mix_effect,
        "new_and_discontinued": turnover_total,
        "new_business_turnover": new_business_turnover,
        "discontinued_business_turnover": disc_business_turnover,
        "continuing_count": continuing_count,
        "new_count": new_count,
        "discontinued_count": disc_count,
    }


def compute_pvmc_bridge(
    con: duckdb.DuckDBPyConnection,
    t0_filter: Union[str, Dict[str, Any]],
    t1_filter: Union[str, Dict[str, Any]],
    product_col: Optional[str] = None,
    qty_col: Optional[str] = None,
    uom_col: Optional[str] = None,
    table_name: str = "transactions",
) -> Dict[str, Any]:
    """
    Main Engine B Entry Point: Decoupled Period-over-Period Macro PVMC Margin Bridge (R5.4 - R5.6).

    Decomposes Delta Margin into:
      Delta Margin = Price Effect + Cost Effect + Volume Effect + Mix Effect + New & Discontinued Business.

    Enforces:
      1. Volume Homogeneity Rule (R5.5): Automatic UoM detection and segmentation.
      2. New & Discontinued Business isolation (R5.6).
      3. Exact penny reconciliation invariant.
    """
    t0_where = parse_period_filter(t0_filter)
    t1_where = parse_period_filter(t1_filter)

    schema_info = resolve_schema_columns(
        con=con,
        product_col=product_col,
        qty_col=qty_col,
        uom_col=uom_col,
        table_name=table_name,
    )

    uom_sql = schema_info["uom_sql"]

    # 1. Volume Homogeneity Detection: Find all distinct UoMs across T0 and T1
    distinct_uoms_query = f"""
        SELECT DISTINCT CAST({uom_sql} AS VARCHAR) AS uom
        FROM {table_name}
        WHERE ({t0_where}) OR ({t1_where});
    """
    raw_uoms = [r[0] for r in con.execute(distinct_uoms_query).fetchall() if r[0] is not None]
    distinct_uoms = sorted(list(set(raw_uoms))) if raw_uoms else ["EA"]

    # 2. Segmented Decomposition
    segment_results = []
    total_base_t0 = 0.0
    total_final_t1 = 0.0
    total_price = 0.0
    total_cost = 0.0
    total_volume = 0.0
    total_mix = 0.0
    total_new = 0.0
    total_disc = 0.0

    for uom_val in distinct_uoms:
        seg = compute_homogeneous_segment_pvmc(
            con=con,
            t0_where=t0_where,
            t1_where=t1_where,
            uom_val=uom_val,
            schema_info=schema_info,
            table_name=table_name,
        )
        segment_results.append(seg)
        total_base_t0 += seg["base_margin_t0"]
        total_final_t1 += seg["final_margin_t1"]
        total_price += seg["price_effect"]
        total_cost += seg["cost_effect"]
        total_volume += seg["volume_effect"]
        total_mix += seg["mix_effect"]
        total_new += seg["new_business_turnover"]
        total_disc += seg["discontinued_business_turnover"]

    total_delta_margin = total_final_t1 - total_base_t0
    total_turnover = total_new + total_disc

    # Algebraic Sum before display rounding
    bridge_calculated_sum = total_price + total_cost + total_volume + total_mix + total_turnover
    reconciliation_delta = abs(total_delta_margin - bridge_calculated_sum)

    # Format segments for output
    formatted_segments = []
    for s in segment_results:
        formatted_segments.append({
            "uom": s["uom"],
            "base_margin_t0": round(s["base_margin_t0"], 2),
            "final_margin_t1": round(s["final_margin_t1"], 2),
            "price_effect": round(s["price_effect"], 2),
            "cost_effect": round(s["cost_effect"], 2),
            "volume_effect": round(s["volume_effect"], 2),
            "mix_effect": round(s["mix_effect"], 2),
            "new_business": round(s["new_business_turnover"], 2),
            "discontinued_business": round(s["discontinued_business_turnover"], 2),
            "new_and_discontinued": round(s["new_and_discontinued"], 2),
            "continuing_count": s["continuing_count"],
            "new_count": s["new_count"],
            "discontinued_count": s["discontinued_count"],
        })

    # Volume Homogeneity Rule:
    # Always satisfied and passed because when heterogeneous UoMs exist,
    # the engine enforces mathematical segmentation across homogeneous pools.
    volume_homogeneity_passed = True

    return {
        "status": "success",
        "t0_period": str(t0_filter) if isinstance(t0_filter, str) else "T0",
        "t1_period": str(t1_filter) if isinstance(t1_filter, str) else "T1",
        "base_margin_t0": round(total_base_t0, 2),
        "final_margin_t1": round(total_final_t1, 2),
        "delta_margin": round(total_delta_margin, 2),
        "price_effect": round(total_price, 2),
        "cost_effect": round(total_cost, 2),
        "volume_effect": round(total_volume, 2),
        "mix_effect": round(total_mix, 2),
        "new_and_discontinued": round(total_turnover, 2),
        "new_business_turnover": round(total_new, 2),
        "discontinued_business_turnover": round(total_disc, 2),
        "volume_homogeneity_passed": volume_homogeneity_passed,
        "reconciliation_delta": round(reconciliation_delta, 4),
        "reconciliation_certified": bool(reconciliation_delta <= 0.01),
        "uom_segments": formatted_segments,
    }
