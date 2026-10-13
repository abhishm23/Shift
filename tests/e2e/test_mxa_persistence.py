"""
AC-7: Single-File .mxa Workspace Persistence Test.

Authoritative Requirement:
Project workspaces save and reload from single .mxa files preserving all state,
findings, calibration profiles, and audit manifests.
(ORIGINAL_REQUEST.md § User Interface & Persistence Invariants, PROJECT.md R1.8, spec_report.md AC-7).
"""

import json
import os
import duckdb
import pytest

from tests.synthetic_data import generate_50k_canonical_dataset


def init_canonical_mxa_schema(con: duckdb.DuckDBPyConnection):
    """Initializes the 8 canonical relational tables in the .mxa database container."""
    con.execute("""
        CREATE TABLE meta_project (
            project_id VARCHAR PRIMARY KEY,
            project_name VARCHAR NOT NULL,
            schema_version VARCHAR NOT NULL,
            reporting_currency VARCHAR(3) NOT NULL,
            integrity_mode VARCHAR NOT NULL DEFAULT 'production'
        );

        CREATE TABLE meta_audit_manifest (
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
            manifest_json JSON NOT NULL
        );

        CREATE TABLE meta_calibration_profiles (
            calibration_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            threshold_strategy VARCHAR NOT NULL,
            haircut_kappa DECIMAL(6, 4) NOT NULL,
            calibration_json JSON NOT NULL,
            is_locked BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            invoice_id VARCHAR NOT NULL,
            account_id VARCHAR NOT NULL,
            extended_list_amt DECIMAL(18, 4) NOT NULL,
            net_invoiced_amt DECIMAL(18, 4) NOT NULL,
            defensible_gap DECIMAL(18, 4) NOT NULL
        );

        CREATE TABLE quarantined_transactions (
            quarantine_id VARCHAR PRIMARY KEY,
            transaction_line_id VARCHAR,
            quarantine_reason VARCHAR NOT NULL
        );

        CREATE TABLE finding_records (
            finding_fingerprint VARCHAR(64) PRIMARY KEY,
            calibration_id VARCHAR NOT NULL,
            dimension_slice_json JSON NOT NULL,
            shrunk_gap_dollars DECIMAL(18, 4) NOT NULL,
            lifecycle_status VARCHAR NOT NULL DEFAULT 'New',
            evidence_tier VARCHAR NOT NULL DEFAULT 'Tier 1'
        );

        CREATE TABLE finding_transactions_map (
            finding_fingerprint VARCHAR(64) NOT NULL,
            transaction_line_id VARCHAR NOT NULL,
            PRIMARY KEY (finding_fingerprint, transaction_line_id)
        );

        CREATE TABLE lifecycle_audit_log (
            log_id VARCHAR PRIMARY KEY,
            finding_fingerprint VARCHAR(64) NOT NULL,
            previous_status VARCHAR NOT NULL,
            new_status VARCHAR NOT NULL,
            changed_by VARCHAR NOT NULL
        );
    """)


def test_mxa_single_file_save_and_reload(tmp_path):
    """
    AC-7: Verifies that an entire analytical project state, calibrations,
    transactions, audit manifest, and findings can be written to a single .mxa file,
    the connection closed, and reloaded with 100% data fidelity.
    """
    mxa_path = str(tmp_path / "commercial_audit_2025.mxa")

    # Step 1: Open fresh .mxa container
    con = duckdb.connect(mxa_path)
    init_canonical_mxa_schema(con)

    # Step 2: Populate all tables
    # Project metadata
    con.execute("INSERT INTO meta_project VALUES ('PROJ-01', 'FY25 Commercial Audit', '1.0.0', 'USD', 'production');")

    # Audit manifest
    manifest_doc = {
        "manifest_id": "MAN-001",
        "status": "CERTIFIED_AUDIT",
        "gross_variance_bp": 0.25,
        "net_variance_bp": 0.10,
    }
    con.execute("""
        INSERT INTO meta_audit_manifest VALUES (
            'MAN-001', 'sales_q4.csv', 'sha256_mock_hash', 1000, 1000, 0,
            1000000.0, 1000025.0, 0.25, 850000.0, 850008.5, 0.10,
            'CERTIFIED_AUDIT', FALSE, NULL, ?
        );
    """, [json.dumps(manifest_doc)])

    # Calibration profile
    calib_doc = {
        "calibration_id": "CALIB-FY25-P75",
        "name": "FY2025 Locked Calibration",
        "threshold_strategy": "P75",
        "haircut_kappa": 0.40,
    }
    con.execute("""
        INSERT INTO meta_calibration_profiles VALUES (
            'CALIB-FY25-P75', 'FY2025 Locked Calibration', 'P75', 0.40, ?, TRUE
        );
    """, [json.dumps(calib_doc)])

    # Canonical transactions (sample 500 rows)
    df, meta = generate_50k_canonical_dataset(n_rows=500, seed=42, inject_exceptions=True)
    for _, row in df.iterrows():
        gap = meta.planted_defensible_gaps.get(row["transaction_line_id"], 0.0)
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?);",
            [row["transaction_line_id"], row["invoice_id"], row["account_id"],
             row["extended_list_amt"], row["net_invoiced_amt"], gap]
        )

    # Findings
    con.execute("""
        INSERT INTO finding_records VALUES (
            'FP-ROGUE-001', 'CALIB-FY25-P75', '{"sales_rep": "Rep_Rogue"}', 45000.00, 'New', 'Tier 1'
        );
    """)
    for lid in meta.planted_line_ids:
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-ROGUE-001', ?);", [lid])

    # Lifecycle audit log
    con.execute("INSERT INTO lifecycle_audit_log VALUES ('LOG-1', 'FP-ROGUE-001', 'None', 'New', 'system');")

    # Step 3: Close connection and verify single-file persistence on disk
    con.close()
    del con

    assert os.path.exists(mxa_path), ".mxa file must exist on disk"
    assert os.path.getsize(mxa_path) > 0, ".mxa file must not be empty"

    # Step 4: Re-open fresh connection from .mxa path and assert exact fidelity
    reloaded_con = duckdb.connect(mxa_path)

    # Verify project metadata
    proj_row = reloaded_con.execute("SELECT project_id, project_name, schema_version FROM meta_project;").fetchone()
    assert proj_row == ("PROJ-01", "FY25 Commercial Audit", "1.0.0")

    # Verify manifest
    manifest_row = reloaded_con.execute("SELECT manifest_id, reconciliation_status, gross_variance_bp FROM meta_audit_manifest;").fetchone()
    assert (manifest_row[0], manifest_row[1], float(manifest_row[2])) == ("MAN-001", "CERTIFIED_AUDIT", 0.25)

    # Verify calibration
    calib_row = reloaded_con.execute("SELECT calibration_id, threshold_strategy, haircut_kappa, is_locked FROM meta_calibration_profiles;").fetchone()
    assert (calib_row[0], calib_row[1], float(calib_row[2]), calib_row[3]) == ("CALIB-FY25-P75", "P75", 0.40, True)

    # Verify transactions row count
    tx_count = reloaded_con.execute("SELECT COUNT(*) FROM transactions;").fetchone()[0]
    assert tx_count == 500, f"Expected 500 transactions, got {tx_count}"

    # Verify finding and transaction mappings
    finding_row = reloaded_con.execute("SELECT finding_fingerprint, shrunk_gap_dollars, lifecycle_status FROM finding_records;").fetchone()
    assert (finding_row[0], float(finding_row[1]), finding_row[2]) == ("FP-ROGUE-001", 45000.00, "New")

    mapped_count = reloaded_con.execute("SELECT COUNT(*) FROM finding_transactions_map WHERE finding_fingerprint = 'FP-ROGUE-001';").fetchone()[0]
    assert mapped_count == 15, f"Expected 15 mapped planted transactions, got {mapped_count}"

    # Step 5: Test ACID state mutation and reload
    reloaded_con.execute("UPDATE finding_records SET lifecycle_status = 'In Review' WHERE finding_fingerprint = 'FP-ROGUE-001';")
    reloaded_con.close()
    del reloaded_con

    # Re-open third time to verify state mutation persisted
    final_con = duckdb.connect(mxa_path)
    updated_status = final_con.execute("SELECT lifecycle_status FROM finding_records WHERE finding_fingerprint = 'FP-ROGUE-001';").fetchone()[0]
    assert updated_status == "In Review", "Updated lifecycle status must persist across sessions"
    final_con.close()
