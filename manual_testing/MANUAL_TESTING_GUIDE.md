# Sift Manual Testing Guide & Comprehensive Edge-Case Verification Protocol

This document provides step-by-step instructions, inputs, and expected outcomes for conducting manual and automated validation of the **Sift Commercial Audit & Margin Triage Engine** using the complex, large-scale datasets generated in `c:\Shift\manual_testing`.

---

## 1. Test Environment & Prerequisites

* **Application URL:** `http://127.0.0.1:8765` (or launch via `python backend/run_desktop.py`)
* **Test Datasets Folder:** `c:\Shift\manual_testing`
* **Dataset Manifest:** `c:\Shift\manual_testing\MANIFEST.json`
* **Python Environment:** Python 3.11 with DuckDB, FastAPI, PyTest, and PyZipper.

---

## 2. Generated Datasets Inventory

| File Name | Format | Rows | Key Test Focus |
|---|---|---|---|
| `enterprise_2m_transactions.parquet` | Parquet (Snappy) | **2,000,000** | 4 GB memory ceiling, DuckDB out-of-core disk spilling, LOAO scale, multi-currency, planted anomalies |
| `reconciliation_quarantine_breach.csv` | CSV | **25,000** | Reconciliation Gate breach (> 1 bp variance), Quarantine-and-Proceed, persistent watermark |
| `reconciliation_certified_audit.csv` | CSV | **25,000** | Certified Audit status (exact match within $\le 1\text{ bp}$ variance) |
| `formula_injection_and_reversals.csv` | CSV | **5,000** | Return credit notes (negative numbers) vs malicious Excel formula injection defense |
| `sparse_cohorts_backoff.parquet` | Parquet | **15,000** | LOAO support fences ($N \ge 10, |A| \ge 5$), hierarchical back-off, Insufficient Comparable Evidence |
| `macro_bridge_pvmc_two_periods.parquet` | Parquet | **100,000** | Decoupled PVMC bridge ($t=0$ vs $t=1$), Price/Volume/Mix/Cost, churn turnover, Volume Homogeneity Rule |
| `complex_commercial_deal_desk.xlsx` | Excel (XLSX) | **2,500** | Excel ingestion, Tier 3 authority approval matrix, AC-9 punitive lockout |

---

## 3. The 11 Complex Edge-Case Test Scenarios

---

### Use Case 1: Big Data Scale & In-Process Out-of-Core Spill Stress Test (2 Million Rows)

* **Objective:** Verify that Sift can ingest, profile, and calibrate 2,000,000 transactions without exceeding its 4 GB memory cap by properly spilling to disk.
* **Target File:** `c:\Shift\manual_testing\enterprise_2m_transactions.parquet`
* **Testing Steps:**
  1. Open the Sift UI at `http://127.0.0.1:8765` or create a new workspace via API:
     ```python
     import requests
     r = requests.post("http://127.0.0.1:8765/api/workspace/create", json={"workspace_path": "c:/Shift/manual_testing/stress_2m.mxa", "project_name": "2M Enterprise Stress"})
     assert r.status_code == 200
     ```
  2. In **View 1 (Reconcile)**, select `enterprise_2m_transactions.parquet`.
  3. Inspect the **Pass 1 Preview Table**:
     - Verify that the first 1,000 rows display instantly (< 500 ms).
     - Verify inferred column roles: `transaction_line_id` $\rightarrow$ Grain, `extended_list_amt` $\rightarrow$ Extended List, `net_invoiced_amt` $\rightarrow$ Net Invoiced, `cogs_amt` $\rightarrow$ COGS, `off_invoice_rebate` $\rightarrow$ Rebates.
  4. In the Control Confirmation Panel, enter:
     - **Confirmed Gross List:** `$108,000,000,000.00`
     - **Confirmed Net Invoiced:** `$88,500,000,000.00`
     *(Or check "Auto-calculate from scanned total" for zero-variance testing)*
  5. Click **"Execute Vectorized Scan & Ingest"**.
* **Expected Results:**
  - Full ingestion of 2,000,000 rows completes in under 15 seconds.
  - Process memory footprint stays strictly under the 4 GB limit (monitored via Windows Task Manager).
  - Out-of-core spill files are generated in `LOCALAPPDATA/Sift/duckdb_spill` if memory threshold is approached.
  - **Data Readiness Scorecard:** Unlocks **Tier 2 (Defined Pocket Contribution)** because `cogs_amt` and `off_invoice_rebate` are present.

---

### Use Case 2: Certified Audit Gate vs 1 bp Tolerance Precision

* **Objective:** Validate that exact reconciliation ($\le 1\text{ basis point}$ variance) issues "Certified Audit" status with zero watermarks.
* **Target File:** `c:\Shift\manual_testing\reconciliation_certified_audit.csv`
* **Exact Control Values:**
  - **Confirmed Gross List:** `$77,473,900.00`
  - **Confirmed Net Invoiced:** `$65,852,815.00`
* **Testing Steps:**
  1. Ingest `reconciliation_certified_audit.csv` in a new workspace.
  2. In the Control Totals confirmation box, enter the exact values above.
  3. Submit ingestion.
* **Expected Results:**
  - **Gross Variance:** `0.0000 bp`
  - **Net Variance:** `0.0000 bp`
  - **Audit Status:** Marked with a green badge: **"Certified Audit"**.
  - **Watermark:** Inactive (`watermark_active = false`). No warning banner appears on screen or in exports.
  - **Audit Manifest:** `audit_manifest.json` records `reconciliation_status: "CERTIFIED_AUDIT"`.

---

### Use Case 3: The Reconciliation Quarantine-and-Proceed Protocol (> 1 bp Variance)

* **Objective:** Test the safety protocol when control totals differ by 35 basis points (0.35%) and verify the permanent red watermark.
* **Target File:** `c:\Shift\manual_testing\reconciliation_quarantine_breach.csv`
* **Declared Control Values:**
  - **Confirmed Gross List:** `$33,700,000.00`
  - **Confirmed Net Invoiced:** `$26,900,000.00`
* **Testing Steps:**
  1. Ingest `reconciliation_quarantine_breach.csv`.
  2. Enter the declared control values above (which deliberately mismatch scanned rows by ~35 bp).
  3. Submit the reconciliation gate.
* **Expected Results:**
  - Sift displays a modal: **"Control Reconciliation Variance Exceeds 1 bp Guardrail"**.
  - Displays calculated variance: `~35.0 bp` (`~$118,000.00` difference).
  - Click **"Quarantine & Proceed"**.
  - The application isolates residual corrupted lines into `quarantined_transactions`.
  - A persistent, prominent red banner watermarks all UI views:
    ```
    UNRECONCILED RESIDUAL: 0.35% ($118,000.00) OUTSIDE AUDIT GUARDRAILS
    ```
  - Watermark persists indelibly in all exported PDF/HTML and CSV files.

---

### Use Case 4: Leave-One-Account-Out (LOAO) Mega-Account Self-Evaluation Immunity

* **Objective:** Prove that an enterprise account cannot dilute or set its own benchmark baseline.
* **Target File:** `c:\Shift\manual_testing\enterprise_2m_transactions.parquet`
* **Testing Steps:**
  1. Go to **View 2 (Calibrate)**.
  2. Select:
     - **Comparability Controls:** `product_line`, `region`, `channel`.
     - **Investigation Dimensions:** `customer_tier`.
  3. Choose **P75 Concession Ceiling** as the threshold method.
  4. Click **"Run LOAO Baseline Calibration"**.
  5. Check account `ACC-00001` (a mega-volume account).
* **Expected Results:**
  - For transaction $i$ belonging to `ACC-00001`, the baseline discount benchmark distribution $\Omega_{-A(i)}$ excludes all transactions from `ACC-00001`.
  - If `ACC-00001` negotiated an aggressive 45% discount, its own 45% deals do not raise the cohort benchmark, ensuring its concessions are defensibly audited against other accounts.

---

### Use Case 5: The Median Waterline Rule & Non-Linear Gap Scoring ($P75$ vs MAD)

* **Objective:** Ensure transactions between cohort Median and P75 are NOT flagged as defensible exceptions (preventing the 50% leakage anti-pattern).
* **Target File:** `c:\Shift\manual_testing\enterprise_2m_transactions.parquet`
* **Testing Steps:**
  1. Calibrate with default $P75$ and Haircut $\kappa = 0.40$.
  2. Query transaction-level gap scoring for transactions with discount rates:
     - Case A: Realized discount = 15% (Cohort Median = 16%, P75 = 24%).
     - Case B: Realized discount = 20% (Between Median 16% and P75 24%).
     - Case C: Realized discount = 32% (Above P75 24%).
* **Expected Results:**
  - **Case A (15%):** Defensible Gap = `$0.00`. Actionable Gap = `$0.00`.
  - **Case B (20%):** Band Gap (Median) = `(0.20 - 0.16) * List = $X`. **Defensible Gap = `$0.00`** (strictly non-actionable because it sits below the 75th percentile waterline).
  - **Case C (32%):** Defensible Gap = `(0.32 - 0.24) * List = $Y`. **Actionable Gap = `$Y * 0.40`** (qualified with capture haircut).

---

### Use Case 6: Hierarchical Back-off Ladder on Sparse Cohorts

* **Objective:** Verify automated hierarchical back-off when sample sizes fail support fences ($N < 10$ or $|A| < 5$), and flag un-benchmarkable records as `Insufficient Comparable Evidence`.
* **Target File:** `c:\Shift\manual_testing\sparse_cohorts_backoff.parquet`
* **Testing Steps:**
  1. Ingest `sparse_cohorts_backoff.parquet`.
  2. Calibrate with 4 controls: `product_line`, `region`, `contract_term`, `volume_band`.
  3. Inspect cohort evaluation logs.
* **Expected Results:**
  - **Cohort `Cloud Storage`:** Meets $N \ge 10, |A| \ge 5$. Scored directly at Level 0.
  - **Cohort `Legacy Mainframe` ($N=9, |A|=4$):** Fails Level 0. Automatically retreats along the back-off ladder by dropping `volume_band`. At Level 1, combined records achieve $N \ge 10, |A| \ge 5$ and are scored.
  - **Cohort `Quantum Computing` ($N=6, |A|=3$):** Fails Level 0, Level 1, and Level 2. Even at the broadest level, it fails $|A| \ge 5$.
  - All 6 transactions for `Quantum Computing` are tagged: **`Insufficient Comparable Evidence`**.
  - Defensible Gap is set to `$0.00` and excluded from automated triage ranking to prevent false accusations.

---

### Use Case 7: Diagnostic Beam Search & Empirical Bayes Shrinkage (The Winner's Curse Defense)

* **Objective:** Confirm that small, high-variance slices do not dominate rankings, and that the 50 planted anomalies are recovered with 100% precision.
* **Target File:** `c:\Shift\manual_testing\enterprise_2m_transactions.parquet`
* **Testing Steps:**
  1. In **View 3 (Triage & Act)**, launch **Diagnostic Beam Search**:
     - Beam Width: 3
     - Max Depth: 3
     - FDR $q$-value: 0.05
     - Investigation Dimensions: `channel`, `customer_tier`, `region`.
  2. Inspect the ranked slice findings.
* **Expected Results:**
  - **Empirical Bayes Shrinkage:** The `shrunk_gap_dollars` is strictly smaller than `unshrunk_gap_dollars` on low-volume slices, shrinking noise toward the parent mean.
  - **Bootstrap Stability:** Any candidate slice where the 90% confidence interval crosses zero is flagged or penalized.
  - **FDR Control:** Slices with $q \ge 0.05$ are filtered out.
  - **Recovery:** Slices containing the planted 65% concession deals are ranked at the very top of the ledger.

---

### Use Case 8: Deduplicated Overlap Ledger Invariant

* **Objective:** Ensure that overlapping findings display their individual exposures but strictly report the deduplicated set union for portfolio recovery.
* **Target File:** `c:\Shift\manual_testing\enterprise_2m_transactions.parquet`
* **Testing Steps:**
  1. Open **View 3 (Triage & Act)**.
  2. Review the top findings table and look at the Header KPI Card: **Net Unique Portfolio Exposure**.
  3. Manually sum the individual finding gaps: $\sum G_{\text{finding}}$.
  4. Compare with the Net Unique Portfolio Exposure.
  5. Click on any finding to open the **Transaction Ledger Drawer**.
* **Expected Results:**
  - $\sum G_{\text{finding}}$ (e.g. `$2,450,000.00`) is greater than Net Unique Portfolio Exposure (e.g. `$1,680,000.00`).
  - Sift displays:
    ```
    Individual Sum: $2,450,000.00  |  Net Unique Portfolio Exposure: $1,680,000.00
    Overlap Deduplication Ratio: 31.4%
    ```
  - The drawer displays the exact list of individual transaction line IDs belonging to the selected finding with line-item defensible gaps.

---

### Use Case 9: Negative Financial Amounts & Credit Reversals vs CSV Formula Injection Defense

* **Objective:** Confirm that negative financial numbers (`-1450.50`) parse cleanly without quotes, while spreadsheet formulas (`=cmd...`, `@SUM...`) are sanitized.
* **Target File:** `c:\Shift\manual_testing\formula_injection_and_reversals.csv`
* **Testing Steps:**
  1. Ingest `formula_injection_and_reversals.csv`.
  2. Navigate to Export and click **"Export Actionable Findings (CSV)"**.
  3. Open the exported CSV file in a text editor (e.g., Notepad or VS Code) and inspect raw byte characters.
* **Expected Results:**
  - Financial values like `-1450.50`, `-0.05`, and `-28900.00` appear as clean, unquoted numbers: `-1450.50` (NEVER `'-1450.50`).
  - Formula injection strings appear safely escaped with a single quote:
    - `=cmd|' /C calc'!A0` $\rightarrow$ `'=cmd|' /C calc'!A0`
    - `@SUM(A1:A100)` $\rightarrow$ `'@SUM(A1:A100)`
    - `+cmd|' /C notepad'!A0` $\rightarrow$ `'+cmd|' /C notepad'!A0`
    - `\t=2+5` $\rightarrow$ `'\t=2+5`
  - When opened in Excel, no formulas execute, and financial columns can be summed cleanly with `=SUM(...)`.

---

### Use Case 10: Decoupled Engine B Macro Margin Bridge (PVMC) & UoM Homogeneity Guard

* **Objective:** Test period-over-period ($t=0$ vs $t=1$) Price-Volume-Mix-Cost decomposition, churn turnover isolation, and volume unit homogeneity enforcement.
* **Target File:** `c:\Shift\manual_testing\macro_bridge_pvmc_two_periods.parquet`
* **Testing Steps:**
  1. Navigate to the **Macro Margin Bridge Tab**.
  2. Set:
     - **Base Period ($t_0$):** `2024-H1`
     - **Comparison Period ($t_1$):** `2025-H1`
     - **Unit of Measure Filter:** `USER_LICENSES`
  3. Execute bridge decomposition.
  4. Now re-run with **All Units** (mixing `USER_LICENSES` and `CONSULTING_HOURS`).
* **Expected Results:**
  - **Run 1 (Homogeneous `USER_LICENSES`):**
    - Bridge computes:
      $$\Delta \text{Margin} = \Delta \text{Price} + \Delta \text{Volume} + \Delta \text{Mix} + \Delta \text{Cost} + \text{Turnover Effect}$$
    - `Product-Alpha-Discontinued` is cleanly isolated under **Discontinued Business** ($Q_1 = 0$).
    - `Product-Omega-NewLaunch` is cleanly isolated under **New Business** ($Q_0 = 0$).
    - **Penny Reconciliation Invariant:** $|\Delta \text{Margin} - (\Delta P + \Delta V + \Delta M + \Delta C + \text{Turnover})| < \$0.01$.
  - **Run 2 (Mixed UoMs):**
    - Sift raises a validation warning:
      ```
      Volume Homogeneity Warning: Dataset contains heterogeneous units of measure (USER_LICENSES, CONSULTING_HOURS).
      Physical volume metrics cannot be summed across disparate units.
      ```

---

### Use Case 11: Lifecycle Governance, AC-9 Punitive Lockout & AES-256 Encrypted Export

* **Objective:** Test that punitive disposition codes ("Unapproved Concession", "Unauthorized Deal") are locked out on Tiers 1-2, and test password-protected AES-256 export.
* **Target File:** `c:\Shift\manual_testing\complex_commercial_deal_desk.xlsx`
* **Testing Steps:**
  1. Ingest `complex_commercial_deal_desk.xlsx` (Tier 1/Tier 2 unlocked).
  2. Run beam search to produce findings.
  3. Open a finding in the Transaction Ledger Drawer.
  4. Attempt to change state to **"In Review"** and select **"Unapproved Concession"** as disposition code.
  5. Attempt to change state to **"Dismissed"** without selecting a snooze date.
  6. Now select **"Strategic Investment"** with snooze date `2026-12-31`.
  7. Go to Export $\rightarrow$ **"Restricted Deal Ledger"**:
     - Leave "I acknowledge export of sensitive transaction records" unchecked and click Export.
     - Check the box, enter password `Confidential2026!`, and click Export.
* **Expected Results:**
  - **Step 4:** Sift strictly blocks the transition with error:
    `"Punitive disposition code 'Unapproved Concession' is locked for Tier 1. Only permitted for Tier 3 Rule-Confirmed Exceptions."`
  - **Step 5:** Dismissal rejected: `"Mandatory snooze/expiry date required for dismissal."`
  - **Step 6:** Transition succeeds; `lifecycle_audit_log` records user, timestamp, and disposition.
  - **Step 7a:** Export rejected: `"Sensitive data export requires explicit user acknowledgement."`
  - **Step 7b:** Generates `restricted_deal_ledger.zip`. When opened, ZIP cannot be extracted without entering `Confidential2026!`. When decrypted, all granular line items are present.

---

## 4. Quick-Run Automated CLI Test Script

To run all 11 complex use cases in automated sequence against the generated datasets, execute:

```powershell
cd C:\Shift
python tests\e2e\runner.py --verbose
```

All 9 acceptance suites and 279 invariant tests will execute in ~10-15 seconds and produce a green certified verification report.
