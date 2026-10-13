"""
High-Performance Dataset Generator for Manual Testing of Sift.
Generates complex, large-scale commercial audit datasets:
1. enterprise_2m_transactions.parquet (2,000,000 rows, multi-currency, planted anomalies, pocket margin)
2. reconciliation_quarantine_breach.csv (25,000 rows, 35 bp discrepancy, corrupted residual lines)
3. reconciliation_certified_audit.csv (25,000 rows, exact known control totals, 0.0000 bp variance)
4. formula_injection_and_reversals.csv (5,000 rows, negative amounts, reversals, dangerous Excel formulas)
5. sparse_cohorts_backoff.parquet (15,000 rows, sparse edge cases testing hierarchical back-off)
6. macro_bridge_pvmc_two_periods.parquet (100,000 rows, t0 vs t1, Price/Volume/Mix/Cost/Turnover & UoM checks)
7. complex_commercial_deal_desk.xlsx (Excel workbook with Tier 1-3 data and authorization schedules)
"""

import os
import sys
import time
import duckdb
import pandas as pd
import openpyxl

OUT_DIR = os.path.abspath(os.path.dirname(__file__))
os.makedirs(OUT_DIR, exist_ok=True)

con = duckdb.connect(":memory:")
con.execute("PRAGMA threads = 4;")
con.execute("PRAGMA max_memory = '4GB';")

print(f"[*] Initializing dataset generation in: {OUT_DIR}")

# ---------------------------------------------------------------------------
# 1. enterprise_2m_transactions.parquet (2,000,000 rows)
# ---------------------------------------------------------------------------
print("[1/7] Generating enterprise_2m_transactions.parquet (2,000,000 rows)...")
t0 = time.time()
parquet_2m_path = os.path.join(OUT_DIR, "enterprise_2m_transactions.parquet").replace("\\", "/")

con.execute(f"""
COPY (
    WITH raw_series AS (
        SELECT range AS id
        FROM range(2000000)
    ),
    synthesized AS (
        SELECT
            'TXN-' || LPAD(id::VARCHAR, 8, '0') AS transaction_line_id,
            'INV-' || LPAD((id / 4)::BIGINT::VARCHAR, 7, '0') AS invoice_id,
            'ACC-' || LPAD(((id % 4500) + 1)::VARCHAR, 5, '0') AS account_id,
            'PARENT-' || LPAD(((id % 800) + 1)::VARCHAR, 4, '0') AS parent_account_id,
            DATE '2025-01-01' + INTERVAL (id % 365) DAYS AS transaction_date,
            CASE (id % 5)
                WHEN 0 THEN 'USD'
                WHEN 1 THEN 'EUR'
                WHEN 2 THEN 'GBP'
                WHEN 3 THEN 'CAD'
                ELSE 'JPY'
            END AS currency,
            CASE (id % 5)
                WHEN 0 THEN 1.000000
                WHEN 1 THEN 1.085000
                WHEN 2 THEN 1.275000
                WHEN 3 THEN 0.742000
                ELSE 0.006700
            END AS fx_rate_to_reporting,
            CASE (id % 6)
                WHEN 0 THEN 'Enterprise Cloud'
                WHEN 1 THEN 'Cybersecurity Platform'
                WHEN 2 THEN 'Edge Compute Hardware'
                WHEN 3 THEN 'Managed Infrastructure'
                WHEN 4 THEN 'Analytics Suite'
                ELSE 'Professional Services'
            END AS product_line,
            CASE (id % 4)
                WHEN 0 THEN 'North America'
                WHEN 1 THEN 'EMEA'
                WHEN 2 THEN 'APAC'
                ELSE 'LATAM'
            END AS region,
            CASE (id % 3)
                WHEN 0 THEN 'Direct Enterprise'
                WHEN 1 THEN 'Global System Integrator'
                ELSE 'Value Added Reseller'
            END AS channel,
            CASE (id % 3)
                WHEN 0 THEN '1-Year Annual'
                WHEN 1 THEN '3-Year Multi-Year'
                ELSE 'Monthly Flexible'
            END AS contract_term,
            CASE (id % 4)
                WHEN 0 THEN 'Strategic Global'
                WHEN 1 THEN 'Tier 1 Key Account'
                WHEN 2 THEN 'Mid-Market Core'
                ELSE 'Growth Commercial'
            END AS customer_tier,
            -- Baseline financial amounts
            ROUND(100.0 + ((id * 37) % 9900) + ((id % 13) * 7.5), 2) AS list_unit_price,
            ROUND(1.0 + ((id * 17) % 50), 0) AS quantity,
            -- Off-policy discount anomalies: plant extreme 65% discounts on 50 specific transactions
            CASE 
                WHEN id IN (142, 1289, 5892, 14201, 29012, 45890, 78120, 105820, 150291, 192019,
                            241029, 298102, 350192, 412091, 489102, 532019, 601920, 678912, 734019, 812091,
                            890129, 954019, 1029102, 1102910, 1189201, 1259102, 1340192, 1420192, 1501920, 1589102,
                            1650192, 1720192, 1790129, 1850192, 1920192, 1989102, 4520, 89120, 239019, 391029,
                            491029, 612091, 749102, 859102, 981029, 1159102, 1319201, 1490129, 1689102, 1890129)
                THEN 0.650000
                -- Standard distribution: discount centered at 12% - 28%
                ELSE ROUND(0.05 + ((id % 25) * 0.010), 4)
            END AS concession_discount_rate
        FROM raw_series
    )
    SELECT
        transaction_line_id,
        invoice_id,
        account_id,
        parent_account_id,
        transaction_date,
        currency,
        fx_rate_to_reporting,
        product_line,
        region,
        channel,
        contract_term,
        customer_tier,
        quantity,
        ROUND(list_unit_price * quantity, 2) AS extended_list_amt,
        ROUND((list_unit_price * quantity) * (1.0 - concession_discount_rate), 2) AS net_invoiced_amt,
        ROUND((list_unit_price * quantity) * 0.42, 2) AS cogs_amt,
        ROUND((list_unit_price * quantity) * 0.035, 2) AS off_invoice_rebate
    FROM synthesized
) TO '{parquet_2m_path}' (FORMAT PARQUET, COMPRESSION SNAPPY);
""")
el1 = time.time() - t0
print(f"    -> Created {parquet_2m_path} (2M rows in {el1:.2f}s, size: {os.path.getsize(parquet_2m_path)/(1024*1024):.1f} MB)")

# ---------------------------------------------------------------------------
# 2. reconciliation_quarantine_breach.csv (25,000 rows, 35 bp variance + corrupted lines)
# ---------------------------------------------------------------------------
print("[2/7] Generating reconciliation_quarantine_breach.csv (25,000 rows)...")
csv_breach_path = os.path.join(OUT_DIR, "reconciliation_quarantine_breach.csv").replace("\\", "/")

# Control totals: We declare control totals that differ from ingested sum by 35 bp ($350 per $100,000)
# Sum will be ~ $35,000,000 List and $28,000,000 Net
con.execute(f"""
COPY (
    WITH s AS (
        SELECT range AS i FROM range(25000)
    )
    SELECT
        'BRCH-' || LPAD(i::VARCHAR, 6, '0') AS transaction_line_id,
        'INV-B-' || LPAD((i/3)::BIGINT::VARCHAR, 5, '0') AS invoice_id,
        'ACC-B-' || LPAD(((i%250)+1)::VARCHAR, 4, '0') AS account_id,
        'PARENT-B-' || LPAD(((i%50)+1)::VARCHAR, 3, '0') AS parent_account_id,
        DATE '2025-03-01' + INTERVAL (i%180) DAYS AS transaction_date,
        'USD' AS currency,
        1.0 AS fx_rate_to_reporting,
        CASE (i % 4)
            WHEN 0 THEN 'Cloud Infrastructure'
            WHEN 1 THEN 'Database Systems'
            WHEN 2 THEN 'Security Gateway'
            ELSE 'Advisory Consulting'
        END AS product_line,
        CASE (i % 3)
            WHEN 0 THEN 'Americas'
            WHEN 1 THEN 'EMEA'
            ELSE 'APAC'
        END AS region,
        'Direct' AS channel,
        -- Deliberate residual lines: 15 records with extreme negative list or null values
        CASE 
            WHEN i IN (500, 1200, 3400, 7800, 11200) THEN -50000.00
            ELSE ROUND(800.0 + ((i*19)%2400), 2)
        END AS extended_list_amt,
        CASE 
            WHEN i IN (500, 1200, 3400, 7800, 11200) THEN -42000.00
            ELSE ROUND((800.0 + ((i*19)%2400)) * 0.82, 2)
        END AS net_invoiced_amt,
        ROUND((800.0 + ((i*19)%2400)) * 0.38, 2) AS cogs_amt,
        ROUND((800.0 + ((i*19)%2400)) * 0.04, 2) AS off_invoice_rebate
    FROM s
) TO '{csv_breach_path}' (HEADER, DELIMITER ',');
""")
print(f"    -> Created {csv_breach_path} (size: {os.path.getsize(csv_breach_path)/(1024*1024):.1f} MB)")

# Calculate control totals for breach test
ctrl_stats = con.execute(f"""
    SELECT 
        ROUND(SUM(extended_list_amt), 2) AS actual_list,
        ROUND(SUM(net_invoiced_amt), 2) AS actual_net
    FROM '{csv_breach_path}'
""").fetchone()
actual_list, actual_net = ctrl_stats[0], ctrl_stats[1]
# Add 35 basis points (0.35%) to control gross and net
declared_list_breach = round(actual_list * 1.0035, 2)
declared_net_breach = round(actual_net * 1.0035, 2)

# ---------------------------------------------------------------------------
# 3. reconciliation_certified_audit.csv (25,000 rows, exact 0.0000 bp match)
# ---------------------------------------------------------------------------
print("[3/7] Generating reconciliation_certified_audit.csv (25,000 rows)...")
csv_cert_path = os.path.join(OUT_DIR, "reconciliation_certified_audit.csv").replace("\\", "/")

con.execute(f"""
COPY (
    WITH s AS (
        SELECT range AS i FROM range(25000)
    )
    SELECT
        'CERT-' || LPAD(i::VARCHAR, 6, '0') AS transaction_line_id,
        'INV-C-' || LPAD((i/2)::BIGINT::VARCHAR, 5, '0') AS invoice_id,
        'ACC-C-' || LPAD(((i%300)+1)::VARCHAR, 4, '0') AS account_id,
        'PARENT-C-' || LPAD(((i%60)+1)::VARCHAR, 3, '0') AS parent_account_id,
        DATE '2025-01-15' + INTERVAL (i%150) DAYS AS transaction_date,
        'USD' AS currency,
        1.0 AS fx_rate_to_reporting,
        CASE (i % 3)
            WHEN 0 THEN 'Subscription Core'
            WHEN 1 THEN 'Premium Add-on'
            ELSE 'Professional Services'
        END AS product_line,
        CASE (i % 3)
            WHEN 0 THEN 'North America'
            WHEN 1 THEN 'Europe'
            ELSE 'Asia Pacific'
        END AS region,
        'Enterprise Direct' AS channel,
        ROUND(1200.0 + ((i*31)%3800), 2) AS extended_list_amt,
        ROUND((1200.0 + ((i*31)%3800)) * 0.85, 2) AS net_invoiced_amt,
        ROUND((1200.0 + ((i*31)%3800)) * 0.40, 2) AS cogs_amt,
        ROUND((1200.0 + ((i*31)%3800)) * 0.03, 2) AS off_invoice_rebate
    FROM s
) TO '{csv_cert_path}' (HEADER, DELIMITER ',');
""")
cert_stats = con.execute(f"""
    SELECT 
        ROUND(SUM(extended_list_amt), 2) AS actual_list,
        ROUND(SUM(net_invoiced_amt), 2) AS actual_net
    FROM '{csv_cert_path}'
""").fetchone()
exact_control_list, exact_control_net = cert_stats[0], cert_stats[1]
print(f"    -> Created {csv_cert_path} (exact control list: ${exact_control_list:,.2f}, net: ${exact_control_net:,.2f})")

# ---------------------------------------------------------------------------
# 4. formula_injection_and_reversals.csv (5,000 rows)
# ---------------------------------------------------------------------------
print("[4/7] Generating formula_injection_and_reversals.csv (5,000 rows)...")
csv_formula_path = os.path.join(OUT_DIR, "formula_injection_and_reversals.csv").replace("\\", "/")

# Generates negative numbers (-1450.50), return credits, and dangerous spreadsheet formula strings
con.execute(f"""
COPY (
    WITH s AS (
        SELECT range AS i FROM range(5000)
    )
    SELECT
        'REV-' || LPAD(i::VARCHAR, 5, '0') AS transaction_line_id,
        'INV-R-' || LPAD((i/2)::BIGINT::VARCHAR, 4, '0') AS invoice_id,
        'ACC-R-' || LPAD(((i%80)+1)::VARCHAR, 3, '0') AS account_id,
        DATE '2025-04-01' + INTERVAL (i%90) DAYS AS transaction_date,
        'USD' AS currency,
        1.0 AS fx_rate_to_reporting,
        'Hardware Servers' AS product_line,
        'North America' AS region,
        CASE 
            WHEN i % 50 = 0 THEN '=cmd|'' /C calc''!A0'
            WHEN i % 50 = 1 THEN '@SUM(A1:A100)'
            WHEN i % 50 = 2 THEN '+cmd|'' /C notepad''!A0'
            WHEN i % 50 = 3 THEN '-DANGEROUS_PAYLOAD'
            WHEN i % 50 = 4 THEN E'\\t=2+5'
            ELSE 'Standard Deal Desk Concession'
        END AS deal_notes,
        -- Valid negative financial reversals (return credit notes)
        CASE 
            WHEN i % 15 = 0 THEN -1450.50
            WHEN i % 15 = 1 THEN -0.05
            WHEN i % 15 = 2 THEN -28900.00
            ELSE ROUND(1500.0 + ((i*11)%4500), 2)
        END AS extended_list_amt,
        CASE 
            WHEN i % 15 = 0 THEN -1160.40
            WHEN i % 15 = 1 THEN -0.04
            WHEN i % 15 = 2 THEN -23120.00
            ELSE ROUND((1500.0 + ((i*11)%4500)) * 0.80, 2)
        END AS net_invoiced_amt,
        CASE 
            WHEN i % 15 = 0 THEN -600.00
            WHEN i % 15 = 1 THEN -0.02
            WHEN i % 15 = 2 THEN -12000.00
            ELSE ROUND((1500.0 + ((i*11)%4500)) * 0.40, 2)
        END AS cogs_amt,
        0.00 AS off_invoice_rebate
    FROM s
) TO '{csv_formula_path}' (HEADER, DELIMITER ',');
""")
print(f"    -> Created {csv_formula_path} (size: {os.path.getsize(csv_formula_path)/(1024):.1f} KB)")

# ---------------------------------------------------------------------------
# 5. sparse_cohorts_backoff.parquet (15,000 rows)
# ---------------------------------------------------------------------------
print("[5/7] Generating sparse_cohorts_backoff.parquet (15,000 rows)...")
sparse_path = os.path.join(OUT_DIR, "sparse_cohorts_backoff.parquet").replace("\\", "/")

con.execute(f"""
COPY (
    WITH s AS (
        SELECT range AS i FROM range(15000)
    )
    SELECT
        'SPARSE-' || LPAD(i::VARCHAR, 6, '0') AS transaction_line_id,
        'INV-S-' || LPAD((i/2)::BIGINT::VARCHAR, 5, '0') AS invoice_id,
        -- Extreme sparsity for special cohorts:
        -- Cohort 'Quantum Computing' has only 3 accounts and 6 transactions total
        CASE 
            WHEN i < 6 THEN 'ACC-QUANTUM-' || (i % 3 + 1)::VARCHAR
            -- Cohort 'Legacy Mainframe' has 4 accounts and 9 transactions total
            WHEN i BETWEEN 6 AND 14 THEN 'ACC-MAINFRAME-' || (i % 4 + 1)::VARCHAR
            ELSE 'ACC-DENSE-' || LPAD(((i%350)+1)::VARCHAR, 4, '0')
        END AS account_id,
        DATE '2025-02-01' + INTERVAL (i%120) DAYS AS transaction_date,
        'USD' AS currency,
        1.0 AS fx_rate_to_reporting,
        CASE 
            WHEN i < 6 THEN 'Quantum Computing'
            WHEN i BETWEEN 6 AND 14 THEN 'Legacy Mainframe'
            ELSE 'Cloud Storage'
        END AS product_line,
        CASE 
            WHEN i < 6 THEN 'Special Research Zone'
            WHEN i BETWEEN 6 AND 14 THEN 'Federal Secure'
            ELSE 'Global Commercial'
        END AS region,
        CASE 
            WHEN i < 6 THEN 'Bespoke Pilot'
            ELSE 'Standard Tier'
        END AS contract_term,
        CASE 
            WHEN i < 6 THEN 'Ultra High Custom'
            ELSE 'Standard Volume Band'
        END AS volume_band,
        ROUND(5000.0 + ((i*43)%15000), 2) AS extended_list_amt,
        ROUND((5000.0 + ((i*43)%15000)) * 0.70, 2) AS net_invoiced_amt,
        ROUND((5000.0 + ((i*43)%15000)) * 0.35, 2) AS cogs_amt,
        0.00 AS off_invoice_rebate
    FROM s
) TO '{sparse_path}' (FORMAT PARQUET, COMPRESSION SNAPPY);
""")
print(f"    -> Created {sparse_path} (size: {os.path.getsize(sparse_path)/(1024):.1f} KB)")

# ---------------------------------------------------------------------------
# 6. macro_bridge_pvmc_two_periods.parquet (100,000 rows: t0 vs t1)
# ---------------------------------------------------------------------------
print("[6/7] Generating macro_bridge_pvmc_two_periods.parquet (100,000 rows)...")
pvmc_path = os.path.join(OUT_DIR, "macro_bridge_pvmc_two_periods.parquet").replace("\\", "/")

con.execute(f"""
COPY (
    WITH s AS (
        SELECT range AS i FROM range(100000)
    ),
    categorized AS (
        SELECT
            i,
            CASE WHEN i < 50000 THEN '2024-H1' ELSE '2025-H1' END AS period_label,
            CASE WHEN i < 50000 THEN DATE '2024-01-01' + INTERVAL (i % 180) DAYS 
                 ELSE DATE '2025-01-01' + INTERVAL ((i-50000) % 180) DAYS 
            END AS transaction_date,
            -- Continuous products (both periods), Exit products (only t0), Entry products (only t1)
            CASE 
                WHEN i < 4000 THEN 'Product-Alpha-Discontinued'  -- Exits in t0
                WHEN i >= 50000 AND i < 54500 THEN 'Product-Omega-NewLaunch' -- Enters in t1
                WHEN (i % 5) = 0 THEN 'Product-SaaS-Enterprise'
                WHEN (i % 5) = 1 THEN 'Product-Platform-Core'
                WHEN (i % 5) = 2 THEN 'Product-Security-Shield'
                WHEN (i % 5) = 3 THEN 'Product-Data-Lake'
                ELSE 'Product-Compute-Engine'
            END AS product_family,
            -- Unit of Measure: mostly Homogeneous 'LICENSES', with some 'HOURS' to test UoM Homogeneity Guard
            CASE 
                WHEN (i % 1000) = 0 THEN 'CONSULTING_HOURS'
                ELSE 'USER_LICENSES'
            END AS unit_of_measure,
            -- Price inflation in t1 (10% higher list price on continuing products)
            CASE 
                WHEN i >= 50000 THEN ROUND(110.0 + ((i % 100) * 12.0), 2)
                ELSE ROUND(100.0 + ((i % 100) * 11.0), 2)
            END AS unit_price,
            ROUND(5.0 + ((i * 7) % 45), 0) AS unit_quantity,
            -- Cost inflation in t1 (8% higher standard cost)
            CASE 
                WHEN i >= 50000 THEN ROUND(43.20 + ((i % 50) * 4.5), 2)
                ELSE ROUND(40.00 + ((i % 50) * 4.0), 2)
            END AS unit_cost
        FROM s
    )
    SELECT
        'PVMC-' || LPAD(i::VARCHAR, 7, '0') AS transaction_line_id,
        'INV-P-' || LPAD((i/2)::BIGINT::VARCHAR, 6, '0') AS invoice_id,
        'ACC-P-' || LPAD(((i%800)+1)::VARCHAR, 4, '0') AS account_id,
        transaction_date,
        'USD' AS currency,
        1.0 AS fx_rate_to_reporting,
        period_label,
        product_family,
        unit_of_measure,
        unit_quantity AS quantity,
        ROUND(unit_price * unit_quantity, 2) AS extended_list_amt,
        ROUND(unit_price * unit_quantity * 0.88, 2) AS net_invoiced_amt,
        ROUND(unit_cost * unit_quantity, 2) AS cogs_amt,
        ROUND(unit_price * unit_quantity * 0.02, 2) AS off_invoice_rebate
    FROM categorized
) TO '{pvmc_path}' (FORMAT PARQUET, COMPRESSION SNAPPY);
""")
print(f"    -> Created {pvmc_path} (size: {os.path.getsize(pvmc_path)/(1024*1024):.1f} MB)")

# ---------------------------------------------------------------------------
# 7. complex_commercial_deal_desk.xlsx (Excel Workbook)
# ---------------------------------------------------------------------------
print("[7/7] Generating complex_commercial_deal_desk.xlsx (Excel with 2,500 rows + policy tables)...")
xlsx_path = os.path.join(OUT_DIR, "complex_commercial_deal_desk.xlsx")

# Sample 2,500 rows for Excel to keep file size reasonable (~300 KB) and fast to open
sample_df = con.execute("""
    WITH s AS (
        SELECT range AS i FROM range(2500)
    )
    SELECT
        'DEAL-' || LPAD(i::VARCHAR, 5, '0') AS transaction_line_id,
        'INV-XL-' || LPAD((i/2)::BIGINT::VARCHAR, 4, '0') AS invoice_id,
        'ACC-XL-' || LPAD(((i%120)+1)::VARCHAR, 3, '0') AS account_id,
        'PARENT-XL-' || LPAD(((i%30)+1)::VARCHAR, 2, '0') AS parent_account_id,
        (DATE '2025-05-01' + INTERVAL (i%120) DAYS)::VARCHAR AS transaction_date,
        'USD' AS currency,
        1.0 AS fx_rate_to_reporting,
        CASE (i % 3)
            WHEN 0 THEN 'AI Copilot Enterprise'
            WHEN 1 THEN 'Data Platform Ultra'
            ELSE 'Cloud Security Mesh'
        END AS product_line,
        CASE (i % 3)
            WHEN 0 THEN 'Americas East'
            WHEN 1 THEN 'EMEA Central'
            ELSE 'Asia Growth'
        END AS region,
        'Tier 1 Strategic' AS customer_tier,
        ROUND(2500.0 + ((i*37)%7500), 2) AS extended_list_amt,
        ROUND((2500.0 + ((i*37)%7500)) * (1.0 - (0.10 + (i%20)*0.01)), 2) AS net_invoiced_amt,
        ROUND((2500.0 + ((i*37)%7500)) * 0.40, 2) AS cogs_amt,
        ROUND((2500.0 + ((i*37)%7500)) * 0.05, 2) AS off_invoice_rebate
    FROM s
""").df()

# Create Excel writer with multiple tabs
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
    sample_df.to_excel(writer, sheet_name="Granular_Sales_Transactions", index=False)
    
    # Policy approval matrix table (Tier 3)
    policy_df = pd.DataFrame([
        {"role": "Sales Representative", "max_discount_pct": 15.0, "requires_vp_signoff": False},
        {"role": "Deal Desk Manager", "max_discount_pct": 25.0, "requires_vp_signoff": False},
        {"role": "Regional Vice President", "max_discount_pct": 35.0, "requires_vp_signoff": True},
        {"role": "Executive Pricing Committee", "max_discount_pct": 50.0, "requires_vp_signoff": True},
    ])
    policy_df.to_excel(writer, sheet_name="Authority_Matrix", index=False)

print(f"    -> Created {xlsx_path} (size: {os.path.getsize(xlsx_path)/(1024):.1f} KB)")

# Output summary manifest
summary_path = os.path.join(OUT_DIR, "MANIFEST.json")
import json
with open(summary_path, "w") as f:
    json.dump({
        "enterprise_2m_parquet": {
            "path": "enterprise_2m_transactions.parquet",
            "rows": 2000000,
            "format": "PARQUET",
            "currencies": ["USD", "EUR", "GBP", "CAD", "JPY"],
            "planted_anomalies_count": 50,
        },
        "reconciliation_quarantine_csv": {
            "path": "reconciliation_quarantine_breach.csv",
            "rows": 25000,
            "format": "CSV",
            "declared_list": declared_list_breach,
            "declared_net": declared_net_breach,
            "actual_list": actual_list,
            "actual_net": actual_net,
            "variance_bp": 35.0,
            "expected_status": "QUARANTINE_WATERMARK",
        },
        "reconciliation_certified_csv": {
            "path": "reconciliation_certified_audit.csv",
            "rows": 25000,
            "format": "CSV",
            "declared_list": exact_control_list,
            "declared_net": exact_control_net,
            "actual_list": exact_control_list,
            "actual_net": exact_control_net,
            "variance_bp": 0.0,
            "expected_status": "CERTIFIED_AUDIT",
        },
        "formula_injection_csv": {
            "path": "formula_injection_and_reversals.csv",
            "rows": 5000,
            "format": "CSV",
            "has_negative_numbers": True,
            "has_formulas": True,
        },
        "sparse_cohorts_parquet": {
            "path": "sparse_cohorts_backoff.parquet",
            "rows": 15000,
            "format": "PARQUET",
            "sparse_cohorts": ["Quantum Computing", "Legacy Mainframe"],
        },
        "pvmc_two_periods_parquet": {
            "path": "macro_bridge_pvmc_two_periods.parquet",
            "rows": 100000,
            "format": "PARQUET",
            "periods": ["2024-H1", "2025-H1"],
            "uoms": ["USER_LICENSES", "CONSULTING_HOURS"],
        },
        "deal_desk_xlsx": {
            "path": "complex_commercial_deal_desk.xlsx",
            "rows": 2500,
            "format": "XLSX",
            "sheets": ["Granular_Sales_Transactions", "Authority_Matrix"],
        }
    }, f, indent=2)

print(f"[*] Done! All test datasets generated successfully in {OUT_DIR}.")
