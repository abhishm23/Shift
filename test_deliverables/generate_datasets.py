import os
import random
import datetime
import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

OUTPUT_DIR = r"c:\Shift\test_deliverables\datasets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ACCOUNTS = [
    ("ACC-1001", "Acme Global Corp", "PARENT-01"),
    ("ACC-1002", "Zenith Technologies", "PARENT-01"),
    ("ACC-1003", "Apex Health Systems", "PARENT-02"),
    ("ACC-1004", "Vanguard Financial", "PARENT-02"),
    ("ACC-1005", "Quantum Logistics", "PARENT-03"),
    ("ACC-1006", "Starlight Retail Group", "PARENT-03"),
    ("ACC-1007", "Horizon Media Holdings", "PARENT-04"),
    ("ACC-1008", "BluePeak Manufacturing", "PARENT-04"),
    ("ACC-1009", "Crestview Energy Partners", "PARENT-05"),
    ("ACC-1010", "Silverline Telecommunications", "PARENT-05"),
    ("ACC-1011", "Aegis Defense Systems", "PARENT-06"),
    ("ACC-1012", "Beacon Bioscience", "PARENT-06"),
    ("ACC-1013", "Cascade Cloud Solutions", "PARENT-07"),
    ("ACC-1014", "Delta Dynamics", "PARENT-07"),
    ("ACC-1015", "Echo Consumer Goods", "PARENT-08"),
    ("ACC-1016", "Frontier Aerospace", "PARENT-08"),
    ("ACC-1017", "Global Horizon Capital", "PARENT-09"),
    ("ACC-1018", "Highland Insurance Group", "PARENT-09"),
    ("ACC-1019", "Ironclad Securities", "PARENT-10"),
    ("ACC-1020", "Jupiter Analytics", "PARENT-10"),
    ("ACC-1021", "Krypton Robotics", "PARENT-11"),
    ("ACC-1022", "Lumina Software Partners", "PARENT-11"),
    ("ACC-1023", "Matrix Distribution Corp", "PARENT-12"),
    ("ACC-1024", "Novus Pharmaceutical", "PARENT-12"),
    ("ACC-1025", "Omni Global Commerce", "PARENT-13"),
]

REGIONS = ["North America", "EMEA", "APAC", "LATAM"]

def random_date(start_year=2025):
    start_dt = datetime.date(start_year, 1, 1)
    end_dt = datetime.date(start_year, 12, 31)
    delta = (end_dt - start_dt).days
    return start_dt + datetime.timedelta(days=random.randint(0, delta))

# ==============================================================================
# DATASET 1: Single-Category Margin Leakage
# ==============================================================================
def generate_dataset_01():
    print("Generating Dataset 01: Single-Category Leakage...")
    rows = []
    categories = ["Software Licenses", "Enterprise Hardware", "Cloud Services", "Consulting Services"]
    
    for i in range(1, 1201):
        line_id = f"TX1-{i:05d}"
        inv_id = f"INV-2025-{(i // 3) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        reg = random.choice(REGIONS)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        curr = random.choice(["USD", "USD", "USD", "EUR", "GBP"])
        fx = 1.0 if curr == "USD" else (1.08 if curr == "EUR" else 1.28)
        
        if cat == "Cloud Services":
            # The Culprit: severe discount concessions (48% - 68%) and eroded margins
            list_amt = round(random.uniform(25000, 150000), 2)
            disc_pct = round(random.uniform(0.48, 0.68), 4)
            net_inv = round(list_amt * (1.0 - disc_pct), 2)
            cogs_amt = round(list_amt * random.uniform(0.42, 0.52), 2)
            rebate = round(net_inv * random.uniform(0.02, 0.05), 2)
        elif cat == "Software Licenses":
            list_amt = round(random.uniform(10000, 80000), 2)
            disc_pct = round(random.uniform(0.08, 0.16), 4)
            net_inv = round(list_amt * (1.0 - disc_pct), 2)
            cogs_amt = round(list_amt * random.uniform(0.12, 0.18), 2)
            rebate = round(net_inv * random.uniform(0.01, 0.03), 2)
        elif cat == "Enterprise Hardware":
            list_amt = round(random.uniform(20000, 110000), 2)
            disc_pct = round(random.uniform(0.10, 0.18), 4)
            net_inv = round(list_amt * (1.0 - disc_pct), 2)
            cogs_amt = round(list_amt * random.uniform(0.45, 0.52), 2)
            rebate = round(net_inv * random.uniform(0.01, 0.03), 2)
        else: # Consulting Services
            list_amt = round(random.uniform(15000, 75000), 2)
            disc_pct = round(random.uniform(0.07, 0.14), 4)
            net_inv = round(list_amt * (1.0 - disc_pct), 2)
            cogs_amt = round(list_amt * random.uniform(0.40, 0.48), 2)
            rebate = 0.0
            
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": curr,
            "fx_rate_to_reporting": fx,
            "category": cat,
            "sales_region": reg,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "discount_pct": disc_pct,
            "off_invoice_rebate": rebate
        })
        
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "dataset_01_single_category_leakage.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 2: Multi-Category Shared Leakage
# ==============================================================================
def generate_dataset_02():
    print("Generating Dataset 02: Multi-Category Shared Leakage...")
    rows = []
    categories = ["Enterprise Hardware", "Professional Services", "Software SaaS", "Maintenance & Support"]
    
    for i in range(1, 1401):
        line_id = f"TX2-{i:05d}"
        inv_id = f"INV-2025-{(i // 3) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        reg = random.choice(REGIONS)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        curr = random.choice(["USD", "USD", "EUR"])
        fx = 1.0 if curr == "USD" else 1.08
        
        if cat == "Enterprise Hardware":
            list_amt = round(random.uniform(30000, 160000), 2)
            disc_pct = round(random.uniform(0.42, 0.58), 4)
            disc_amt = round(list_amt * disc_pct, 2)
            net_inv = round(list_amt - disc_amt, 2)
            cogs_amt = round(list_amt * random.uniform(0.52, 0.62), 2)
            rebate = round(net_inv * random.uniform(0.02, 0.06), 2)
        elif cat == "Professional Services":
            list_amt = round(random.uniform(20000, 95000), 2)
            disc_pct = round(random.uniform(0.46, 0.64), 4)
            disc_amt = round(list_amt * disc_pct, 2)
            net_inv = round(list_amt - disc_amt, 2)
            cogs_amt = round(list_amt * random.uniform(0.55, 0.65), 2)
            rebate = 0.0
        elif cat == "Software SaaS":
            list_amt = round(random.uniform(15000, 85000), 2)
            disc_pct = round(random.uniform(0.10, 0.18), 4)
            disc_amt = round(list_amt * disc_pct, 2)
            net_inv = round(list_amt - disc_amt, 2)
            cogs_amt = round(list_amt * random.uniform(0.14, 0.20), 2)
            rebate = round(net_inv * random.uniform(0.01, 0.03), 2)
        else: # Maintenance & Support
            list_amt = round(random.uniform(10000, 50000), 2)
            disc_pct = round(random.uniform(0.05, 0.12), 4)
            disc_amt = round(list_amt * disc_pct, 2)
            net_inv = round(list_amt - disc_amt, 2)
            cogs_amt = round(list_amt * random.uniform(0.22, 0.28), 2)
            rebate = round(net_inv * random.uniform(0.01, 0.02), 2)
            
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": curr,
            "fx_rate_to_reporting": fx,
            "product_line": cat,
            "sales_region": reg,
            "extended_list_amt": list_amt,
            "discount_amt": disc_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "dataset_02_multicategory_shared_leakage.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 3: Transaction-Level Outliers (Runaway Rogue Deals)
# ==============================================================================
def generate_dataset_03():
    print("Generating Dataset 03: Transaction-Level Outliers...")
    rows = []
    categories = ["Cloud Infrastructure", "Enterprise Software", "Storage Systems", "Professional Services"]
    
    # 1,080 healthy rows
    for i in range(1, 1081):
        line_id = f"TX3-{i:05d}"
        inv_id = f"INV-2025-{(i // 3) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        reg = random.choice(REGIONS)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(15000, 120000), 2)
        disc_pct = round(random.uniform(0.06, 0.18), 4)
        net_inv = round(list_amt * (1.0 - disc_pct), 2)
        cogs_amt = round(list_amt * random.uniform(0.25, 0.40), 2)
        rebate = round(net_inv * random.uniform(0.01, 0.03), 2)
        
        rows.append({
            "line_id": line_id,
            "invoice_id": inv_id,
            "customer_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "invoice_date": tx_date,
            "currency": "USD",
            "product_category": cat,
            "region": reg,
            "list_price": list_amt,
            "discount_pct": disc_pct,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    # 20 extreme rogue transaction outliers
    for j in range(1, 21):
        line_id = f"OUTLIER-TX-{j:03d}"
        inv_id = f"INV-ROGUE-{j:03d}"
        acc_id, acc_name, parent_id = ACCOUNTS[j % len(ACCOUNTS)]
        cat = random.choice(categories)
        reg = random.choice(REGIONS)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        # Massive deals with 74% - 92% discounts and extreme negative pocket margin
        list_amt = round(random.uniform(350000, 1250000), 2)
        disc_pct = round(random.uniform(0.74, 0.92), 4)
        net_inv = round(list_amt * (1.0 - disc_pct), 2)
        cogs_amt = round(list_amt * random.uniform(0.40, 0.55), 2)
        rebate = round(list_amt * random.uniform(0.05, 0.12), 2)
        
        rows.append({
            "line_id": line_id,
            "invoice_id": inv_id,
            "customer_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "invoice_date": tx_date,
            "currency": "USD",
            "product_category": cat,
            "region": reg,
            "list_price": list_amt,
            "discount_pct": disc_pct,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    df = pd.DataFrame(rows)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    path = os.path.join(OUTPUT_DIR, "dataset_03_transaction_level_outliers.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 4: Zero and Negative Margins & Credit Notes
# ==============================================================================
def generate_dataset_04():
    print("Generating Dataset 04: Zero and Negative Margins...")
    rows = []
    categories = ["Hardware Components", "Software Subscriptions", "Managed Services", "Replacement Parts"]
    
    # 1. Normal positive transactions (450 rows)
    for i in range(1, 451):
        line_id = f"TX4-POS-{i:04d}"
        inv_id = f"INV-2025-{(i // 2) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(10000, 60000), 2)
        disc = round(random.uniform(0.08, 0.15), 4)
        net_inv = round(list_amt * (1.0 - disc), 2)
        cogs_amt = round(list_amt * random.uniform(0.35, 0.45), 2)
        rebate = round(net_inv * 0.02, 2)
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    # 2. Credit Notes / Return Reversals (150 rows)
    for i in range(1, 151):
        line_id = f"TX4-CRN-{i:04d}"
        inv_id = f"CRN-2025-{i:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = -round(random.uniform(5000, 35000), 2)
        net_inv = round(list_amt * random.uniform(0.85, 0.95), 2)
        cogs_amt = round(list_amt * random.uniform(0.35, 0.45), 2)
        rebate = 0.0
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    # 3. Zero Margin / Break-Even Transactions (100 rows)
    for i in range(1, 101):
        line_id = f"TX4-ZERO-{i:04d}"
        inv_id = f"INV-BE-{i:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(8000, 45000), 2)
        cost_val = round(list_amt * 0.65, 2)
        net_inv = cost_val
        cogs_amt = cost_val
        rebate = 0.0
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    # 4. Cost Exceeding Price / Sub-Zero Margin (100 rows)
    for i in range(1, 101):
        line_id = f"TX4-SUBZERO-{i:04d}"
        inv_id = f"INV-LOSS-{i:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(12000, 75000), 2)
        net_inv = round(list_amt * random.uniform(0.35, 0.50), 2)
        cogs_amt = round(list_amt * random.uniform(0.60, 0.80), 2)
        rebate = round(net_inv * 0.03, 2)
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    # 5. Free Replacement / Zero Invoiced with positive COGS (50 rows)
    for i in range(1, 51):
        line_id = f"TX4-WARR-{i:04d}"
        inv_id = f"WARR-2025-{i:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = "Replacement Parts"
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(2000, 15000), 2)
        net_inv = 0.00
        cogs_amt = round(list_amt * 0.45, 2)
        rebate = 0.0
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    # 6. Accounting Adjustment (50 rows): Zero List with Net Invoiced
    for i in range(1, 51):
        line_id = f"TX4-ADJ-{i:04d}"
        inv_id = f"ADJ-2025-{i:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = "Software Subscriptions"
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = 0.00
        net_inv = round(random.uniform(-5000, 5000), 2)
        cogs_amt = 0.00
        rebate = 0.0
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate
        })
        
    df = pd.DataFrame(rows)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    path = os.path.join(OUTPUT_DIR, "dataset_04_zero_and_negative_margins.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 5: Missing and Null Columns
# ==============================================================================
def generate_dataset_05():
    print("Generating Dataset 05: Missing and Null Columns...")
    rows = []
    categories = ["SaaS Cloud", "Enterprise On-Prem", "Technical Services", "Hardware Appliances"]
    
    # Note: Source schema intentionally omits 'currency' and 'parent_account_id' columns completely
    for i in range(1, 801):
        acc_id, acc_name, _ = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        
        # 5% missing line_id
        line_id = f"TX5-{i:05d}" if random.random() > 0.05 else ""
        inv_id = f"INV-2025-{(i // 2) + 1:04d}"
        
        # 8% missing date
        tx_date = random_date(2025).strftime("%Y-%m-%d") if random.random() > 0.08 else ""
        
        list_amt = round(random.uniform(10000, 80000), 2)
        disc_pct = round(random.uniform(0.08, 0.20), 4)
        net_inv = round(list_amt * (1.0 - disc_pct), 2)
        
        # 12% missing cogs_amt
        cogs_amt = round(list_amt * random.uniform(0.30, 0.45), 2) if random.random() > 0.12 else ""
        
        # 30% missing off_invoice_rebate
        rebate = round(net_inv * 0.02, 2) if random.random() > 0.30 else ""
        
        # 5% missing account_id
        if random.random() < 0.05:
            acc_id = ""
            
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "transaction_date": tx_date,
            "category": cat,
            "extended_list_amt": list_amt,
            "net_invoiced_amt": net_inv
        })
        
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "dataset_05_missing_null_columns.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 6: Malformed Data Types and Non-Standard Dates
# ==============================================================================
def generate_dataset_06():
    print("Generating Dataset 06: Malformed Types and Dates...")
    rows = []
    categories = ["Unified Communications", "Cloud Compute", "Data Warehouse", "Security Suite"]
    
    date_formats = ["iso", "eu", "dotted", "textual", "epoch", "invalid"]
    
    for i in range(1, 851):
        line_id = f"TX6-{i:05d}"
        inv_id = f"INV-2025-{(i // 3) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        dt = random_date(2025)
        
        # Format date according to varied formats
        fmt_choice = random.choices(date_formats, weights=[40, 20, 15, 10, 10, 5])[0]
        if fmt_choice == "iso":
            tx_date = dt.strftime("%Y-%m-%d")
        elif fmt_choice == "eu":
            tx_date = dt.strftime("%d/%m/%Y")
        elif fmt_choice == "dotted":
            tx_date = dt.strftime("%Y.%m.%d")
        elif fmt_choice == "textual":
            tx_date = dt.strftime("%b %d, %Y")
        elif fmt_choice == "epoch":
            tx_date = str(int(datetime.datetime(dt.year, dt.month, dt.day).timestamp()))
        else:
            tx_date = random.choice(["2025-02-31", "2025-13-45", "INVALID_DATE", "0000-00-00"])
            
        base_list = round(random.uniform(5000, 75000), 2)
        base_net = round(base_list * random.uniform(0.75, 0.90), 2)
        base_cogs = round(base_list * random.uniform(0.30, 0.45), 2)
        base_disc = round(base_list - base_net, 2)
        
        # Contaminate numeric fields with text/symbols in ~15% of rows
        noise_type = random.random()
        if noise_type < 0.05:
            list_val = f"${base_list:,.2f}"
            net_val = f"${base_net:,.2f}"
            cogs_val = f"${base_cogs:,.2f}"
            disc_val = f"${base_disc:,.2f}"
        elif noise_type < 0.09:
            list_val = base_list
            net_val = "FREE" if random.random() < 0.5 else "N/A"
            cogs_val = base_cogs
            disc_val = "#VALUE!"
        elif noise_type < 0.12:
            list_val = "UNKNOWN"
            net_val = base_net
            cogs_val = "null"
            disc_val = "--"
        else:
            list_val = base_list
            net_val = base_net
            cogs_val = base_cogs
            disc_val = base_disc
            
        rows.append({
            "line_id": line_id,
            "invoice_id": inv_id,
            "customer_id": acc_id,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "product_line": cat,
            "extended_list_amt": list_val,
            "net_invoiced_amt": net_val,
            "cogs_amt": cogs_val,
            "discount_amt": disc_val
        })
        
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "dataset_06_malformed_types_dates.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 7: Extreme Scale Outliers (Multi-Billion to Micro-Cent)
# ==============================================================================
def generate_dataset_07():
    print("Generating Dataset 07: Extreme Scale Outliers...")
    rows = []
    normal_categories = ["Standard Commercial Software", "Enterprise Storage Systems", "IT Support Services", "Corporate Networking"]
    
    # 1. Normal scale baseline (750 rows)
    for i in range(1, 751):
        line_id = f"TX7-NORM-{i:05d}"
        inv_id = f"INV-2025-{(i // 3) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(normal_categories)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(50000, 250000), 2)
        disc_pct = round(random.uniform(0.10, 0.20), 4)
        net_inv = round(list_amt * (1.0 - disc_pct), 2)
        cogs_amt = round(list_amt * random.uniform(0.35, 0.45), 2)
        rebate = round(net_inv * 0.02, 2)
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "extended_list_amt": str(list_amt),
            "net_invoiced_amt": str(net_inv),
            "cogs_amt": str(cogs_amt),
            "off_invoice_rebate": str(rebate)
        })
        
    # 2. Multi-Billion Dollar Mega-Transactions (50 rows)
    for i in range(1, 51):
        line_id = f"TX7-MEGA-{i:03d}"
        inv_id = f"INV-MEGA-2025-{i:03d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = "Sovereign Infrastructure"
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(1.5e9, 9.5e9), 2)
        disc_pct = round(random.uniform(0.12, 0.25), 4)
        net_inv = round(list_amt * (1.0 - disc_pct), 2)
        cogs_amt = round(list_amt * random.uniform(0.40, 0.55), 2)
        rebate = round(net_inv * 0.03, 2)
        
        if i <= 10:
            rows.append({
                "transaction_line_id": line_id,
                "invoice_id": inv_id,
                "account_id": acc_id,
                "customer_name": acc_name,
                "parent_account_id": parent_id,
                "transaction_date": tx_date,
                "currency": "USD",
                "category": cat,
                "extended_list_amt": f"{list_amt:.4e}",
                "net_invoiced_amt": f"{net_inv:.4e}",
                "cogs_amt": f"{cogs_amt:.4e}",
                "off_invoice_rebate": f"{rebate:.4e}"
            })
        else:
            rows.append({
                "transaction_line_id": line_id,
                "invoice_id": inv_id,
                "account_id": acc_id,
                "customer_name": acc_name,
                "parent_account_id": parent_id,
                "transaction_date": tx_date,
                "currency": "USD",
                "category": cat,
                "extended_list_amt": f"{list_amt:.2f}",
                "net_invoiced_amt": f"{net_inv:.2f}",
                "cogs_amt": f"{cogs_amt:.2f}",
                "off_invoice_rebate": f"{rebate:.2f}"
            })
            
    # 3. Micro-Cent High-Frequency Transactions (150 rows)
    for i in range(1, 151):
        line_id = f"TX7-MICRO-{i:04d}"
        inv_id = f"INV-MICRO-{i:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = "Micro-API Telemetry"
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        list_amt = round(random.uniform(0.00001, 0.00095), 6)
        net_inv = round(list_amt * 0.85, 6)
        cogs_amt = round(list_amt * 0.40, 6)
        rebate = round(net_inv * 0.01, 6)
        
        if i <= 10:
            rows.append({
                "transaction_line_id": line_id,
                "invoice_id": inv_id,
                "account_id": acc_id,
                "customer_name": acc_name,
                "parent_account_id": parent_id,
                "transaction_date": tx_date,
                "currency": "USD",
                "category": cat,
                "extended_list_amt": f"{list_amt:.3e}",
                "net_invoiced_amt": f"{net_inv:.3e}",
                "cogs_amt": f"{cogs_amt:.3e}",
                "off_invoice_rebate": f"{rebate:.3e}"
            })
        else:
            rows.append({
                "transaction_line_id": line_id,
                "invoice_id": inv_id,
                "account_id": acc_id,
                "customer_name": acc_name,
                "parent_account_id": parent_id,
                "transaction_date": tx_date,
                "currency": "USD",
                "category": cat,
                "extended_list_amt": f"{list_amt:.6f}",
                "net_invoiced_amt": f"{net_inv:.6f}",
                "cogs_amt": f"{cogs_amt:.6f}",
                "off_invoice_rebate": f"{rebate:.6f}"
            })
            
    df = pd.DataFrame(rows)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    path = os.path.join(OUTPUT_DIR, "dataset_07_extreme_scale_outliers.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

# ==============================================================================
# DATASET 8: Discount Stacking & Complex Booking Leakage
# ==============================================================================
def generate_dataset_08():
    print("Generating Dataset 08: Discount Stacking & Booking Leakage...")
    rows = []
    categories = ["Platform Enterprise SaaS", "Hardware Appliances", "Consulting Engagements", "Managed Security"]
    
    for i in range(1, 1501):
        line_id = f"TX8-{i:05d}"
        inv_id = f"INV-2025-{(i // 3) + 1:04d}"
        acc_id, acc_name, parent_id = random.choice(ACCOUNTS)
        cat = random.choice(categories)
        reg = random.choice(REGIONS)
        tx_date = random_date(2025).strftime("%Y-%m-%d")
        
        gross_booking = round(random.uniform(40000, 200000), 2)
        
        # 30% of rows suffer compound discount stacking
        if random.random() < 0.30:
            # Discount stacking trap:
            # Tier 1: High base discount 22% - 32%
            base_disc_pct = round(random.uniform(0.22, 0.32), 4)
            after_base = gross_booking * (1.0 - base_disc_pct)
            # Tier 2: End-of-quarter promo concession dollar amount: $8,000 - $25,000
            promo_amt = round(random.uniform(8000, 25000), 2)
            booking_amt = max(1000.0, round(after_base - promo_amt, 2))
            # Tier 3: Invoiced adjustment / deal desk concession
            net_inv = round(booking_amt * random.uniform(0.92, 0.98), 2)
            # COGS standard: 38% - 48% of gross booking
            cogs_amt = round(gross_booking * random.uniform(0.38, 0.48), 2)
            # Tier 4: Back-end off-invoice rebate: 8% - 14% of net invoiced
            rebate = round(net_inv * random.uniform(0.08, 0.14), 2)
        else:
            # Disciplined commercial deal
            base_disc_pct = round(random.uniform(0.08, 0.16), 4)
            promo_amt = 0.00
            booking_amt = round(gross_booking * (1.0 - base_disc_pct), 2)
            net_inv = booking_amt
            cogs_amt = round(gross_booking * random.uniform(0.25, 0.35), 2)
            rebate = round(net_inv * 0.02, 2)
            
        standard_margin = round(gross_booking - cogs_amt, 2)
        pocket_margin = round(net_inv - cogs_amt - rebate, 2)
        
        rows.append({
            "transaction_line_id": line_id,
            "invoice_id": inv_id,
            "account_id": acc_id,
            "customer_name": acc_name,
            "parent_account_id": parent_id,
            "transaction_date": tx_date,
            "currency": "USD",
            "category": cat,
            "sales_region": reg,
            "gross_booking_val": gross_booking,
            "base_discount_pct": base_disc_pct,
            "promo_discount_amt": promo_amt,
            "booking_amt": booking_amt,
            "net_invoiced_amt": net_inv,
            "cogs_amt": cogs_amt,
            "off_invoice_rebate": rebate,
            "standard_margin_amt": standard_margin,
            "pocket_margin_amt": pocket_margin
        })
        
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "dataset_08_discount_stacking_complex.csv")
    df.to_csv(path, index=False)
    print(f"Saved {path}: {len(df)} rows")

if __name__ == "__main__":
    print("Starting synthetic dataset generation...")
    generate_dataset_01()
    generate_dataset_02()
    generate_dataset_03()
    generate_dataset_04()
    generate_dataset_05()
    generate_dataset_06()
    generate_dataset_07()
    generate_dataset_08()
    print("All 8 datasets generated successfully!")
