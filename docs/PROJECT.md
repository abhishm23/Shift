# Project: Sift — Local-First, Air-Gapped Commercial Audit & Margin Triage Desktop Application

## Architecture
Sift is architected as an air-gapped, local-first analytical desktop application featuring an embedded in-process DuckDB columnar engine, a local reactive user interface (React + Tailwind CSS + Lucide icons), single-file `.mxa` transactional workspace persistence, and an isolated local desktop runtime harness with full Tauri packaging configuration (`src-tauri/`).

```
+-------------------------------------------------------------------------+
|                              Sift Desktop UI                            |
|     (React + Tailwind CSS + Lucide Icons bundled locally via Vite)       |
|   View 1: Reconcile  |  View 2: Calibrate  |  View 3: Triage & Act      |
+-------------------------------------------------------------------------+
                                    | IPC / Localhost HTTP
+-------------------------------------------------------------------------+
|                       Application Backend Core                          |
|  - Fast API / IPC Router (127.0.0.1:8765)                               |
|  - Engine A: LOAO Calibration, Shrinkage & Diagnostic Beam Search       |
|  - Engine B: Decoupled Macro Margin Bridge (PVMC Decomposition)         |
|  - Safe Export & Formula Injection Defense Engine                       |
|  - Lifecycle State Machine & Run-over-Run Diffing                       |
+-------------------------------------------------------------------------+
                                    | Embedded In-Process
+-------------------------------------------------------------------------+
|                       In-Process DuckDB 1.0 Engine                      |
|  - max_memory: 4GB, temp_directory: disk spilling                       |
|  - Canonical 11-field line-grain schema                                 |
|  - Vectorized LOAO Aggregations (O(|Cohorts| * |Accounts|))             |
|  - Single-file .mxa Workspace Container (SQLite/DuckDB Storage)         |
+-------------------------------------------------------------------------+
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | R1.1 | Tauri desktop application scaffolding and config | M1 | ORIGINAL_REQUEST §R1 |
| 2 | R1.2 | Local desktop harness with Edge/WebView2 standalone app mode | M1 | ORIGINAL_REQUEST §R1 |
| 3 | R1.3 | Embedded in-process DuckDB engine integration | M1 | ORIGINAL_REQUEST §R1 |
| 4 | R1.4 | DuckDB 4 GB memory limit enforcement | M1 | ORIGINAL_REQUEST §R1 |
| 5 | R1.5 | Automatic disk-spilling temp directory configuration | M1 | ORIGINAL_REQUEST §R1 |
| 6 | R1.6 | Local UI bundling (React + Tailwind + Lucide inline SVGs) | M1 | ORIGINAL_REQUEST §R1 |
| 7 | R1.7 | Air-gapped zero-network / zero-telemetry enforcement | M1 | ORIGINAL_REQUEST §R1 |
| 8 | R1.8 | Single-file `.mxa` workspace persistence container | M1 | ORIGINAL_REQUEST §R1 |
| 9 | R2.1 | Pass 1 streaming preview (1,000 rows) with auto-mapping | M2 | ORIGINAL_REQUEST §R2 |
| 10 | R2.2 | Pass 2 vectorized DuckDB scan (grain, credit notes, cardinality) | M2 | ORIGINAL_REQUEST §R2 |
| 11 | R2.3 | CSV and Parquet dual ingestion support | M2 | ORIGINAL_REQUEST §R2 |
| 12 | R2.4 | Canonical line-grain schema (11 fields) | M2 | ORIGINAL_REQUEST §R2 |
| 13 | R2.5 | Data readiness scorecard (Tiers 1, 2, 3) | M2 | ORIGINAL_REQUEST §R2 |
| 14 | R2.6 | User-confirmed control totals reconciliation gate (1 bp) | M2 | ORIGINAL_REQUEST §R2 |
| 15 | R2.7 | Certified Audit status issuance on <= 1 bp variance | M2 | ORIGINAL_REQUEST §R2 |
| 16 | R2.8 | Quarantine-and-Proceed protocol for > 1 bp variance | M2 | ORIGINAL_REQUEST §R2 |
| 17 | R2.9 | Indelible quarantine watermark display across UI and exports | M2 | ORIGINAL_REQUEST §R2 |
| 18 | R2.10 | Immutable `audit_manifest.json` generation | M2 | ORIGINAL_REQUEST §R2 |
| 19 | R3.1 | Three-column comparability attribute classification | M3 | ORIGINAL_REQUEST §R3 |
| 20 | R3.2 | Realized discount rate formulation | M3 | ORIGINAL_REQUEST §R3 |
| 21 | R3.3 | Leave-One-Account-Out (LOAO) peer cohort isolation | M3 | ORIGINAL_REQUEST §R3 |
| 22 | R3.4 | Cohort support fences (N >= 10, Accounts >= 5) | M3 | ORIGINAL_REQUEST §R3 |
| 23 | R3.5 | Hierarchical back-off on support fence failure | M3 | ORIGINAL_REQUEST §R3 |
| 24 | R3.6 | Insufficient Comparable Evidence flagging and exclusion | M3 | ORIGINAL_REQUEST §R3 |
| 25 | R3.7 | Benchmark boundary threshold (P75 vs Median + 1.5*MAD) | M3 | ORIGINAL_REQUEST §R3 |
| 26 | R3.8 | Defensible Gap, Band Gap, and Actionable Opportunity (kappa) | M3 | ORIGINAL_REQUEST §R3 |
| 27 | R3.9 | Versioned `.calib.json` calibration profiles & historical freezing | M3 | ORIGINAL_REQUEST §R3 |
| 28 | R4.1 | Empirical Bayes shrinkage pulling slice gaps toward parent cohort | M4 | ORIGINAL_REQUEST §R4 |
| 29 | R4.2 | 200-iteration bootstrap stability checks (90% CI zero-crossing) | M4 | ORIGINAL_REQUEST §R4 |
| 30 | R4.3 | Benjamini-Hochberg False Discovery Rate (FDR q < 0.05) control | M4 | ORIGINAL_REQUEST §R4 |
| 31 | R4.4 | Bounded beam search traversal (width 3, depth 3) | M4 | ORIGINAL_REQUEST §R4 |
| 32 | R4.5 | Multi-signal priority vector ranking (Dollar, Ratio, Bootstrap, Coverage) | M4 | ORIGINAL_REQUEST §R4 |
| 33 | R4.6 | Overlap-aware ledger mapping transactions to findings | M4 | ORIGINAL_REQUEST §R4 |
| 34 | R4.7 | Deduplicated Net Unique Portfolio Exposure (union of dollars) | M4 | ORIGINAL_REQUEST §R4 |
| 35 | R5.1 | Tier 3 rule-based compound stacking against contractual caps | M5 | ORIGINAL_REQUEST §R5 |
| 36 | R5.2 | Statistical exploratory pairwise interaction rate calculation | M5 | ORIGINAL_REQUEST §R5 |
| 37 | R5.3 | Programmatic tone guard blocking "Policy Violation" in statistical mode | M5 | ORIGINAL_REQUEST §R5 |
| 38 | R5.4 | Decoupled Engine B period-over-period PVMC margin bridge | M5 | ORIGINAL_REQUEST §R5 |
| 39 | R5.5 | Volume Homogeneity Rule across units of measure | M5 | ORIGINAL_REQUEST §R5 |
| 40 | R5.6 | New & Discontinued Business isolation (entries/exits Q0=0 or Q1=0) | M5 | ORIGINAL_REQUEST §R5 |
| 41 | R6.1 | Deterministic SHA-256 finding fingerprinting | M6 | ORIGINAL_REQUEST §R6 |
| 42 | R6.2 | 5-state lifecycle state machine (New, Assigned, In Review, Dismissed, Actioned) | M6 | ORIGINAL_REQUEST §R6 |
| 43 | R6.3 | Programmatic punitive disposition code lockout on Tiers 1-2 | M6 | ORIGINAL_REQUEST §R6 |
| 44 | R6.4 | Mandatory dismissal category and snooze/expiry date | M6 | ORIGINAL_REQUEST §R6 |
| 45 | R6.5 | Run-over-run diffing (New, Persisting/Growing, Resolved/Narrowed) | M6 | ORIGINAL_REQUEST §R6 |
| 46 | R7.1 | Minimalist Three-View UI (View 1 Reconcile, View 2 Calibrate, View 3 Triage & Act) | M7 | ORIGINAL_REQUEST §R7 |
| 47 | R8.1 | Executive Audit Summary export (PDF/HTML) with account/line redaction | M6 | ORIGINAL_REQUEST §R8 |
| 48 | R8.2 | Actionable Findings Ledger export (CSV/Excel) without raw lines | M6 | ORIGINAL_REQUEST §R8 |
| 49 | R8.3 | Restricted Deal Ledger export (AES-256 encrypted ZIP / password XLSX) | M6 | ORIGINAL_REQUEST §R8 |
| 50 | R8.4 | Two-step CSV formula injection defense preserving negative numbers | M6 | ORIGINAL_REQUEST §R8 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Independent opaque-box test runner, synthetic dataset generators, and verification suites for Tiers 1-4 | none | DONE |
| M1 | Desktop Shell & Core Engine | Desktop harness, Tauri config, in-process DuckDB (4GB limit, disk spilling), and `.mxa` workspace storage | none | DONE |
| M2 | Ingestion & Reconciliation Gate | Two-pass ingestion (CSV/Parquet), canonical schema, readiness scorecard, 1 bp gate, watermark, and `audit_manifest.json` | M1 | DONE |
| M3 | LOAO Calibration & Gap Scoring | Comparability controls, LOAO cohort isolation, support fences & back-off, P75/MAD thresholding, gap scoring, `.calib.json` freezing | M1, M2 | PLANNED |
| M4 | Diagnostic Beam Search & Overlap Ledger | Empirical Bayes shrinkage, 200-iteration bootstrap, Benjamini-Hochberg FDR, beam search (w=3, d=3), overlap-aware deduplicated ledger | M1, M2, M3 | PLANNED |
| M5 | Interaction Detection & PVMC Bridge | Compound stacking, pairwise interaction rate with tone guard, decoupled PVMC macro margin bridge with volume homogeneity & churn isolation | M1, M2 | PLANNED |
| M6 | Fingerprinting, State Machine & Safe Export | SHA-256 fingerprinting, 5-state lifecycle with punitive lockout, run-over-run diffing, 3 export paths, and CSV formula injection defense | M1, M2, M3, M4 | PLANNED |
| M7 | Minimalist Three-View UI & Integration | Three-view UI (Reconcile, Calibrate, Triage & Act), KPI cards, interactive panels, drawer, renewal calendar, and end-to-end integration | M1-M6 | PLANNED |
| Final | E2E Verification & Adversarial Hardening | Phase 1: Pass 100% of E2E test suite (Tiers 1-4); Phase 2: Tier 5 Adversarial Coverage Hardening with Challenger and Forensic Auditor | M1-M7, E2E | PLANNED |

## Interface Contracts

### M1 Storage & Engine Interface
- `open_workspace(path: str) -> Connection`: Opens or creates single-file `.mxa` DuckDB database. Configures `max_memory='4GB'` and `temp_directory`.
- `init_schema(con: Connection) -> None`: Initializes the 8 core tables (`meta_project`, `meta_audit_manifest`, `meta_calibration_profiles`, `transactions`, `quarantined_transactions`, `finding_records`, `finding_transactions_map`, `lifecycle_audit_log`).
- `get_workspace_meta(con: Connection) -> dict`: Returns project metadata, audit status, and active calibration ID.

### M2 Ingestion & Gate Interface
- `preview_source(file_path: str, nrows: int = 1000) -> dict`: Returns sample rows, inferred column data types, and proposed mappings to canonical schema.
- `execute_ingestion(con: Connection, file_path: str, column_mapping: dict, control_gross: float, control_net: float) -> dict`: Runs Pass 2 vectorized scan into `transactions`, evaluates 1 bp reconciliation gate, isolates residuals into `quarantined_transactions` if needed, updates `meta_audit_manifest`, and returns readiness tier status (`tier_unlocked: int`, `certified_audit: bool`, `watermark: str | None`).

### M3 LOAO Calibration Interface
- `compute_loao_baselines(con: Connection, controls: list[str], threshold_method: str = 'P75', kappa: float = 0.40) -> dict`: Computes LOAO cohort statistics over $\Omega_{-A(i)}$, applies support fences ($N \ge 10, |A| \ge 5$) with hierarchical back-off, computes Defensible Gap, Band Gap, and Actionable Opportunity, and populates baseline metrics.
- `freeze_calibration(con: Connection, profile_name: str) -> str`: Exports versioned `.calib.json` profile and records snapshot into `meta_calibration_profiles`.

### M4 Beam Search & Overlap Ledger Interface
- `run_beam_search(con: Connection, investigation_dims: list[str], width: int = 3, depth: int = 3, fdr_q: float = 0.05) -> list[dict]`: Runs Empirical Bayes shrinkage, 200-iteration bootstrap stability checks, Benjamini-Hochberg FDR control, and multi-signal priority vector beam search. Populates `finding_records` and `finding_transactions_map`.
- `get_overlap_ledger(con: Connection) -> dict`: Returns list of findings with individual dollar gaps, and the deduplicated `net_unique_portfolio_exposure` calculated as the set union of flagged transaction dollars.

### M5 Interaction & PVMC Bridge Interface
- `evaluate_interactions(con: Connection, dim_a: str, dim_b: str) -> list[dict]`: Computes pairwise interaction rate $\mathcal{I}_{\text{rate}}$. Applies tone guard blocking "Policy Violation" in statistical mode.
- `compute_pvmc_bridge(con: Connection, t0_filter: str, t1_filter: str) -> dict`: Computes decoupled macro margin bridge decomposing $\Delta \text{Margin}$ into Price Effect, Cost Effect, Volume Effect, Mix Effect, and New & Discontinued Business with volume homogeneity checks and penny reconciliation.

### M6 Fingerprinting, State Machine & Safe Export Interface
- `compute_finding_fingerprint(slice_dims: dict, filters: dict, calib_id: str) -> str`: Returns deterministic SHA-256 hash.
- `transition_finding(con: Connection, finding_id: str, new_state: str, disposition_code: str = None, dismissal_reason: str = None, snooze_date: str = None, user: str = 'auditor') -> dict`: Validates lifecycle transition and blocks punitive codes on Tiers 1-2.
- `export_executive_summary(con: Connection, out_path: str, format: str = 'html') -> str`: Generates high-level report with account names and line IDs redacted.
- `export_actionable_findings(con: Connection, out_path: str) -> str`: Exports finding summary without raw transaction rows, sanitized with formula injection defense.
- `export_restricted_deal_ledger(con: Connection, out_path: str, password: str) -> str`: Exports full line-item records encrypted with AES-256.
- `sanitize_csv_cell(value: Any) -> str`: Two-step formula injection defense: preserves valid negative numbers (`-1450.50`), quotes dangerous execution prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`).

### M7 UI Interface
- REST / JSON-RPC API on `http://127.0.0.1:8765` providing endpoints corresponding to M1-M6 interfaces for View 1 (Reconcile), View 2 (Calibrate), and View 3 (Triage & Act).

## Code Layout
```
c:\Shift\
├── .agents\                      # Agent workspace directories (metadata only)
├── ORIGINAL_REQUEST.md           # Authoritative user requirements
├── PROJECT.md                    # Project specification, milestones & contracts
├── TEST_INFRA.md                 # E2E test suite index and test methodology
├── TEST_READY.md                 # E2E test readiness publication
├── src-tauri\                    # Tauri configuration and packaging
│   ├── tauri.conf.json
│   └── Cargo.toml
├── src\                          # Frontend UI (React + Tailwind + Lucide)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src\
│       ├── App.jsx
│       ├── components\
│       │   ├── View1Reconcile.jsx
│       │   ├── View2Calibrate.jsx
│       │   ├── View3Triage.jsx
│       │   ├── WatermarkBanner.jsx
│       │   ├── OverlapLedgerDrawer.jsx
│       │   └── PVMCBridgeView.jsx
│       └── services\
│           └── api.js
├── backend\                      # Analytical Engine Core (Python + DuckDB)
│   ├── app.py                   # FastAPI application & IPC router
│   ├── config.py                # DuckDB configuration (4GB, temp_dir)
│   ├── storage.py               # .mxa workspace manager & DDL schemas
│   ├── ingestion.py             # Two-pass ingestion & 1 bp reconciliation gate
│   ├── loao.py                  # LOAO calibration, support fences & gap scoring
│   ├── beam_search.py           # Empirical Bayes, bootstrap, FDR, beam traversal
│   ├── overlap_ledger.py        # Deduplicated overlap ledger SQL mechanics
│   ├── interactions.py          # Pairwise interactions & tone guard
│   ├── pvmc_bridge.py           # Decoupled PVMC macro margin bridge
│   ├── lifecycle.py             # State machine, SHA-256 fingerprints & diffing
│   ├── export_engine.py         # 3 export paths & CSV formula injection defense
│   └── run_desktop.py           # Local desktop shell launcher (Edge/WebView2)
└── tests\
    ├── conftest.py
    ├── synthetic_data.py        # Synthetic 50k dataset + 15 injected exceptions generator
    ├── test_m1_storage.py
    ├── test_m2_ingestion.py
    ├── test_m3_loao.py
    ├── test_m4_beam_search.py
    ├── test_m5_pvmc.py
    ├── test_m6_lifecycle_export.py
    ├── test_m7_api.py
    └── e2e\
        ├── runner.py            # Comprehensive E2E test runner
        ├── test_planted_exceptions.py  # 50k rows, 15 injected exceptions test (AC-1)
        ├── test_waterline_null.py      # Uniform distribution null test (AC-2)
        ├── test_reconciliation_invariant.py # Penny-level net variance match (AC-3)
        ├── test_overlap_invariant.py   # Net unique exposure set union match (AC-4)
        ├── test_negative_numeric.py    # Formula injection & negative numbers (AC-5)
        ├── test_air_gap.py             # Zero network call verification (AC-6)
        ├── test_mxa_persistence.py     # .mxa single-file reload invariant (AC-7)
        ├── test_quarantine_watermark.py# Indelible watermark invariant (AC-8)
        └── test_punitive_lockout.py    # Gated disposition code lockout (AC-9)
```
