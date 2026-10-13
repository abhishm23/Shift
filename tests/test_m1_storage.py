"""
Milestone 1 Test Suite: Storage & In-Process DuckDB Engine
Validates memory boundaries (4GB), disk spilling temp directory, 8-table DDL,
relational constraints (PK/FK), binary DUCK magic header, persistence, attach/detach,
and concurrency locking.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
import pytest
import duckdb

from backend.config import DuckDBConfig
from backend.storage import (
    CORE_TABLES,
    open_workspace,
    create_workspace,
    init_schema,
    get_workspace_meta,
    checkpoint_workspace,
    save_workspace,
    close_workspace,
    attach_workspace,
    detach_workspace,
    verify_workspace_integrity,
)


def test_duckdb_config_pragmas(temp_workspace_dir):
    """Verifies that DuckDBConfig properly applies 4GB memory ceiling and spill directory."""
    spill_dir = os.path.join(temp_workspace_dir, "test_spill")
    cfg = DuckDBConfig(max_memory="4GB", temp_directory=spill_dir, threads=4)

    con = duckdb.connect(":memory:", config=cfg.to_connect_config())
    try:
        cfg.apply_to_connection(con)

        # In DuckDB 1.0 64-bit, 4GB limit is reported as 3.7 GiB (4 * 1024^3 bytes)
        max_mem = con.execute("SELECT current_setting('max_memory')").fetchone()[0]
        assert "3.7 GiB" in max_mem or "4" in max_mem, f"Unexpected max_memory setting: {max_mem}"

        temp_dir = con.execute("SELECT current_setting('temp_directory')").fetchone()[0]
        assert os.path.isdir(temp_dir), f"Temp spill directory '{temp_dir}' must exist"
        assert os.path.samefile(temp_dir, spill_dir)

        threads = con.execute("SELECT current_setting('threads')").fetchone()[0]
        assert int(threads) == 4
    finally:
        con.close()


def test_init_schema_all_tables_created():
    """Verifies that init_schema creates all 8 core relational tables and indices."""
    con = duckdb.connect(":memory:")
    try:
        init_schema(con, project_name="Audit Alpha", reporting_currency="USD")

        tables = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name"
            ).fetchall()
        ]

        for req_table in CORE_TABLES:
            assert req_table in tables, f"Missing expected core table: {req_table}"
        assert len(tables) >= 8

        # Verify indices
        indices = [
            r[0]
            for r in con.execute(
                "SELECT index_name FROM duckdb_indexes() ORDER BY index_name"
            ).fetchall()
        ]
        assert "idx_tx_account" in indices
        assert "idx_tx_date" in indices
        assert "idx_map_tx" in indices
    finally:
        con.close()


def test_init_schema_idempotence():
    """Verifies that executing init_schema multiple times is idempotent and non-destructive."""
    con = duckdb.connect(":memory:")
    try:
        init_schema(con, project_name="Idempotent Test")

        # Insert test record into transactions
        con.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('TX-100', 'INV-1', 'ACC-A', '2026-01-15', 'USD', 1.0, 1000.0, 800.0, 1000.0, 800.0, 0.20);
            """
        )

        # Re-run init_schema
        init_schema(con, project_name="Idempotent Test")

        # Assert record preserved
        count = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert count == 1
    finally:
        con.close()


def test_canonical_schema_column_types():
    """Verifies canonical 11-field line-grain schema column presence and types in transactions."""
    con = duckdb.connect(":memory:")
    try:
        init_schema(con)

        cols = {
            r[0]: r[1]
            for r in con.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='transactions'"
            ).fetchall()
        }

        # 11 canonical fields
        expected_fields = [
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
        ]
        for field in expected_fields:
            assert field in cols, f"Canonical field {field} missing from transactions table"

        # Verify key types
        assert cols["transaction_date"] == "DATE"
        assert "DECIMAL" in cols["extended_list_amt"]
        assert "DECIMAL" in cols["net_invoiced_amt"]
        assert "DECIMAL" in cols["realized_discount_rate"]
    finally:
        con.close()


def test_workspace_create_and_reopen(temp_workspace_dir):
    """Verifies single-file .mxa persistence: create, write, close, and reload."""
    ws_path = os.path.join(temp_workspace_dir, "commercial_audit_fy26.mxa")

    con = create_workspace(ws_path, project_name="FY26 Commercial Audit", reporting_currency="EUR")
    try:
        con.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('LINE-001', 'INV-501', 'ACC-99', '2026-03-01', 'EUR', 1.0, 50000.0, 42000.0, 50000.0, 42000.0, 0.16);
            """
        )
        checkpoint_workspace(con)
    finally:
        close_workspace(con)

    assert os.path.isfile(ws_path)
    assert os.path.getsize(ws_path) > 0

    # Re-open workspace
    reloaded_con = open_workspace(ws_path)
    try:
        meta = get_workspace_meta(reloaded_con)
        assert meta["project_name"] == "FY26 Commercial Audit"
        assert meta["reporting_currency"] == "EUR"

        row = reloaded_con.execute(
            "SELECT transaction_line_id, net_invoiced_amt FROM transactions WHERE transaction_line_id='LINE-001'"
        ).fetchone()
        assert row == ("LINE-001", 42000.0)
    finally:
        close_workspace(reloaded_con)


def test_workspace_save_checkpoint(temp_workspace_dir):
    """Verifies that checkpoint_workspace / save_workspace commits WAL to disk for secondary readers."""
    ws_path = os.path.join(temp_workspace_dir, "checkpoint_test.mxa")

    con = create_workspace(ws_path, project_name="Checkpoint Project")
    try:
        con.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('LINE-CHK', 'INV-CHK', 'ACC-CHK', '2026-02-15', 'USD', 1.0, 100.0, 80.0, 100.0, 80.0, 0.20);
            """
        )
        save_workspace(con)
    finally:
        close_workspace(con)

    # Read back with a separate connection
    read_con = duckdb.connect(ws_path, read_only=True)
    try:
        count = read_con.execute("SELECT COUNT(*) FROM transactions WHERE transaction_line_id='LINE-CHK'").fetchone()[0]
        assert count == 1
    finally:
        read_con.close()


def test_workspace_meta_crud(temp_workspace_dir):
    """Verifies get_workspace_meta retrieves project metadata, audit manifest status, and calibration info."""
    ws_path = os.path.join(temp_workspace_dir, "meta_test.mxa")
    con = create_workspace(ws_path, project_name="Meta CRUD Test", reporting_currency="GBP")
    try:
        meta_initial = get_workspace_meta(con)
        assert meta_initial["project_name"] == "Meta CRUD Test"
        assert meta_initial["reporting_currency"] == "GBP"
        assert meta_initial["audit_status"] == "Unreconciled"
        assert meta_initial["watermark_active"] is False
        assert meta_initial["active_calibration_id"] is None

        # Insert audit manifest
        con.execute(
            """
            INSERT INTO meta_audit_manifest (
                manifest_id, source_filename, source_sha256, total_rows_scanned,
                total_rows_ingested, total_rows_quarantined, confirmed_gross_list,
                ingested_gross_list, gross_variance_bp, confirmed_net_invoiced,
                ingested_net_invoiced, net_variance_bp, reconciliation_status,
                watermark_active, watermark_text, manifest_json
            ) VALUES (
                'MAN-01', 'q1.csv', 'dummy_hash', 1000, 1000, 0,
                10000.0, 10000.0, 0.0, 8000.0, 8000.0, 0.0, 'CERTIFIED_AUDIT',
                FALSE, NULL, '{"certified": true}'
            );
            """
        )

        # Insert calibration profile
        con.execute(
            """
            INSERT INTO meta_calibration_profiles (
                calibration_id, name, historical_start_date, historical_end_date,
                comparability_controls, investigation_dimensions, threshold_strategy,
                calibration_json
            ) VALUES (
                'CALIB-2026', 'FY26 Baseline', '2025-01-01', '2025-12-31',
                ['region', 'family'], ['sales_rep'], 'P75', '{"name": "FY26 Baseline"}'
            );
            """
        )

        meta_updated = get_workspace_meta(con)
        assert meta_updated["audit_status"] == "CERTIFIED_AUDIT"
        assert meta_updated["watermark_active"] is False
        assert meta_updated["active_calibration_id"] == "CALIB-2026"
        assert meta_updated["active_calibration_name"] == "FY26 Baseline"
    finally:
        close_workspace(con)


def test_workspace_attach_and_detach(temp_workspace_dir):
    """Verifies ATTACH and DETACH for cross-workspace comparisons and baseline imports."""
    ws1_path = os.path.join(temp_workspace_dir, "ws1.mxa")
    ws2_path = os.path.join(temp_workspace_dir, "ws2.mxa")

    con1 = create_workspace(ws1_path, project_name="WS1 Project")
    try:
        con1.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('TX-1', 'INV-1', 'ACC-1', '2026-01-01', 'USD', 1.0, 1000.0, 900.0, 1000.0, 900.0, 0.10);
            """
        )
        checkpoint_workspace(con1)
    finally:
        close_workspace(con1)

    con2 = create_workspace(ws2_path, project_name="WS2 Project")
    try:
        con2.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('TX-2', 'INV-2', 'ACC-2', '2026-01-02', 'USD', 1.0, 2000.0, 1600.0, 2000.0, 1600.0, 0.20);
            """
        )
        checkpoint_workspace(con2)
    finally:
        close_workspace(con2)

    # Master connection attaching both workspaces
    master_con = duckdb.connect(":memory:")
    try:
        attach_workspace(master_con, ws1_path, "ws1_db", read_only=True)
        attach_workspace(master_con, ws2_path, "ws2_db", read_only=True)

        tx1 = master_con.execute("SELECT transaction_line_id FROM ws1_db.transactions").fetchone()[0]
        tx2 = master_con.execute("SELECT transaction_line_id FROM ws2_db.transactions").fetchone()[0]
        assert tx1 == "TX-1"
        assert tx2 == "TX-2"

        detach_workspace(master_con, "ws1_db")
        detach_workspace(master_con, "ws2_db")
    finally:
        master_con.close()


def test_primary_key_constraints():
    """Verifies that Primary Key duplicates raise duckdb.ConstraintException."""
    con = duckdb.connect(":memory:")
    try:
        init_schema(con)

        con.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('DUP-01', 'INV-1', 'ACC-1', '2026-01-01', 'USD', 1.0, 100.0, 80.0, 100.0, 80.0, 0.20);
            """
        )

        with pytest.raises(duckdb.ConstraintException):
            con.execute(
                """
                INSERT INTO transactions (
                    transaction_line_id, invoice_id, account_id, transaction_date,
                    currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                    reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
                ) VALUES ('DUP-01', 'INV-2', 'ACC-2', '2026-01-02', 'USD', 1.0, 200.0, 160.0, 200.0, 160.0, 0.20);
                """
            )
    finally:
        con.close()


def test_foreign_key_constraints():
    """Verifies that inserting a child row with non-existent foreign key raises duckdb.ConstraintException."""
    con = duckdb.connect(":memory:")
    try:
        init_schema(con)

        # finding_transactions_map references finding_records and transactions
        with pytest.raises(duckdb.ConstraintException):
            con.execute(
                """
                INSERT INTO finding_transactions_map (
                    finding_fingerprint, transaction_line_id, allocated_defensible_gap
                ) VALUES ('NON-EXISTENT-FP', 'NON-EXISTENT-TX', 1500.0);
                """
            )
    finally:
        con.close()


def test_foreign_key_deletion_behavior():
    """
    Verifies that deleting a parent record referenced by a child raises ConstraintException,
    proving that DuckDB 1.0 blocks cascade deletion and downstream modules must do two-stage cleanup.
    """
    con = duckdb.connect(":memory:")
    try:
        init_schema(con)

        # 1. Insert parent calibration
        con.execute(
            """
            INSERT INTO meta_calibration_profiles (
                calibration_id, name, historical_start_date, historical_end_date,
                comparability_controls, investigation_dimensions, threshold_strategy,
                calibration_json
            ) VALUES ('CALIB-1', 'Test Calib', '2025-01-01', '2025-12-31', ['ctrl'], ['dim'], 'P75', '{}');
            """
        )

        # 2. Insert transaction
        con.execute(
            """
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting, extended_list_amt, net_invoiced_amt,
                reporting_list_amt, reporting_invoiced_amt, realized_discount_rate
            ) VALUES ('TX-PARENT', 'INV-1', 'ACC-1', '2026-01-01', 'USD', 1.0, 1000.0, 800.0, 1000.0, 800.0, 0.20);
            """
        )

        # 3. Insert finding record
        con.execute(
            """
            INSERT INTO finding_records (
                finding_fingerprint, calibration_id, depth, dimension_slice_json,
                raw_transaction_count, distinct_account_count, gross_list_volume,
                unshrunk_gap_dollars, shrunk_gap_dollars, concentration_ratio,
                bootstrap_stability_score, bootstrap_ci_lower, bootstrap_ci_upper,
                fdr_p_value, fdr_q_value, fdr_rejected, unique_incremental_gap
            ) VALUES (
                'FP-PARENT-01', 'CALIB-1', 1, '{"rep": "Alice"}',
                10, 5, 50000.0, 5000.0, 4200.0, 0.084, 0.95, 100.0, 8000.0,
                0.001, 0.005, TRUE, 4200.0
            );
            """
        )

        # 4. Insert junction mapping
        con.execute(
            """
            INSERT INTO finding_transactions_map (
                finding_fingerprint, transaction_line_id, allocated_defensible_gap
            ) VALUES ('FP-PARENT-01', 'TX-PARENT', 500.0);
            """
        )

        # Attempting to delete parent finding_records without deleting mapping first must raise ConstraintException
        with pytest.raises(duckdb.ConstraintException):
            con.execute("DELETE FROM finding_records WHERE finding_fingerprint = 'FP-PARENT-01';")

        # Clean two-stage deletion succeeds
        con.execute("DELETE FROM finding_transactions_map WHERE finding_fingerprint = 'FP-PARENT-01';")
        con.execute("DELETE FROM finding_records WHERE finding_fingerprint = 'FP-PARENT-01';")
        assert con.execute("SELECT COUNT(*) FROM finding_records").fetchone()[0] == 0
    finally:
        con.close()


def test_verify_workspace_integrity_valid(temp_workspace_dir):
    """Verifies binary magic bytes (b'DUCK' at offset 8..12) and table verification on valid workspace."""
    ws_path = os.path.join(temp_workspace_dir, "valid_workspace.mxa")
    con = create_workspace(ws_path, project_name="Integrity Alpha")
    close_workspace(con)

    # Boolean check
    assert verify_workspace_integrity(ws_path) is True

    # Detailed dictionary check
    det = verify_workspace_integrity(ws_path, details=True)
    assert det["valid"] is True
    assert det["magic"] == "DUCK"
    assert det["file_size_bytes"] >= 12
    assert det["missing_tables"] == []
    assert len(det["tables_found"]) == 8
    assert det["error"] is None


def test_verify_workspace_integrity_corrupted(temp_workspace_dir):
    """Verifies that non-existent, truncated, or non-DuckDB files fail integrity verification."""
    # 1. Non-existent file
    assert verify_workspace_integrity("non_existent_file.mxa") is False
    det_missing = verify_workspace_integrity("non_existent_file.mxa", details=True)
    assert det_missing["valid"] is False
    assert "does not exist" in det_missing["error"]

    # 2. Truncated file (<12 bytes)
    trunc_path = os.path.join(temp_workspace_dir, "truncated.mxa")
    with open(trunc_path, "wb") as f:
        f.write(b"SHORT")
    assert verify_workspace_integrity(trunc_path) is False
    det_trunc = verify_workspace_integrity(trunc_path, details=True)
    assert det_trunc["valid"] is False
    assert "too small" in det_trunc["error"]

    # 3. Corrupted magic header
    bad_magic_path = os.path.join(temp_workspace_dir, "bad_magic.mxa")
    with open(bad_magic_path, "wb") as f:
        f.write(b"\x00" * 8 + b"EVIL" + b"\x00" * 1024)
    assert verify_workspace_integrity(bad_magic_path) is False
    det_bad = verify_workspace_integrity(bad_magic_path, details=True)
    assert det_bad["valid"] is False
    assert "Invalid magic bytes" in det_bad["error"]


def test_file_locking_cross_process(temp_workspace_dir):
    """Verifies that holding a write lock blocks secondary write attempts from another process."""
    ws_path = os.path.join(temp_workspace_dir, "lock_test.mxa")
    con = create_workspace(ws_path, project_name="Lock Test")
    try:
        # Spawn separate Python process attempting to open the same file with write access
        sub_code = f"""
import duckdb
try:
    con2 = duckdb.connect(r'{ws_path}', read_only=False)
    print('CONNECTED')
except Exception as e:
    print('BLOCKED:', type(e).__name__)
"""
        res = subprocess.run(
            [sys.executable, "-c", sub_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert "BLOCKED" in res.stdout or "IOException" in res.stdout or res.returncode != 0
    finally:
        close_workspace(con)


def test_concurrent_read_only_access(temp_workspace_dir):
    """Verifies that when no process holds a write lock, multiple read_only connections succeed."""
    ws_path = os.path.join(temp_workspace_dir, "ro_test.mxa")
    con = create_workspace(ws_path, project_name="Read Only Test")
    close_workspace(con)

    r1 = duckdb.connect(ws_path, read_only=True)
    r2 = duckdb.connect(ws_path, read_only=True)
    try:
        c1 = r1.execute("SELECT COUNT(*) FROM meta_project").fetchone()[0]
        c2 = r2.execute("SELECT COUNT(*) FROM meta_project").fetchone()[0]
        assert c1 == 1
        assert c2 == 1
    finally:
        r1.close()
        r2.close()
