"""
AC-6: Air-Gap Verification Test.

Authoritative Requirement:
Complete execution of ingestion, LOAO calibration, beam search triage, and
report generation in a sandboxed, network-disabled environment with zero network requests.
(ORIGINAL_REQUEST.md § Acceptance Criteria, PROJECT.md R1.7, spec_report.md AC-6).
"""

import socket
from typing import Generator
import pytest

from tests.synthetic_data import generate_50k_canonical_dataset, save_dataset_csv
from tests.e2e.test_helpers import (
    get_configured_duckdb,
    compute_reference_loao_p75,
    apply_empirical_bayes_and_fdr,
    sanitize_csv_cell,
)


class AirGapViolationError(RuntimeError):
    """Raised when an outbound network call is attempted in air-gapped mode."""
    pass


@pytest.fixture
def air_gap_enforcer(monkeypatch):
    """
    Air-gap fixture that blocks all outbound socket connections to non-loopback addresses.
    Tracks attempted connections and fails if any external network access is detected.
    """
    attempted_external_calls = []
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        # Allow loopback/internal IPC only
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        attempted_external_calls.append(address)
        raise AirGapViolationError(
            f"AIR-GAP VIOLATION: Attempted outbound network connection to {address}"
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield attempted_external_calls


def test_complete_analytical_lifecycle_under_strict_air_gap(air_gap_enforcer, tmp_path):
    """
    AC-6: Executes full lifecycle (data generation, ingestion, LOAO calibration,
    beam search triage, and CSV export) under strict air-gap enforcement.
    Asserts zero outbound network attempts and 100% offline completion.
    """
    # 1. Generate dataset completely offline
    df, meta = generate_50k_canonical_dataset(n_rows=2000, seed=42, inject_exceptions=True)
    raw_csv = tmp_path / "airgap_input.csv"
    save_dataset_csv(df, str(raw_csv))

    # 2. In-Process DuckDB Engine execution
    con = get_configured_duckdb()
    con.execute(f"CREATE TABLE transactions AS SELECT * FROM read_csv_auto('{raw_csv.as_posix()}');")

    # Add realized discount rate
    con.execute("""
        ALTER TABLE transactions ADD COLUMN realized_discount_rate DECIMAL(10, 6);
        UPDATE transactions 
        SET realized_discount_rate = (extended_list_amt - net_invoiced_amt) / extended_list_amt;
    """)

    # 3. LOAO Baseline Calculation offline
    scored_df = compute_reference_loao_p75(con, table_name="transactions", min_tx=5, min_accounts=3)
    assert not scored_df.empty

    # 4. Beam search / FDR triage offline
    slice_res = apply_empirical_bayes_and_fdr(scored_df, group_cols=["sales_rep", "discount_reason"])
    assert not slice_res.empty

    # 5. Export generation offline
    export_csv = tmp_path / "airgap_export.csv"
    with open(export_csv, "w", encoding="utf-8") as f:
        f.write("slice,shrunk_gap\n")
        for _, row in slice_res.iterrows():
            clean_slice = sanitize_csv_cell(str(row["group_keys"]))
            clean_gap = sanitize_csv_cell(row["shrunk_total_gap"])
            f.write(f"{clean_slice},{clean_gap}\n")

    assert export_csv.exists()
    assert export_csv.stat().st_size > 0

    # 6. Verify zero external network connections occurred
    assert len(air_gap_enforcer) == 0, (
        f"Air-gap violated! Detected {len(air_gap_enforcer)} outbound network attempts: {air_gap_enforcer}"
    )
