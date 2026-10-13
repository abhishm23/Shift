"""
Sift Single-File .mxa Workspace Storage Engine
Manages DuckDB in-process analytical persistence, 8 core relational tables,
lifecycle checkpoints, cross-workspace attachment, and binary header validation.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import duckdb

from backend.config import DuckDBConfig

# The 8 canonical tables required in every Sift .mxa workspace container
CORE_TABLES = [
    "meta_project",
    "meta_audit_manifest",
    "meta_calibration_profiles",
    "transactions",
    "quarantined_transactions",
    "finding_records",
    "finding_transactions_map",
    "lifecycle_audit_log",
]

# Canonical DDL for all 8 tables and indices
# CRITICAL NOTE: DuckDB 1.0 does NOT support ON DELETE CASCADE or foreign key cascade actions.
# Foreign keys must use standard REFERENCES table(column).
SCHEMA_DDL = """
-- 1. Project Metadata
CREATE TABLE IF NOT EXISTS meta_project (
    project_id VARCHAR PRIMARY KEY,
    project_name VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    schema_version VARCHAR NOT NULL,
    reporting_currency VARCHAR(3) NOT NULL,
    integrity_mode VARCHAR NOT NULL DEFAULT 'production'
);

-- 2. Immutable Audit Manifest Table
CREATE TABLE IF NOT EXISTS meta_audit_manifest (
    manifest_id VARCHAR PRIMARY KEY,
    source_filename VARCHAR NOT NULL,
    source_sha256 VARCHAR NOT NULL,
    total_rows_scanned BIGINT NOT NULL,
    total_rows_ingested BIGINT NOT NULL,
    total_rows_quarantined BIGINT NOT NULL,
    confirmed_gross_list DECIMAL(18, 4) NOT NULL,
    ingested_gross_list DECIMAL(18, 4) NOT NULL,
    gross_variance_bp DECIMAL(10, 4) NOT NULL,
    confirmed_net_invoiced DECIMAL(18, 4) NOT NULL,
    ingested_net_invoiced DECIMAL(18, 4) NOT NULL,
    net_variance_bp DECIMAL(10, 4) NOT NULL,
    reconciliation_status VARCHAR NOT NULL,
    watermark_active BOOLEAN NOT NULL DEFAULT FALSE,
    watermark_text VARCHAR,
    sign_off_user VARCHAR,
    sign_off_notes VARCHAR,
    manifest_json JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Versioned Calibration Profiles
CREATE TABLE IF NOT EXISTS meta_calibration_profiles (
    calibration_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    historical_start_date DATE NOT NULL,
    historical_end_date DATE NOT NULL,
    comparability_controls VARCHAR[] NOT NULL,
    investigation_dimensions VARCHAR[] NOT NULL,
    threshold_strategy VARCHAR NOT NULL,
    mad_multiplier DECIMAL(6, 2) DEFAULT 1.5,
    haircut_kappa DECIMAL(6, 4) DEFAULT 0.40,
    min_transactions INTEGER DEFAULT 10,
    min_distinct_accounts INTEGER DEFAULT 5,
    calibration_json JSON NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT TRUE
);

-- 4. Canonical Transactions Table (11 Canonical Fields + Reporting Derivations)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_line_id VARCHAR PRIMARY KEY,
    invoice_id VARCHAR NOT NULL,
    account_id VARCHAR NOT NULL,
    parent_account_id VARCHAR,
    transaction_date DATE NOT NULL,
    currency VARCHAR(3) NOT NULL,
    fx_rate_to_reporting DECIMAL(18, 6) NOT NULL,
    extended_list_amt DECIMAL(18, 4) NOT NULL,
    net_invoiced_amt DECIMAL(18, 4) NOT NULL,
    cogs_amt DECIMAL(18, 4),
    off_invoice_rebate DECIMAL(18, 4),
    reporting_list_amt DECIMAL(18, 4) NOT NULL,
    reporting_invoiced_amt DECIMAL(18, 4) NOT NULL,
    reporting_cogs_amt DECIMAL(18, 4),
    reporting_rebate_amt DECIMAL(18, 4),
    realized_discount_rate DECIMAL(10, 6) NOT NULL,
    defensible_gap DECIMAL(18, 4) DEFAULT 0.0,
    is_credit_reversal BOOLEAN NOT NULL DEFAULT FALSE,
    dimension_attributes JSON
);

CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(transaction_date);

-- 5. Quarantined Residual Transactions
CREATE TABLE IF NOT EXISTS quarantined_transactions (
    quarantine_id VARCHAR PRIMARY KEY,
    transaction_line_id VARCHAR,
    raw_record_json JSON NOT NULL,
    quarantine_reason VARCHAR NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Finding Records (Ranked Slices Scored by Beam Search)
CREATE TABLE IF NOT EXISTS finding_records (
    finding_fingerprint VARCHAR(64) PRIMARY KEY,
    calibration_id VARCHAR NOT NULL REFERENCES meta_calibration_profiles(calibration_id),
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

-- 7. Overlap Inverted Map (Transaction -> Finding Membership)
CREATE TABLE IF NOT EXISTS finding_transactions_map (
    finding_fingerprint VARCHAR(64) NOT NULL REFERENCES finding_records(finding_fingerprint),
    transaction_line_id VARCHAR NOT NULL REFERENCES transactions(transaction_line_id),
    allocated_defensible_gap DECIMAL(18, 4) NOT NULL,
    PRIMARY KEY (finding_fingerprint, transaction_line_id)
);

CREATE INDEX IF NOT EXISTS idx_map_tx ON finding_transactions_map(transaction_line_id);

-- 8. Lifecycle Audit Log
CREATE TABLE IF NOT EXISTS lifecycle_audit_log (
    log_id VARCHAR PRIMARY KEY,
    finding_fingerprint VARCHAR(64) NOT NULL REFERENCES finding_records(finding_fingerprint),
    previous_status VARCHAR NOT NULL,
    new_status VARCHAR NOT NULL,
    changed_by VARCHAR NOT NULL,
    disposition_code VARCHAR,
    notes VARCHAR,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""


def init_schema(
    con: duckdb.DuckDBPyConnection,
    project_name: str = "Sift Project",
    reporting_currency: str = "USD",
    schema_version: str = "1.0.0",
    integrity_mode: str = "production",
) -> None:
    """
    Idempotently creates all 8 core relational tables and indices.
    If meta_project is empty, inserts initial project metadata.
    If meta_project exists and custom project parameters are supplied, updates the record.
    """
    con.execute(SCHEMA_DDL)

    existing = con.execute("SELECT COUNT(*) FROM meta_project").fetchone()[0]
    if existing == 0:
        proj_id = f"PROJ-{uuid.uuid4().hex[:8].upper()}"
        con.execute(
            """
            INSERT INTO meta_project (
                project_id, project_name, schema_version, reporting_currency, integrity_mode
            ) VALUES (?, ?, ?, ?, ?);
            """,
            [proj_id, project_name, schema_version, reporting_currency, integrity_mode],
        )
    else:
        if project_name != "Sift Project" or reporting_currency != "USD":
            con.execute(
                """
                UPDATE meta_project
                SET project_name = ?, reporting_currency = ?, integrity_mode = ?, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = (SELECT project_id FROM meta_project ORDER BY created_at ASC LIMIT 1);
                """,
                [project_name, reporting_currency, integrity_mode],
            )


def open_workspace(
    path: str,
    config: Optional[DuckDBConfig] = None,
    read_only: bool = False,
    project_name: str = "Sift Project",
    reporting_currency: str = "USD",
) -> duckdb.DuckDBPyConnection:
    """
    Opens an existing .mxa workspace file or creates a new one.
    Configures max_memory='4GB', temp_directory for disk-spilling, threads, and concurrency pragmas.
    If opening in read-write mode and schema is uninitialized, initializes the 8 core tables.
    """
    if config is None:
        config = DuckDBConfig()

    # Ensure parent directory exists for file-backed databases
    if path != ":memory:":
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    connect_kwargs = config.to_connect_config()
    con = duckdb.connect(
        database=path,
        read_only=read_only,
        config=connect_kwargs,
    )

    # Enforce pragmas explicitly
    config.apply_to_connection(con)

    # If opening in read-write mode, ensure schema exists
    if not read_only:
        tables = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        ]
        if "meta_project" not in tables:
            init_schema(
                con,
                project_name=project_name,
                reporting_currency=reporting_currency,
            )

    return con


def create_workspace(
    path: str,
    project_name: str = "Sift Project",
    reporting_currency: str = "USD",
    integrity_mode: str = "production",
    config: Optional[DuckDBConfig] = None,
) -> duckdb.DuckDBPyConnection:
    """
    Creates a new .mxa workspace file, initializes all 8 core tables,
    populates project metadata, checkpoints WAL, and returns connection.
    """
    con = open_workspace(
        path,
        config=config,
        read_only=False,
        project_name=project_name,
        reporting_currency=reporting_currency,
    )
    init_schema(
        con,
        project_name=project_name,
        reporting_currency=reporting_currency,
        integrity_mode=integrity_mode,
    )
    checkpoint_workspace(con)
    return con


def checkpoint_workspace(con: duckdb.DuckDBPyConnection) -> None:
    """
    Executes CHECKPOINT to flush write-ahead log (WAL) pages to the single .mxa file.
    """
    con.execute("CHECKPOINT;")


def save_workspace(con: duckdb.DuckDBPyConnection) -> None:
    """
    Alias for checkpoint_workspace: ensures durability on disk.
    """
    checkpoint_workspace(con)


def close_workspace(con: duckdb.DuckDBPyConnection) -> None:
    """
    Safely checkpoints WAL and closes the DuckDB database connection.
    """
    try:
        con.execute("CHECKPOINT;")
    except Exception:
        pass
    finally:
        con.close()


def attach_workspace(
    con: duckdb.DuckDBPyConnection,
    path: str,
    alias: str,
    read_only: bool = True,
) -> None:
    """
    Attaches an external .mxa file into the active connection under an alias.
    Enables cross-project diffing, run-over-run comparisons, and baseline imports.
    """
    norm_path = os.path.abspath(path).replace("\\", "/")
    mode = "(READ_ONLY)" if read_only else "(READ_WRITE)"
    con.execute(f"ATTACH '{norm_path}' AS {alias} {mode};")


def detach_workspace(
    con: duckdb.DuckDBPyConnection,
    alias: str,
) -> None:
    """
    Detaches the specified workspace alias from the active connection.
    """
    con.execute(f"DETACH {alias};")


def get_workspace_meta(con: duckdb.DuckDBPyConnection) -> Dict[str, Any]:
    """
    Retrieves project metadata, audit manifest reconciliation status, watermark flag,
    and active calibration profile ID.
    """
    result: Dict[str, Any] = {
        "project_id": None,
        "project_name": "Untitled Project",
        "schema_version": "1.0.0",
        "reporting_currency": "USD",
        "integrity_mode": "production",
        "audit_status": "Unreconciled",
        "watermark_active": False,
        "watermark_text": None,
        "active_calibration_id": None,
        "active_calibration_name": None,
    }

    try:
        proj_row = con.execute(
            """
            SELECT project_id, project_name, schema_version, reporting_currency, integrity_mode
            FROM meta_project
            ORDER BY created_at ASC
            LIMIT 1;
            """
        ).fetchone()
        if proj_row:
            result["project_id"] = proj_row[0]
            result["project_name"] = proj_row[1]
            result["schema_version"] = proj_row[2]
            result["reporting_currency"] = proj_row[3]
            result["integrity_mode"] = proj_row[4]
    except Exception:
        pass

    try:
        manifest_row = con.execute(
            """
            SELECT manifest_id, reconciliation_status, watermark_active, watermark_text
            FROM meta_audit_manifest
            ORDER BY created_at DESC
            LIMIT 1;
            """
        ).fetchone()
        if manifest_row:
            result["audit_status"] = manifest_row[1]
            result["watermark_active"] = bool(manifest_row[2])
            result["watermark_text"] = manifest_row[3]
    except Exception:
        pass

    try:
        calib_row = con.execute(
            """
            SELECT calibration_id, name
            FROM meta_calibration_profiles
            ORDER BY created_at DESC
            LIMIT 1;
            """
        ).fetchone()
        if calib_row:
            result["active_calibration_id"] = calib_row[0]
            result["active_calibration_name"] = calib_row[1]
    except Exception:
        pass

    return result


def verify_workspace_integrity(
    path: str,
    check_tables: bool = True,
    details: bool = False,
) -> Union[bool, Dict[str, Any]]:
    """
    Verifies the binary and structural integrity of an .mxa workspace container:
    1. Checks file existence and non-zero size.
    2. Validates DuckDB binary magic header (offset 8..12 == b'DUCK').
    3. If check_tables=True, opens read-only connection and asserts all 8 core tables exist.

    If details is False (default): returns bool (True if valid, False otherwise).
    If details is True: returns detailed status dictionary.
    """
    detail_res: Dict[str, Any] = {
        "valid": False,
        "file_path": path,
        "file_size_bytes": 0,
        "magic": None,
        "tables_found": [],
        "missing_tables": CORE_TABLES.copy(),
        "error": None,
    }

    if not os.path.isfile(path):
        detail_res["error"] = f"File does not exist: {path}"
        return detail_res if details else False

    try:
        size = os.path.getsize(path)
        detail_res["file_size_bytes"] = size
        if size < 12:
            detail_res["error"] = f"File too small ({size} bytes), must be at least 12 bytes"
            return detail_res if details else False

        with open(path, "rb") as f:
            f.seek(8)
            magic = f.read(4)
            detail_res["magic"] = magic.decode("latin1", errors="replace")
            if magic != b"DUCK":
                detail_res["error"] = f"Invalid magic bytes at offset 8..12: {magic!r}, expected b'DUCK'"
                return detail_res if details else False

        if check_tables:
            temp_con = duckdb.connect(database=path, read_only=True)
            try:
                found = [
                    r[0]
                    for r in temp_con.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                    ).fetchall()
                ]
                detail_res["tables_found"] = sorted(found)
                missing = [tbl for tbl in CORE_TABLES if tbl not in found]
                detail_res["missing_tables"] = missing
                if missing:
                    detail_res["error"] = f"Missing core tables: {missing}"
                    return detail_res if details else False
            finally:
                temp_con.close()

        detail_res["valid"] = True
        return detail_res if details else True

    except Exception as e:
        detail_res["error"] = str(e)
        return detail_res if details else False
