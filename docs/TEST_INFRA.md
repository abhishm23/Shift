# Sift E2E Testing Infrastructure & Verification Architecture

## 1. Overview & Testing Philosophy

The Sift E2E test harness is an air-gapped, opaque-box verification system engineered to enforce commercial audit accuracy, mathematical invariants, and air-gapped security guardrails as mandated by `ORIGINAL_REQUEST.md` and `PROJECT.md`.

Testing adheres to four core principles:
1. **Progressive Testability & Independence**: Each test suite runs self-contained, isolates its state in temporary workspaces, and verifies invariants independently without ordering dependencies.
2. **Deterministic Ground-Truth Seeding**: Synthetic data generators produce realistic commercial sales transactions with known, seeded distributions and deterministically track injected anomalies.
3. **Rigorous Invariant Verification**: Facade tests that always pass are strictly prohibited. Tests verify actual mathematical identities (exact penny balance, set-union deduplication, FDR thresholds, 1 bp reconciliation gate).
4. **Air-Gap & Security Invariants**: Outbound socket requests are blackholed and tested for zero-leakage; spreadsheet formula injection defenses are tested against dangerous prefix vectors while preserving negative numeric currency values.

---

## 2. Test Architecture & Directory Layout

```
c:\Shift\tests\
├── __init__.py                          # Test package root
├── conftest.py                          # Pytest fixtures (50k dataset, waterline, temp workspaces)
├── synthetic_data.py                    # 50k transaction generator + 15 planted exceptions
└── e2e\
    ├── __init__.py                      # E2E test subpackage
    ├── test_helpers.py                  # Reference mathematical oracles & DuckDB helpers
    ├── runner.py                        # Standalone E2E test runner with terminal & JSON reports
    ├── test_planted_exceptions.py       # AC-1: 50k rows, 15 planted exceptions, 100% P/R
    ├── test_waterline_null.py           # AC-2: Uniform distribution, 0 defensible exceptions
    ├── test_reconciliation_invariant.py # AC-3: Net variance = Unfavorable + Favorable to exact cent
    ├── test_overlap_invariant.py        # AC-4: Net unique exposure = set union of transaction dollars
    ├── test_negative_numeric.py         # AC-5: Negative currency unquoted; formulas escaped
    ├── test_air_gap.py                  # AC-6: Zero outbound network calls verified
    ├── test_mxa_persistence.py          # AC-7: Single-file .mxa save/reload ACID fidelity
    ├── test_quarantine_watermark.py     # AC-8: Permanent watermark when control variance > 1 bp
    └── test_punitive_lockout.py         # AC-9: Punitive disposition codes locked on Tiers 1-2
```

---

## 3. Acceptance Criteria Coverage Matrix

| AC # | Target Criterion | Test Module | Exact Invariant Checked | Authoritative Source |
|------|------------------|-------------|-------------------------|----------------------|
| **AC-1** | Synthetic Planted Exception Test | `tests/e2e/test_planted_exceptions.py` | Engine recovers exactly 15 planted exceptions with 100% Precision and 100% Recall ($FP=0, FN=0$) from 50,000 canonical rows | ORIGINAL_REQUEST §59, PROJECT.md R3/R4 |
| **AC-2** | Waterline Null-Hypothesis Test | `tests/e2e/test_waterline_null.py` | On uniform non-anomalous distribution, engine returns exactly 0 defensible exception findings under default P75 and FDR control ($q < 0.05$) | ORIGINAL_REQUEST §60, PROJECT.md R4.3 |
| **AC-3** | Reconciliation Invariant | `tests/e2e/test_reconciliation_invariant.py` | Portfolio Net Variance strictly matches Gross Unfavorable Gap + Favorable Variance to the exact cent ($0.0000) | ORIGINAL_REQUEST §61, PROJECT.md R2.6 |
| **AC-4** | Overlap Ledger Invariant | `tests/e2e/test_overlap_invariant.py` | Reported Net Unique Portfolio Exposure strictly equals the deduplicated set union of transaction dollars across active findings | ORIGINAL_REQUEST §62, PROJECT.md R4.7 |
| **AC-5** | Negative Numeric Integrity | `tests/e2e/test_negative_numeric.py` | Negative numbers (e.g., `-1450.50`, `-0.05`) parse cleanly as numeric floats and are not prepended with single quotes in CSV exports; dangerous formulas (`=`, `+`, `-`, `@`, `\t`, `\r`) are neutralized | ORIGINAL_REQUEST §63, PROJECT.md R8.4 |
| **AC-6** | Air-Gap Verification | `tests/e2e/test_air_gap.py` | Complete ingestion, calibration, triage, and export execute with zero outbound network calls | ORIGINAL_REQUEST §64, PROJECT.md R1.7 |
| **AC-7** | Workspace Persistence | `tests/e2e/test_mxa_persistence.py` | Workspaces save and reload from single `.mxa` DuckDB files preserving all metadata, manifests, calibrations, and findings | ORIGINAL_REQUEST §67, PROJECT.md R1.8 |
| **AC-8** | Quarantine Watermark | `tests/e2e/test_quarantine_watermark.py` | Permanent watermark `UNRECONCILED RESIDUAL: X.XX% ($Y) OUTSIDE AUDIT GUARDRAILS` displays on screen, reports, and exports whenever residual exceeds 1 bp | ORIGINAL_REQUEST §68, PROJECT.md R2.8/R2.9 |
| **AC-9** | Punitive Disposition Lockout | `tests/e2e/test_punitive_lockout.py` | Punitive disposition codes (`Unapproved Concession`, `Unauthorized Deal`) are locked on Tier 1 and Tier 2 findings, unlocking only for Tier 3 | ORIGINAL_REQUEST §69, PROJECT.md R6.3 |

---

## 4. Synthetic Data Generators (`tests/synthetic_data.py`)

### 4.1 Canonical 50k Dataset & Planted Exceptions
- **Row Count**: 50,000 canonical rows.
- **Line Grain Fields**: `transaction_line_id`, `invoice_id`, `account_id`, `parent_account_id`, `transaction_date`, `currency`, `fx_rate_to_reporting`, `extended_list_amt`, `net_invoiced_amt`, `cogs_amt`, `off_invoice_rebate`, `product_family`, `sales_region`, `industry`, `sales_rep`, `discount_reason`, `channel`.
- **Planted Cohort**:
  - Target: `{"product_family": "Enterprise Storage", "sales_region": "North America", "sales_rep": "Rep_Rogue", "discount_reason": "Executive Override"}`
  - Planted Transactions: Exactly 15 transactions distributed across 5 distinct customer accounts (3 transactions each) satisfying LOAO cohort support fences ($N \ge 10, |A| \ge 5$).
  - Concession Disparity: Baseline cohort P75 discount rate is $\approx 18.5\%$. Planted transactions feature excessive, off-policy discounts of $48.0\%$ to $60.0\%$, producing large, defensible dollar gaps.
  - Ground Truth Registry: `PlantedGroundTruth` dataclass records transaction IDs (`TX-PLANTED-001` through `TX-PLANTED-015`), individual discount rates, and exact defensible gaps.

### 4.2 Waterline Uniform Null Distribution
- **Distribution**: 20,000 rows with uniformly distributed discounts in $[0.12, 0.16]$ across all dimensions and customer accounts.
- **Null Invariant**: Zero anomalous slices or statistical outliers. Under P75 boundary fences and Benjamini-Hochberg FDR control ($q < 0.05$), exactly 0 slices are declared defensible exception findings.

### 4.3 Control Total Discrepancy Generator
- Computes exact Gross List Revenue and Net Invoiced Revenue sums.
- Parameterized by `discrepancy_bp`:
  - $\le 1.0$ bp: Grants `CERTIFIED_AUDIT`, watermark disabled.
  - $> 1.0$ bp (e.g. 5.0 bp): Initiates `QUARANTINED_AND_PROCEEDED`, generates permanent watermark warning.

---

## 5. Execution Commands

### Run Generator Self-Tests
```bash
pytest -v tests/synthetic_data.py
```

### Run Full E2E Test Suite via Pytest
```bash
pytest -v tests/e2e/
```

### Run Standalone E2E Test Runner
```bash
python tests/e2e/runner.py
```

### Run Specific Criteria or Generate JSON Report
```bash
# Run specific AC criteria
python tests/e2e/runner.py --ac 1,3,5

# Verbose output with JSON report output
python tests/e2e/runner.py --verbose --json reports/e2e_summary.json
```

---

## 6. Integration Protocol for Milestone Developers (M1–M7)

When backend components in `backend/` are implemented, the E2E tests automatically discover and bind to them:
1. `backend.loao.compute_loao_baselines` and `backend.beam_search.run_beam_search` are invoked in AC-1 and AC-2.
2. `backend.storage.open_workspace` and `backend.storage.init_schema` are validated against AC-7.
3. `backend.export_engine.sanitize_csv_cell` is validated against AC-5.
4. `backend.lifecycle.transition_finding` is validated against AC-9.
5. In the absence of specific backend modules, the test suite executes using authoritative reference DuckDB engines and mathematical oracles, ensuring immediate verifiability and zero blockage.
