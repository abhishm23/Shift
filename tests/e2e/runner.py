"""
Independent E2E Acceptance Test Suite Runner for Sift.

Executes all 9 Acceptance Criteria test suites (AC-1 through AC-9),
evaluates mathematical invariants, and outputs formatted execution summaries
in both human-readable terminal tables and structured JSON reports.

Usage:
    python tests/e2e/runner.py
    python tests/e2e/runner.py --verbose
    python tests/e2e/runner.py --ac 1,3,5
    python tests/e2e/runner.py --json report.json
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


AC_DEFINITIONS = [
    {
        "ac_id": "AC-1",
        "name": "Synthetic Planted Exception Test",
        "file": "tests/e2e/test_planted_exceptions.py",
        "invariant": "100% Precision & 100% Recall on 15 injected exceptions without background FPs",
    },
    {
        "ac_id": "AC-2",
        "name": "Waterline Null-Hypothesis Test",
        "file": "tests/e2e/test_waterline_null.py",
        "invariant": "Exactly 0 defensible exception findings under default P75 and FDR control",
    },
    {
        "ac_id": "AC-3",
        "name": "Reconciliation Invariant Test",
        "file": "tests/e2e/test_reconciliation_invariant.py",
        "invariant": "Net Variance == Gross Unfavorable Gap + Favorable Variance to the exact cent ($0.0000)",
    },
    {
        "ac_id": "AC-4",
        "name": "Overlap Ledger Invariant Test",
        "file": "tests/e2e/test_overlap_invariant.py",
        "invariant": "Net Unique Portfolio Exposure strictly equals set union of transaction dollars",
    },
    {
        "ac_id": "AC-5",
        "name": "Negative Numeric Integrity Test",
        "file": "tests/e2e/test_negative_numeric.py",
        "invariant": "Negative numbers parse cleanly and are unquoted; dangerous formulas are escaped",
    },
    {
        "ac_id": "AC-6",
        "name": "Air-Gap Verification Test",
        "file": "tests/e2e/test_air_gap.py",
        "invariant": "Complete analytical lifecycle executed with zero external network requests",
    },
    {
        "ac_id": "AC-7",
        "name": "Workspace .mxa Persistence Test",
        "file": "tests/e2e/test_mxa_persistence.py",
        "invariant": "Single-file .mxa saves and reloads project state, manifest, and findings intact",
    },
    {
        "ac_id": "AC-8",
        "name": "Quarantine Watermark Invariant Test",
        "file": "tests/e2e/test_quarantine_watermark.py",
        "invariant": "Permanent watermark displayed on UI and exports when control residual > 1 bp",
    },
    {
        "ac_id": "AC-9",
        "name": "Punitive Disposition Lockout Test",
        "file": "tests/e2e/test_punitive_lockout.py",
        "invariant": "Punitive disposition codes programmatically blocked on Tiers 1 and 2",
    },
]


class PytestSummaryCollector:
    """Pytest plugin to capture individual test outcomes and timings."""
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.results.append({
                "nodeid": report.nodeid,
                "outcome": report.outcome.upper(),
                "duration": round(report.duration, 4),
                "error": str(report.longrepr) if report.failed else None,
            })


def run_ac_suite(ac_item: Dict[str, str], verbose: bool = False) -> Dict[str, Any]:
    """Runs pytest for a specific AC test file and returns summary metrics."""
    target_file = os.path.join(REPO_ROOT, ac_item["file"])
    collector = PytestSummaryCollector()
    args = [target_file, "-q"]
    if verbose:
        args.append("-v")

    t0 = time.time()
    exit_code = pytest.main(args, plugins=[collector])
    elapsed = round(time.time() - t0, 3)

    passed_count = sum(1 for r in collector.results if r["outcome"] == "PASSED")
    failed_count = sum(1 for r in collector.results if r["outcome"] == "FAILED")
    skipped_count = sum(1 for r in collector.results if r["outcome"] == "SKIPPED")

    status = "PASSED" if (exit_code == 0 and failed_count == 0) else "FAILED"

    return {
        "ac_id": ac_item["ac_id"],
        "name": ac_item["name"],
        "file": ac_item["file"],
        "invariant": ac_item["invariant"],
        "status": status,
        "elapsed_seconds": elapsed,
        "total_tests": len(collector.results),
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "test_details": collector.results,
    }


def print_terminal_report(results: List[Dict[str, Any]], total_time: float) -> None:
    """Prints a structured, formatted ASCII report to stdout."""
    border = "=" * 105
    divider = "-" * 105

    print("\n" + border)
    print(" SIFT AIR-GAPPED COMMERCIAL AUDIT & MARGIN TRIAGE — E2E ACCEPTANCE VERIFICATION REPORT")
    print(border)
    print(f" {'AC ID':<6} | {'Acceptance Criterion':<38} | {'Tests':<6} | {'Status':<8} | {'Time':<7} | {'Invariant Checked'}")
    print(divider)

    all_passed = True
    total_tests = 0
    total_passed = 0

    for r in results:
        total_tests += r["total_tests"]
        total_passed += r["passed"]
        if r["status"] != "PASSED":
            all_passed = False

        status_str = f"\033[92m{r['status']}\033[0m" if r["status"] == "PASSED" else f"\033[91m{r['status']}\033[0m"
        # Fallback if ANSI colors not supported
        if not sys.stdout.isatty():
            status_str = r["status"]

        print(f" {r['ac_id']:<6} | {r['name']:<38} | {r['total_tests']:<6} | {status_str:<8} | {r['elapsed_seconds']:>5.2f}s | {r['invariant'][:30]}...")

    print(divider)
    summary_status = "ALL ACCEPTANCE CRITERIA PASSED" if all_passed else "SOME CRITERIA FAILED"
    print(f" TOTAL: {len(results)} Criteria | {total_tests} Tests ({total_passed} Passed, {total_tests - total_passed} Failed) | Elapsed: {total_time:.2f}s | Result: {summary_status}")
    print(border + "\n")


def main():
    parser = argparse.ArgumentParser(description="Sift E2E Acceptance Test Suite Runner")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose pytest output")
    parser.add_argument("--ac", type=str, help="Comma-separated list of ACs to run (e.g. 1,3,5 or AC-1,AC-3)")
    parser.add_argument("--json", type=str, dest="json_path", help="Path to write structured JSON report")
    args = parser.parse_args()

    selected_ac_ids = None
    if args.ac:
        raw_list = [x.strip().upper() for x in args.ac.split(",")]
        selected_ac_ids = set()
        for x in raw_list:
            if not x.startswith("AC-"):
                selected_ac_ids.add(f"AC-{x}")
            else:
                selected_ac_ids.add(x)

    suites_to_run = [
        item for item in AC_DEFINITIONS
        if selected_ac_ids is None or item["ac_id"] in selected_ac_ids
    ]

    if not suites_to_run:
        print("No matching acceptance criteria found for execution.")
        sys.exit(1)

    print(f"Executing {len(suites_to_run)} Acceptance Criteria test suites...")
    start_time = time.time()
    results = []

    for item in suites_to_run:
        res = run_ac_suite(item, verbose=args.verbose)
        results.append(res)

    total_time = round(time.time() - start_time, 3)
    print_terminal_report(results, total_time)

    if args.json_path:
        report_data = {
            "title": "Sift E2E Acceptance Verification Report",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_elapsed_seconds": total_time,
            "overall_success": all(r["status"] == "PASSED" for r in results),
            "total_criteria": len(results),
            "criteria_results": results,
        }
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"Structured JSON report written to: {args.json_path}")

    # Exit code: 0 if all passed, 1 otherwise
    if not all(r["status"] == "PASSED" for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
