# Project Sift: Commercial Audit & Margin Triage Engine
## Developer Defect Remediation & Verification Walkthrough

**Document Version:** 1.0.0 (Developer Resolution Walkthrough)  
**Date:** 2026-09-17  
**Author:** Antigravity Engineering Team  
**Audience:** QA Engineering, Financial Controllers, Deal Desk Operations, Lead System Architect  
**Deliverables Updated:** `TEST_DELIVERABLES.md`, `DEFECT_LOG.md`, `TEST_DELIVERABLES.xlsx`

---

## 1. Executive Summary

Following comprehensive black-box and stress testing across 72 test cases and 16 million commercial transactions (including a 1M-row wide CSV and a 15M-row wide Parquet dataset), the QA engineering team documented **10 specific defects** (`DEF-UI-01` through `DEF-UI-10`).

The development team has completed an end-to-end investigation, resolved all architectural and interface root causes, rebuilt the production React frontend bundle, and verified that **100% of the defects (10 of 10) are fully resolved and prepared for QA retesting**.

### Remediation Scorecard

| Defect ID | Associated TC | Feature Area | Severity | Status | Verification Summary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-UI-01** | TC-021 | View 1 Readiness Tier Scorecard | High | **Fixed** | Pocket Contribution (Tier 2) strictly locks when COGS/rebates are missing; clean state reset on new files. |
| **DEF-UI-02** | TC-022 | View 1 Column Mapping | High | **Fixed** | Interactive `<select>` controls added in both preview table headers and column mapping grid. |
| **DEF-UI-03** | TC-033 | View 2 Calibration | Critical | **Fixed** | Dataset columns and types wired from View 1 to View 2; auto-categorizes into 3 attribute buckets. |
| **DEF-UI-04** | TC-041 | View 3 Beam Search | Critical | **Fixed** | Beam search accepts dynamic investigation dimensions selected during calibration, uncovering verified slices. |
| **DEF-UI-05** | TC-058 | View 1 Wide Schema Preview | Medium | **Fixed** | Added view mode toggle ("Canonical 11" vs "All Columns N") allowing horizontal inspection of all 87 columns. |
| **DEF-UI-06** | TC-059 | View 1 Ingestion Engine | Critical | **Fixed** | Excluded derived `pocket_margin_amt` from raw projection; safely projects `_raw_pocket_margin_amt` without DuckDB binder error. |
| **DEF-UI-07** | TC-060 | View 1 Reconciliation Gate | High | **Fixed** | Added vectorized full-file aggregation in preview pass; GL totals compare against entire dataset rather than 1,000-row sample. |
| **DEF-UI-08** | TC-062 | View 2 Attribute Selector | Critical | **Fixed** | All 62 categorical dimensions in wide schemas render as interactive chips across the 3 calibration buckets. |
| **DEF-UI-09** | TC-064 | View 3 Beam Search Traversal | Critical | **Fixed** | Dynamic traversal and backend fallback discovery isolate buried compound culprits (Alpha, Beta, Gamma) in 15M transactions. |
| **DEF-UI-10** | TC-068 | UI Usability & Taxonomy | Medium | **Fixed** | Real-time attribute search and domain taxonomy pills (Sales, Product, Customer, Deal, Financial) added in View 1 & 2. |

---

## 2. Root Cause Analysis & Technical Fixes

### DEF-UI-01 (TC-021): Readiness Tier Dynamic Locking on Missing Pocket Margin Fields
- **Root Cause:**
  1. In `View1Reconcile.jsx`, tier unlocking logic evaluated row preview presence without strictly verifying that detected or mapped columns contained `cogs_amt` or `off_invoice_rebate`. Furthermore, readiness states were retained across sequential file previews.
  2. The synthetic dataset `dataset_05_missing_null_columns.csv` had erroneously included `cogs_amt` and `off_invoice_rebate` columns despite being specified as a dataset lacking pocket margin components.
- **Remediation:**
  1. Updated `View1Reconcile.jsx` lines 48-75 to implement strict schema validation:
     ```javascript
     const hasCogs = detectedColumns.some(c => c.toLowerCase() === 'cogs_amt');
     const hasRebate = detectedColumns.some(c => c.toLowerCase() === 'off_invoice_rebate');
     const t2 = t1 && (hasCogs || hasRebate);
     ```
  2. Implemented clean state reset on file preview (`columnMapping`, `previewRows`, `scannedGross`, `scannedNet`, `detectedColumns`, `readinessTier`).
  3. Re-generated `dataset_05_missing_null_columns.csv` and updated `generate_datasets.py` to drop `cogs_amt` and `off_invoice_rebate`.
- **Expected Retest Behavior:**
  Loading `dataset_05_missing_null_columns.csv` unlocks Tier 1 (Gross-to-Net) and displays Tier 2 as **Locked**, with a warning badge explaining that COGS or rebate columns are missing.

---

### DEF-UI-02 (TC-022): Absence of Interactive Column Remapping Selectors in View 1
- **Root Cause:**
  `View1Reconcile.jsx` rendered proposed column mappings purely as read-only text badges; no interactive `<select>` elements existed to allow users to override or adjust column mappings.
- **Remediation:**
  Added interactive `<select>` dropdown controls in both the data preview table headers and the dedicated column mapping drawer:
  ```jsx
  <select
    value={columnMapping[col] || ''}
    onChange={(e) => handleMapColumn(col, e.target.value)}
    className="bg-slate-900 border border-slate-700 text-[11px] rounded px-1.5 py-0.5 text-cyan-300"
  >
    <option value="">-- Ignore / Unmapped --</option>
    {CANONICAL_FIELDS.map(f => (
      <option key={f.key} value={f.key}>{f.label}</option>
    ))}
  </select>
  ```
- **Expected Retest Behavior:**
  Users can click on any column's mapping dropdown in the preview table or mapping drawer and reassign the canonical target field; changes reflect immediately in preview totals and validation scorecard.

---

### DEF-UI-03 & DEF-UI-08 (TC-033, TC-062): Three-Column Attribute Categorization Not Populated in View 2
- **Root Cause:**
  `App.jsx` rendered `<View2Calibrate />` without passing column schema props from View 1, and `View2Calibrate.jsx` initialized its three attribute categorization lists (`comparabilityControls`, `investigationDims`, `excludedAttributes`) to empty arrays (`[]`), rendering *"No attributes loaded yet"*.
- **Remediation:**
  1. In `View1Reconcile.jsx`, added an `onColumnsDetected` callback that transmits detected columns, inferred types, and column mappings to `App.jsx`.
  2. In `App.jsx`, added state variables `datasetColumns`, `inferredTypes`, `columnMapping`, and `investigationDims` and passed them down to `View2Calibrate.jsx`.
  3. In `View2Calibrate.jsx`, implemented an auto-categorization `useEffect` that sorts detected columns upon load:
     - **Excluded Attributes:** Identifiers (`*_id`), transaction dates/timestamps, and financial metrics (`*_amt`, `*_pct`, `*_val`, `*_rate`).
     - **Fair Pricing Factors:** Legitimate price drivers (product family, category, customer tier, region, currency, market).
     - **Audited Deal Factors:** Governance factors scrutinized for pricing leaks (sales rep, channel, contract type, payment terms, SLA).
  4. Added bidirectional synchronization with `App.jsx` via `setInvestigationDims`.
- **Expected Retest Behavior:**
  Navigating to Step 2 immediately displays all detected dataset columns populated across the 3 categorization buckets. On wide datasets (87 columns), all 62 categorical dimensions appear as interactive chips.

---

### DEF-UI-04 & DEF-UI-09 (TC-041, TC-064): Hardcoded Investigation Dimensions in View 3 Beam Search
- **Root Cause:**
  In `View3Triage.jsx`, `handleRunBeamSearch` had a hardcoded payload:
  `investigationDims: ['sales_rep', 'channel', 'contract_type']`. When datasets had different dimension names (or in wide-schema stress tests), beam search failed to find candidate slices and returned 0 findings.
- **Remediation:**
  1. In `View3Triage.jsx`, accepted `investigationDims` and `datasetColumns` props from `App.jsx`.
  2. Updated `handleRunBeamSearch` to dynamically transmit the user's calibrated investigation dimensions:
     ```javascript
     let dimsToRun = [];
     if (investigationDims && investigationDims.length > 0) {
       dimsToRun = [...investigationDims];
     } else if (datasetColumns && datasetColumns.length > 0) {
       dimsToRun = datasetColumns.filter(col => !isMetric(col) && !isId(col)).slice(0, 10);
     }
     ```
  3. In `backend/beam_search.py`, added dynamic dimension discovery fallback if requested dimensions do not match the table schema.
- **Expected Retest Behavior:**
  Clicking "Scan for High-Priority Profit Leaks" executes beam search using the active dimensions chosen in Step 2, discovering verified exception slices and buried compound culprits across all schemas.

---

### DEF-UI-05 (TC-058): Missing Visibility for Non-Canonical Columns in View 1 (87 Columns)
- **Root Cause:**
  `View1Reconcile.jsx` only iterated over the 11 `CANONICAL_FIELDS` for table headers, hiding the remaining 76 business attributes in wide schemas like `dataset_stress_1m_wide.csv`.
- **Remediation:**
  Added a View Mode toggle in `View1Reconcile.jsx`:
  - **"Canonical Mapping (11)":** Focuses strictly on the core reconciliation ledger.
  - **"All Columns (87)":** Renders a wide, horizontally scrollable preview table with data type badges and mapping dropdowns for every column in the dataset.
- **Expected Retest Behavior:**
  Switching to "All Columns" enables horizontal scrolling and full inspection of all 87 columns in `dataset_stress_1m_wide.csv`.

---

### DEF-UI-06 (TC-059): DuckDB Pass 2 Ingestion Duplicate Column Conflict
- **Root Cause:**
  Pass 2 vectorized ingestion in `backend/ingestion.py` projected a calculated `pocket_margin_amt` into the INSERT query without checking if the source dataset already contained a `pocket_margin_amt` column. On schemas like `dataset_stress_15m_wide.parquet`, DuckDB threw `HTTP 400 Binder Error: Duplicate column name pocket_margin_amt in INSERT`.
- **Remediation:**
  1. In `backend/ingestion.py`, excluded reserved/derived columns (`pocket_margin_amt`, `pocket_margin_pct`, `reporting_list_amt`, `gross_invoiced_amt`, etc.) from `extra_dim_cols`.
  2. Projected raw pocket margin as `_raw_pocket_margin_amt` and used `COALESCE(_raw_pocket_margin_amt, ...)` in the insert expression.
- **Expected Retest Behavior:**
  Ingesting `dataset_stress_15m_wide.parquet` executes cleanly via vectorized streaming with zero DuckDB binder errors, loading all 15 million rows.

---

### DEF-UI-07 (TC-060): Reconciliation Gate Evaluates Against 1,000-Row Sample Instead of Full Dataset
- **Root Cause:**
  `View1Reconcile.jsx` calculated control variance against the 1,000-row sample preview sum instead of the full file totals, producing a false 99.9% variance on large files like `dataset_stress_1m_wide.csv` ($31M sample vs $31.6B actual) and locking users into quarantine mode before ingestion.
- **Remediation:**
  1. In `backend/ingestion.py`, updated `preview_source()` to execute a fast vectorized full-file aggregation query `SELECT COUNT(*), SUM(extended_list_amt), SUM(net_invoiced_amt)` returning `scanned_gross`, `scanned_net`, and `total_rows`.
  2. In `View1Reconcile.jsx`, updated reconciliation gate math to compare GL inputs against `scanned_gross` and `scanned_net`.
- **Expected Retest Behavior:**
  Entering official GL control totals ($31,643,595,200.00 Gross, $27,842,500,000.00 Net) computes a 0.00% variance (within 1 bp tolerance), enabling clean reconciliation without forced quarantine.

---

### DEF-UI-10 (TC-068): UI Usability & Taxonomy Friction on High-Dimensional Schemas
- **Root Cause:**
  Wide schemas (87 columns) caused severe cognitive clutter and vertical scrolling with no search, filtering, or domain taxonomy hierarchy.
- **Remediation:**
  1. Implemented real-time search input and domain taxonomy filter pills (`ALL`, `SALES`, `PRODUCT`, `CUSTOMER`, `DEAL`, `METRICS`) in both `View1Reconcile.jsx` and `View2Calibrate.jsx`.
  2. Added bulk move actions (`Move Filtered → Controls / Audited / Excluded`) and scrollable containers with compact tag badges.
- **Expected Retest Behavior:**
  Commercial users can filter by domain (e.g. Sales, Product, Customer) or keyword to manage high-dimensional datasets without cognitive friction.

---

## 3. Step-by-Step QA Retest Verification Procedures

### Retest 1: DEF-UI-01 / TC-021 (Readiness Tier Scorecard)
1. Launch Sift desktop application (`http://127.0.0.1:8765`).
2. In Step 1, enter path: `c:\Shift\test_deliverables\datasets\dataset_05_missing_null_columns.csv`.
3. Click **Preview File**.
4. Inspect the Readiness Tier Scorecard.
5. **Expected Result:**
   - Tier 1 (Gross-to-Net) is **Active** (green checkmark).
   - Tier 2 (Pocket Contribution) is **Locked** (amber lock badge) with message indicating missing COGS and rebate fields.

### Retest 2: DEF-UI-02 / TC-022 (Interactive Column Remapping)
1. Load `dataset_01_single_category_leakage.csv` in Step 1.
2. Click **Preview File**.
3. In the preview table headers or the column mapping drawer, locate the dropdown for a column (e.g. `channel`).
4. Select a different canonical field or choose `-- Ignore / Unmapped --`.
5. **Expected Result:**
   - Dropdown updates the mapping reactively.
   - Preview summary updates immediately without application reload.

### Retest 3: DEF-UI-03 & DEF-UI-08 / TC-033, TC-062 (3-Column Attribute Population)
1. Load `dataset_01_single_category_leakage.csv` or `dataset_stress_1m_wide.csv` in Step 1 and complete reconciliation.
2. Navigate to Step 2: **2. Compare Similar Deals**.
3. Inspect the Three-Column Attribute Grouping container.
4. **Expected Result:**
   - No column displays "No attributes loaded yet".
   - Columns are cleanly populated into Fair Pricing Factors, Audited Deal Factors, and Excluded Attributes.
   - For wide schemas (87 columns), all 62 categorical dimensions appear as interactive chips.

### Retest 4: DEF-UI-04 & DEF-UI-09 / TC-041, TC-064 (Dynamic Beam Search Traversal)
1. In Step 2, ensure audited factors include relevant dimensions (e.g., `sales_rep`, `channel`, `contract_type`).
2. Navigate to Step 3: **3. Discover Profit Opportunities**.
3. Click **Scan for High-Priority Profit Leaks**.
4. **Expected Result:**
   - Beam search completes successfully without 500/Binder errors.
   - Table populates with verified profit leak slices with net unique portfolio exposure and dollar gaps.

### Retest 5: DEF-UI-05 / TC-058 (Wide Schema Preview Visibility)
1. In Step 1, enter path: `c:\Shift\test_deliverables\datasets\dataset_stress_1m_wide.csv`.
2. Click **Preview File**.
3. Click the toggle **"All Columns (87)"**.
4. **Expected Result:**
   - Preview table renders all 87 source columns.
   - Horizontal scrolling is smooth, and data type badges appear above every column.

### Retest 6: DEF-UI-06 / TC-059 (Pass 2 Vectorized Ingestion on Raw Pocket Margin)
1. In Step 1, enter path: `c:\Shift\test_deliverables\datasets\dataset_stress_15m_wide.parquet`.
2. Click **Preview File**.
3. Enter control totals: Gross = `474653928000.00`, Net = `417637500000.00`.
4. Click **Confirm & Ingest Full Dataset**.
5. **Expected Result:**
   - Ingestion completes without DuckDB binder duplicate column errors.
   - All 15,000,000 rows ingest cleanly.

### Retest 7: DEF-UI-07 / TC-060 (Reconciliation Gate Variance)
1. In Step 1, enter path: `c:\Shift\test_deliverables\datasets\dataset_stress_1m_wide.csv`.
2. Click **Preview File**.
3. Enter official GL control totals:
   - Gross: `31643595200.00`
   - Net: `27842500000.00`
4. Inspect the reconciliation status panel.
5. **Expected Result:**
   - Control Gross and Control Net variance display **0.00%** (within 1 bp tolerance).
   - Reconciliation status displays **RECONCILED (WITHIN 1 BP TOLERANCE)** with a green checkmark.
   - Quarantine mode is NOT forced.

### Retest 8: DEF-UI-10 / TC-068 (Domain Taxonomy Filtering)
1. In Step 1 and Step 2 with `dataset_stress_1m_wide.csv` loaded:
2. Type "rep" into the attribute search box.
3. Click the **Sales** taxonomy pill.
4. **Expected Result:**
   - All 3 columns instantly filter to show only sales-related attributes.
   - Clicking **+ Controls** moves matching items into Controls in bulk.
   - Column scrolling is constrained to 380px with no vertical layout breakage.

---

## 4. Build & Regression Test Verification

1. **Frontend Production Build:**
   ```bash
   cd c:\Shift\src
   npm run build
   ```
   **Result:** Vite production build completed in 1.74s with zero errors (`dist/index.html`, `dist/assets/`).

2. **Automated Backend Regression Suite:**
   ```bash
   cd c:\Shift
   python -m pytest tests/ -q
   ```
   **Result:** All 310 automated regression tests passing (100% pass rate).

3. **Deliverable Parity:**
   - `TEST_DELIVERABLES.xlsx`: Sheets 1, 2, and 3 updated with developer comments and `Fixed` status.
   - `TEST_DELIVERABLES.md`: 12-column test matrix regenerated with green `Fixed` badges and detailed comments.
   - `DEFECT_LOG.md`: Dedicated defect log regenerated with 100% parity against Excel.

---

## 5. Layman UX & Usability Enhancements (File Upload & Minimalist Scenarios)

In response to user experience feedback regarding accessibility for non-technical users:

1. **Prominent "Browse & Select Sales File" Ingestion Hub:**
   - Designed a high-visibility, first-step file selection center directly inside Step 1 (`View1Reconcile.jsx`).
   - Features a prominent gradient action button (`[ 📁 Browse & Select Sales File ]`) launching native operating system file selection dialogs (`.xlsx`, `.xls`, `.csv`, `.parquet`).
   - Implemented responsive drag-and-drop listener with animated drag-over borders and visual drop feedback.
   - Added backend multipart upload streaming endpoint (`POST /api/ingest/upload` in `backend/app.py`), persisting uploaded files safely to `uploads/` with desktop runtime path pass-through fallback.
   - Preserves manual path input alongside browse button for full developer scripting and 100% Playwright test automation backward-compatibility.

2. **Minimalist, Default-Collapsed Commercial Use Case Guide:**
   - Refactored `src/src/components/UseCaseGuide.jsx` to load collapsed by default (`isOpen = false`), occupying a compact ~38px vertical banner.
   - Features an intuitive `[ Explore Scenarios ▾ ]` expander that discloses all 4 real-world commercial scenarios in plain layman terminology upon demand.
   - Users can collapse the guide at any time via `[ Collapse Guide ▴ ]`, ensuring zero interface clutter.

3. **Automated Verification:**
   - `test_deliverables/verify_new_ui_features.py`: 100% pass rate covering button visibility, default collapsed state, expansion, collapse, and path entry.
   - `test_deliverables/retest_all_10_playwright.py`: 10/10 defect retests pass in headless Chromium.
   - `python -m pytest tests/`: 310 passed in 209s.

---
*Verified and Approved for QA Retest by Antigravity Engineering.*
