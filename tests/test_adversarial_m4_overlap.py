"""
Empirical Adversarial Stress Suite for Milestone 4: Overlap Ledger Deduplication & Dismissal Governance
Author: Challenger 2 (Overlap Deduplication & Double-Count Stress Challenger)

Adversarially tests:
1. AC-4 Overlap Ledger Exact Set Union Invariant across complex multi-way overlap topologies.
2. Double-Counting Mathematical Identity: Naive Sum vs Net Unique Exposure and exact double-count attribution.
3. Dismissal Governance & Shared Transaction Preservation: Multi-step cascading dismissals and un-dismissals.
4. Non-Dismissed Lifecycle States: 'New', 'Assigned', 'In Review', 'Actioned' all participate in exposure.
5. Inverted Transaction Drawer Multi-Membership & Active Overlap Dynamic Filtering.
6. Pathological Boundary Stress: Zero-gap transactions, penny precision at scale ($10^9), dense multi-finding overlaps, uninitialized schemas.
"""

import duckdb
import pytest
import numpy as np
from decimal import Decimal

from backend.overlap_ledger import (
    compute_net_unique_portfolio_exposure,
    get_overlap_ledger,
    get_finding_transactions,
    record_findings_to_db,
)


def setup_test_schema(con: duckdb.DuckDBPyConnection):
    """Initializes canonical schema for overlap testing."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS meta_calibration_profiles (
            calibration_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL
        );
        INSERT INTO meta_calibration_profiles VALUES ('CALIB-1', 'Test Calib');

        CREATE TABLE IF NOT EXISTS transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            invoice_id VARCHAR,
            account_id VARCHAR NOT NULL,
            transaction_date DATE,
            extended_list_amt DECIMAL(18, 4) NOT NULL,
            net_invoiced_amt DECIMAL(18, 4) NOT NULL,
            realized_discount_rate DECIMAL(10, 6) DEFAULT 0.0,
            defensible_gap DECIMAL(18, 4) NOT NULL,
            product_family VARCHAR,
            sales_region VARCHAR,
            threshold_concession DECIMAL(10, 6) DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS finding_records (
            finding_fingerprint VARCHAR(64) PRIMARY KEY,
            calibration_id VARCHAR DEFAULT 'CALIB-1',
            depth INTEGER DEFAULT 1,
            dimension_slice_json JSON NOT NULL,
            raw_transaction_count BIGINT NOT NULL,
            distinct_account_count BIGINT DEFAULT 1,
            gross_list_volume DECIMAL(18, 4) DEFAULT 0.0,
            unshrunk_gap_dollars DECIMAL(18, 4) NOT NULL,
            shrunk_gap_dollars DECIMAL(18, 4) NOT NULL,
            concentration_ratio DECIMAL(10, 6) DEFAULT 0.0,
            bootstrap_stability_score DECIMAL(6, 4) DEFAULT 1.0,
            bootstrap_ci_lower DECIMAL(18, 4) DEFAULT 0.0,
            bootstrap_ci_upper DECIMAL(18, 4) DEFAULT 0.0,
            fdr_p_value DOUBLE DEFAULT 0.0,
            fdr_q_value DOUBLE DEFAULT 0.0,
            fdr_rejected BOOLEAN DEFAULT TRUE,
            unique_incremental_gap DECIMAL(18, 4) DEFAULT 0.0,
            lifecycle_status VARCHAR NOT NULL DEFAULT 'New',
            assigned_owner VARCHAR,
            dismissal_category VARCHAR,
            dismissal_snooze_date DATE,
            action_target_recovery DECIMAL(18, 4) DEFAULT 0.0,
            evidence_tier VARCHAR DEFAULT 'Tier 1',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS finding_transactions_map (
            finding_fingerprint VARCHAR(64) NOT NULL,
            transaction_line_id VARCHAR NOT NULL,
            allocated_defensible_gap DECIMAL(18, 4) NOT NULL,
            PRIMARY KEY (finding_fingerprint, transaction_line_id)
        );
    """)


class TestAC4SetUnionInvariant:
    """
    Adversarial Challenge 1: Verify exact SQL set union invariant across
    disjoint, partial, cyclic, nested, and complex multi-way topologies.
    """

    def test_disjoint_findings_zero_overlap(self):
        """Disjoint findings: naive sum strictly equals net unique exposure, overlap = 0.0."""
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        # 2 disjoint findings, 5 tx each
        for i in range(1, 11):
            con.execute(
                "INSERT INTO transactions VALUES (?, 'INV', 'ACC', '2026-01-01', 1000.0, 800.0, 0.2, ?, 'PF', 'REG', 0.1)",
                [f"TX-{i:02d}", 200.0],
            )

        # Finding 1: TX-01..TX-05 ($1,000)
        con.execute(
            "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) "
            "VALUES ('FP-1', '{\"rep\": \"Alice\"}', 5, 1000.0, 1000.0)"
        )
        for i in range(1, 6):
            con.execute("INSERT INTO finding_transactions_map VALUES ('FP-1', ?, 200.0)", [f"TX-{i:02d}"])

        # Finding 2: TX-06..TX-10 ($1,000)
        con.execute(
            "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) "
            "VALUES ('FP-2', '{\"rep\": \"Bob\"}', 5, 1000.0, 1000.0)"
        )
        for i in range(6, 11):
            con.execute("INSERT INTO finding_transactions_map VALUES ('FP-2', ?, 200.0)", [f"TX-{i:02d}"])

        ledger = get_overlap_ledger(con)
        assert ledger["net_unique_portfolio_exposure"] == 2000.00
        assert ledger["net_unique_transactions"] == 10
        assert ledger["gross_unshrunk_gap_sum"] == 2000.00
        assert ledger["overlap_double_counted_dollars"] == 0.00
        assert ledger["overlap_pct"] == 0.00

    def test_cyclic_chain_overlap(self):
        """
        Cyclic chain overlap:
        A has {1, 2, 3}, B has {3, 4, 5}, C has {5, 6, 1}.
        Total unique transactions = 6.
        Shared transactions: 1 (A, C), 3 (A, B), 5 (B, C).
        Each transaction has gap = $150.00.
        """
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        for i in range(1, 7):
            con.execute(
                "INSERT INTO transactions VALUES (?, 'INV', 'ACC', '2026-01-01', 1000.0, 850.0, 0.15, 150.0, 'PF', 'REG', 0.1)",
                [f"TX-{i}"],
            )

        slices = [
            ("FP-A", {"dim": "A"}, ["TX-1", "TX-2", "TX-3"]),
            ("FP-B", {"dim": "B"}, ["TX-3", "TX-4", "TX-5"]),
            ("FP-C", {"dim": "C"}, ["TX-5", "TX-6", "TX-1"]),
        ]

        for fp, dim, txs in slices:
            gap_sum = len(txs) * 150.0
            con.execute(
                "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) "
                "VALUES (?, '{\"dim\": \"X\"}', ?, ?, ?)",
                [fp, len(txs), gap_sum, gap_sum],
            )
            for tid in txs:
                con.execute("INSERT INTO finding_transactions_map VALUES (?, ?, 150.0)", [fp, tid])

        ledger = get_overlap_ledger(con)
        # 6 unique transactions * $150 = $900.00
        assert ledger["net_unique_portfolio_exposure"] == 900.00
        assert ledger["net_unique_transactions"] == 6
        # Naive sum = 3 * (3 * 150) = $1350.00
        assert ledger["gross_unshrunk_gap_sum"] == 1350.00
        # Overlap double counted = 1350 - 900 = $450.00 (exactly the 3 shared transactions * $150)
        assert ledger["overlap_double_counted_dollars"] == 450.00
        assert ledger["overlap_pct"] == round(450.0 / 1350.0 * 100.0, 2)

    def test_complete_subset_nested_overlap(self):
        """
        Finding 2 is a strict 100% subset of Finding 1.
        FP-1 has TX-1..TX-10 ($100 each = $1,000)
        FP-2 has TX-1..TX-5 ($100 each = $500)
        FP-3 has TX-1..TX-2 ($100 each = $200)
        Net unique exposure MUST be strictly $1,000.00 (10 transactions).
        """
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        for i in range(1, 11):
            con.execute(
                "INSERT INTO transactions VALUES (?, 'INV', 'ACC', '2026-01-01', 1000.0, 900.0, 0.10, 100.0, 'PF', 'REG', 0.05)",
                [f"TX-{i:02d}"],
            )

        con.execute(
            "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) "
            "VALUES ('FP-1', '{\"level\": 1}', 10, 1000.0, 1000.0), "
            "       ('FP-2', '{\"level\": 2}', 5, 500.0, 500.0), "
            "       ('FP-3', '{\"level\": 3}', 2, 200.0, 200.0)"
        )

        for i in range(1, 11):
            con.execute("INSERT INTO finding_transactions_map VALUES ('FP-1', ?, 100.0)", [f"TX-{i:02d}"])
        for i in range(1, 6):
            con.execute("INSERT INTO finding_transactions_map VALUES ('FP-2', ?, 100.0)", [f"TX-{i:02d}"])
        for i in range(1, 3):
            con.execute("INSERT INTO finding_transactions_map VALUES ('FP-3', ?, 100.0)", [f"TX-{i:02d}"])

        ledger = get_overlap_ledger(con)
        assert ledger["net_unique_portfolio_exposure"] == 1000.00
        assert ledger["net_unique_transactions"] == 10
        assert ledger["gross_unshrunk_gap_sum"] == 1700.00
        assert ledger["overlap_double_counted_dollars"] == 700.00


class TestDoubleCountMathematicalIdentity:
    """
    Adversarial Challenge 2: Verify that double_counted_dollars strictly equals
    sum_{t in Union} (M(t) - 1) * gap(t), where M(t) is active finding multiplicity.
    """

    def test_multiplicity_attribution_theorem(self):
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        # Create 20 transactions with varying defensible gap amounts
        rng = np.random.default_rng(12345)
        gaps = {}
        for i in range(1, 21):
            tx_id = f"TX-{i:02d}"
            gap = round(float(rng.uniform(50.0, 500.0)), 2)
            gaps[tx_id] = gap
            con.execute(
                "INSERT INTO transactions VALUES (?, 'INV', 'ACC', '2026-01-01', 2000.0, 1500.0, 0.25, ?, 'PF', 'REG', 0.1)",
                [tx_id, gap],
            )

        # Generate 6 overlapping findings with varying memberships
        finding_configs = [
            ("F1", [1, 2, 3, 4, 5]),
            ("F2", [3, 4, 5, 6, 7, 8]),
            ("F3", [5, 6, 7, 8, 9, 10]),
            ("F4", [8, 9, 10, 11, 12, 13]),
            ("F5", [1, 5, 10, 15, 20]),
            ("F6", [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]),
        ]

        tx_multiplicity = {f"TX-{i:02d}": 0 for i in range(1, 21)}

        for fid, tx_indices in finding_configs:
            f_tx_ids = [f"TX-{idx:02d}" for idx in tx_indices]
            f_gap_sum = sum(gaps[tid] for tid in f_tx_ids)
            con.execute(
                "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) "
                "VALUES (?, '{\"name\": \"test\"}', ?, ?, ?)",
                [fid, len(f_tx_ids), f_gap_sum, f_gap_sum],
            )
            for tid in f_tx_ids:
                tx_multiplicity[tid] += 1
                con.execute("INSERT INTO finding_transactions_map VALUES (?, ?, ?)", [fid, tid, gaps[tid]])

        # Theoretical calculations:
        active_tids = {tid for tid, m in tx_multiplicity.items() if m > 0}
        theoretical_net_exposure = round(sum(gaps[tid] for tid in active_tids), 2)
        theoretical_naive_sum = round(sum(tx_multiplicity[tid] * gaps[tid] for tid in active_tids), 2)
        theoretical_double_count = round(sum((tx_multiplicity[tid] - 1) * gaps[tid] for tid in active_tids), 2)

        ledger = get_overlap_ledger(con)
        assert abs(ledger["net_unique_portfolio_exposure"] - theoretical_net_exposure) < 0.01
        assert abs(ledger["gross_unshrunk_gap_sum"] - theoretical_naive_sum) < 0.01
        assert abs(ledger["overlap_double_counted_dollars"] - theoretical_double_count) < 0.01
        assert ledger["gross_unshrunk_gap_sum"] > ledger["net_unique_portfolio_exposure"]


class TestDismissalGovernanceAndStateTransitions:
    """
    Adversarial Challenge 3: Verify dismissal governance:
    - Non-shared transactions are excluded upon dismissal.
    - Shared transactions remain protected under surviving active findings.
    - Un-dismissing / re-activating restores transaction exposure.
    - Non-dismissed states ('New', 'Assigned', 'In Review', 'Actioned') all preserve exposure.
    """

    def test_cascading_dismissals_and_surviving_protection(self):
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        # 4 transactions: TX-1 ($100), TX-2 ($200), TX-3 ($300), TX-4 ($400)
        # FP-A: TX-1, TX-2 ($300)
        # FP-B: TX-2, TX-3 ($500)
        # FP-C: TX-2, TX-4 ($600)
        # Note: TX-2 is shared across ALL 3 findings!
        for tid, gap in [("TX-1", 100.0), ("TX-2", 200.0), ("TX-3", 300.0), ("TX-4", 400.0)]:
            con.execute(
                "INSERT INTO transactions VALUES (?, 'INV', 'ACC', '2026-01-01', 1000.0, 500.0, 0.5, ?, 'PF', 'REG', 0.1)",
                [tid, gap],
            )

        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) VALUES ('FP-A', '{\"dim\": \"A\"}', 2, 300.0, 300.0)")
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) VALUES ('FP-B', '{\"dim\": \"B\"}', 2, 500.0, 500.0)")
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) VALUES ('FP-C', '{\"dim\": \"C\"}', 2, 600.0, 600.0)")

        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-A', 'TX-1', 100.0), ('FP-A', 'TX-2', 200.0)")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-B', 'TX-2', 200.0), ('FP-B', 'TX-3', 300.0)")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-C', 'TX-2', 200.0), ('FP-C', 'TX-4', 400.0)")

        # State 0: All 3 active
        l0 = get_overlap_ledger(con)
        assert l0["active_finding_count"] == 3
        assert l0["dismissed_finding_count"] == 0
        assert l0["net_unique_portfolio_exposure"] == 1000.00  # TX-1 + TX-2 + TX-3 + TX-4
        assert l0["net_unique_transactions"] == 4
        assert l0["gross_unshrunk_gap_sum"] == 1400.00        # 300 + 500 + 600
        assert l0["overlap_double_counted_dollars"] == 400.00 # TX-2 counted 3 times -> +400

        # State 1: Dismiss FP-A
        con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-A'")
        l1 = get_overlap_ledger(con)
        assert l1["active_finding_count"] == 2
        assert l1["dismissed_finding_count"] == 1
        # Surviving: FP-B (TX-2, TX-3) and FP-C (TX-2, TX-4)
        # TX-1 dropped out; TX-2 REMAINS protected!
        assert l1["net_unique_portfolio_exposure"] == 900.00   # TX-2 ($200) + TX-3 ($300) + TX-4 ($400)
        assert l1["net_unique_transactions"] == 3
        assert l1["gross_unshrunk_gap_sum"] == 1100.00        # 500 + 600
        assert l1["overlap_double_counted_dollars"] == 200.00 # TX-2 counted 2 times -> +200

        # State 2: Dismiss FP-B
        con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-B'")
        l2 = get_overlap_ledger(con)
        assert l2["active_finding_count"] == 1
        assert l2["dismissed_finding_count"] == 2
        # Surviving: FP-C (TX-2, TX-4)
        # TX-3 dropped out; TX-2 STILL REMAINS protected!
        assert l2["net_unique_portfolio_exposure"] == 600.00   # TX-2 ($200) + TX-4 ($400)
        assert l2["net_unique_transactions"] == 2
        assert l2["gross_unshrunk_gap_sum"] == 600.00
        assert l2["overlap_double_counted_dollars"] == 0.00

        # State 3: Dismiss FP-C (All dismissed)
        con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-C'")
        l3 = get_overlap_ledger(con)
        assert l3["active_finding_count"] == 0
        assert l3["dismissed_finding_count"] == 3
        assert l3["net_unique_portfolio_exposure"] == 0.00
        assert l3["net_unique_transactions"] == 0
        assert l3["gross_unshrunk_gap_sum"] == 0.00
        assert l3["overlap_double_counted_dollars"] == 0.00

        # State 4: Un-dismiss FP-A (re-activate)
        con.execute("UPDATE finding_records SET lifecycle_status = 'In Review' WHERE finding_fingerprint = 'FP-A'")
        l4 = get_overlap_ledger(con)
        assert l4["active_finding_count"] == 1
        assert l4["dismissed_finding_count"] == 2
        assert l4["net_unique_portfolio_exposure"] == 300.00   # TX-1 + TX-2
        assert l4["net_unique_transactions"] == 2

    def test_lifecycle_statuses_assigned_in_review_actioned(self):
        """
        Verify that all non-dismissed states ('New', 'Assigned', 'In Review', 'Actioned')
        are treated as active and contribute to Net Unique Portfolio Exposure.
        """
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        for i in range(1, 5):
            con.execute(
                "INSERT INTO transactions VALUES (?, 'INV', 'ACC', '2026-01-01', 1000.0, 500.0, 0.5, 250.0, 'PF', 'REG', 0.1)",
                [f"TX-{i}"],
            )

        statuses = [("FP-NEW", "New", "TX-1"), ("FP-ASG", "Assigned", "TX-2"), ("FP-REV", "In Review", "TX-3"), ("FP-ACT", "Actioned", "TX-4")]
        for fp, st, tid in statuses:
            con.execute(
                "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) "
                "VALUES (?, '{\"dim\": \"X\"}', 1, 250.0, 250.0, ?)",
                [fp, st],
            )
            con.execute("INSERT INTO finding_transactions_map VALUES (?, ?, 250.0)", [fp, tid])

        ledger = get_overlap_ledger(con)
        assert ledger["active_finding_count"] == 4
        assert ledger["dismissed_finding_count"] == 0
        assert ledger["net_unique_portfolio_exposure"] == 1000.00
        assert ledger["net_unique_transactions"] == 4


class TestTransactionDrawerDrawerQueries:
    """
    Adversarial Challenge 4: Verify transaction drawer queries:
    - Overlap flags (is_overlap) dynamically reflect only active finding memberships.
    - Dismissed findings are not listed in active other_findings.
    """

    def test_drawer_filters_dismissed_findings_from_overlaps(self):
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        con.execute(
            "INSERT INTO transactions VALUES ('TX-SHARED', 'INV-1', 'ACC-1', '2026-01-01', 10000.0, 8000.0, 0.2, 500.0, 'Hardware', 'US-East', 0.15)"
        )
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) VALUES ('FP-1', '{\"rep\": \"Alice\"}', 1, 500.0, 500.0, 'New')")
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) VALUES ('FP-2', '{\"reason\": \"Match\"}', 1, 500.0, 500.0, 'New')")

        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-1', 'TX-SHARED', 500.0)")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-2', 'TX-SHARED', 500.0)")

        # When FP-2 is active: FP-1's drawer must report FP-2 as an overlap
        txs_active = get_finding_transactions(con, "FP-1")
        assert len(txs_active) == 1
        assert txs_active[0]["is_overlap"] is True
        assert "FP-2" in txs_active[0]["other_findings"]
        assert txs_active[0]["total_active_finding_memberships"] == 2

        # Dismiss FP-2
        con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-2'")

        # Now: FP-1's drawer must NOT report FP-2 as an active overlap
        txs_dismissed = get_finding_transactions(con, "FP-1")
        assert len(txs_dismissed) == 1
        assert txs_dismissed[0]["is_overlap"] is False
        assert txs_dismissed[0]["other_findings"] == []
        assert txs_dismissed[0]["total_active_finding_memberships"] == 1


class TestBoundaryAndScaleStress:
    """
    Adversarial Challenge 5: Boundary conditions, empty databases, zero-gap rows,
    and high-volume transactions ($10^9) with decimal pennies.
    """

    def test_uninitialized_database_resilience(self):
        """Uninitialized database returns clean empty ledger without throwing exceptions."""
        con = duckdb.connect(":memory:")
        ledger = get_overlap_ledger(con)
        assert ledger["status"] == "success"
        assert ledger["net_unique_portfolio_exposure"] == 0.0
        assert ledger["active_finding_count"] == 0

        net = compute_net_unique_portfolio_exposure(con)
        assert net["net_unique_portfolio_exposure"] == 0.0

        drawer = get_finding_transactions(con, "NON-EXISTENT")
        assert drawer == []

    def test_zero_gap_transactions_invariant(self):
        """Transactions with 0.0 defensible gap are counted in tx count but add 0 to dollar exposure."""
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        con.execute(
            "INSERT INTO transactions VALUES ('TX-ZERO-1', 'INV', 'ACC', '2026-01-01', 1000.0, 1000.0, 0.0, 0.0, 'PF', 'REG', 0.0), "
            "                                ('TX-ZERO-2', 'INV', 'ACC', '2026-01-01', 1000.0, 1000.0, 0.0, 0.0, 'PF', 'REG', 0.0)"
        )
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) VALUES ('FP-Z', '{\"dim\": \"Z\"}', 2, 0.0, 0.0)")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-Z', 'TX-ZERO-1', 0.0), ('FP-Z', 'TX-ZERO-2', 0.0)")

        ledger = get_overlap_ledger(con)
        assert ledger["net_unique_portfolio_exposure"] == 0.00
        assert ledger["net_unique_transactions"] == 2
        assert ledger["gross_unshrunk_gap_sum"] == 0.00
        assert ledger["overlap_double_counted_dollars"] == 0.00
        assert ledger["overlap_pct"] == 0.00

    def test_billion_dollar_exact_penny_precision(self):
        """
        Stress test with $1.25 Billion portfolio exposure and precision pennies ($0.01).
        Verifies no floating-point cancellation or precision degradation.
        """
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        # Insert 3 transactions totaling $1,250,000,000.33
        t1_gap = 500000000.11
        t2_gap = 500000000.11
        t3_gap = 250000000.11
        expected_total = 1250000000.33

        con.execute("INSERT INTO transactions VALUES ('TX-B1', 'INV', 'ACC', '2026-01-01', 1e9, 5e8, 0.5, ?, 'PF', 'REG', 0.1)", [t1_gap])
        con.execute("INSERT INTO transactions VALUES ('TX-B2', 'INV', 'ACC', '2026-01-01', 1e9, 5e8, 0.5, ?, 'PF', 'REG', 0.1)", [t2_gap])
        con.execute("INSERT INTO transactions VALUES ('TX-B3', 'INV', 'ACC', '2026-01-01', 1e9, 7.5e8, 0.25, ?, 'PF', 'REG', 0.1)", [t3_gap])

        # FP-1 contains TX-B1, TX-B2 ($1,000,000,000.22)
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) VALUES ('FP-B1', '{\"dim\": \"B1\"}', 2, 1000000000.22, 1000000000.22)")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-B1', 'TX-B1', ?), ('FP-B1', 'TX-B2', ?)", [t1_gap, t2_gap])

        # FP-2 contains TX-B2, TX-B3 ($750,000,000.22) -> TX-B2 shared!
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) VALUES ('FP-B2', '{\"dim\": \"B2\"}', 2, 750000000.22, 750000000.22)")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-B2', 'TX-B2', ?), ('FP-B2', 'TX-B3', ?)", [t2_gap, t3_gap])

        ledger = get_overlap_ledger(con)
        assert abs(ledger["net_unique_portfolio_exposure"] - expected_total) < 0.01
        assert ledger["net_unique_transactions"] == 3
        expected_naive = 1000000000.22 + 750000000.22
        assert abs(ledger["gross_unshrunk_gap_sum"] - expected_naive) < 0.01
        assert abs(ledger["overlap_double_counted_dollars"] - t2_gap) < 0.01

    def test_high_volume_dense_overlap_scale(self):
        """
        Stress test with 2,000 transactions and 20 overlapping findings.
        Verifies query execution speed and set union correctness under high volume.
        """
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        n_tx = 2000
        # Batch insert transactions
        tx_rows = [
            (f"TX-{i:04d}", f"INV-{i:04d}", f"ACC-{(i % 20) + 1}", "2026-01-01", 10000.0, 8000.0, 0.20, 100.0, "PF", "REG", 0.10)
            for i in range(n_tx)
        ]
        con.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tx_rows)

        # Create 20 overlapping findings, each covering 200 transactions with sliding window step 100
        # Window 0: 0..199
        # Window 1: 100..299
        # ...
        # Window 18: 1800..1999
        # Window 19: 1900..1999 (100 tx)
        covered_ids = set()
        for f_idx in range(20):
            start = f_idx * 100
            end = min(n_tx, start + 200)
            window_tids = [f"TX-{i:04d}" for i in range(start, end)]
            covered_ids.update(window_tids)
            f_gap = len(window_tids) * 100.0
            fp = f"FP-SCALE-{f_idx:02d}"
            con.execute(
                "INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars) "
                "VALUES (?, '{\"slice\": \"test\"}', ?, ?, ?)",
                [fp, len(window_tids), f_gap, f_gap],
            )
            map_rows = [(fp, tid, 100.0) for tid in window_tids]
            con.executemany("INSERT INTO finding_transactions_map VALUES (?, ?, ?)", map_rows)

        ledger = get_overlap_ledger(con)
        assert ledger["net_unique_transactions"] == len(covered_ids)
        assert ledger["net_unique_portfolio_exposure"] == len(covered_ids) * 100.0
        assert ledger["active_finding_count"] == 20
        assert ledger["gross_unshrunk_gap_sum"] > ledger["net_unique_portfolio_exposure"]
        assert ledger["overlap_double_counted_dollars"] == round(ledger["gross_unshrunk_gap_sum"] - ledger["net_unique_portfolio_exposure"], 2)


class TestAPITriageAndDBPersistence:
    """
    Adversarial Challenge 6: FastAPI Triage Endpoints & Persistence Integration:
    - record_findings_to_db idempotency.
    - FastAPI GET /api/triage/overlap_ledger under active vs dismissed findings.
    - FastAPI GET /api/triage/findings/{id}/transactions drawer response.
    """

    def test_record_findings_idempotency(self):
        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        con.execute(
            "INSERT INTO transactions VALUES ('TX-1', 'INV', 'ACC', '2026-01-01', 1000.0, 800.0, 0.2, 200.0, 'PF', 'REG', 0.1)"
        )

        finding = {
            "finding_fingerprint": "FP-IDEMPOTENT",
            "dimension_slice": {"sales_rep": "Alice"},
            "depth": 1,
            "raw_transaction_count": 1,
            "distinct_account_count": 1,
            "gross_list_volume": 1000.0,
            "unshrunk_gap_dollars": 200.0,
            "shrunk_gap_dollars": 180.0,
            "concentration_ratio": 0.2,
            "bootstrap_stability_score": 1.0,
            "bootstrap_ci_lower": 100.0,
            "bootstrap_ci_upper": 250.0,
            "fdr_p_value": 0.001,
            "fdr_q_value": 0.002,
            "fdr_rejected": True,
            "unique_incremental_gap": 200.0,
            "transaction_ids": ["TX-1"],
        }

        # First record
        record_findings_to_db(con, [finding])
        assert con.execute("SELECT COUNT(*) FROM finding_records").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM finding_transactions_map").fetchone()[0] == 1

        # Second record (identical) -> should replace cleanly without duplicating rows
        record_findings_to_db(con, [finding])
        assert con.execute("SELECT COUNT(*) FROM finding_records").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM finding_transactions_map").fetchone()[0] == 1

        l = get_overlap_ledger(con)
        assert l["net_unique_portfolio_exposure"] == 200.00
        assert l["active_finding_count"] == 1

    def test_fastapi_overlap_ledger_and_drawer_endpoints(self):
        from fastapi.testclient import TestClient
        from backend.app import app, state
        from backend.storage import close_workspace

        if state.is_open():
            close_workspace(state.connection)
            state.connection = None
            state.active_path = None

        con = duckdb.connect(":memory:")
        setup_test_schema(con)

        con.execute(
            "INSERT INTO transactions VALUES ('TX-100', 'INV', 'ACC', '2026-01-01', 5000.0, 4000.0, 0.2, 1000.0, 'Hardware', 'EMEA', 0.15), "
            "                                ('TX-101', 'INV', 'ACC', '2026-01-01', 5000.0, 4000.0, 0.2, 1000.0, 'Hardware', 'EMEA', 0.15)"
        )
        con.execute("INSERT INTO finding_records (finding_fingerprint, dimension_slice_json, raw_transaction_count, unshrunk_gap_dollars, shrunk_gap_dollars, lifecycle_status) VALUES ('FP-API-1', '{\"region\": \"EMEA\"}', 2, 2000.0, 2000.0, 'New')")
        con.execute("INSERT INTO finding_transactions_map VALUES ('FP-API-1', 'TX-100', 1000.0), ('FP-API-1', 'TX-101', 1000.0)")

        state.connection = con
        state.active_path = ":memory:"

        client = TestClient(app)
        try:
            resp = client.get("/api/triage/overlap_ledger")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["net_unique_portfolio_exposure"] == 2000.00
            assert data["active_finding_count"] == 1
            assert data["dismissed_finding_count"] == 0

            # Test drawer endpoint
            resp_drawer = client.get("/api/triage/findings/FP-API-1/transactions")
            assert resp_drawer.status_code == 200
            txs = resp_drawer.json()
            assert len(txs) == 2
            assert txs[0]["transaction_line_id"] in ["TX-100", "TX-101"]

            # Dismiss finding FP-API-1
            con.execute("UPDATE finding_records SET lifecycle_status = 'Dismissed' WHERE finding_fingerprint = 'FP-API-1'")
            resp2 = client.get("/api/triage/overlap_ledger")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["net_unique_portfolio_exposure"] == 0.00
            assert data2["active_finding_count"] == 0
            assert data2["dismissed_finding_count"] == 1

        finally:
            state.connection = None
            state.active_path = None
            con.close()

