"""
Sift Deduplicated Overlap-Aware Ledger & Inverted Transaction Mapping (Milestone 4)

Authoritative Features:
- R4.6: Canonical transaction-level gap ledger mapping each row to defensible gap
        and slice finding memberships.
- R4.7: Deduplicated Net Unique Portfolio Exposure strictly computed as the SQL set
        union of transaction dollars across active findings (preventing double-counting).
- AC-4: Exact penny set union invariant and dismissal governance protection.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

import duckdb


def compute_net_unique_portfolio_exposure(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "transactions",
) -> Dict[str, Any]:
    """
    Computes the canonical deduplicated Net Unique Portfolio Exposure via SQL set union
    across active (non-dismissed) findings in finding_records.

    Returns:
        dict with keys:
            - net_unique_portfolio_exposure (float)
            - net_unique_transactions (int)
            - net_unique_list_volume (float)
    """
    tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
    if "finding_records" not in tables or "finding_transactions_map" not in tables:
        return {
            "net_unique_portfolio_exposure": 0.0,
            "net_unique_transactions": 0,
            "net_unique_list_volume": 0.0,
        }

    # Check if extended_list_amt exists on transactions
    tx_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]
    has_list = "extended_list_amt" in tx_cols
    list_expr = "COALESCE(SUM(t.extended_list_amt), 0.0)" if has_list else "0.0"

    query = f"""
        SELECT 
            COALESCE(SUM(t.defensible_gap), 0.0) AS net_unique_portfolio_exposure,
            COUNT(DISTINCT t.transaction_line_id) AS net_unique_transactions,
            {list_expr} AS net_unique_list_volume
        FROM {table_name} t
        WHERE t.transaction_line_id IN (
            SELECT DISTINCT ftm.transaction_line_id
            FROM finding_transactions_map ftm
            JOIN finding_records fr ON ftm.finding_fingerprint = fr.finding_fingerprint
            WHERE fr.lifecycle_status != 'Dismissed'
        );
    """
    row = con.execute(query).fetchone()
    if not row:
        return {
            "net_unique_portfolio_exposure": 0.0,
            "net_unique_transactions": 0,
            "net_unique_list_volume": 0.0,
        }

    return {
        "net_unique_portfolio_exposure": round(float(row[0] or 0.0), 2),
        "net_unique_transactions": int(row[1] or 0),
        "net_unique_list_volume": round(float(row[2] or 0.0), 2),
    }


def get_overlap_ledger(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "transactions",
) -> Dict[str, Any]:
    """
    Generates comprehensive overlap audit summary comparing gross finding totals
    against the deduplicated Net Unique Portfolio Exposure.
    """
    tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
    if "finding_records" not in tables or "finding_transactions_map" not in tables:
        return {
            "status": "success",
            "findings": [],
            "active_finding_count": 0,
            "dismissed_finding_count": 0,
            "net_unique_portfolio_exposure": 0.0,
            "net_unique_transactions": 0,
            "net_unique_list_volume": 0.0,
            "gross_unshrunk_gap_sum": 0.0,
            "gross_shrunk_gap_sum": 0.0,
            "overlap_double_counted_dollars": 0.0,
            "overlap_pct": 0.0,
            "overlap_ratio_pct": 0.0,
        }

    # Inspect finding_records columns
    fr_cols = [c[1] for c in con.execute("PRAGMA table_info('finding_records');").fetchall()]
    unshrunk_col = "unshrunk_gap_dollars" if "unshrunk_gap_dollars" in fr_cols else "gross_unshrunk_gap"
    has_shrunk = "shrunk_gap_dollars" in fr_cols
    has_slice_json = "dimension_slice_json" in fr_cols
    has_depth = "depth" in fr_cols
    has_boot = "bootstrap_stability_score" in fr_cols
    has_conc = "concentration_ratio" in fr_cols
    has_inc = "unique_incremental_gap" in fr_cols

    shrunk_expr = "shrunk_gap_dollars" if has_shrunk else unshrunk_col
    slice_expr = "dimension_slice_json" if has_slice_json else "slice_name"
    depth_expr = "depth" if has_depth else "1"
    boot_expr = "bootstrap_stability_score" if has_boot else "1.0"
    conc_expr = "concentration_ratio" if has_conc else "0.0"
    inc_expr = "unique_incremental_gap" if has_inc else unshrunk_col

    # Query all findings
    query = f"""
        SELECT 
            finding_fingerprint,
            {slice_expr} AS slice_repr,
            {depth_expr} AS depth,
            lifecycle_status,
            COALESCE({unshrunk_col}, 0.0) AS unshrunk_gap,
            COALESCE({shrunk_expr}, 0.0) AS shrunk_gap,
            COALESCE({conc_expr}, 0.0) AS concentration_ratio,
            COALESCE({boot_expr}, 0.0) AS bootstrap_stability_score,
            COALESCE({inc_expr}, 0.0) AS unique_incremental_gap
        FROM finding_records
        ORDER BY {shrunk_expr} DESC;
    """
    rows = con.execute(query).fetchall()

    findings_list = []
    active_count = 0
    dismissed_count = 0
    gross_unshrunk_sum = 0.0
    gross_shrunk_sum = 0.0

    for r in rows:
        fp = str(r[0])
        raw_slice = r[1]
        if isinstance(raw_slice, str):
            try:
                slice_dict = json.loads(raw_slice)
            except Exception:
                slice_dict = {"slice": raw_slice}
        elif isinstance(raw_slice, dict):
            slice_dict = raw_slice
        else:
            slice_dict = {"slice": str(raw_slice)}

        status = str(r[3])
        unshrunk_gap = float(r[4] or 0.0)
        shrunk_gap = float(r[5] or 0.0)

        if status != "Dismissed":
            active_count += 1
            gross_unshrunk_sum += unshrunk_gap
            gross_shrunk_sum += shrunk_gap
        else:
            dismissed_count += 1

        # Retrieve member transaction count for this finding
        tx_count_row = con.execute(
            "SELECT COUNT(*) FROM finding_transactions_map WHERE finding_fingerprint = ?",
            [fp],
        ).fetchone()
        tx_count = int(tx_count_row[0]) if tx_count_row else 0

        title_parts = [f"{k}: {v}" for k, v in slice_dict.items()]
        title = " & ".join(title_parts) if title_parts else fp

        findings_list.append({
            "finding_fingerprint": fp,
            "id": fp[:16],
            "sha256": fp,
            "title": title,
            "dimension_slice": slice_dict,
            "depth": int(r[2]),
            "lifecycle_status": status,
            "status": status,
            "unshrunk_gap_dollars": round(unshrunk_gap, 2),
            "defensibleGap": round(unshrunk_gap, 2),
            "shrunk_gap_dollars": round(shrunk_gap, 2),
            "actionableOpportunity": round(shrunk_gap * 0.40, 2),
            "concentration_ratio": round(float(r[6] or 0.0), 4),
            "concentrationRatio": round(float(r[6] or 0.0), 4),
            "bootstrap_stability_score": round(float(r[7] or 0.0), 4),
            "bootstrapStable": bool(float(r[7] or 0.0) >= 0.90),
            "unique_incremental_gap": round(float(r[8] or 0.0), 2),
            "raw_transaction_count": tx_count,
            "transactionCount": tx_count,
        })

    # Net unique portfolio exposure via set union
    net_metrics = compute_net_unique_portfolio_exposure(con, table_name=table_name)
    net_exposure = net_metrics["net_unique_portfolio_exposure"]
    net_txs = net_metrics["net_unique_transactions"]
    net_list_vol = net_metrics["net_unique_list_volume"]

    double_count = max(0.0, gross_unshrunk_sum - net_exposure)
    overlap_pct = round((double_count / gross_unshrunk_sum * 100.0), 2) if gross_unshrunk_sum > 0 else 0.0

    return {
        "status": "success",
        "findings": findings_list,
        "active_finding_count": active_count,
        "dismissed_finding_count": dismissed_count,
        "net_unique_portfolio_exposure": round(net_exposure, 2),
        "net_unique_transactions": net_txs,
        "net_unique_list_volume": round(net_list_vol, 2),
        "gross_unshrunk_gap_sum": round(gross_unshrunk_sum, 2),
        "gross_shrunk_gap_sum": round(gross_shrunk_sum, 2),
        "overlap_double_counted_dollars": round(double_count, 2),
        "overlap_pct": overlap_pct,
        "overlap_ratio_pct": overlap_pct,
    }


def get_finding_transactions(
    con: duckdb.DuckDBPyConnection,
    finding_fingerprint: str,
    table_name: str = "transactions",
) -> List[Dict[str, Any]]:
    """
    Returns transaction-level detail rows for the slide-over drawer in View 3.
    Annotates each row with active finding memberships and an is_overlap flag.
    """
    tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
    if "finding_transactions_map" not in tables or "finding_records" not in tables:
        return []

    # Check available columns in transactions table
    tx_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]

    col_acc = "account_id" if "account_id" in tx_cols else "NULL AS account_id"
    col_inv = "invoice_id" if "invoice_id" in tx_cols else "NULL AS invoice_id"
    col_date = "transaction_date" if "transaction_date" in tx_cols else "NULL AS transaction_date"
    col_list = "extended_list_amt" if "extended_list_amt" in tx_cols else "0.0 AS extended_list_amt"
    col_net = "net_invoiced_amt" if "net_invoiced_amt" in tx_cols else "0.0 AS net_invoiced_amt"
    col_disc = "realized_discount_rate" if "realized_discount_rate" in tx_cols else "0.0 AS realized_discount_rate"
    col_pf = "product_family" if "product_family" in tx_cols else "NULL AS product_family"
    col_reg = "sales_region" if "sales_region" in tx_cols else "NULL AS sales_region"
    col_p75 = "threshold_concession" if "threshold_concession" in tx_cols else (
        "p75_concession" if "p75_concession" in tx_cols else "0.0 AS threshold_concession"
    )

    query = f"""
        SELECT 
            t.transaction_line_id,
            {col_inv},
            {col_acc},
            {col_date},
            {col_list},
            {col_net},
            {col_disc},
            t.defensible_gap,
            {col_pf},
            {col_reg},
            {col_p75},
            ftm.allocated_defensible_gap
        FROM {table_name} t
        JOIN finding_transactions_map ftm ON t.transaction_line_id = ftm.transaction_line_id
        WHERE ftm.finding_fingerprint = ?
        ORDER BY t.defensible_gap DESC;
    """
    rows = con.execute(query, [finding_fingerprint]).fetchall()

    if not rows:
        return []

    # Get multi-finding memberships for all transactions in this finding
    tx_ids = [r[0] for r in rows]
    placeholders = ", ".join(["?"] * len(tx_ids))
    memberships_query = f"""
        SELECT 
            ftm.transaction_line_id,
            LIST(DISTINCT ftm.finding_fingerprint) AS all_findings
        FROM finding_transactions_map ftm
        JOIN finding_records fr ON ftm.finding_fingerprint = fr.finding_fingerprint
        WHERE ftm.transaction_line_id IN ({placeholders})
          AND fr.lifecycle_status != 'Dismissed'
        GROUP BY ftm.transaction_line_id;
    """
    membership_rows = con.execute(memberships_query, tx_ids).fetchall()
    memberships_map: Dict[str, List[str]] = {r[0]: r[1] for r in membership_rows}

    detail_rows = []
    for r in rows:
        tx_id = str(r[0])
        all_fps = memberships_map.get(tx_id, [finding_fingerprint])
        other_fps = [f for f in all_fps if f != finding_fingerprint]
        is_overlap = len(other_fps) > 0

        list_price = float(r[4] or 0.0)
        net_invoiced = float(r[5] or 0.0)
        disc_rate = float(r[6] or 0.0)
        gap = float(r[7] or 0.0)
        p75 = float(r[10] or 0.0)

        detail_rows.append({
            "transaction_line_id": tx_id,
            "line_id": tx_id,
            "invoice_id": str(r[1] or ""),
            "account_id": str(r[2] or ""),
            "transaction_date": str(r[3] or ""),
            "extended_list_amt": list_price,
            "list_price": list_price,
            "net_invoiced_amt": net_invoiced,
            "net_invoiced": net_invoiced,
            "realized_discount_rate": disc_rate,
            "discount_pct": round(disc_rate * 100.0, 2),
            "defensible_gap": gap,
            "product_family": str(r[8] or ""),
            "sales_region": str(r[9] or ""),
            "region": str(r[9] or ""),
            "cohort_p75": round(p75 * 100.0, 2),
            "allocated_defensible_gap": float(r[11] or gap),
            "other_findings": other_fps,
            "is_overlap": is_overlap,
            "total_active_finding_memberships": len(all_fps),
        })

    return detail_rows


def record_findings_to_db(
    con: duckdb.DuckDBPyConnection,
    findings: List[Dict[str, Any]],
    calibration_id: str = "CALIB-DEFAULT",
    table_name: str = "transactions",
) -> None:
    """
    Idempotently persists finding records and transaction line mappings into DuckDB.
    """
    if not findings:
        return

    for f in findings:
        fp = f["finding_fingerprint"]
        dim_slice_json = json.dumps(f["dimension_slice"])
        depth = int(f.get("depth", 1))
        tx_count = int(f.get("raw_transaction_count", len(f.get("transaction_ids", []))))
        acct_count = int(f.get("distinct_account_count", 1))
        list_vol = float(f.get("gross_list_volume", 0.0))
        unshrunk_gap = float(f.get("unshrunk_gap_dollars", 0.0))
        shrunk_gap = float(f.get("shrunk_gap_dollars", unshrunk_gap))
        conc_ratio = float(f.get("concentration_ratio", 0.0))
        stability_score = float(f.get("bootstrap_stability_score", 1.0))
        ci_lower = float(f.get("bootstrap_ci_lower", 0.0))
        ci_upper = float(f.get("bootstrap_ci_upper", 0.0))
        p_val = float(f.get("fdr_p_value", 0.0))
        q_val = float(f.get("fdr_q_value", p_val))
        rejected = bool(f.get("fdr_rejected", True))
        inc_gap = float(f.get("unique_incremental_gap", unshrunk_gap))
        target_recovery = round(shrunk_gap * 0.40, 2)

        con.execute(
            """
            INSERT OR REPLACE INTO finding_records (
                finding_fingerprint, calibration_id, depth, dimension_slice_json,
                raw_transaction_count, distinct_account_count, gross_list_volume,
                unshrunk_gap_dollars, shrunk_gap_dollars, concentration_ratio,
                bootstrap_stability_score, bootstrap_ci_lower, bootstrap_ci_upper,
                fdr_p_value, fdr_q_value, fdr_rejected, unique_incremental_gap,
                lifecycle_status, action_target_recovery, evidence_tier,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'New', ?, 'Tier 1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            );
            """,
            [
                fp, calibration_id, depth, dim_slice_json,
                tx_count, acct_count, list_vol,
                unshrunk_gap, shrunk_gap, conc_ratio,
                stability_score, ci_lower, ci_upper,
                p_val, q_val, rejected, inc_gap,
                target_recovery,
            ]
        )

        # Batch insert transaction mappings
        tx_ids = f.get("transaction_ids", [])
        if tx_ids:
            # Check if defensible_gap column exists on transactions
            tx_cols = [c[1] for c in con.execute(f"PRAGMA table_info('{table_name}');").fetchall()]
            gap_col = "defensible_gap" if "defensible_gap" in tx_cols else "0.0"

            # Query the gaps for these transaction IDs
            placeholders = ", ".join(["?"] * len(tx_ids))
            gap_rows = con.execute(
                f"SELECT transaction_line_id, {gap_col} FROM {table_name} WHERE transaction_line_id IN ({placeholders});",
                tx_ids,
            ).fetchall()

            mappings = []
            for tid, tgap in gap_rows:
                mappings.append([fp, str(tid), float(tgap or 0.0)])

            # Bulk insert mappings
            if mappings:
                con.executemany(
                    """
                    INSERT OR REPLACE INTO finding_transactions_map (
                        finding_fingerprint, transaction_line_id, allocated_defensible_gap
                    ) VALUES (?, ?, ?);
                    """,
                    mappings,
                )
