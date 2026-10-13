# Sift Stress Dataset Manifest

Generated at: 2026-09-17T04:38:58.175154+00:00
Project Root: `c:/Shift`
Deliverables Directory: `c:/Shift/test_deliverables/datasets/`

## 1. File Metadata Overview

| Metric | Dataset 1 (CSV) | Dataset 2 (Parquet) |
| :--- | :--- | :--- |
| **Filename** | `dataset_stress_1m_wide.csv` | `dataset_stress_15m_wide.parquet` |
| **Storage Format** | Standard CSV (RFC 4180) | Compressed Columnar Parquet (Snappy) |
| **Exact Row Count** | **1,000,000** rows | **15,000,000** rows |
| **Total Columns** | **87** columns | **87** columns |
| **Categorical Columns** | 62 columns (Requirement >= 60) | 62 columns (Requirement >= 60) |
| **Numerical Metric Columns** | 18 columns (Requirement >= 15) | 18 columns (Requirement >= 15) |
| **File Size (Bytes)** | 1,365,864,931 bytes | 1,644,056,293 bytes |
| **File Size (Human Readable)** | 1302.59 MB | 1.53 GB (1567.89 MB) |
| **SHA-256 Checksum** | `ee54dd538f4158bf7ca4317e1b4fbbaee2fef70b99c2b084c9d8eb9ebce865af` | `f079a90595101d9a1e5c6323cd0389e9f651c23f9f2caa89d3996b5190633c2c` |
| **Generation Latency** | 4.88s | 45.44s |

---

## 2. Deeply Buried Multi-Attribute Culprit Ground Truth

The synthetic datasets contain intentionally engineered 3-to-5 level compound slices with runaway margin and booking concessions that **strictly do not appear at top-level category aggregates**.

### Top-Level Aggregate Health Invariant
For every top-level single dimension (e.g., `sales_theater`, `prod_family`, `partner_program_tier`), the aggregate mean discount remains strictly within the standard healthy commercial corridor (**11.0% - 15.0%**). Background transactions adhere to a bounded concession distribution with parametric 75th percentile ($P75$) of **15.00%**.

### Culprit Signatures & Exact Ground Truth

#### Culprit Alpha (4-Level Compound Slice)
- **Mathematical Definition:**
  `sales_theater == 'EMEA'` AND
  `partner_program_tier == 'Gold'` AND
  `contract_commitment_type == 'MultiYear'` AND
  `prod_family == 'EnterpriseCloud'`
- **Ground Truth Values:**

| Metric | Dataset 1M (CSV) | Dataset 15M (Parquet) |
| :--- | :--- | :--- |
| **Slice Row Count ($N$)** | **2,465** rows | **37,472** rows |
| **Mean List Price ($\bar{L}$)** | $31,449.65 | $31,795.44 |
| **Mean Concession Rate ($\bar{r}$)** | **62.55%** (Runaway: 55%-70%) | **62.48%** (Runaway: 55%-70%) |
| **Baseline Cohort P75 ($\tau$)** | 15.00% | 15.00% |
| **Defensible Gap Dollar Sum ($G^{defensible}$)** | **$36,863,807.07** | **$565,779,610.76** |
| **Actionable Opportunity ($G^{actionable} = G^{def} \\times 0.40$)** | **$14,745,522.83** | **$226,311,844.30** |

#### Culprit Beta (5-Level Compound Slice)
- **Mathematical Definition:**
  `sales_theater == 'Americas'` AND
  `cust_industry_vertical == 'Financial Services'` AND
  `channel_type == 'System Integrator'` AND
  `deal_discount_governance_tier == 'Tier 4 Exception Policy'` AND
  `prod_line_of_business == 'Software Solutions'`
- **Ground Truth Values:**

| Metric | Dataset 1M (CSV) | Dataset 15M (Parquet) |
| :--- | :--- | :--- |
| **Slice Row Count ($N$)** | **462** rows | **7,877** rows |
| **Mean List Price ($\bar{L}$)** | $31,838.08 | $30,969.73 |
| **Mean Concession Rate ($\bar{r}$)** | **65.02%** (Runaway: 58%-72%) | **65.01%** (Runaway: 58%-72%) |
| **Baseline Cohort P75 ($\tau$)** | 15.00% | 15.00% |
| **Defensible Gap Dollar Sum ($G^{defensible}$)** | **$7,420,727.14** | **$122,057,902.51** |
| **Actionable Opportunity ($G^{actionable} = G^{def} \\times 0.40$)** | **$2,968,290.86** | **$48,823,161.00** |

#### Culprit Gamma (3-Level Compound Slice)
- **Mathematical Definition:**
  `sales_theater == 'APAC'` AND
  `prod_deployment_mode == 'Sovereign Air-Gap'` AND
  `contract_sla_tier == 'Ultra Five-Nines'`
- **Ground Truth Values:**

| Metric | Dataset 1M (CSV) | Dataset 15M (Parquet) |
| :--- | :--- | :--- |
| **Slice Row Count ($N$)** | **15,785** rows | **235,374** rows |
| **Mean List Price ($\bar{L}$)** | $31,526.35 | $31,473.99 |
| **Mean Concession Rate ($\bar{r}$)** | **59.01%** (Runaway: 52%-66%) | **58.99%** (Runaway: 52%-66%) |
| **Baseline Cohort P75 ($\tau$)** | 15.00% | 15.00% |
| **Defensible Gap Dollar Sum ($G^{defensible}$)** | **$218,951,306.69** | **$3,258,354,279.89** |
| **Actionable Opportunity ($G^{actionable} = G^{def} \\times 0.40$)** | **$87,580,522.67** | **$1,303,341,711.96** |

---

## 3. Complete Column Schema Table (87 Columns)

All 87 columns are fully compatible with Sift canonical ingestion, LOAO comparability categorization, diagnostic beam search, and Decoupled Engine B margin bridges.

| # | Column Name | Data Type | Business Classification |
| :--- | :--- | :--- | :--- |
| 1 | `transaction_line_id` | String / Dictionary | Line-Grain Canonical / Identifier |
| 2 | `invoice_id` | String / Dictionary | Line-Grain Canonical / Identifier |
| 3 | `account_id` | String / Dictionary | Line-Grain Canonical / Identifier |
| 4 | `customer_name` | String / Dictionary | Line-Grain Canonical / Identifier |
| 5 | `parent_account_id` | String / Dictionary | Line-Grain Canonical / Identifier |
| 6 | `transaction_date` | String / Dictionary | Line-Grain Canonical / Identifier |
| 7 | `currency` | String / Dictionary | Line-Grain Canonical / Identifier |
| 8 | `extended_list_amt` | Float64 | Numerical Metric / Financial Concession |
| 9 | `net_invoiced_amt` | Float64 | Numerical Metric / Financial Concession |
| 10 | `cogs_amt` | Float64 | Numerical Metric / Financial Concession |
| 11 | `off_invoice_rebate` | Float64 | Numerical Metric / Financial Concession |
| 12 | `fx_rate_to_reporting` | Float64 | Numerical Metric / Financial Concession |
| 13 | `list_unit_price` | Float64 | Numerical Metric / Financial Concession |
| 14 | `order_quantity` | Float64 | Numerical Metric / Financial Concession |
| 15 | `base_discount_amt` | Float64 | Numerical Metric / Financial Concession |
| 16 | `promo_discount_amt` | Float64 | Numerical Metric / Financial Concession |
| 17 | `freight_shipping_amt` | Float64 | Numerical Metric / Financial Concession |
| 18 | `tax_vat_amt` | Float64 | Numerical Metric / Financial Concession |
| 19 | `standard_margin_amt` | Float64 | Numerical Metric / Financial Concession |
| 20 | `pocket_margin_amt` | Float64 | Numerical Metric / Financial Concession |
| 21 | `gross_booking_val` | Float64 | Numerical Metric / Financial Concession |
| 22 | `net_booking_val` | Float64 | Numerical Metric / Financial Concession |
| 23 | `rebate_accrual_pct` | Float64 | Numerical Metric / Financial Concession |
| 24 | `payment_terms_penalty` | Float64 | Numerical Metric / Financial Concession |
| 25 | `credit_adjustment_amt` | Float64 | Numerical Metric / Financial Concession |
| 26 | `sales_theater` | Categorical Dictionary | Sales Hierarchy Dimension |
| 27 | `sales_region` | Categorical Dictionary | Sales Hierarchy Dimension |
| 28 | `sales_area` | Categorical Dictionary | Sales Hierarchy Dimension |
| 29 | `sales_territory` | Categorical Dictionary | Sales Hierarchy Dimension |
| 30 | `sales_district` | Categorical Dictionary | Sales Hierarchy Dimension |
| 31 | `sales_rep_tier` | Categorical Dictionary | Sales Hierarchy Dimension |
| 32 | `channel_type` | Categorical Dictionary | Sales Hierarchy Dimension |
| 33 | `partner_program_tier` | Categorical Dictionary | Sales Hierarchy Dimension |
| 34 | `distributor_tier` | Categorical Dictionary | Sales Hierarchy Dimension |
| 35 | `sales_motion` | Categorical Dictionary | Sales Hierarchy Dimension |
| 36 | `quota_class` | Categorical Dictionary | Sales Hierarchy Dimension |
| 37 | `deal_desk_lead` | Categorical Dictionary | Sales Hierarchy Dimension |
| 38 | `prod_line_of_business` | Categorical Dictionary | Product Taxonomy Dimension |
| 39 | `prod_family` | Categorical Dictionary | Product Taxonomy Dimension |
| 40 | `prod_category` | Categorical Dictionary | Product Taxonomy Dimension |
| 41 | `prod_subcategory` | Categorical Dictionary | Product Taxonomy Dimension |
| 42 | `prod_edition` | Categorical Dictionary | Product Taxonomy Dimension |
| 43 | `prod_lifecycle_status` | Categorical Dictionary | Product Taxonomy Dimension |
| 44 | `prod_licensing_model` | Categorical Dictionary | Product Taxonomy Dimension |
| 45 | `prod_deployment_mode` | Categorical Dictionary | Product Taxonomy Dimension |
| 46 | `prod_hardware_form_factor` | Categorical Dictionary | Product Taxonomy Dimension |
| 47 | `prod_support_tier` | Categorical Dictionary | Product Taxonomy Dimension |
| 48 | `prod_release_train` | Categorical Dictionary | Product Taxonomy Dimension |
| 49 | `prod_billing_metric` | Categorical Dictionary | Product Taxonomy Dimension |
| 50 | `prod_warranty_code` | Categorical Dictionary | Product Taxonomy Dimension |
| 51 | `cust_industry_vertical` | Categorical Dictionary | Customer Classification Dimension |
| 52 | `cust_sub_industry` | Categorical Dictionary | Customer Classification Dimension |
| 53 | `cust_enterprise_segment` | Categorical Dictionary | Customer Classification Dimension |
| 54 | `cust_tier` | Categorical Dictionary | Customer Classification Dimension |
| 55 | `cust_credit_rating` | Categorical Dictionary | Customer Classification Dimension |
| 56 | `cust_procurement_type` | Categorical Dictionary | Customer Classification Dimension |
| 57 | `cust_hq_country` | Categorical Dictionary | Customer Classification Dimension |
| 58 | `cust_operating_geo` | Categorical Dictionary | Customer Classification Dimension |
| 59 | `cust_relationship_tenure` | Categorical Dictionary | Customer Classification Dimension |
| 60 | `cust_tax_exempt_status` | Categorical Dictionary | Customer Classification Dimension |
| 61 | `cust_duns_rating` | Categorical Dictionary | Customer Classification Dimension |
| 62 | `cust_payment_behavior_score` | Categorical Dictionary | Customer Classification Dimension |
| 63 | `cust_risk_tier` | Categorical Dictionary | Customer Classification Dimension |
| 64 | `cust_buying_persona` | Categorical Dictionary | Customer Classification Dimension |
| 65 | `cust_preferred_language` | Categorical Dictionary | Customer Classification Dimension |
| 66 | `contract_commitment_type` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 67 | `contract_billing_frequency` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 68 | `contract_auto_renewal` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 69 | `contract_sla_tier` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 70 | `deal_pricing_approval_level` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 71 | `deal_discount_governance_tier` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 72 | `deal_strategic_flag` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 73 | `deal_origination_source` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 74 | `deal_currency_hedging_flag` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 75 | `deal_incoterms` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 76 | `order_fulfillment_center` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 77 | `shipping_priority_tier` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 78 | `payment_method_type` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 79 | `invoice_settlement_term` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 80 | `deal_contract_type` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 81 | `audit_right_stipulation` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 82 | `order_entry_channel` | Categorical Dictionary | Sales Hierarchy Dimension |
| 83 | `order_validation_status` | Categorical Dictionary | Contract & Deal Stipulation Dimension |
| 84 | `fulfillment_status` | Categorical Dictionary | Operations & Metadata Dimension |
| 85 | `billing_system_id` | Categorical Dictionary | Operations & Metadata Dimension |
| 86 | `fiscal_quarter` | Categorical Dictionary | Operations & Metadata Dimension |
| 87 | `price_book_version` | Categorical Dictionary | Operations & Metadata Dimension |

---

## 4. In-Process DuckDB Verification Log

```text
### In-Process DuckDB Verification Report
Verification Timestamp: 2026-09-17T04:38:55.454382+00:00

#### 1. Verifying dataset_stress_1m_wide.csv
- Verified Row Count: 1,000,000 (Expected: 1,000,000) -> PASS
- Verified Column Count: 87 (Expected: 87) -> PASS
- Top-Level Single-Dimension Aggregates (sales_theater):
    * APAC: 249,514 rows, Mean Discount: 14.98% (Healthy Band: 10% - 15%)
    * Americas: 250,097 rows, Mean Discount: 12.11% (Healthy Band: 10% - 15%)
    * EMEA: 250,288 rows, Mean Discount: 12.49% (Healthy Band: 10% - 15%)
    * Japan: 250,101 rows, Mean Discount: 12.01% (Healthy Band: 10% - 15%)
- Culprit Alpha (4-Level Compound Slice) Verification in 1M CSV:
    * Rows: 2,465
    * Mean List Price: $31,449.65
    * Mean Discount %: 62.55% (Runaway Exception: 55% - 70%)
    * Defensible Gap Sum: $36,863,807.07
    * Actionable Opportunity (40%): $14,745,522.83

#### 2. Verifying dataset_stress_15m_wide.parquet
- Verified Row Count: 15,000,000 (Expected: 15,000,000) in 0.01s -> PASS
- Verified Column Count: 87 (Expected: 87) -> PASS
- Top-Level Single-Dimension Aggregates (sales_theater) on 15M Parquet:
    * APAC: 3,750,647 rows, Mean Discount: 14.95% (Healthy Band: 10% - 15%)
    * Americas: 3,750,363 rows, Mean Discount: 12.11% (Healthy Band: 10% - 15%)
    * EMEA: 3,751,302 rows, Mean Discount: 12.5% (Healthy Band: 10% - 15%)
    * Japan: 3,747,688 rows, Mean Discount: 12.0% (Healthy Band: 10% - 15%)
- Culprit Alpha (4-Level Compound Slice) Verification in 15M Parquet:
    * Rows: 37,472
    * Mean List Price: $31,795.44
    * Mean Discount %: 62.48% (Runaway Exception: 55% - 70%)
    * Defensible Gap Sum: $565,779,610.76
    * Actionable Opportunity (40%): $226,311,844.3
```

---

## 5. Automated Python Verification Code

To independently reproduce the verification of row counts, column counts, and culprit signatures, execute:

```python
import duckdb

con = duckdb.connect(":memory:")

# 1. Verify 1M CSV
print("Verifying 1M CSV...")
csv_rows = con.execute("SELECT COUNT(*) FROM read_csv_auto('c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv', header=True)").fetchone()[0]
print(f"Row count 1M CSV: {csv_rows:,}")

# 2. Verify 15M Parquet
print("Verifying 15M Parquet...")
pq_rows = con.execute("SELECT COUNT(*) FROM read_parquet('c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet')").fetchone()[0]
print(f"Row count 15M Parquet: {pq_rows:,}")

# 3. Verify Culprit Alpha 4-level signature in 15M Parquet
alpha_res = con.execute('''
    SELECT 
        COUNT(*) as slice_rows,
        ROUND(AVG(extended_list_amt), 2) as mean_list,
        ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
        ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
        ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
    FROM read_parquet('c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet')
    WHERE sales_theater = 'EMEA'
      AND partner_program_tier = 'Gold'
      AND contract_commitment_type = 'MultiYear'
      AND prod_family = 'EnterpriseCloud'
''').fetchone()

print(f"Culprit Alpha: Rows={alpha_res[0]:,}, MeanDisc={alpha_res[2]}%, DefGap=${alpha_res[3]:,}, ActOpp=${alpha_res[4]:,}")
con.close()
```
