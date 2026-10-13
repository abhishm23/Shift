# Original User Request

## 2026-09-15T13:55:53Z

Build "Sift", a local-first, air-gapped commercial audit and margin triage desktop application. Sift enables financial controllers, pricing teams, and commercial deal desks to ingest sales transactions, compute defensible margin exceptions via Leave-One-Account-Out (LOAO) statistical baselines, prioritize revenue recovery opportunities with overlap-aware ledgers, and manage an auditable review workflow.

Working directory: c:/Shift
Integrity mode: development

## Requirements

### R1. Desktop Harness, In-Process Data Engine & Air-Gapped Persistence
- Implement a desktop application shell using Tauri with an embedded in-process DuckDB analytical engine.
- Configure DuckDB with a default 4 GB memory limit and automatic disk-spilling for large aggregations and joins.
- Bundle a local UI using Preact or React with Tailwind CSS and local Lucide icons. All assets, fonts, and chart renderers must be bundled locally with zero telemetry and zero external network calls.
- Persist project state, baseline calibrations, and audit manifests in single-file `.mxa` project workspaces (using DuckDB or SQLite storage).

### R2. Canonical Schema Ingestion, Data Readiness Scorecard & Reconciliation Gate
- **Two-Pass Ingestion:** Implement Pass 1 (streaming preview of first 1,000 rows to propose column mappings) and Pass 2 (vectorized DuckDB scan to validate uniqueness of grain, detect credit notes/reversals, and profile cardinality) supporting CSV and Parquet formats.
- **Canonical Line-Grain Schema:** Map source fields to: `transaction_line_id`, `invoice_id`, `account_id`, `parent_account_id`, `transaction_date`, `currency`, `fx_rate_to_reporting`, `extended_list_amt`, `net_invoiced_amt`, `cogs_amt`, and `off_invoice_rebate`.
- **Readiness Tier Scorecard:** Dynamically unlock Tier 1 (Price Realization & Discount Exceptions), Tier 2 (Defined Pocket Contribution with standard accrual or pro-rata invoiced allocation), and Tier 3 (Policy Compliance Auditing with external approval matrices).
- **Reconciliation Gate & Watermark:** Verify user-confirmed control totals (Total Gross List Revenue and Total Net Invoiced Revenue). If variance is within ±0.01% (1 bp), award "Certified Audit". If variance > 1 bp, initiate the Quarantine-and-Proceed protocol: isolate unreconciled residual rows, log an itemized residual report, and permanently watermark all views, exports, and reports with `UNRECONCILED RESIDUAL: X.XX% ($Y) OUTSIDE AUDIT GUARDRAILS`. Generate an immutable `audit_manifest.json` recording source hash, row count, validation logs, control discrepancies, and user sign-off.

### R3. LOAO Baseline Calibration, Boundary Fencing & Non-Linear Gap Scoring
- **Comparability Assignment:** Require users to categorize attributes into Comparability Controls (justifiable price drivers), Investigation Dimensions (audited attributes strictly barred from comparability controls), and Outcome Metrics.
- **LOAO Cohort Mechanics:** Benchmark transactions using Leave-One-Account-Out logic (excluding all transactions of the evaluated account from the cohort distribution). Enforce cohort support fences (minimum 10 transactions across at least 5 distinct customer accounts). Implement hierarchical back-off when support fails; if the broadest cohort fails, flag as `Insufficient Comparable Evidence` and exclude from automated scoring.
- **Baseline Freezing:** Calculate baselines from locked historical baseline periods and export/import as versioned `.calib.json` calibration profiles. Disallow dynamic rolling baselines during active review.
- **Formulations:** Compute Realized Discount Rate ($r_i = (\text{extended\_list\_amt}_i - \text{net\_invoiced\_amt}_i) / \text{extended\_list\_amt}_i$). Define Benchmark Boundary Threshold ($\tau_{\text{cohort}}$) as the 75th percentile ($P75$) of discount concessions or $\text{Median} + 1.5 \times \text{MAD}$ (never treating median as a policy ceiling). Compute Defensible Gap ($G_i^{\text{defensible}} = \max(0, r_i - \tau_{\text{cohort}}) \times \text{extended\_list\_amt}_i$), Baseline Band Gap ($G_i^{\text{median}} = \max(0, r_i - \text{Median}_{\text{cohort}}) \times \text{extended\_list\_amt}_i$), and Actionable Opportunity Estimate ($G_i^{\text{actionable}} = G_i^{\text{defensible}} \times \kappa$, default $\kappa = 0.40$).

### R4. Diagnostic Traversal Beam Search, Statistical Shrinkage & Deduplicated Overlap Ledger
- **Winner's Curse Defense:** Apply Empirical Bayes Shrinkage to pull slice gap estimates toward the parent cohort mean based on sample volume and variance. Run 200-iteration bootstrap stability checks on shortlisted slices (flagging findings where the 90% CI crosses zero). Apply Benjamini-Hochberg False Discovery Rate (FDR) control ($q < 0.05$).
- **Beam Search Traversal:** Implement bounded beam search (width: 3, max depth: 3) ranking candidates via a multi-signal priority vector: (1) Absolute Dollar Gap, (2) Relative Concentration Ratio ($\text{Gap} / \text{Volume}$), (3) Bootstrap Confidence Stability, (4) Incremental Coverage.
- **Overlap-Aware Ledger:** Maintain a transaction-level gap ledger mapping each row to its defensible gap and slice finding memberships. Always report deduplicated Net Unique Portfolio Exposure alongside individual finding totals.

### R5. Interaction Detection & Decoupled Macro Margin Bridge (Engine B)
- **Interaction Analysis:** Support Tier 3 rule-based compound stacking audits against contractual caps. Support statistical exploratory pairwise interaction analysis ($\hat{r}_{AB} = \bar{r}_A + \bar{r}_B - \bar{r}_{\text{global}}$, $\mathcal{I}_{\text{rate}} = r_{AB} - \hat{r}_{AB}$). If $\mathcal{I}_{\text{rate}} > 0$ with significant support, label as *"Anomalous Joint Concession: Pairwise combination exhibits a larger-than-expected concession gap. Review contract terms."* Programmatically block the term "Policy Violation" in statistical mode.
- **Decoupled Engine B (PVMC Bridge):** Implement an independent period-over-period ($t=0$ vs $t=1$) margin bridge decomposed into $\Delta \text{Price} + \Delta \text{Volume} + \Delta \text{Mix} + \Delta \text{Cost} + \text{Turnover Effect}$. Enforce the Volume Homogeneity Rule across units. Isolate entries and exits ($Q_0 = 0$ or $Q_1 = 0$) under a dedicated "New & Discontinued Business" component.

### R6. Deterministic Fingerprinting, Lifecycle State Machine & Run-over-Run Diffing
- **Fingerprinting:** Identify every finding by a deterministic SHA-256 hash ($\text{SHA256}(\text{Slice Dimension Values} + \text{Comparability Filters} + \text{Calibration ID})$).
- **Gated Lifecycle State Machine:** Manage finding transitions: `New` → `Assigned` → `In Review` → `Dismissed` or `Actioned`. Programmatically disable punitive disposition codes ("Unapproved Concession", "Unauthorized Deal") unless the evidence tier is confirmed as Tier 3 `Rule-Confirmed Exception`. Require mandatory disposition category and snooze/expiry date for dismissals.
- **Run-over-Run Diffing:** Compare sequential runs to classify findings into New, Persisting/Growing, and Resolved/Narrowed, tracking realized recovery on recurring accounts.

### R7. Minimalist Three-View UI
- **View 1 (Reconcile):** Ingestion container for CSV/Parquet, Data Readiness Scorecard displaying unlocked tiers, and Control Total Confirmation Panel with 1 bp variance check and Quarantine-and-Proceed override.
- **View 2 (Calibrate):** Three-column selector (Comparability Controls, Investigation Dimensions, Excluded), historical baseline period locking, boundary threshold selector ($P75$ vs MAD), capture-rate haircut input, and `.calib.json` save/load.
- **View 3 (Triage & Act):** KPI cards (Net Unique Portfolio Exposure, Reconciled Control Base, Active Finding Count, Validated Actionable Total); Ranked Findings Ledger; Transaction Ledger Drawer with line-level details; Renewal Calendar View; What-If Scenario Panel; and Decoupled Macro Margin Bridge view.

### R8. Safe Export Engine & Formula Injection Defense
- **Three Export Paths:**
  1. Executive Audit Summary (PDF/HTML): High-level charts and bridges with transaction line IDs and customer account names fully redacted.
  2. Actionable Findings Ledger (CSV/Excel): Finding definitions, unique exposures, owners, and review statuses without raw line rows.
  3. Restricted Deal Ledger (AES-256 encrypted ZIP or password-protected XLSX): Full line-item records requiring explicit user acknowledgement of sensitive export.
- **Formula Injection Defense:** Neutralize CSV formula injection by prepending a single quote (`'`) to any text string starting with `=`, `+`, `-`, `@`, `\t`, or `\r`. Strictly verify numeric parsing first so valid negative financial values (e.g., `-1450.50`) remain unquoted raw numbers.

## Acceptance Criteria

### Automated Verification Test Suite
- [ ] **Synthetic Planted Exception Test:** The test suite runs a synthetic 50,000-row dataset with 15 injected off-policy anomalous transactions; the engine recovers this exact cohort with 100% precision and 100% recall without false positives on background data.
- [ ] **Waterline Null-Hypothesis Test:** On a synthetically uniform, non-anomalous distribution, the engine returns exactly 0 defensible exception findings under default $P75$ boundary bounds.
- [ ] **Reconciliation Invariant:** Aggregate portfolio net variance strictly matches the sum of Gross Unfavorable Gap and Favorable Variance to the exact cent across all test datasets.
- [ ] **Overlap Ledger Invariant:** Reported Net Unique Portfolio Exposure strictly equals the deduplicated union of transaction dollars across active findings (summing individual finding exposures without displaying shared intersections is prohibited).
- [ ] **Negative Numeric Integrity Test:** Negative numbers and currency amounts (e.g., `-1450.50`, `-0.05`) parse cleanly as numeric values and are not prepended with single quotes during CSV export.
- [ ] **Air-Gap Verification:** Complete execution of ingestion, LOAO calibration, beam search triage, and report generation in a sandboxed, network-disabled environment with zero network requests.

### User Interface & Persistence Invariants
- [ ] Project workspaces save and reload from single `.mxa` files preserving all state, findings, calibration profiles, and audit manifests.
- [ ] Quarantine watermark permanently displays on screen, reports, and exports whenever control reconciliation residual exceeds 1 bp.
- [ ] Punitive disposition codes ("Unapproved Concession", "Unauthorized Deal") cannot be selected on Tier 1 or Tier 2 findings.

## Follow-up — 2026-09-15T22:45:54Z

The server was restarted and the user has instructed: 'continue where it was left'. Please inspect existing workspace state in c:/Shift and resume coordination from Milestone 1 implementation.

## Follow-up — 2026-09-16T00:08:10Z

Continue Project Sift where it was left off in working directory c:/Shift.

Current Verified State:
- Phase 0 (Specification & Architecture in PROJECT.md) is completed.
- E2E Test Suite (tests/e2e/ AC-1 to AC-9) is fully implemented.
- Milestone 1 (Tauri shell, DuckDB storage backend/storage.py with 4GB limit & disk spilling, .mxa workspace lifecycle): COMPLETED and verified.
- Milestone 2 (Canonical 2-pass ingestion backend/ingestion.py, 3-tier readiness scorecard, 1bp reconciliation gate, quarantine watermark): COMPLETED and verified.
- Milestone 3 (LOAO cohort baseline calibration backend/loao.py, support fences, hierarchical back-off, P75/MAD bounds, non-linear gap scoring, .calib.json profiles): COMPLETED and verified (17/17 tests passing).
- Total existing passing tests: 63/63.

Remaining Scope to Complete:
1. Milestone 4: Diagnostic Beam Search & Overlap-Aware Ledger (backend/beam_search.py):
   - Empirical Bayes shrinkage pulling slice gaps toward parent cohort
   - 200-iteration bootstrap stability checks (flagging findings where 90% CI crosses zero)
   - Benjamini-Hochberg FDR control (q < 0.05)
   - Bounded beam search traversal (width 3, depth 3) with multi-signal priority vector (Dollar Gap, Concentration Ratio, Bootstrap Stability, Incremental Coverage)
   - Canonical transaction gap ledger tracking multi-finding memberships
   - Deduplicated Net Unique Portfolio Exposure calculation (union of dollars).
2. Milestone 5: Interaction Detection & Decoupled PVMC Margin Bridge (backend/interactions.py & backend/bridge.py):
   - Tier 3 rule-based compound stacking against contractual caps
   - Statistical exploratory pairwise interaction testing (r_AB - r_hat_AB), strictly blocking the term "Policy Violation"
   - Decoupled Engine B period-over-period PVMC margin bridge (Price, Volume with homogeneity enforcement, Mix, Cost, and New & Discontinued Business turnover).
3. Milestone 6: Deterministic Fingerprinting, Lifecycle State Machine & Safe Export (backend/lifecycle.py & backend/export.py):
   - Deterministic SHA-256 finding fingerprints
   - 5-state lifecycle state machine (New, Assigned, In Review, Dismissed, Actioned) with programmatic lockout of punitive codes on Tiers 1-2, mandatory dismissal category & snooze date
   - Run-over-run diffing (New, Persisting/Growing, Resolved/Narrowed) tracking realized recovery
   - Three safe export paths: Redacted Executive Audit Summary (PDF/HTML), Actionable Findings Ledger (CSV/Excel), and AES-256 encrypted Restricted Deal Ledger
   - Formula injection defense: sanitize text strings starting with =, +, -, @, \t, \r by prepending a single quote while preserving valid negative financial numbers.
4. Milestone 7: Minimalist Three-View UI & API Integration (src/):
   - View 1 (Reconcile): Ingestion, scorecard, reconciliation gate with permanent residual watermark
   - View 2 (Calibrate): 3-column attribute selector, baseline period locking, boundary threshold selector, capture haircut slider
   - View 3 (Triage & Act): KPI cards, ranked ledger table, transaction detail drawer, renewal calendar, what-if scenario slider, PVMC bridge
   - Fast API endpoints wired for all features.
5. Final Acceptance: Run and pass 100% of the automated verification test suite (tests/e2e/runner.py covering AC-1 to AC-9).

## Follow-up — 2026-09-16T06:21:00Z

Overhaul Project Sift's desktop application to load as a strictly clean slate with zero demo data or fake numbers, and redesign the user interface with plain-English, layman-friendly explanations, step-by-step guidance, and an interactive collapsible real-world use case guide.

Working directory: c:/Shift
Integrity mode: development
Requested team: Full multi-agent team (UI designers, frontend engineers, and reviewers for a comprehensive overhaul)

## Requirements

### R1. Strictly Clean Slate Initial Experience
When Sift launches, the dashboard must load into a strictly clean slate with zero pre-populated demo data, zero mock numbers, zero fake file paths, zero mock general ledger figures, and zero pre-computed findings or watermark warnings. There must be no sample data or demo buttons. All metric cards, status indicators, and ledger tables must reflect an uninitialized state awaiting user data.

### R2. Plain-English, Layman-Friendly Navigation & Terminology
Replace all dense financial and technical jargon on primary headings, tabs, and step indicators with intuitive, plain-English titles and subtitles:
- Primary View 1: "1. Add & Check Data" (Upload sales data and verify that totals match accounting records)
- Primary View 2: "2. Compare Similar Deals" (Group products and customers to compare pricing like-for-like)
- Primary View 3: "3. Discover Profit Opportunities" (Identify pricing exceptions, margin leaks, and recoverable revenue)
Include friendly tooltips and conversational explanations that clarify financial terms for non-specialists.

### R3. Interactive Collapsible Use-Case & Insights Guide
Implement a prominent, collapsible guide directly on the dashboard explaining what the tool does and how anyone can benefit from it. Detail at least 4 practical commercial scenarios in clear, everyday language:
1. Identifying unintended or runaway customer discounts.
2. Detecting discount stacking where multiple promotions erode profit margins.
3. Discovering pricing benchmarks to negotiate higher contract renewal rates.
4. Verifying that granular sales transactions reconcile against accounting records before executive audits.

### R4. Progressive Disclosure for Laymen and Data Specialists
Ensure the default user interface is welcoming and straightforward for general users, while providing progressive disclosure toggles (e.g., "Advanced Technical Details") allowing data engineers, financial controllers, and pricing specialists to inspect underlying DuckDB query metrics, LOAO statistics, and export controls.

### R5. Build, Packaging & Invariant Integrity
Compile the updated React 18 production bundle (`npm run build` in `src/`). Ensure that all core backend APIs, in-process DuckDB analytical routines, and the existing 279 automated pytest regression tests pass with 100% success.

## Acceptance Criteria

### Clean Slate Verification
- [ ] Fresh dashboard launch renders zero mock file paths (no `commercial_sales_2025.parquet`), zero fake GL inputs (inputs are empty), zero pre-seeded findings, and no initial residual watermark banner.
- [ ] File upload area displays clear, simple instructions on supported formats (`.xlsx`, `.csv`, `.parquet`) and expected columns without pre-selecting demo columns.
- [ ] No "Load Demo Data" or sample dataset buttons exist anywhere on the dashboard.

### Layman User Experience & Explanations
- [ ] Primary tabs are clearly labeled: "1. Add & Check Data", "2. Compare Similar Deals", and "3. Discover Profit Opportunities".
- [ ] Collapsible use-case guide is present, can be expanded and collapsed, and describes at least 4 real-world pricing and margin scenarios in everyday language.
- [ ] Every major action button includes clear, conversational labels explaining what will happen next.

### Technical & Analytical Robustness
- [ ] `npm run build` executes without errors and updates `src/dist/`.
- [ ] Ingestion, calibration, triage, and export pipelines remain fully functional when a real dataset is provided.
- [ ] All 279 automated regression tests pass via `python -m pytest tests/` with zero failures.

## Follow-up — 2026-09-17T02:52:14Z

An autonomous QA test engineering team to conduct exhaustive black-box UI testing, boundary exploration, and regression testing on the data analysis tool launched via `run.bat`, strictly interacting via the UI like a user without inspecting source code or calling backend APIs, to break the tool, uncover defects, and deliver a comprehensive test suite and defect register.

Working directory: c:/Shift/test_deliverables
Integrity mode: development

## Requirements

### R1. Synthetic Test Dataset Generation
Generate diverse synthetic datasets representing realistic business and adversarial scenarios for margin and booking leakage analysis:
- Booking leakage with designated booking columns, discount calculation rules, and standard margin formulas.
- Single-category culpability where one specific category is the primary driver of margin loss.
- Multi-category shared culpability where multiple categories simultaneously contribute to the leakage.
- Granular transaction-level culprits where specific individual transactions drive outsized negative margins.
- Boundary and negative scenarios: negative values, zero margins, missing/null columns, malformed data types, extreme outliers, and non-standard date formats.

### R2. Strict Black-Box UI Testing & Navigation
Launch the application using `run.bat` in the project root and interact strictly through the user interface (navigating element-by-element like a human user):
- Do not inspect application source code or call backend APIs directly.
- Test every interactive component: dataset upload, column mapping (booking, discount, standard margin), calculation configuration, category-level leakage visualizers, and transaction-level drill-down tables.
- Attempt unexpected and unsupported user journeys (e.g., submitting incomplete configurations, altering mappings mid-analysis, rapid switching, boundary inputs) to test error handling and system resilience.

### R3. Dual-Format Test Deliverables & Defect Register
Produce a complete test deliverables suite in both Markdown (`c:/Shift/test_deliverables/TEST_DELIVERABLES.md`) and Excel (`c:/Shift/test_deliverables/TEST_DELIVERABLES.xlsx`):
- Each test case must include: Test Case ID, Feature Area, Scenario Description, Preconditions, Synthetic Dataset Used, Step-by-Step UI Execution Steps, Expected Result, Actual Result, Severity (Critical, High, Medium, Low).
- Two distinct status columns:
  1. `Tester Status` (Pass / Fail / Blocked)
  2. `Developer Status` (New / Triaged / In-Progress / Resolved / Won't Fix / Working as Designed)
- A dedicated `Developer Comments` column providing ample space for the development team to record feedback, root-cause notes, or mitigation steps.
- A summary section reporting total test cases executed, pass/fail ratios, critical defects found, and user experience/robustness observations.

## Acceptance Criteria

### Test Dataset & Scenario Breadth
- [ ] At least 8 distinct synthetic datasets are generated and saved in `c:/Shift/test_deliverables/datasets/` covering single-category leakage, multi-category shared leakage, transaction-level outliers, and corrupt/boundary data.
- [ ] Test cases cover all core analytical workflows: dataset import, column mapping, formula validation, category aggregation, and transaction drill-down.

### Black-Box UI Execution Integrity
- [ ] Application is launched via `run.bat` and all verification is performed through UI interactions without reading backend source code or bypassing the UI via API calls.
- [ ] Edge cases and negative user paths are tested to evaluate graceful degradation and error messaging.

### Deliverable Structure & Verification
- [ ] Both `TEST_DELIVERABLES.md` and `TEST_DELIVERABLES.xlsx` exist in `c:/Shift/test_deliverables/` and contain all executed test cases.
- [ ] The deliverables contain separate `Tester Status`, `Developer Status`, and `Developer Comments` columns.
- [ ] Every failed test or defect is accompanied by reproducible UI steps, severity rating, and reference to the input dataset.

## Follow-up — 2026-09-17T04:26:49Z

An autonomous QA and performance engineering team to conduct massive-scale stress testing, deep culprit anomaly detection, and user-experience (UX) latency profiling on the data analysis tool launched via `run.bat`, strictly interacting via the UI like a user without inspecting source code or calling backend APIs, to verify system resilience under extreme data loads and document usability friction.

Working directory: c:/Shift/test_deliverables
Integrity mode: development

## Requirements

### R1. Massive High-Dimensional Synthetic Stress Datasets
Generate massive high-volume, wide-schema datasets in `c:/Shift/test_deliverables/datasets/`:
- Schema Width: 60+ categorical attribute columns (sales hierarchy tiers, product taxonomies, customer classifications, partner tiers, geographies, contract stipulations) and 15+ numerical metric columns (gross booking, invoiced amount, list price, base discount, promo discount, rebate accruals, standard margin, pocket margin, shipping, tax, etc.).
- Deeply Buried Culprits: Intentionally engineer margin/booking leakages hidden deep within multi-attribute combinations (e.g., 3-to-5 level compound slices) that do not appear at top-level category aggregates.
- Scaled Formats:
  1. `dataset_stress_1m_wide.csv`: 1,000,000 rows with 75+ columns (CSV format to stress streaming parser and column alignment UI).
  2. `dataset_stress_15m_wide.parquet`: 15,000,000 rows with 75+ columns (compressed columnar Parquet format to stress vectorized scan, 4GB RAM budget, disk-spilling, and deep beam search).

### R2. Strict Black-Box UI Deep-Search & Stress Execution
Execute deep analytical workflows strictly via the UI (`http://127.0.0.1:8765`) without inspecting source code or making backend API calls:
- Navigate and test wide-schema ingestion (handling 75+ columns in mapping and preview), reconciliation gating, baseline calibration, and deep beam search.
- Stress-test system resource limits: verify in-process memory containment (enforcing the 4GB RAM budget with disk-spilling), monitor CPU load, and verify that the application neither freezes nor crashes.
- Validate that the tool's multi-level analysis successfully traverses the dimensional hierarchy to identify the buried multi-attribute culprit.

### R3. UX Complexity, Usability & Latency Profiling
Perform systematic user-experience (UX) and wait-time evaluations:
- Benchmark time-to-insight: measure elapsed seconds across Pass 1 streaming preview, reconciliation calculation, baseline locking, and beam search triage.
- UX Thresholds & Defect Logging:
  * Flag any UI operation taking > 30 seconds without active progress indicator, percentage, or status estimate as a **High UX Defect**.
  * Flag any workflow taking > 3 minutes total time-to-insight as a **Performance Defect**.
  * Document usability friction: assess whether navigating 75 columns in table headers or mapping chips is overwhelming, clunky, or confusing for a non-technical business user.

### R4. Dual-Format Deliverables & Defect Register Update
Expand and update both `c:/Shift/test_deliverables/TEST_DELIVERABLES.md` and `c:/Shift/test_deliverables/TEST_DELIVERABLES.xlsx`:
- Integrate the new stress testing cases, execution records, elapsed latencies, and resource consumption telemetry.
- Maintain the mandated 12 columns with distinct `Tester Status`, `Developer Status`, and `Developer Comments`.
- Itemize all newly identified stress, performance, and UX defects in Sheet 2 and `DEFECT_LOG.md` with step-by-step reproduction instructions and developer recommendations.

## Acceptance Criteria

### Stress Datasets & Dimensional Depth
- [ ] Both `dataset_stress_1m_wide.csv` (1M rows, 75+ columns) and `dataset_stress_15m_wide.parquet` (15M rows, 75+ columns) are generated and cataloged in `DATASET_MANIFEST.md`.
- [ ] Datasets contain mathematically verified deeply buried multi-attribute margin culprits (3-5 level interactions).

### Black-Box UI Stress & Memory Invariant
- [ ] Ingestion, calibration, and beam search executed strictly through the browser UI without direct API calls.
- [ ] System remains within its 4GB memory boundary without out-of-memory (OOM) crashes during 15M row operations.

### UX Profiling & Deliverables Completeness
- [ ] Latency benchmarks (elapsed seconds) recorded for each major stage.
- [ ] Any operation exceeding 30s without progress feedback or > 3 minutes total time is logged with root-cause analysis and developer guidance.
- [ ] Both `TEST_DELIVERABLES.md` and `TEST_DELIVERABLES.xlsx` are updated with the stress test results, preserving all 12 standard columns.

## Follow-up — 2026-09-17T05:51:47Z

An autonomous QA test engineering team to conduct rigorous black-box UI re-testing of the 10 previously identified defects (DEF-UI-01 through DEF-UI-10) and comprehensive regression testing of all potentially affected components in Project Sift launched via `run.bat`. The team will verify developer fixes, uncover any side-effects or new regressions, and update the dual-format test deliverables and defect register with clear re-testing statuses and remediation notes.

Working directory: c:/Shift/test_deliverables
Integrity mode: development

## Requirements

### R1. Black-Box UI Re-Testing of Open Defects
Re-test each of the 10 identified defects strictly through the UI (`http://127.0.0.1:8765`):
- **DEF-UI-01 (TC-021)**: Verify Tier 2 pocket contribution correctly locks when pocket margin fields (COGS, rebates) are absent.
- **DEF-UI-02 (TC-022)**: Verify presence and functionality of interactive column remapping dropdowns in View 1.
- **DEF-UI-03 (TC-033)**: Verify View 2 Three-Column attribute categorization receives and populates dataset column chips.
- **DEF-UI-04 (TC-041)**: Verify View 3 beam search uses dynamic investigated dimensions rather than hardcoded dummy columns.
- **DEF-UI-05 (TC-058)**: Verify non-canonical columns (all 87 columns in wide datasets) are visible, browsable, or expandable in View 1.
- **DEF-UI-06 (TC-059)**: Verify Pass 2 DuckDB ingestion succeeds without duplicate column name conflicts on schemas containing `pocket_margin_amt`.
- **DEF-UI-07 (TC-060)**: Verify Reconciliation Gate evaluates control totals against the true full dataset rather than the 1,000-row sample.
- **DEF-UI-08 (TC-062)**: Verify all 62 categorical dimensions appear as selectable comparability chips in View 2.
- **DEF-UI-09 (TC-064)**: Verify beam search successfully traverses high-dimensional space and isolates buried compound culprits (Alpha, Beta, Gamma).
- **DEF-UI-10 (TC-068)**: Verify column search, taxonomy filtering, or organization drawers mitigate cognitive overload on wide schemas.

### R2. Comprehensive Impact & Regression Testing
Perform full regression testing on all features potentially affected by the code fixes:
- Re-run the existing baseline tests (TC-001 to TC-055) and wide-schema stress tests (TC-056 to TC-072) via Playwright.
- Verify that core invariants remain intact: Clean Slate launch, 1 bp reconciliation gate & quarantine protocol, permanent watermark persistence, baseline calibration locking, PVMC margin bridge waterfall, and zero-egress air-gap.
- Probe for new regressions, edge-case breaks, or unhandled exceptions introduced by the developer's modifications.

### R3. Deliverables & Defect Lifecycle Register Update
Update `c:/Shift/test_deliverables/TEST_DELIVERABLES.md`, `c:/Shift/test_deliverables/TEST_DELIVERABLES.xlsx`, and `c:/Shift/test_deliverables/DEFECT_LOG.md`:
- Update `Tester Status` for each retested case (`Pass` if verified fixed, `Fail` if defect persists or regression occurred).
- Update `Developer Status` (e.g. `Verified Fixed`, `Re-Opened`, or `New` for newly discovered issues).
- In `Developer Comments`, document explicit retest observations, regression verification notes, and actionable remediation steps for any remaining or newly discovered defects.
- Maintain the mandated 12 standard columns and exact 1:1 mathematical parity across all sheets and markdown logs.

## Acceptance Criteria

### Retest & Regression Breadth
- [ ] All 10 previously logged defects (DEF-UI-01 through DEF-UI-10) are explicitly retested via Playwright UI automation with recorded evidence.
- [ ] Full regression suite (all 72 test cases) is re-executed across both standard and wide-schema (87 columns, 1M/15M rows) datasets.
- [ ] Any regressions or side-effects caused by the fixes are caught, categorized by severity, and documented.

### Deliverables & Defect Parity
- [ ] Both `TEST_DELIVERABLES.xlsx` and `TEST_DELIVERABLES.md` are updated with the retest results across all 12 columns.
- [ ] Sheet 2 of the Excel workbook and `DEFECT_LOG.md` reflect current defect statuses (marking verified fixes and re-opening unresolved issues).
- [ ] 100% mathematical parity maintained between failed test cases and open/re-opened defect records.

