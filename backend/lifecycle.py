"""
Milestone 6: Finding Lifecycle State Machine, SHA-256 Fingerprinting,
Punitive Code Lockout (AC-9), Governance Auditing, and Run-over-Run Diffing.
"""

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
import duckdb

VALID_LIFECYCLE_STATES: Set[str] = {
    "New",
    "Assigned",
    "In Review",
    "Dismissed",
    "Actioned",
}

PUNITIVE_DISPOSITION_CODES: Set[str] = {
    "Unapproved Concession",
    "Unauthorized Deal",
    "Policy Breach",
}

VALID_DISMISSAL_CATEGORIES: Set[str] = {
    "Strategic Investment",
    "Volume Tiering Justification",
    "Data Classification Defect",
    "Statistical Anomaly",
    "Market Alignment",
    "Customer Volume Justified",
    "Legacy Contract Terms",
    "Pre-Approved Override",
}


def compute_finding_fingerprint(
    slice_dims: Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
    calib_id: str = "",
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint identifying a finding slice.
    Fingerprint = SHA256(CanonicalJson(slice_dims) + CanonicalJson(filters) + calib_id)
    """
    canonical_payload = {
        "slice_dims": {k: str(v) for k, v in sorted(slice_dims.items())},
        "filters": {k: str(v) for k, v in sorted((filters or {}).items())},
        "calib_id": str(calib_id).strip(),
    }
    encoded = json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_finding_transition(
    evidence_tier: str,
    new_state: str,
    disposition_code: Optional[str] = None,
    dismissal_category: Optional[str] = None,
    snooze_date: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validates finding lifecycle state transitions according to R6.2, R6.3, R6.4, and AC-9.
    - Programmatically disables punitive disposition codes on Tiers 1-2.
    - Punitive codes are permitted ONLY on Tier 3 Rule-Confirmed Exceptions.
    - Requires mandatory dismissal category and snooze/expiry date on Dismissed state.
    """
    if new_state not in VALID_LIFECYCLE_STATES:
        return False, f"Invalid target state: {new_state}. Allowed: {sorted(VALID_LIFECYCLE_STATES)}"

    # AC-9 Punitive Disposition Code Lockdown
    if disposition_code in PUNITIVE_DISPOSITION_CODES:
        clean_tier = str(evidence_tier).strip()
        is_tier_3 = clean_tier in ("Tier 3", "Tier 3 (Rule-Confirmed Exception)", "Tier 3 Policy Compliance")
        if not is_tier_3:
            return False, (
                f"Punitive disposition code '{disposition_code}' is locked for {evidence_tier}. "
                "Only permitted for Tier 3 Rule-Confirmed Exceptions."
            )

    # Dismissal Governance Invariant
    if new_state == "Dismissed":
        if not dismissal_category or dismissal_category not in VALID_DISMISSAL_CATEGORIES:
            return False, (
                f"Mandatory valid dismissal category required for dismissal. "
                f"Got: '{dismissal_category}'. Allowed: {sorted(VALID_DISMISSAL_CATEGORIES)}"
            )
        if not snooze_date or not str(snooze_date).strip():
            return False, "Mandatory snooze/expiry date required for dismissal."

    return True, "Valid transition"


def transition_finding(
    con: duckdb.DuckDBPyConnection,
    finding_fingerprint: str,
    new_state: str,
    disposition_code: Optional[str] = None,
    dismissal_category: Optional[str] = None,
    snooze_date: Optional[str] = None,
    assigned_owner: Optional[str] = None,
    notes: Optional[str] = None,
    user: str = "auditor",
) -> Dict[str, Any]:
    """
    Applies a validated lifecycle state transition to a finding record,
    enforcing AC-9 punitive lockout, and inserts a relational audit trail entry
    into lifecycle_audit_log.
    """
    row = con.execute(
        """
        SELECT finding_fingerprint, lifecycle_status, evidence_tier, assigned_owner,
               dismissal_category, dismissal_snooze_date
        FROM finding_records
        WHERE finding_fingerprint = ?
        """,
        [finding_fingerprint],
    ).fetchone()

    if not row:
        raise ValueError(f"Finding record '{finding_fingerprint}' not found in workspace.")

    current_status = row[1]
    evidence_tier = row[2] or "Tier 1"

    valid, error_msg = validate_finding_transition(
        evidence_tier=evidence_tier,
        new_state=new_state,
        disposition_code=disposition_code,
        dismissal_category=dismissal_category,
        snooze_date=snooze_date,
    )

    if not valid:
        raise ValueError(error_msg)

    final_owner = assigned_owner if assigned_owner is not None else row[3]
    final_category = dismissal_category if new_state == "Dismissed" else row[4]
    final_snooze = snooze_date if new_state == "Dismissed" else row[5]

    con.execute(
        """
        UPDATE finding_records
        SET lifecycle_status = ?,
            assigned_owner = ?,
            dismissal_category = ?,
            dismissal_snooze_date = TRY_CAST(? AS DATE),
            updated_at = CURRENT_TIMESTAMP
        WHERE finding_fingerprint = ?
        """,
        [new_state, final_owner, final_category, final_snooze, finding_fingerprint],
    )

    log_id = str(uuid.uuid4())
    con.execute(
        """
        INSERT INTO lifecycle_audit_log (
            log_id, finding_fingerprint, previous_status, new_status, changed_by,
            disposition_code, notes, logged_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            log_id,
            finding_fingerprint,
            current_status,
            new_state,
            user,
            disposition_code,
            notes or "",
        ],
    )

    return {
        "finding_fingerprint": finding_fingerprint,
        "previous_status": current_status,
        "new_status": new_state,
        "evidence_tier": evidence_tier,
        "disposition_code": disposition_code,
        "dismissal_category": final_category,
        "dismissal_snooze_date": str(final_snooze) if final_snooze else None,
        "assigned_owner": final_owner,
        "changed_by": user,
        "log_id": log_id,
    }


def get_finding_history(
    con: duckdb.DuckDBPyConnection,
    finding_fingerprint: str,
) -> List[Dict[str, Any]]:
    """Returns the complete immutable audit history for a finding."""
    rows = con.execute(
        """
        SELECT log_id, finding_fingerprint, previous_status, new_status,
               changed_by, disposition_code, notes, logged_at
        FROM lifecycle_audit_log
        WHERE finding_fingerprint = ?
        ORDER BY logged_at ASC
        """,
        [finding_fingerprint],
    ).fetchall()

    history = []
    for r in rows:
        history.append({
            "log_id": r[0],
            "finding_fingerprint": r[1],
            "previous_status": r[2],
            "new_status": r[3],
            "changed_by": r[4],
            "disposition_code": r[5],
            "notes": r[6],
            "logged_at": str(r[7]),
        })
    return history


def diff_audit_runs(
    con_historical: duckdb.DuckDBPyConnection,
    con_current: duckdb.DuckDBPyConnection,
) -> Dict[str, Any]:
    """
    Compares two sequential project workspace runs to classify findings into:
    - New: Fingerprints appearing for the first time in current period.
    - Persisting / Growing: Fingerprints in both where current exposure >= historical.
    - Resolved / Narrowed: Fingerprints in historical but contracted/absent in current.
    - Benefit Realization: Track realized recovery by measuring gap reductions on repeating accounts.
    """
    hist_rows = con_historical.execute(
        """
        SELECT finding_fingerprint, shrunk_gap_dollars, gross_list_volume,
               distinct_account_count, dimension_slice_json, lifecycle_status
        FROM finding_records
        """
    ).fetchall()

    curr_rows = con_current.execute(
        """
        SELECT finding_fingerprint, shrunk_gap_dollars, gross_list_volume,
               distinct_account_count, dimension_slice_json, lifecycle_status
        FROM finding_records
        """
    ).fetchall()

    hist_map = {r[0]: {"gap": float(r[1]), "volume": float(r[2]), "accounts": r[3], "slice": r[4], "status": r[5]} for r in hist_rows}
    curr_map = {r[0]: {"gap": float(r[1]), "volume": float(r[2]), "accounts": r[3], "slice": r[4], "status": r[5]} for r in curr_rows}

    new_findings = []
    persisting_growing = []
    resolved_narrowed = []

    for fp, curr_data in curr_map.items():
        if fp not in hist_map:
            new_findings.append({
                "finding_fingerprint": fp,
                "current_gap": curr_data["gap"],
                "dimension_slice": curr_data["slice"],
                "status": "New",
            })
        else:
            hist_data = hist_map[fp]
            gap_delta = curr_data["gap"] - hist_data["gap"]
            if gap_delta >= 0:
                persisting_growing.append({
                    "finding_fingerprint": fp,
                    "historical_gap": hist_data["gap"],
                    "current_gap": curr_data["gap"],
                    "gap_delta": gap_delta,
                    "dimension_slice": curr_data["slice"],
                    "status": "Growing" if gap_delta > 0.01 else "Persisting",
                })
            else:
                resolved_narrowed.append({
                    "finding_fingerprint": fp,
                    "historical_gap": hist_data["gap"],
                    "current_gap": curr_data["gap"],
                    "gap_reduction": abs(gap_delta),
                    "dimension_slice": curr_data["slice"],
                    "status": "Narrowed",
                })

    for fp, hist_data in hist_map.items():
        if fp not in curr_map:
            resolved_narrowed.append({
                "finding_fingerprint": fp,
                "historical_gap": hist_data["gap"],
                "current_gap": 0.0,
                "gap_reduction": hist_data["gap"],
                "dimension_slice": hist_data["slice"],
                "status": "Resolved",
            })

    total_realized_recovery = sum(item.get("gap_reduction", 0.0) for item in resolved_narrowed)

    return {
        "summary": {
            "new_count": len(new_findings),
            "persisting_growing_count": len(persisting_growing),
            "resolved_narrowed_count": len(resolved_narrowed),
            "total_realized_recovery_dollars": round(total_realized_recovery, 2),
        },
        "new_findings": new_findings,
        "persisting_growing": persisting_growing,
        "resolved_narrowed": resolved_narrowed,
    }
