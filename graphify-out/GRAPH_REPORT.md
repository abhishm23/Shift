# Graph Report - Shift  (2026-09-21)

## Corpus Check
- 162 files · ~583,795 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1664 nodes · 2595 edges · 163 communities (147 shown, 16 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- post
- get_overlap_ledger
- test_m3_loao.py
- test_m4_beam_search.py
- bundle
- test_adversarial_ui_2_2.py
- _create_controlled_source
- generate_50k_canonical_dataset
- package.json
- test_m6_lifecycle_export.py
- 2. Root Cause Analysis & Technical Fixes
- get_configured_duckdb
- test_m5_pvmc.py
- test_full_analytical_pipeline_and_export_integrity
- test_m1_shell.py
- test_adversarial_ui_cleanslate.py
- test_adversarial_m5_pvmc.py
- e2e/test_quarantine_watermark.py
- App.jsx
- parametrize
- ToneGuard
- perform_installation
- CulpritStatsAccumulator
- execute_ingestion
- get_workspace_meta
- compute_pvmc_bridge
- WorkspaceState
- generate_waterline_null_dataset
- UITestRunner
- TestFrontendAssetAirGap
- init_schema
- LOAOResult
- test_adversarial_m1_2.py
- close_workspace
- Round2UITestRunner
- validate_finding_transition
- compute_portfolio_reconciliation
- conftest.py
- runner.py
- 1. Observation
- loao.py
- test_m2_ingestion.py
- BRIEFING — 2026-09-21T10:01:00+05:30
- enterprise_2m_parquet
- 3. The 11 Complex Edge-Case Test Scenarios
- app.py
- Sift E2E Testing Infrastructure & Verification Architecture
- pvmc_two_periods_parquet
- reconciliation_certified_csv
- reconciliation_quarantine_csv
- test_deliverables/generate_datasets.py
- test_challenger_adversarial_deep.py
- Victory Audit Handoff Report: Sift Commercial Audit Application
- .apply_to_connection
- MANIFEST.json
- TestDesktopRunnerAirGap
- BRIEFING — 2026-09-21T04:23:00Z
- deal_desk_xlsx
- Developer Sub-Agent Round 2 Handoff Report
- formula_injection_csv
- verify_stress_challenger.py
- host_header_validation_middleware
- test_tone_guard_sanitizer
- Victory Auditor Progress Log
- adversarial_challenger_test.py
- TestContentSecurityPolicyHeaders
- backend/__init__.py
- manual_testing/generate_datasets.py
- build_distribution.py
- generate_icon.py
- e2e/__init__.py
- sift-shell
- Interface Contracts
- Project Sift: Distribution & Deployment Guide
- BRIEFING — 2026-09-21T04:22:45Z
- Requirements
- BRIEFING — 2026-09-21T04:10:00Z
- Requirements
- Sift Stress Dataset Manifest
- sanitize_csv_cell
- BRIEFING — 2026-09-21T04:32:00Z
- Original User Request
- Requirements
- Phase Breakdown
- Sentinel Final Handoff Report — 2026-09-21T04:32:00Z
- Progress Tracking — Sift QA/Dev Alternating Cycle
- Dispatch: QA Test Engineer (Round 2)
- Requirements
- E2E Test Suite Publication & Readiness Declaration
- Dispatch: Developer (Round 2)
- Requirements
- update_round2_dev_deliverables.py
- Progress — Round 2 Isolated QA Test Engineer
- Acceptance Criteria
- Acceptance Criteria
- Acceptance Criteria
- Requirements
- Requirements
- TEST_DELIVERABLES_90a5dc69.md
- Sift Commercial Audit & Margin Triage — UI Test Results
- Dispatch Log
- Acceptance Criteria
- Acceptance Criteria
- complex_commercial_deal_desk_4e7e5362.md
- Developer Round 2 Progress
- Detailed Defect Records
- Sift Commercial Audit & Margin Triage — Comprehensive UI Test Suite Deliverables
- test_mxa_persistence.py
- Final Orchestration Handoff Report: Sift Commercial Audit QA/Dev Cycle
- calculate_realized_discount_rate
- client
- api_test_client
- victory_auditor_1/DISPATCH.md
- compute_loao_baselines
- test_superadditive_anomalous_joint_concession

## God Nodes (most connected - your core abstractions)
1. `execute_ingestion()` - 58 edges
2. `init_schema()` - 42 edges
3. `compute_loao_baselines()` - 40 edges
4. `run_beam_search()` - 38 edges
5. `close_workspace()` - 38 edges
6. `generate_50k_canonical_dataset()` - 32 edges
7. `open_workspace()` - 31 edges
8. `compute_pvmc_bridge()` - 28 edges
9. `create_workspace()` - 28 edges
10. `get_configured_duckdb()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `test_subadditive_dampening_interaction()` --uses--> `ToneGuard`  [INFERRED]
  tests/test_m5_pvmc.py → backend/interactions.py
- `test_superadditive_anomalous_joint_concession()` --uses--> `ToneGuard`  [INFERRED]
  tests/test_m5_pvmc.py → backend/interactions.py
- `test_tone_guard_sanitizer()` --uses--> `ToneGuard`  [INFERRED]
  tests/test_m5_pvmc.py → backend/interactions.py
- `test_planted_exception_recovery_100pct_precision_recall()` --calls--> `run_beam_search()`  [EXTRACTED]
  tests/e2e/test_planted_exceptions.py → backend/beam_search.py
- `test_waterline_uniform_null_returns_zero_defensible_findings()` --calls--> `run_beam_search()`  [EXTRACTED]
  tests/e2e/test_waterline_null.py → backend/beam_search.py

## Import Cycles
- None detected.

## Communities (163 total, 16 thin omitted)

### Community 0 - "post"
Cohesion: 0.12
Nodes (23): api_compute_pvmc_bridge(), api_diff_runs(), api_evaluate_interactions(), api_export_actionable_findings(), api_export_executive_summary(), api_export_restricted_deal_ledger(), api_run_beam_search(), api_transition_finding() (+15 more)

### Community 1 - "get_overlap_ledger"
Cohesion: 0.06
Nodes (41): compute_net_unique_portfolio_exposure(), get_finding_transactions(), get_overlap_ledger(), Any, DuckDBPyConnection, Sift Deduplicated Overlap-Aware Ledger & Inverted Transaction Mapping…, Returns transaction-level detail rows for the slide-over drawer in View 3.…, Computes the canonical deduplicated Net Unique Portfolio Exposure via SQL set… (+33 more)

### Community 2 - "test_m3_loao.py"
Cohesion: 0.11
Nodes (19): classify_attributes(), Categorizes input columns into default Three-Column Comparability sets: -…, Comprehensive Unit & Integration Test Suite for Milestone 3: LOAO Calibration &…, Tests automatic classification helper into controls, investigation dims, and…, Core LOAO Invariant: An account's own transactions MUST NOT influence its peer…, Tests hierarchical back-off: - Tier 0: Granular cohort satisfies N >= 10, |A|…, AC-1 Verification through backend.loao: Runs compute_loao_baselines on the…, AC-2 Verification: On a synthetically uniform distribution in [0.12, 0.16],… (+11 more)

### Community 3 - "test_m4_beam_search.py"
Cohesion: 0.08
Nodes (44): apply_benjamini_hochberg_fdr(), compute_empirical_bayes_shrinkage(), compute_finding_fingerprint(), compute_wald_hypothesis_test(), _ensure_schema_exists(), _get_or_create_calibration_id(), Any, DuckDBPyConnection (+36 more)

### Community 4 - "bundle"
Cohesion: 0.04
Nodes (46): icons/128x128@2x.png, icons/128x128.png, icons/32x32.png, icons/icon.icns, icons/icon.ico, build, beforeBuildCommand, beforeDevCommand (+38 more)

### Community 5 - "test_adversarial_ui_2_2.py"
Cohesion: 0.07
Nodes (33): BidirectionalMapping, _normalize_name(), preview_source(), propose_column_mapping(), dict, Sift Schema Ingestion & Reconciliation Gate (Milestone 2) Implements: 1. Pass 1…, Dictionary that allows lookup by canonical field or source column. Canonical…, Normalizes column name for fuzzy matching (lowercase, no symbols/spaces). (+25 more)

### Community 6 - "_create_controlled_source"
Cohesion: 0.06
Nodes (29): _create_controlled_source(), parametrize, Path, Stress-tests the exact 1 bp (0.01%) gate boundary. - <= 1.0000 bp: MUST award…, Discrepancy at exactly 1.0000 bp (0.01%) on net revenue: Variance =…, Discrepancy at 1.0001 bp on net revenue: Variance = confirmed_net * 0.00010001.…, Discrepancy at exactly 1.0000 bp on gross revenue (with net variance = 0.0):…, Discrepancy at 1.0001 bp on gross revenue (with net variance = 0.0): Must… (+21 more)

### Community 7 - "generate_50k_canonical_dataset"
Cohesion: 0.07
Nodes (36): AC-3: Reconciliation Invariant Test. Authoritative Requirement: Aggregate…, generate_50k_canonical_dataset(), generate_reconciliation_dataset(), PlantedGroundTruth, Any, DataFrame, Synthetic Commercial Sales Transaction Data Generator for Sift. Generates: 1.…, Generates a dataset and corresponding control totals with specified discrepancy… (+28 more)

### Community 8 - "package.json"
Cohesion: 0.06
Nodes (30): autoprefixer, clsx, lucide-react, postcss, react, react-dom, dependencies, clsx (+22 more)

### Community 9 - "test_m6_lifecycle_export.py"
Cohesion: 0.12
Nodes (26): compute_finding_fingerprint(), diff_audit_runs(), get_finding_history(), Any, DuckDBPyConnection, Milestone 6: Finding Lifecycle State Machine, SHA-256 Fingerprinting, Punitive…, Applies a validated lifecycle state transition to a finding record, enforcing…, Returns the complete immutable audit history for a finding. (+18 more)

### Community 10 - "2. Root Cause Analysis & Technical Fixes"
Cohesion: 0.08
Nodes (24): 1. Executive Summary, 2. Root Cause Analysis & Technical Fixes, 3. Step-by-Step QA Retest Verification Procedures, 4. Build & Regression Test Verification, 5. Layman UX & Usability Enhancements (File Upload & Minimalist Scenarios), DEF-UI-01 (TC-021): Readiness Tier Dynamic Locking on Missing Pocket Margin Fields, DEF-UI-02 (TC-022): Absence of Interactive Column Remapping Selectors in View 1, DEF-UI-03 & DEF-UI-08 (TC-033, TC-062): Three-Column Attribute Categorization Not Populated in View 2 (+16 more)

### Community 11 - "get_configured_duckdb"
Cohesion: 0.10
Nodes (29): air_gap_enforcer(), fixture, AC-6: Air-Gap Verification Test. Authoritative Requirement: Complete execution…, Air-gap fixture that blocks all outbound socket connections to non-loopback…, AC-6: Executes full lifecycle (data generation, ingestion, LOAO calibration,…, test_complete_analytical_lifecycle_under_strict_air_gap(), apply_empirical_bayes_and_fdr(), compute_reference_loao_p75() (+21 more)

### Community 12 - "test_m5_pvmc.py"
Cohesion: 0.07
Nodes (27): tests/test_m5_pvmc.py Milestone 5 Comprehensive Test Suite: Interaction…, T-INT-02: Verifies cap breach exposure calculation across a multi-transaction…, T-INT-03: Verifies that contractual cap breaches are formally classified as…, T-PVMC-01: Verifies exact penny reconciliation across a multi-SKU portfolio:…, T-PVMC-02: Pure price increase of +10%. Volumes and unit costs unchanged.…, T-PVMC-03: Pure cost inflation: Unit COGS increases by $5. Volume and prices…, T-PVMC-04: Pure volume expansion of 1.5x. Prices, costs, and portfolio mix…, T-PVMC-05: Total volume constant (200 units). Prices and costs constant. 50… (+19 more)

### Community 13 - "test_full_analytical_pipeline_and_export_integrity"
Cohesion: 0.15
Nodes (19): export_actionable_findings(), export_executive_summary(), export_restricted_deal_ledger(), Any, DuckDBPyConnection, Milestone 6: Safe Export Engine & Formula Injection Defense. Supports: 1.…, Two-step formula injection defense: Phase 1: Pure numeric preservation…, Exports full line-item records encrypted with AES-256 password protection.… (+11 more)

### Community 14 - "test_m1_shell.py"
Cohesion: 0.08
Nodes (25): client(), fixture, Milestone 1 Test Suite: Desktop Shell & Local Runtime Harness Verifies Tauri…, Verifies find_edge_browser discovers Microsoft Edge or Chromium on host., Verifies build_browser_args includes --app, window size, profile dir, and anti-…, Verifies GET /api/health returns status ok, app sift, version 0.1.0, and…, Verifies host header validation blocks external hosts and permits loopback., Verifies that security headers (CSP, nosniff, DENY, etc.) are returned on… (+17 more)

### Community 15 - "test_adversarial_ui_cleanslate.py"
Cohesion: 0.08
Nodes (23): Adversarial Clean Slate & Asset Air-Gap Challenge Test Suite Author:…, Verify that WatermarkBanner component logic strictly suppresses rendering when…, CRITICAL ADVERSARIAL CHALLENGE: In App.jsx, WatermarkBanner MUST receive…, Verify that View1Reconcile's reconciliation calculation requires BOTH valid…, Verify that dist/index.html enforces strict CSP and contains zero external…, Audit all JS/CSS files in src/dist/assets for external URLs., Deep scan across all files in src/dist for common CDN signatures., r""" Adversarial Integrity Invariant: Verify that repository root… (+15 more)

### Community 16 - "test_adversarial_m5_pvmc.py"
Cohesion: 0.10
Nodes (22): evaluate_contractual_cap_stacking(), evaluate_interactions(), Any, DuckDBPyConnection, backend/interactions.py Milestone 5 (M5.1): Interaction Detection, Compound…, Returns the mandatory canonical commercial label for an interaction result., Evaluates Tier 3 rule-based compound concession stacking against a contractual…, Evaluates statistical exploratory pairwise interaction between two dimensions.… (+14 more)

### Community 17 - "e2e/test_quarantine_watermark.py"
Cohesion: 0.23
Nodes (11): evaluate_reconciliation_gate(), format_export_with_watermark_guard(), AC-8: Quarantine Watermark Invariant Test. Authoritative Requirement:…, AC-8: Dataset with variance > 1.0 bp (e.g. 5.0 bp / 0.05%, $4,250 residual)…, AC-8: Integrates directly with synthetic_data.generate_reconciliation_dataset., Evaluates the 1 bp reconciliation gate. If variance <= 1.0 bp: returns…, Simulates export generator applying the indelible watermark header whenever…, AC-8: Dataset with variance <= 1.0 bp (e.g. 0.45 bp) receives CERTIFIED_AUDIT… (+3 more)

### Community 18 - "App.jsx"
Cohesion: 0.17
Nodes (11): App(), OverlapLedgerDrawer(), PVMCBridgeView(), UseCaseGuide(), CANONICAL_FIELDS, getColumnTaxonomy(), View1Reconcile(), View2Calibrate() (+3 more)

### Community 19 - "parametrize"
Cohesion: 0.11
Nodes (13): parametrize, Verify that DNS rebinding defense guards all endpoints, not just /api/health., Verify empty host header is strictly rejected., Verify legitimate local loopback hosts pass through host validation., Adversarial challenge verifying that CORS rejects all external and untrusted…, Challenge: Send OPTIONS preflight with foreign Origin. Requirement: access-…, Challenge: Send GET request with foreign Origin header. Requirement: Response…, Verify explicitly allowed loopback origins receive matching CORS headers. (+5 more)

### Community 20 - "ToneGuard"
Cohesion: 0.19
Nodes (18): Raised when a blacklisted punitive phrase is attempted in statistical…, Tone Guard Programmatic Enforcer (R5.3). Enforces approved commercial auditing…, Checks if text contains any forbidden punitive phrases in statistical mode., Validates text against Tone Guard rules. Raises ToneGuardViolationError if a…, ToneGuard, ToneGuardViolationError, Challenge 1.3: Verify all blacklisted punitive phrases are blocked under…, Challenge 1.1: Verify case variations (UPPER, lower, mIxEd, Title) are strictly… (+10 more)

### Community 21 - "perform_installation"
Cohesion: 0.15
Nodes (19): RuntimeError, create_shortcut(), get_base_res(), gui_main(), kill_running_sift(), perform_installation(), Path, Standalone Zero-Admin Setup Wizard for Sift Commercial Deal Desk. Installs Sift… (+11 more)

### Community 22 - "CulpritStatsAccumulator"
Cohesion: 0.20
Nodes (15): Schema, Table, generate_4gb_dataset(), build_pyarrow_schema(), compute_file_sha256(), CulpritStatsAccumulator, generate_batch_table(), generate_dataset_15m_parquet() (+7 more)

### Community 23 - "execute_ingestion"
Cohesion: 0.08
Nodes (22): compute_data_readiness_scorecard(), execute_ingestion(), Any, DuckDBPyConnection, Computes data completeness metrics across Tiers 1, 2, and 3: - Tier 1: Core…, Pass 2: Vectorized DuckDB scan and 1 bp reconciliation gate. - Loads CSV or…, Adversarial Empirical Stress Suite for Milestone 2: Reconciliation Invariant…, Adversarially tests grain deduplication of duplicate transaction_line_id… (+14 more)

### Community 24 - "get_workspace_meta"
Cohesion: 0.33
Nodes (6): post_workspace_open(), Opens or connects to an existing single-file .mxa project workspace., WorkspaceOpenRequest, get_workspace_meta(), Any, Retrieves project metadata, audit manifest reconciliation status, watermark…

### Community 25 - "compute_pvmc_bridge"
Cohesion: 0.10
Nodes (25): compute_homogeneous_segment_pvmc(), compute_pvmc_bridge(), parse_period_filter(), Any, DuckDBPyConnection, backend/pvmc_bridge.py Decoupled Engine B: Period-over-Period Macro PVMC Margin…, Computes exact PVMC decomposition for a single homogeneous UoM segment., Translates period shorthand or expressions into a validated DuckDB SQL WHERE… (+17 more)

### Community 27 - "generate_waterline_null_dataset"
Cohesion: 0.15
Nodes (13): generate_waterline_null_dataset(), Generates a waterline uniform, non-anomalous distribution dataset where all…, Verify that waterline distribution has tightly bounded discounts with zero…, test_waterline_distribution_properties(), parametrize, Adversarial Test 1.3: Uniform Discount Range Stress. Verifies that regardless…, Adversarial Test 1.4: Alternative Threshold Strategy (Median + 1.5 * MAD).…, Stress-tests false discovery control of run_beam_search on purely non-anomalous… (+5 more)

### Community 29 - "TestFrontendAssetAirGap"
Cohesion: 0.12
Nodes (10): client(), fixture, Ensure clean workspace state before each test client invocation., Adversarial verification of frontend production bundle in src/dist. Ensures…, Verify src/dist/index.html includes meta tag Content-Security-Policy…, Verify all CSS files in src/dist/assets: - No http:// or https:// - No remote…, Verify that all runtime network invocation primitives (fetch, XMLHttpRequest,…, Audit all URI strings across JS chunks: Assert that every URI is either: 1.… (+2 more)

### Community 30 - "init_schema"
Cohesion: 0.06
Nodes (34): init_schema(), Idempotently creates all 8 core relational tables and indices. If meta_project…, Verify all 8 core tables exist and have complete canonical columns with correct…, Adversarial verification: Primary Key uniqueness must be enforced on ALL 8 core…, Verify that inserting child records referencing non-existent parent keys is…, Stress-test deletion mechanics: 1. Verify DuckDB blocks parent deletions when…, test_stress_ddl_table_presence_and_columns(), test_stress_fk_blocking_and_twostage_deletion() (+26 more)

### Community 31 - "LOAOResult"
Cohesion: 0.16
Nodes (6): LOAOResult, Any, DataFrame, dict, Result container for compute_loao_baselines. Implements dict for summary…, Returns JSON-serializable summary dictionary without the raw DataFrame.

### Community 32 - "test_adversarial_m1_2.py"
Cohesion: 0.22
Nodes (13): build_browser_args(), find_edge_browser(), is_port_in_use(), main(), probe_sift_health(), Sift Local Desktop Runtime Harness Launches backend FastAPI analytical server…, Construct command-line arguments for standalone, air-gapped app window., Check if a TCP port is currently open and accepting connections. (+5 more)

### Community 33 - "close_workspace"
Cohesion: 0.08
Nodes (55): DuckDBConfig, DuckDB and Storage Configuration for Sift Desktop Application. Enforces 4GB…, Configuration container for in-process DuckDB engine., attach_workspace(), checkpoint_workspace(), close_workspace(), create_workspace(), detach_workspace() (+47 more)

### Community 35 - "validate_finding_transition"
Cohesion: 0.20
Nodes (13): Validates finding lifecycle state transitions according to R6.41 and AC-9.…, validate_finding_transition(), AC-9: Punitive Disposition Code Lockdown Test. Authoritative Requirement:…, AC-9: Setting punitive disposition codes on Tier 1 finding must be rejected., AC-9: Setting punitive disposition codes on Tier 2 finding must be rejected., AC-9: Setting punitive disposition codes on Tier 3 (Rule-Confirmed Exception)…, AC-9: Non-punitive commercial disposition codes must be permitted on Tier 1 and…, AC-9: Dismissals without mandatory category or snooze date must be rejected. (+5 more)

### Community 36 - "compute_portfolio_reconciliation"
Cohesion: 0.09
Nodes (17): compute_portfolio_reconciliation(), DataFrame, Computes portfolio reconciliation metrics: - Line variance: Delta_i =…, AC-3: Invariant holds to the cent on 50,000-row canonical dataset., AC-3: Invariant holds to the cent on waterline uniform dataset., AC-3: Tests invariant across edge conditions: 1. All transactions are…, test_reconciliation_invariant_extreme_boundary_cases(), test_reconciliation_invariant_on_50k_dataset() (+9 more)

### Community 37 - "conftest.py"
Cohesion: 0.21
Nodes (12): canonical_50k_data(), fixture, Pytest configuration and shared fixtures for Sift test suite., Generates and caches 50,000-row synthetic dataset with 15 planted exceptions., Generates and caches waterline uniform null distribution dataset., Provides a fresh isolated temporary directory for test artifacts and .mxa files., Default comparability controls., Default investigation dimensions. (+4 more)

### Community 38 - "runner.py"
Cohesion: 0.23
Nodes (9): main(), print_terminal_report(), Any, PytestSummaryCollector, Independent E2E Acceptance Test Suite Runner for Sift. Executes all 9…, Runs pytest for a specific AC test file and returns summary metrics., Prints a structured, formatted ASCII report to stdout., Pytest plugin to capture individual test outcomes and timings. (+1 more)

### Community 39 - "1. Observation"
Cohesion: 0.12
Nodes (16): 1.1 Strict Isolation Compliance, 1.2 Extreme-Scale Dataset Generation & Staging, 1.3 Application Server & Black-Box UI Test Execution, 1.4 Verbatim Test Execution Outputs & Performance Metrics, 1.5 Verification of Historical Defect Fixes (DEF-UI-01 to DEF-UI-10), 1.6 Deliverable Ledgers Synchronization, 1. Observation, 2. Logic Chain (+8 more)

### Community 40 - "loao.py"
Cohesion: 0.17
Nodes (17): export_calibration_profile(), freeze_calibration(), get_active_calibration_profile(), _get_table_columns(), load_calibration_profile(), DuckDBPyConnection, Path, Sift Leave-One-Account-Out (LOAO) Calibration & Defensible Gap Scoring… (+9 more)

### Community 41 - "test_m2_ingestion.py"
Cohesion: 0.05
Nodes (36): client(), fixture, Milestone 2 Test Suite: Schema Ingestion & Reconciliation Gate Comprehensive…, Verifies Pass 1 Parquet preview with canonical column names., Verifies preview_source raises FileNotFoundError for non-existent path., Verifies vectorized loading, converted columns, and reporting metrics., Verifies that discrepancy <= 1.0 bp receives CERTIFIED_AUDIT with no watermark., Verifies that discrepancy > 1.0 bp triggers QUARANTINED_AND_PROCEEDED with AC-8… (+28 more)

### Community 42 - "BRIEFING — 2026-09-21T10:01:00+05:30"
Cohesion: 0.17
Nodes (11): Artifact Index, Attack Surface, Audit Progress, Audit Scope, BRIEFING — 2026-09-21T10:01:00+05:30, Current Parent, 🔒 Key Constraints, Key Decisions Made (+3 more)

### Community 43 - "enterprise_2m_parquet"
Cohesion: 0.18
Nodes (11): enterprise_2m_parquet, currencies, format, path, planted_anomalies_count, rows, CAD, EUR (+3 more)

### Community 44 - "3. The 11 Complex Edge-Case Test Scenarios"
Cohesion: 0.12
Nodes (16): 1. Test Environment & Prerequisites, 2. Generated Datasets Inventory, 3. The 11 Complex Edge-Case Test Scenarios, 4. Quick-Run Automated CLI Test Script, Sift Manual Testing Guide & Comprehensive Edge-Case Verification Protocol, Use Case 10: Decoupled Engine B Macro Margin Bridge (PVMC) & UoM Homogeneity Guard, Use Case 11: Lifecycle Governance, AC-9 Punitive Lockout & AES-256 Encrypted Export, Use Case 1: Big Data Scale & In-Process Out-of-Core Spill Stress Test (2 Million Rows) (+8 more)

### Community 45 - "app.py"
Cohesion: 0.10
Nodes (32): api_get_finding_history(), api_get_finding_transactions(), api_get_overlap_ledger(), CalibrateFreezeRequest, fallback_landing(), get_calibrate_profiles(), get_health(), get_workspace_metadata() (+24 more)

### Community 46 - "Sift E2E Testing Infrastructure & Verification Architecture"
Cohesion: 0.13
Nodes (14): 1. Overview & Testing Philosophy, 2. Test Architecture & Directory Layout, 3. Acceptance Criteria Coverage Matrix, 4.1 Canonical 50k Dataset & Planted Exceptions, 4.2 Waterline Uniform Null Distribution, 4.3 Control Total Discrepancy Generator, 4. Synthetic Data Generators (`tests/synthetic_data.py`), 5. Execution Commands (+6 more)

### Community 47 - "pvmc_two_periods_parquet"
Cohesion: 0.20
Nodes (10): pvmc_two_periods_parquet, format, path, periods, rows, uoms, 2024-H1, 2025-H1 (+2 more)

### Community 48 - "reconciliation_certified_csv"
Cohesion: 0.20
Nodes (10): reconciliation_certified_csv, actual_list, actual_net, declared_list, declared_net, expected_status, format, path (+2 more)

### Community 49 - "reconciliation_quarantine_csv"
Cohesion: 0.20
Nodes (10): reconciliation_quarantine_csv, actual_list, actual_net, declared_list, declared_net, expected_status, format, path (+2 more)

### Community 50 - "test_deliverables/generate_datasets.py"
Cohesion: 0.38
Nodes (9): generate_dataset_01(), generate_dataset_02(), generate_dataset_03(), generate_dataset_04(), generate_dataset_05(), generate_dataset_06(), generate_dataset_07(), generate_dataset_08() (+1 more)

### Community 51 - "test_challenger_adversarial_deep.py"
Cohesion: 0.14
Nodes (13): tests/test_challenger_adversarial_deep.py Adversarial Challenge & Invariant…, Tests that datasets containing an explicit 'pocket_margin_amt' column ingest…, Tests that the real 87-column stress dataset (dataset_stress_1m_wide.csv) which…, Verifies that <= 1 bp achieves Certified Audit while > 1 bp triggers Quarantine…, Empirically verifies Culprit Alpha, Beta, Gamma in dataset_stress_1m_wide.csv., Verifies 4GB memory ceiling enforcement and disk spill directory configuration., Stress-tests DuckDB spilling to disk under tight memory constraints (32MB)…, test_4gb_ram_boundary_and_spilling_config() (+5 more)

### Community 52 - "Victory Audit Handoff Report: Sift Commercial Audit Application"
Cohesion: 0.20
Nodes (9): 1.1 Phase A: Timeline & Sequential Alternating Loop Audit, 1.2 Phase B: Cheating & Forensic Integrity Checks, 1.3 Phase C: Independent Test & Workspace Hygiene Execution, 1. Observation, 2. Logic Chain, 3. Caveats, 4. Conclusion, 5. Verification Method (+1 more)

### Community 53 - ".apply_to_connection"
Cohesion: 0.25
Nodes (5): Any, DuckDBPyConnection, Returns verified, writable temporary spilling directory. Creates the directory…, Returns dictionary of connection parameters accepted by duckdb.connect., Applies configuration pragmas directly to an existing DuckDB connection.

### Community 54 - "MANIFEST.json"
Cohesion: 0.25
Nodes (7): sparse_cohorts_parquet, format, path, rows, sparse_cohorts, Legacy Mainframe, Quantum Computing

### Community 55 - "TestDesktopRunnerAirGap"
Cohesion: 0.25
Nodes (5): Adversarial verification of backend/run_desktop.py launcher and command line…, Verify host Edge/Chromium discovery finds a real, executable binary., Verify the exact air-gap and sandboxing arguments generated for standalone…, Verify probe_sift_health correctly validates response payload structure., TestDesktopRunnerAirGap

### Community 56 - "BRIEFING — 2026-09-21T04:23:00Z"
Cohesion: 0.17
Nodes (11): Artifact Index, BRIEFING — 2026-09-21T04:23:00Z, Change Tracker, Current Parent, 🔒 Key Constraints, Key Decisions Made, Loaded Skills, Mission (+3 more)

### Community 57 - "deal_desk_xlsx"
Cohesion: 0.29
Nodes (7): deal_desk_xlsx, format, path, rows, sheets, Authority_Matrix, Granular_Sales_Transactions

### Community 58 - "Developer Sub-Agent Round 2 Handoff Report"
Cohesion: 0.20
Nodes (9): 1.1 Deliverable Ledgers & QA Round 2 Findings Inspection, 1.2 Architectural Review & Code Verification, 1.3 Full Backend Regression Suite Execution, 1. Observation, 2. Logic Chain, 3. Caveats, 4. Conclusion, 5. Verification Method (+1 more)

### Community 59 - "formula_injection_csv"
Cohesion: 0.33
Nodes (6): formula_injection_csv, format, has_formulas, has_negative_numbers, path, rows

### Community 60 - "verify_stress_challenger.py"
Cohesion: 0.50
Nodes (4): compute_sha256(), Path, verify_stress_challenger.py Empirical Adversarial Verification of Sift Stress…, run_adversarial_verification()

### Community 61 - "host_header_validation_middleware"
Cohesion: 0.67
Nodes (4): host_header_validation_middleware(), security_headers_middleware(), middleware, Request

### Community 62 - "test_tone_guard_sanitizer"
Cohesion: 0.50
Nodes (3): Replaces forbidden punitive phrases with approved commercial taxonomy., Verifies that ToneGuard.sanitize cleanly replaces punitive terms in statistical…, test_tone_guard_sanitizer()

### Community 64 - "adversarial_challenger_test.py"
Cohesion: 0.83
Nodes (3): log_test(), preview_file(), run_adversarial_suite()

### Community 65 - "TestContentSecurityPolicyHeaders"
Cohesion: 0.50
Nodes (3): Adversarial challenge asserting strict air-gapped CSP and protective security…, Stress test: When a DNS rebinding attack is rejected with HTTP 403, does the…, TestContentSecurityPolicyHeaders

### Community 116 - "Interface Contracts"
Cohesion: 0.14
Nodes (13): Architecture, Code Layout, Feature Inventory, Interface Contracts, M1 Storage & Engine Interface, M2 Ingestion & Gate Interface, M3 LOAO Calibration Interface, M4 Beam Search & Overlap Ledger Interface (+5 more)

### Community 117 - "Project Sift: Distribution & Deployment Guide"
Cohesion: 0.15
Nodes (12): 1. Distribution Overview & Strategy, 2. Distribution Formats: Which One to Use When?, 3. Detailed Usage Instructions, 4. System & Hardware Requirements, 5. Security, Privacy & Compliance Safeguards, 6. Verification & Test Data, Enterprise IT Silent Deployment:, Option A: Portable Archive (`Sift-v1.0-Portable.zip`) (+4 more)

### Community 118 - "BRIEFING — 2026-09-21T04:22:45Z"
Cohesion: 0.17
Nodes (11): Active Timers, Artifact Index, BRIEFING — 2026-09-21T04:22:45Z, Current Parent, 🔒 Key Constraints, Key Decisions Made, Mission, 🔒 My Identity (+3 more)

### Community 119 - "Requirements"
Cohesion: 0.17
Nodes (11): Acceptance Criteria, Deliverables Integrity & State Hygiene, End-to-End Visual UI Testing, Initial Request — 2026-09-21T03:45:50Z, Original User Request, R1. Synthetic Data Generation & Isolated Test Engineer Harness, R2. Deliverables Logging & Cumulative Round Appending, R3. Developer Implementation & Workspace Hygiene (+3 more)

### Community 120 - "BRIEFING — 2026-09-21T04:10:00Z"
Cohesion: 0.17
Nodes (11): Artifact Index, BRIEFING — 2026-09-21T04:10:00Z, Change Tracker, Current Parent, 🔒 Key Constraints, Key Decisions Made, Loaded Skills, Mission (+3 more)

### Community 121 - "Requirements"
Cohesion: 0.17
Nodes (11): Acceptance Criteria, Deliverables Integrity & State Hygiene, End-to-End Visual UI Testing, Initial Request — 2026-09-21T03:45:50Z, Original User Request, R1. Synthetic Data Generation & Isolated Test Engineer Harness, R2. Deliverables Logging & Cumulative Round Appending, R3. Developer Implementation & Workspace Hygiene (+3 more)

### Community 122 - "Sift Stress Dataset Manifest"
Cohesion: 0.17
Nodes (11): 1. File Metadata Overview, 2. Deeply Buried Multi-Attribute Culprit Ground Truth, 3. Complete Column Schema Table (87 Columns), 4. In-Process DuckDB Verification Log, 5. Automated Python Verification Code, Culprit Alpha (4-Level Compound Slice), Culprit Beta (5-Level Compound Slice), Culprit Gamma (3-Level Compound Slice) (+3 more)

### Community 123 - "sanitize_csv_cell"
Cohesion: 0.24
Nodes (10): Any, Two-step formula injection defense algorithm: Phase 1: Pure numeric…, sanitize_csv_cell(), AC-5: Negative Numeric Integrity & Formula Injection Defense Test.…, AC-5: Valid negative and signed numbers must remain raw and unquoted., AC-5: Malicious non-numeric text strings starting with =, +, -, @, \\t, \\r…, AC-5: Verifies that in an actual exported CSV file: 1. Negative financial…, test_csv_export_byte_stream_integrity() (+2 more)

### Community 124 - "BRIEFING — 2026-09-21T04:32:00Z"
Cohesion: 0.22
Nodes (8): Artifact Index, BRIEFING — 2026-09-21T04:32:00Z, 🔒 Key Constraints, Mission, 🔒 My Identity, Project Status, User Context, Victory Audit Status

### Community 126 - "Original User Request"
Cohesion: 0.22
Nodes (8): 2026-09-15T13:55:53Z, Follow-up — 2026-09-15T22:45:54Z, Follow-up — 2026-09-16T00:08:10Z, Follow-up — 2026-09-16T06:21:00Z, Follow-up — 2026-09-17T02:52:14Z, Follow-up — 2026-09-17T04:26:49Z, Follow-up — 2026-09-17T05:51:47Z, Original User Request

### Community 127 - "Requirements"
Cohesion: 0.22
Nodes (9): R1. Desktop Harness, In-Process Data Engine & Air-Gapped Persistence, R2. Canonical Schema Ingestion, Data Readiness Scorecard & Reconciliation Gate, R3. LOAO Baseline Calibration, Boundary Fencing & Non-Linear Gap Scoring, R4. Diagnostic Traversal Beam Search, Statistical Shrinkage & Deduplicated Overlap Ledger, R5. Interaction Detection & Decoupled Macro Margin Bridge (Engine B), R6. Deterministic Fingerprinting, Lifecycle State Machine & Run-over-Run Diffing, R7. Minimalist Three-View UI, R8. Safe Export Engine & Formula Injection Defense (+1 more)

### Community 128 - "Phase Breakdown"
Cohesion: 0.25
Nodes (7): Mission, Operational Plan: Sift Autonomous Alternating QA/Dev Cycle, Phase 1: Round 2 — Isolated QA Test Engineer, Phase 2: Round 2 — Developer Remediation & Workspace Hygiene, Phase 3: Round 3 — Isolated QA Retest & Regression Verification, Phase 4: Final Synthesis & Sentinel Report, Phase Breakdown

### Community 129 - "Sentinel Final Handoff Report — 2026-09-21T04:32:00Z"
Cohesion: 0.29
Nodes (6): Caveats, Conclusion, Logic Chain, Observation, Sentinel Final Handoff Report — 2026-09-21T04:32:00Z, Verification Method

### Community 131 - "Progress Tracking — Sift QA/Dev Alternating Cycle"
Cohesion: 0.40
Nodes (4): Current Status, Iteration Status, Notes & Observations, Progress Tracking — Sift QA/Dev Alternating Cycle

### Community 132 - "Dispatch: QA Test Engineer (Round 2)"
Cohesion: 0.33
Nodes (5): 2026-09-21T03:47:33Z, Assigned Tasks for Round 2, Context & Role, Dispatch: QA Test Engineer (Round 2), Strict Constraints & Isolation Rules (MANDATORY)

### Community 133 - "Requirements"
Cohesion: 0.33
Nodes (6): R1. Strictly Clean Slate Initial Experience, R2. Plain-English, Layman-Friendly Navigation & Terminology, R3. Interactive Collapsible Use-Case & Insights Guide, R4. Progressive Disclosure for Laymen and Data Specialists, R5. Build, Packaging & Invariant Integrity, Requirements

### Community 134 - "E2E Test Suite Publication & Readiness Declaration"
Cohesion: 0.33
Nodes (5): 1. Executive Declaration, 2. Acceptance Criteria Verification Summary, 3. Artifact Index, 4. How to Verify, E2E Test Suite Publication & Readiness Declaration

### Community 135 - "Dispatch: Developer (Round 2)"
Cohesion: 0.40
Nodes (4): 2026-09-21T04:09:03Z, Context & Role, Dispatch: Developer (Round 2), Key Requirements (R2 & R3)

### Community 136 - "Requirements"
Cohesion: 0.40
Nodes (5): R1. Massive High-Dimensional Synthetic Stress Datasets, R2. Strict Black-Box UI Deep-Search & Stress Execution, R3. UX Complexity, Usability & Latency Profiling, R4. Dual-Format Deliverables & Defect Register Update, Requirements

### Community 138 - "Progress — Round 2 Isolated QA Test Engineer"
Cohesion: 0.50
Nodes (3): Milestones, Progress — Round 2 Isolated QA Test Engineer, Status Summary

### Community 139 - "Acceptance Criteria"
Cohesion: 0.50
Nodes (4): Acceptance Criteria, Clean Slate Verification, Layman User Experience & Explanations, Technical & Analytical Robustness

### Community 140 - "Acceptance Criteria"
Cohesion: 0.50
Nodes (4): Acceptance Criteria, Black-Box UI Execution Integrity, Deliverable Structure & Verification, Test Dataset & Scenario Breadth

### Community 141 - "Acceptance Criteria"
Cohesion: 0.50
Nodes (4): Acceptance Criteria, Black-Box UI Stress & Memory Invariant, Stress Datasets & Dimensional Depth, UX Profiling & Deliverables Completeness

### Community 142 - "Requirements"
Cohesion: 0.50
Nodes (4): R1. Black-Box UI Re-Testing of Open Defects, R2. Comprehensive Impact & Regression Testing, R3. Deliverables & Defect Lifecycle Register Update, Requirements

### Community 143 - "Requirements"
Cohesion: 0.50
Nodes (4): R1. Synthetic Test Dataset Generation, R2. Strict Black-Box UI Testing & Navigation, R3. Dual-Format Test Deliverables & Defect Register, Requirements

### Community 144 - "TEST_DELIVERABLES_90a5dc69.md"
Cohesion: 0.50
Nodes (3): Sheet: Defect Register, Sheet: Executive Summary, Sheet: Test Deliverables & Results

### Community 145 - "Sift Commercial Audit & Margin Triage — UI Test Results"
Cohesion: 0.50
Nodes (3): Complete Test Execution Log, Executive Summary, Sift Commercial Audit & Margin Triage — UI Test Results

### Community 148 - "Acceptance Criteria"
Cohesion: 0.67
Nodes (3): Acceptance Criteria, Automated Verification Test Suite, User Interface & Persistence Invariants

### Community 149 - "Acceptance Criteria"
Cohesion: 0.67
Nodes (3): Acceptance Criteria, Deliverables & Defect Parity, Retest & Regression Breadth

### Community 153 - "Detailed Defect Records"
Cohesion: 0.14
Nodes (13): 10. DEF-UI-10: UI/UX Wide Schema Usability Friction - Medium Severity, 1. DEF-UI-01: View 1 Readiness Tier Scorecard - High Severity, 2. DEF-UI-02: View 1 Column Mapping - High Severity, 3. DEF-UI-03: View 2 Calibration - Critical Severity, 4. DEF-UI-04: View 3 Beam Search - Critical Severity, 5. DEF-UI-05: View 1 Wide Schema Preview - Medium Severity, 6. DEF-UI-06: View 1 Pass 2 Ingestion Engine - Critical Severity, 7. DEF-UI-07: View 1 Reconciliation Gate - High Severity (+5 more)

### Community 156 - "Sift Commercial Audit & Margin Triage — Comprehensive UI Test Suite Deliverables"
Cohesion: 0.40
Nodes (4): 1. Executive Test & Architectural Verification Summary, 2. Complete Test Case Results (16 Mandated Columns: Preserving 100% Historical + Round 2 Columns), 3. Defect Register & Resolution Ledger (14 Mandated Columns: Preserving 100% Historical + Round 2 Columns), Sift Commercial Audit & Margin Triage — Comprehensive UI Test Suite Deliverables

### Community 158 - "test_mxa_persistence.py"
Cohesion: 0.33
Nodes (6): init_canonical_mxa_schema(), DuckDBPyConnection, AC-7: Single-File .mxa Workspace Persistence Test. Authoritative Requirement:…, Initializes the 8 canonical relational tables in the .mxa database container., AC-7: Verifies that an entire analytical project state, calibrations,…, test_mxa_single_file_save_and_reload()

### Community 160 - "Final Orchestration Handoff Report: Sift Commercial Audit QA/Dev Cycle"
Cohesion: 0.33
Nodes (5): 1. Executive Summary, 2. Milestone State, 3. Subagent Roster, 4. Key Artifacts & Paths, Final Orchestration Handoff Report: Sift Commercial Audit QA/Dev Cycle

### Community 161 - "calculate_realized_discount_rate"
Cohesion: 0.33
Nodes (6): calculate_realized_discount_rate(), Computes realized discount rate: r_i = (extended_list_amt - net_invoiced_amt) /…, Verifies realized discount rate formula (list - net) / list., Verifies edge cases: zero list, negative list, and null net., test_realized_discount_rate_edge_cases(), test_realized_discount_rate_standard()

### Community 162 - "client"
Cohesion: 0.40
Nodes (5): client(), memory_db(), fixture, Provides an in-memory DuckDB connection with canonical transactions schema., FastAPI TestClient with air-gap loopback headers.

### Community 164 - "api_test_client"
Cohesion: 0.67
Nodes (3): api_test_client(), fixture, Fixture providing a FastAPI TestClient with an active test workspace.

### Community 166 - "compute_loao_baselines"
Cohesion: 0.12
Nodes (19): build_hierarchical_loao_sql(), compute_loao_baselines(), Constructs the fully vectorized multi-tier hierarchical LOAO DuckDB query.…, Computes Leave-One-Account-Out (LOAO) peer cohort statistics over…, Validates three-column attribute classification boundaries: 1. Comparability…, validate_three_column_classification(), If an account is the only account in a cohort, it has 0 peers in that cohort., Verifies that when even the global cohort fails support fences, the… (+11 more)

## Knowledge Gaps
- **364 isolated node(s):** `path`, `rows`, `format`, `USD`, `EUR` (+359 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `execute_ingestion()` connect `execute_ingestion` to `close_workspace`, `compute_portfolio_reconciliation`, `test_adversarial_ui_2_2.py`, `_create_controlled_source`, `test_m2_ingestion.py`, `app.py`, `test_full_analytical_pipeline_and_export_integrity`, `test_challenger_adversarial_deep.py`, `init_schema`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `init_schema()` connect `init_schema` to `close_workspace`, `test_m3_loao.py`, `test_m4_beam_search.py`, `test_adversarial_ui_2_2.py`, `loao.py`, `test_m2_ingestion.py`, `test_m6_lifecycle_export.py`, `test_m5_pvmc.py`, `test_full_analytical_pipeline_and_export_integrity`, `app.py`, `test_challenger_adversarial_deep.py`, `execute_ingestion`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `close_workspace()` connect `close_workspace` to `post`, `test_adversarial_m1_2.py`, `get_overlap_ledger`, `test_m3_loao.py`, `test_m4_beam_search.py`, `test_m2_ingestion.py`, `test_m5_pvmc.py`, `app.py`, `test_m1_shell.py`, `test_challenger_adversarial_deep.py`, `execute_ingestion`, `get_workspace_meta`, `TestFrontendAssetAirGap`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `path`, `rows`, `format` to the rest of the system?**
  _364 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `post` be split into smaller, more focused modules?**
  _Cohesion score 0.11857707509881422 - nodes in this community are weakly interconnected._
- **Should `get_overlap_ledger` be split into smaller, more focused modules?**
  _Cohesion score 0.06038961038961039 - nodes in this community are weakly interconnected._
- **Should `test_m3_loao.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._