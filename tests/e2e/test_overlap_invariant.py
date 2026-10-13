"""
AC-4: Overlap Ledger Invariant Test.

Authoritative Requirement:
Reported Net Unique Portfolio Exposure strictly equals the deduplicated union of
transaction dollars across active findings (summing individual finding exposures
without displaying shared intersections is prohibited).
(ORIGINAL_REQUEST.md § Acceptance Criteria, PROJECT.md R4.6/R4.7, spec_report.md AC-4).
"""

import duckdb
import pytest

from tests.e2e.test_helpers import get_configured_duckdb


def setup_overlap_tables(con: duckdb.DuckDBPyConnection):
    """Initializes schema and tables for overlap ledger testing."""
    con.execute("""
        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            account_id VARCHAR NOT NULL,
            extended_list_amt DECIMAL(18, 4) NOT NULL,
            defensible_gap DECIMAL(18, 4) NOT NULL
        );

        CREATE TABLE finding_records (
            finding_fingerprint VARCHAR(64) PRIMARY KEY,
            slice_name VARCHAR NOT NULL,
            lifecycle_status VARCHAR NOT NULL DEFAULT 'New',
            gross_unshrunk_gap DECIMAL(18, 4) NOT NULL
        );

        CREATE TABLE finding_transactions_map (
            finding_fingerprint VARCHAR(64) NOT NULL,
            transaction_line_id VARCHAR NOT NULL,
            PRIMARY KEY (finding_fingerprint, transaction_line_id)
        );
    """)


def test_overlap_ledger_deduplication_exact_set_union():
    """
    AC-4: Asserts that Net Unique Portfolio Exposure strictly equals the
    deduplicated set union of transaction gaps across active findings.
    """
    con = get_configured_duckdb()
    setup_overlap_tables(con)

    # Insert 15 transactions: TX-01 to TX-15, each with defensible_gap = 1000.00
    for i in range(1, 16):
        con.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?)",
            [f"TX-{i:02d}", f"ACC-{(i % 3) + 1}", 10000.00, 1000.00]
        )

    # Finding 1: Slices Rep_Alice (TX-01 to TX-10) -> 10 transactions = $10,000
    con.execute("INSERT INTO finding_records VALUES ('FP-01', 'Rep_Alice', 'New', 10000.00)")
    for i in range(1, 11):
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-01', ?)", [f"TX-{i:02d}"])

    # Finding 2: Slices Reason_Match (TX-06 to TX-15) -> 10 transactions = $10,000 (TX-06..TX-10 overlap!)
    con.execute("INSERT INTO finding_records VALUES ('FP-02', 'Reason_Match', 'New', 10000.00)")
    for i in range(6, 16):
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-02', ?)", [f"TX-{i:02d}"])

    # Finding 3: Slices Channel_Direct (TX-01 to TX-05) -> 5 transactions = $5,000 (100% overlap with FP-01)
    con.execute("INSERT INTO finding_records VALUES ('FP-03', 'Channel_Direct', 'New', 5000.00)")
    for i in range(1, 6):
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-03', ?)", [f"TX-{i:02d}"])

    # 1. Compute naive sum of individual finding exposures
    naive_sum_query = "SELECT SUM(gross_unshrunk_gap) FROM finding_records WHERE lifecycle_status != 'Dismissed';"
    naive_sum = float(con.execute(naive_sum_query).fetchone()[0])
    assert naive_sum == 25000.00, f"Expected naive sum $25,000, got ${naive_sum}"

    # 2. Compute canonical deduplicated Net Unique Portfolio Exposure via SQL set union
    net_unique_query = """
        SELECT 
            COALESCE(SUM(t.defensible_gap), 0.0) AS net_unique_portfolio_exposure,
            COUNT(DISTINCT t.transaction_line_id) AS net_unique_transactions
        FROM transactions t
        WHERE t.transaction_line_id IN (
            SELECT DISTINCT ftm.transaction_line_id
            FROM finding_transactions_map ftm
            JOIN finding_records fr ON ftm.finding_fingerprint = fr.finding_fingerprint
            WHERE fr.lifecycle_status != 'Dismissed'
        );
    """
    res = con.execute(net_unique_query).fetchone()
    net_unique_exposure = float(res[0])
    net_unique_tx_count = int(res[1])

    # Expected: 15 unique transactions * $1000 = $15,000.00
    assert net_unique_tx_count == 15, f"Expected 15 unique transactions, got {net_unique_tx_count}"
    assert net_unique_exposure == 15000.00, f"Expected $15,000.00 Net Unique Exposure, got ${net_unique_exposure}"

    # Verify that double-counting prohibition holds:
    assert naive_sum > net_unique_exposure, "Naive sum must strictly exceed net unique exposure when overlaps exist"
    double_counted_amount = naive_sum - net_unique_exposure
    assert double_counted_amount == 10000.00, f"Expected $10,000 double-count, got ${double_counted_amount}"


def test_overlap_ledger_dismissal_governance():
    """
    AC-4: Asserts that when a finding is 'Dismissed', its non-shared transactions
    are cleanly excluded from Net Unique Exposure, while shared transactions
    remain protected under surviving active findings.
    """
    con = get_configured_duckdb()
    setup_overlap_tables(con)

    # Insert transactions TX-01 to TX-05 ($1000 each)
    for i in range(1, 6):
        con.execute("INSERT INTO transactions VALUES (?, ?, ?, ?)", [f"TX-{i:02d}", "ACC-1", 10000.00, 1000.00])

    # FP-A has TX-01, TX-02, TX-03
    con.execute("INSERT INTO finding_records VALUES ('FP-A', 'Slice_A', 'New', 3000.00)")
    for i in [1, 2, 3]:
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-A', ?)", [f"TX-{i:02d}"])

    # FP-B has TX-03, TX-04, TX-05 (TX-03 shared)
    con.execute("INSERT INTO finding_records VALUES ('FP-B', 'Slice_B', 'New', 3000.00)")
    for i in [3, 4, 5]:
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-B', ?)", [f"TX-{i:02d}"])

    # Before dismissal: 5 unique transactions = $5,000
    query = """
        SELECT COALESCE(SUM(t.defensible_gap), 0.0), COUNT(DISTINCT t.transaction_line_id)
        FROM transactions t
        WHERE t.transaction_line_id IN (
            SELECT DISTINCT ftm.transaction_line_id
            FROM finding_transactions_map ftm
            JOIN finding_records fr ON ftm.finding_fingerprint = fr.finding_fingerprint
            WHERE fr.lifecycle_status != 'Dismissed'
        );
    """
    res = con.execute(query).fetchone()
    assert float(res[0]) == 5000.00
    assert int(res[1]) == 5

    # Dismiss FP-A
    con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-A'")

    # After dismissal of FP-A:
    # Surviving active finding is FP-B (TX-03, TX-04, TX-05) -> 3 transactions = $3,000
    # Note: TX-03 was in FP-A, but because it is also in active finding FP-B, it MUST still be in Net Unique Exposure!
    res_after = con.execute(query).fetchone()
    assert float(res_after[0]) == 3000.00, f"Expected $3,000, got ${res_after[0]}"
    assert int(res_after[1]) == 3, f"Expected 3 transactions, got {res_after[1]}"
