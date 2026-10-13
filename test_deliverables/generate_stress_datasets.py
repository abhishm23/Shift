# c:/Shift/test_deliverables/generate_stress_datasets.py
"""
generate_stress_datasets.py
Massive High-Dimensional Synthetic Stress Dataset Generator for Project Sift.

Produces:
1. c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv (1,000,000 rows, 87 columns, standard CSV)
2. c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet (15,000,000 rows, 87 columns, snappy Parquet)

Schema Specifications:
- 7 Line-Grain Canonical / Identifier columns
- 18 Numerical Metric columns
- 62 Categorical Dimension columns across rich business taxonomies
Total = 87 columns (>= 75 columns required, >= 60 categorical, >= 15 numerical)

Deeply Buried Culprits:
- Culprit Alpha (4-level): sales_theater == "EMEA" & partner_program_tier == "Gold" & contract_commitment_type == "MultiYear" & prod_family == "EnterpriseCloud"
- Culprit Beta (5-level): sales_theater == "Americas" & cust_industry_vertical == "Financial Services" & channel_type == "System Integrator" & deal_discount_governance_tier == "Tier 4 Exception Policy" & prod_line_of_business == "Software Solutions"
- Culprit Gamma (3-level): sales_theater == "APAC" & prod_deployment_mode == "Sovereign Air-Gap" & contract_sla_tier == "Ultra Five-Nines"
"""

import os
import sys
import time
import math
import hashlib
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import duckdb

OUTPUT_DIR = Path(r"c:/Shift/test_deliverables/datasets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILE = OUTPUT_DIR / "dataset_stress_1m_wide.csv"
PARQUET_FILE = OUTPUT_DIR / "dataset_stress_15m_wide.parquet"
MANIFEST_FILE = OUTPUT_DIR / "DATASET_MANIFEST.md"

CATEGORICAL_TAXONOMY = {
    # Sales hierarchy (12 columns)
    "sales_theater": ["Americas", "EMEA", "APAC", "Japan"],
    "sales_region": [
        "North America", "Southern Europe", "DACH", "UK_Ireland", 
        "Nordics", "Greater China", "ANZ", "ASEAN", "Japan Core"
    ],
    "sales_area": ["East", "West", "Central", "North", "South"],
    "sales_territory": [f"TERR-{i:02d}" for i in range(1, 21)],
    "sales_district": [f"DIST-{i:02d}" for i in range(1, 11)],
    "sales_rep_tier": ["Associate", "Senior", "Principal", "Strategic Director"],
    "channel_type": ["Direct Enterprise", "Value Added Reseller", "System Integrator", "Digital Marketplace", "OEM Partner"],
    "partner_program_tier": ["Registered", "Silver", "Gold", "Platinum", "Global Elite"],
    "distributor_tier": ["Tier 1 Global", "Tier 2 Regional", "Boutique Specialist", "Direct Fulfilled"],
    "sales_motion": ["New Logo", "Expansion", "Contract Renewal", "Cross-Sell", "Hardware Refresh"],
    "quota_class": ["Core Field Sales", "Specialist Overlay", "Global Accounts", "Commercial General"],
    "deal_desk_lead": ["Lead Alpha", "Lead Beta", "Lead Gamma", "Lead Delta", "Lead Epsilon"],

    # Product taxonomy (13 columns)
    "prod_line_of_business": ["Infrastructure Systems", "Software Solutions", "Cloud Platforms", "Security Engineering"],
    "prod_family": ["EnterpriseCloud", "StorageCore", "CyberSecurity", "NetworkingMesh", "ComputeMatrix"],
    "prod_category": ["PaaS Infrastructure", "Block & File Storage", "Endpoint Protection", "Core Routing", "GPU Compute Cluster"],
    "prod_subcategory": ["High-Throughput IOPS", "Cold Archive", "Zero-Trust EDR", "SDN Optical", "Distributed Fabric"],
    "prod_edition": ["Standard", "Professional", "Enterprise", "Ultimate Mission-Critical"],
    "prod_lifecycle_status": ["General Availability", "Active Growth", "Mature Maintenance", "End-of-Sale Announced"],
    "prod_licensing_model": ["Annual Subscription", "Multi-Year Term", "Consumption Metered", "Perpetual Enterprise"],
    "prod_deployment_mode": ["Multi-Tenant Cloud", "Single-Tenant Cloud", "Hybrid On-Prem", "Sovereign Air-Gap"],
    "prod_hardware_form_factor": ["Rackmount 1U", "Blade Enclosure", "Virtual Appliance", "Software Only SaaS"],
    "prod_support_tier": ["Bronze 8x5", "Silver 12x5", "Gold 24x7", "Mission Critical Premier"],
    "prod_release_train": ["LTS-2024", "LTS-2025", "Rolling-Current", "Edge-Preview"],
    "prod_billing_metric": ["Per Core", "Per Seat", "Per Terabyte", "Flat Instance"],
    "prod_warranty_code": ["Standard 1Yr", "Extended 3Yr", "Premium 5Yr", "Component Lifetime"],

    # Customer classification (15 columns)
    "cust_industry_vertical": [
        "Financial Services", "Healthcare & Life Sciences", "Manufacturing & Robotics", 
        "Public Sector & Defense", "Retail & Consumer", "Technology & Media"
    ],
    "cust_sub_industry": [
        "Investment Banking", "Health Systems", "Industrial Automation", 
        "Federal Defense", "Global E-Commerce", "Enterprise SaaS"
    ],
    "cust_enterprise_segment": ["Small Medium Business", "Commercial Mid-Market", "Enterprise Large", "Fortune 100 Global"],
    "cust_tier": ["Tier A Key Strategic", "Tier B Core Growth", "Tier C Established", "Tier D Standard"],
    "cust_credit_rating": ["AAA Prime", "AA High Grade", "A Upper Medium", "BBB Lower Medium", "BB Speculative"],
    "cust_procurement_type": ["Centralized Corporate", "Division Autonomous", "Government Schedule", "Third-Party BPO"],
    "cust_hq_country": [
        "United States", "United Kingdom", "Germany", "France", "Japan", 
        "Singapore", "Australia", "Canada", "Switzerland", "Netherlands"
    ],
    "cust_operating_geo": ["Single Country Domestic", "Pan-Regional Continental", "Transatlantic", "Global Multinational"],
    "cust_relationship_tenure": ["New Under 1Yr", "Established 1-3Yrs", "Mature 4-7Yrs", "Strategic 8+Yrs"],
    "cust_tax_exempt_status": ["Standard Taxable", "Exempt Non-Profit", "Exempt Government", "Resale Certificate"],
    "cust_duns_rating": ["5A1 Superior", "4A1 High", "3A2 Good", "2A2 Moderate", "1A3 Fair"],
    "cust_payment_behavior_score": ["Prompt Within Terms", "Standard 30D", "Minor Delinquent", "Supervised Terms"],
    "cust_risk_tier": ["Low Risk", "Medium Risk", "High Risk", "Watchlist Supervised"],
    "cust_buying_persona": [
        "Chief Financial Officer", "Chief Information Officer", "Chief Information Security Officer", 
        "VP Global Procurement", "VP Infrastructure"
    ],
    "cust_preferred_language": ["English", "German", "French", "Japanese", "Spanish"],

    # Contract & Deal stipulations (16 columns)
    "contract_commitment_type": ["Annual Commit", "MultiYear", "Month-to-Month", "Flexible Consumption"],
    "contract_billing_frequency": ["Upfront In Advance", "Annual Installments", "Quarterly In Advance", "Monthly In Arrears"],
    "contract_auto_renewal": ["Evergreen Auto-Renew", "Written Notice 60D", "Fixed Term Expiration", "Annual Extension Option"],
    "contract_sla_tier": ["Standard 99.5%", "Enhanced 99.9%", "Mission Critical 99.99%", "Ultra Five-Nines"],
    "deal_pricing_approval_level": ["Field Rep Discretion", "Regional Manager", "VP Deal Desk", "CFO Exception Board"],
    "deal_discount_governance_tier": ["Tier 1 Standard Matrix", "Tier 2 Commercial Escalation", "Tier 3 Executive Approval", "Tier 4 Exception Policy"],
    "deal_strategic_flag": ["Standard Commercial", "Strategic Flagship", "Greenfield Displacement", "Defensive Protection"],
    "deal_origination_source": ["Inbound Digital", "Direct Account Exec", "Reseller Partner", "RFP Competitive Bid"],
    "deal_currency_hedging_flag": ["Unhedged Spot", "Fully Hedged Treasury", "Correlated Basket", "Local Currency Pegged"],
    "deal_incoterms": ["DDP Destination Delivered", "FOB Shipping Point", "EXW Ex Works", "CIP Carriage Paid", "Digital Delivery"],
    "order_fulfillment_center": ["FC-US-East", "FC-US-West", "FC-EU-Central", "FC-APAC-East"],
    "shipping_priority_tier": ["Standard Ground", "Second Day Air", "Priority Next Flight", "Digital Electronic Provision"],
    "payment_method_type": ["Corporate Wire Transfer", "ACH Electronic", "Corporate Credit Card", "Commercial Trade Credit"],
    "invoice_settlement_term": ["Net 30 Days", "Net 45 Days", "Net 60 Days", "2/10 Net 30", "Net 90 Extended"],
    "deal_contract_type": ["Master Services Agreement", "Statement of Work", "Enterprise Agreement Rider", "Volume Purchase Order"],
    "audit_right_stipulation": ["Full Annual Audit", "Third Party Audit On Notice", "Records Inspection Only", "No Direct Audit"],

    # Operations & System metadata (6 columns)
    "order_entry_channel": ["EDI B2B Gateway", "CRM Opportunity Sync", "ERP Order Portal", "Manual Sales Order"],
    "order_validation_status": ["System Clean Auto-Passed", "Deal Desk Certified", "Compliance Cleared", "Manual Exception Allowed"],
    "fulfillment_status": ["Shipped Complete", "Partial Backordered", "Digitally Activated", "Staged For Deployment"],
    "billing_system_id": ["SAP-Billing-01", "Oracle-BRM-02", "Zuora-Core-03", "Workday-Financials-01"],
    "fiscal_quarter": ["FY25-Q1", "FY25-Q2", "FY25-Q3", "FY25-Q4"],
    "price_book_version": ["PB-2025-Standard-v1", "PB-2025-Enterprise-v2", "PB-2025-Volume-v1", "PB-2025-Special-v3"],
}

CATEGORICAL_PA_ARRAYS = {
    col: pa.array(vals, type=pa.string())
    for col, vals in CATEGORICAL_TAXONOMY.items()
}

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]
CURRENCY_FX = [1.0, 1.08, 1.28, 0.0068, 0.74, 0.65]
CURRENCY_PA = pa.array(CURRENCIES, type=pa.string())

NUM_ACCOUNTS = 1000
ACCOUNTS_LIST = [f"ACC-{i:04d}" for i in range(1, NUM_ACCOUNTS + 1)]
PARENTS_LIST = [f"PARENT-{(i - 1) % 100 + 1:03d}" for i in range(1, NUM_ACCOUNTS + 1)]
CUSTOMERS_LIST = [f"Enterprise Client {i:04d} Inc." for i in range(1, NUM_ACCOUNTS + 1)]

PA_ACCOUNTS = pa.array(ACCOUNTS_LIST, type=pa.string())
PA_PARENTS = pa.array(PARENTS_LIST, type=pa.string())
PA_CUSTOMERS = pa.array(CUSTOMERS_LIST, type=pa.string())

BASE_DATE = datetime.date(2025, 1, 1)
DATES_LIST = [(BASE_DATE + datetime.timedelta(days=d)).isoformat() for d in range(365)]
PA_DATES = pa.array(DATES_LIST, type=pa.string())

# Culprit Alpha (4-level): EMEA + Gold + MultiYear + EnterpriseCloud
IDX_THEATER_EMEA = CATEGORICAL_TAXONOMY["sales_theater"].index("EMEA")
IDX_PARTNER_GOLD = CATEGORICAL_TAXONOMY["partner_program_tier"].index("Gold")
IDX_CONTRACT_MULTIYEAR = CATEGORICAL_TAXONOMY["contract_commitment_type"].index("MultiYear")
IDX_PROD_ENTCLOUD = CATEGORICAL_TAXONOMY["prod_family"].index("EnterpriseCloud")

# Culprit Beta (5-level): Americas + Financial Services + System Integrator + Tier 4 Exception Policy + Software Solutions
IDX_THEATER_AMERICAS = CATEGORICAL_TAXONOMY["sales_theater"].index("Americas")
IDX_IND_FINANCIAL = CATEGORICAL_TAXONOMY["cust_industry_vertical"].index("Financial Services")
IDX_CHANNEL_SI = CATEGORICAL_TAXONOMY["channel_type"].index("System Integrator")
IDX_GOV_TIER4 = CATEGORICAL_TAXONOMY["deal_discount_governance_tier"].index("Tier 4 Exception Policy")
IDX_LOB_SW = CATEGORICAL_TAXONOMY["prod_line_of_business"].index("Software Solutions")

# Culprit Gamma (3-level): APAC + Sovereign Air-Gap + Ultra Five-Nines
IDX_THEATER_APAC = CATEGORICAL_TAXONOMY["sales_theater"].index("APAC")
IDX_DEPLOY_AIRGAP = CATEGORICAL_TAXONOMY["prod_deployment_mode"].index("Sovereign Air-Gap")
IDX_SLA_FIVENINES = CATEGORICAL_TAXONOMY["contract_sla_tier"].index("Ultra Five-Nines")

BASELINE_P75_DISCOUNT = 0.1500  # Parametric P75 of background [0.06, 0.18] distribution


class CulpritStatsAccumulator:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.count = 0
        self.sum_list_amt = 0.0
        self.sum_net_amt = 0.0
        self.sum_discount_rate = 0.0
        self.sum_defensible_gap = 0.0
        self.sum_actionable_opp = 0.0

    def update(self, list_amts: np.ndarray, net_amts: np.ndarray, disc_rates: np.ndarray, defensible_gaps: np.ndarray):
        n = len(list_amts)
        if n == 0:
            return
        self.count += n
        self.sum_list_amt += float(np.sum(list_amts))
        self.sum_net_amt += float(np.sum(net_amts))
        self.sum_discount_rate += float(np.sum(disc_rates))
        self.sum_defensible_gap += float(np.sum(defensible_gaps))
        self.sum_actionable_opp += float(np.sum(defensible_gaps * 0.40))

    @property
    def mean_list_price(self) -> float:
        return self.sum_list_amt / self.count if self.count > 0 else 0.0

    @property
    def mean_discount_pct(self) -> float:
        return (self.sum_discount_rate / self.count * 100.0) if self.count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "slice_row_count": self.count,
            "mean_list_price": round(self.mean_list_price, 2),
            "mean_discount_pct": round(self.mean_discount_pct, 2),
            "baseline_cohort_p75_pct": round(BASELINE_P75_DISCOUNT * 100.0, 2),
            "defensible_gap_sum": round(self.sum_defensible_gap, 2),
            "actionable_opp_sum": round(self.sum_actionable_opp, 2),
        }


def build_pyarrow_schema() -> pa.Schema:
    fields = [
        # 1-7: Canonical Line-grain identifiers & metadata
        pa.field("transaction_line_id", pa.string()),
        pa.field("invoice_id", pa.string()),
        pa.field("account_id", pa.dictionary(pa.int32(), pa.string())),
        pa.field("customer_name", pa.dictionary(pa.int32(), pa.string())),
        pa.field("parent_account_id", pa.dictionary(pa.int32(), pa.string())),
        pa.field("transaction_date", pa.dictionary(pa.int32(), pa.string())),
        pa.field("currency", pa.dictionary(pa.int32(), pa.string())),
        
        # 8-25: Numerical metric columns (18 columns)
        pa.field("extended_list_amt", pa.float64()),
        pa.field("net_invoiced_amt", pa.float64()),
        pa.field("cogs_amt", pa.float64()),
        pa.field("off_invoice_rebate", pa.float64()),
        pa.field("fx_rate_to_reporting", pa.float64()),
        pa.field("list_unit_price", pa.float64()),
        pa.field("order_quantity", pa.float64()),
        pa.field("base_discount_amt", pa.float64()),
        pa.field("promo_discount_amt", pa.float64()),
        pa.field("freight_shipping_amt", pa.float64()),
        pa.field("tax_vat_amt", pa.float64()),
        pa.field("standard_margin_amt", pa.float64()),
        pa.field("pocket_margin_amt", pa.float64()),
        pa.field("gross_booking_val", pa.float64()),
        pa.field("net_booking_val", pa.float64()),
        pa.field("rebate_accrual_pct", pa.float64()),
        pa.field("payment_terms_penalty", pa.float64()),
        pa.field("credit_adjustment_amt", pa.float64()),
    ]
    
    # 26-87: Categorical dimension columns (62 columns)
    for col in CATEGORICAL_TAXONOMY.keys():
        fields.append(pa.field(col, pa.dictionary(pa.int32(), pa.string())))

    return pa.schema(fields)

def generate_batch_table(
    start_row_idx: int,
    batch_size: int,
    rng: np.random.Generator,
    id_prefix: str,
    acc_alpha: CulpritStatsAccumulator,
    acc_beta: CulpritStatsAccumulator,
    acc_gamma: CulpritStatsAccumulator,
) -> pa.Table:
    end_row_idx = start_row_idx + batch_size
    
    # 1. Line grain IDs and Invoice IDs
    line_ids = [f"{id_prefix}-{i:08d}" for i in range(start_row_idx, end_row_idx)]
    inv_ids = [f"INV-{id_prefix}-{(i // 4) + 1:07d}" for i in range(start_row_idx, end_row_idx)]
    
    pa_line_ids = pa.array(line_ids, type=pa.string())
    pa_inv_ids = pa.array(inv_ids, type=pa.string())
    
    # 2. Account, Parent, Customer mapping (1000 accounts)
    acct_idx = rng.integers(0, NUM_ACCOUNTS, size=batch_size, dtype=np.int32)
    pa_acct = pa.DictionaryArray.from_arrays(acct_idx, PA_ACCOUNTS)
    pa_parent = pa.DictionaryArray.from_arrays(acct_idx, PA_PARENTS)
    pa_cust = pa.DictionaryArray.from_arrays(acct_idx, PA_CUSTOMERS)
    
    # 3. Transaction Dates (365 days)
    date_idx = rng.integers(0, 365, size=batch_size, dtype=np.int32)
    pa_dates = pa.DictionaryArray.from_arrays(date_idx, PA_DATES)
    
    # 4. Currency and FX
    curr_idx = rng.choice(len(CURRENCIES), size=batch_size, p=[0.55, 0.20, 0.12, 0.05, 0.04, 0.04]).astype(np.int32)
    pa_curr = pa.DictionaryArray.from_arrays(curr_idx, CURRENCY_PA)
    fx_rates = np.array(CURRENCY_FX, dtype=np.float64)[curr_idx]
    
    # 5. Categorical Dimensions (62 columns)
    cat_indices = {}
    pa_cat_arrays = {}
    for col, vals in CATEGORICAL_TAXONOMY.items():
        n_vals = len(vals)
        idx = rng.integers(0, n_vals, size=batch_size, dtype=np.int32)
        cat_indices[col] = idx
        pa_cat_arrays[col] = pa.DictionaryArray.from_arrays(idx, CATEGORICAL_PA_ARRAYS[col])

    # 6. Deeply Buried Multi-Attribute Culprit Masks
    mask_alpha = (
        (cat_indices["sales_theater"] == IDX_THEATER_EMEA) &
        (cat_indices["partner_program_tier"] == IDX_PARTNER_GOLD) &
        (cat_indices["contract_commitment_type"] == IDX_CONTRACT_MULTIYEAR) &
        (cat_indices["prod_family"] == IDX_PROD_ENTCLOUD)
    )

    mask_beta = (
        (cat_indices["sales_theater"] == IDX_THEATER_AMERICAS) &
        (cat_indices["cust_industry_vertical"] == IDX_IND_FINANCIAL) &
        (cat_indices["channel_type"] == IDX_CHANNEL_SI) &
        (cat_indices["deal_discount_governance_tier"] == IDX_GOV_TIER4) &
        (cat_indices["prod_line_of_business"] == IDX_LOB_SW)
    )

    mask_gamma = (
        (cat_indices["sales_theater"] == IDX_THEATER_APAC) &
        (cat_indices["prod_deployment_mode"] == IDX_DEPLOY_AIRGAP) &
        (cat_indices["contract_sla_tier"] == IDX_SLA_FIVENINES)
    )

    # 7. Discount Rates
    disc_rates = rng.uniform(0.06, 0.18, size=batch_size)

    n_alpha = np.sum(mask_alpha)
    if n_alpha > 0:
        disc_rates[mask_alpha] = rng.uniform(0.55, 0.70, size=n_alpha)

    n_beta = np.sum(mask_beta)
    if n_beta > 0:
        disc_rates[mask_beta] = rng.uniform(0.58, 0.72, size=n_beta)

    n_gamma = np.sum(mask_gamma)
    if n_gamma > 0:
        disc_rates[mask_gamma] = rng.uniform(0.52, 0.66, size=n_gamma)

    # 8. Numerical Financial Concessions & Metrics
    list_unit_price = np.round(rng.uniform(25.0, 2500.0, size=batch_size), 2)
    order_quantity = rng.integers(1, 50, size=batch_size, dtype=np.int32).astype(np.float64)
    extended_list_amt = np.round(list_unit_price * order_quantity, 2)

    base_disc_rate = np.minimum(disc_rates, 0.12)
    base_discount_amt = np.round(extended_list_amt * base_disc_rate, 2)
    total_disc_amt = np.round(extended_list_amt * disc_rates, 2)
    promo_discount_amt = np.maximum(0.0, total_disc_amt - base_discount_amt)
    net_invoiced_amt = np.maximum(0.0, extended_list_amt - total_disc_amt)

    realized_disc_rates = np.where(extended_list_amt > 0, (extended_list_amt - net_invoiced_amt) / extended_list_amt, 0.0)

    cogs_ratio = rng.uniform(0.42, 0.52, size=batch_size)
    cogs_amt = np.round(extended_list_amt * cogs_ratio, 2)

    rebate_ratio = rng.uniform(0.015, 0.035, size=batch_size)
    off_invoice_rebate = np.round(net_invoiced_amt * rebate_ratio, 2)

    freight_shipping_amt = np.round(rng.uniform(15.0, 150.0, size=batch_size), 2)
    tax_vat_amt = np.round(net_invoiced_amt * rng.uniform(0.05, 0.10, size=batch_size), 2)

    standard_margin_amt = np.round(net_invoiced_amt - cogs_amt, 2)
    pocket_margin_amt = np.round(net_invoiced_amt - cogs_amt - off_invoice_rebate - freight_shipping_amt, 2)
    gross_booking_val = extended_list_amt
    net_booking_val = net_invoiced_amt
    rebate_accrual_pct = np.round(np.where(net_invoiced_amt > 0, off_invoice_rebate / net_invoiced_amt, 0.0), 4)

    payment_terms_penalty = np.round(net_invoiced_amt * rng.choice([0.0, 0.005, 0.01, 0.02], size=batch_size, p=[0.70, 0.15, 0.10, 0.05]), 2)
    credit_adjustment_amt = np.round(rng.choice([0.0, 0.0, 0.0, -25.0, -50.0, 15.0], size=batch_size), 2)

    defensible_gaps = np.maximum(0.0, realized_disc_rates - BASELINE_P75_DISCOUNT) * extended_list_amt

    if n_alpha > 0:
        acc_alpha.update(
            extended_list_amt[mask_alpha],
            net_invoiced_amt[mask_alpha],
            realized_disc_rates[mask_alpha],
            defensible_gaps[mask_alpha]
        )

    if n_beta > 0:
        acc_beta.update(
            extended_list_amt[mask_beta],
            net_invoiced_amt[mask_beta],
            realized_disc_rates[mask_beta],
            defensible_gaps[mask_beta]
        )

    if n_gamma > 0:
        acc_gamma.update(
            extended_list_amt[mask_gamma],
            net_invoiced_amt[mask_gamma],
            realized_disc_rates[mask_gamma],
            defensible_gaps[mask_gamma]
        )

    cols = {
        "transaction_line_id": pa_line_ids,
        "invoice_id": pa_inv_ids,
        "account_id": pa_acct,
        "customer_name": pa_cust,
        "parent_account_id": pa_parent,
        "transaction_date": pa_dates,
        "currency": pa_curr,
        "extended_list_amt": pa.array(extended_list_amt, type=pa.float64()),
        "net_invoiced_amt": pa.array(net_invoiced_amt, type=pa.float64()),
        "cogs_amt": pa.array(cogs_amt, type=pa.float64()),
        "off_invoice_rebate": pa.array(off_invoice_rebate, type=pa.float64()),
        "fx_rate_to_reporting": pa.array(fx_rates, type=pa.float64()),
        "list_unit_price": pa.array(list_unit_price, type=pa.float64()),
        "order_quantity": pa.array(order_quantity, type=pa.float64()),
        "base_discount_amt": pa.array(base_discount_amt, type=pa.float64()),
        "promo_discount_amt": pa.array(promo_discount_amt, type=pa.float64()),
        "freight_shipping_amt": pa.array(freight_shipping_amt, type=pa.float64()),
        "tax_vat_amt": pa.array(tax_vat_amt, type=pa.float64()),
        "standard_margin_amt": pa.array(standard_margin_amt, type=pa.float64()),
        "pocket_margin_amt": pa.array(pocket_margin_amt, type=pa.float64()),
        "gross_booking_val": pa.array(gross_booking_val, type=pa.float64()),
        "net_booking_val": pa.array(net_booking_val, type=pa.float64()),
        "rebate_accrual_pct": pa.array(rebate_accrual_pct, type=pa.float64()),
        "payment_terms_penalty": pa.array(payment_terms_penalty, type=pa.float64()),
        "credit_adjustment_amt": pa.array(credit_adjustment_amt, type=pa.float64()),
    }

    for col_name, pa_arr in pa_cat_arrays.items():
        cols[col_name] = pa_arr

    return pa.Table.from_pydict(cols)


def compute_file_sha256(filepath: Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

def generate_dataset_1m_csv() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    print("\n" + "="*80)
    print("STEP 1: Generating dataset_stress_1m_wide.csv (1,000,000 rows x 87 columns)...")
    print("="*80)
    t0 = time.time()
    
    total_rows = 1_000_000
    chunk_size = 250_000
    num_chunks = total_rows // chunk_size
    seed = 42

    acc_alpha = CulpritStatsAccumulator("Culprit Alpha (4-Level)", "EMEA + Gold + MultiYear + EnterpriseCloud")
    acc_beta = CulpritStatsAccumulator("Culprit Beta (5-Level)", "Americas + Financial Services + SI + Tier 4 Gov + Software Solutions")
    acc_gamma = CulpritStatsAccumulator("Culprit Gamma (3-Level)", "APAC + Sovereign Air-Gap + Ultra Five-Nines")

    schema = build_pyarrow_schema()

    with open(CSV_FILE, "wb") as f_out:
        writer = pacsv.CSVWriter(f_out, schema)
        for c in range(num_chunks):
            t_chunk_0 = time.time()
            start_row = c * chunk_size + 1
            rng = np.random.default_rng(seed + c)
            
            table = generate_batch_table(
                start_row_idx=start_row,
                batch_size=chunk_size,
                rng=rng,
                id_prefix="TX-1M",
                acc_alpha=acc_alpha,
                acc_beta=acc_beta,
                acc_gamma=acc_gamma,
            )
            writer.write_table(table)
            t_chunk_1 = time.time()
            print(f"  -> Chunk {c+1}/{num_chunks} written ({start_row:,} to {start_row + chunk_size - 1:,}) in {t_chunk_1 - t_chunk_0:.2f}s")
        writer.close()

    t1 = time.time()
    file_size_bytes = CSV_FILE.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    print(f"-> 1M CSV generated in {t1 - t0:.2f}s. File size: {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)")
    
    print("Computing SHA-256 checksum for 1M CSV...")
    t_sha = time.time()
    sha256_hash = compute_file_sha256(CSV_FILE)
    print(f"  SHA-256: {sha256_hash} (computed in {time.time() - t_sha:.2f}s)")

    meta = {
        "filename": CSV_FILE.name,
        "format": "Standard CSV (RFC 4180)",
        "row_count": total_rows,
        "column_count": len(schema.names),
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_mb, 2),
        "sha256": sha256_hash,
        "elapsed_seconds": round(t1 - t0, 2),
    }

    culprits = {
        "alpha": acc_alpha.to_dict(),
        "beta": acc_beta.to_dict(),
        "gamma": acc_gamma.to_dict(),
    }
    return meta, culprits


def generate_dataset_15m_parquet() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    print("\n" + "="*80)
    print("STEP 2: Generating dataset_stress_15m_wide.parquet (15,000,000 rows x 87 columns)...")
    print("="*80)
    t0 = time.time()

    total_rows = 15_000_000
    chunk_size = 500_000
    num_chunks = total_rows // chunk_size
    seed = 10042

    acc_alpha = CulpritStatsAccumulator("Culprit Alpha (4-Level)", "EMEA + Gold + MultiYear + EnterpriseCloud")
    acc_beta = CulpritStatsAccumulator("Culprit Beta (5-Level)", "Americas + Financial Services + SI + Tier 4 Gov + Software Solutions")
    acc_gamma = CulpritStatsAccumulator("Culprit Gamma (3-Level)", "APAC + Sovereign Air-Gap + Ultra Five-Nines")

    schema = build_pyarrow_schema()

    with pq.ParquetWriter(PARQUET_FILE, schema, compression="snappy") as writer:
        for c in range(num_chunks):
            t_chunk_0 = time.time()
            start_row = c * chunk_size + 1
            rng = np.random.default_rng(seed + c)

            table = generate_batch_table(
                start_row_idx=start_row,
                batch_size=chunk_size,
                rng=rng,
                id_prefix="TX-15M",
                acc_alpha=acc_alpha,
                acc_beta=acc_beta,
                acc_gamma=acc_gamma,
            )
            writer.write_table(table)
            t_chunk_1 = time.time()
            print(f"  -> Chunk {c+1}/{num_chunks} written ({start_row:,} to {start_row + chunk_size - 1:,}) in {t_chunk_1 - t_chunk_0:.2f}s")

    t1 = time.time()
    file_size_bytes = PARQUET_FILE.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    file_size_gb = file_size_bytes / (1024 * 1024 * 1024)
    print(f"-> 15M Parquet generated in {t1 - t0:.2f}s. File size: {file_size_gb:.2f} GB ({file_size_mb:.2f} MB, {file_size_bytes:,} bytes)")

    print("Computing SHA-256 checksum for 15M Parquet...")
    t_sha = time.time()
    sha256_hash = compute_file_sha256(PARQUET_FILE)
    print(f"  SHA-256: {sha256_hash} (computed in {time.time() - t_sha:.2f}s)")

    meta = {
        "filename": PARQUET_FILE.name,
        "format": "Compressed Columnar Parquet (Snappy)",
        "row_count": total_rows,
        "column_count": len(schema.names),
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_mb, 2),
        "file_size_gb": round(file_size_gb, 2),
        "sha256": sha256_hash,
        "elapsed_seconds": round(t1 - t0, 2),
    }

    culprits = {
        "alpha": acc_alpha.to_dict(),
        "beta": acc_beta.to_dict(),
        "gamma": acc_gamma.to_dict(),
    }
    return meta, culprits

def verify_stress_datasets(meta_1m: Dict[str, Any], meta_15m: Dict[str, Any]) -> str:
    print("\n" + "="*80)
    print("STEP 3: Running Independent In-Process DuckDB Verification...")
    print("="*80)
    
    con = duckdb.connect(":memory:")
    output_lines = []

    def log(msg: str):
        print(msg)
        output_lines.append(msg)

    log("### In-Process DuckDB Verification Report")
    log(f"Verification Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")

    # 1. Verify 1M CSV
    log("\n#### 1. Verifying dataset_stress_1m_wide.csv")
    csv_path_escaped = str(CSV_FILE).replace("\\", "/")
    
    res_1m = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{csv_path_escaped}', header=True)").fetchone()[0]
    log(f"- Verified Row Count: {res_1m:,} (Expected: 1,000,000) -> {'PASS' if res_1m == 1000000 else 'FAIL'}")
    
    cols_1m = [col[0] for col in con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{csv_path_escaped}', header=True) LIMIT 1").fetchall()]
    log(f"- Verified Column Count: {len(cols_1m)} (Expected: 87) -> {'PASS' if len(cols_1m) == 87 else 'FAIL'}")

    theater_stats_1m = con.execute(f"""
        SELECT 
            sales_theater, 
            COUNT(*) as row_cnt,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct
        FROM read_csv_auto('{csv_path_escaped}', header=True)
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    log("- Top-Level Single-Dimension Aggregates (sales_theater):")
    for row in theater_stats_1m:
        log(f"    * {row[0]}: {row[1]:,} rows, Mean Discount: {row[2]}% (Healthy Band: 10% - 15%)")

    alpha_1m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_csv_auto('{csv_path_escaped}', header=True)
        WHERE sales_theater = 'EMEA'
          AND partner_program_tier = 'Gold'
          AND contract_commitment_type = 'MultiYear'
          AND prod_family = 'EnterpriseCloud'
    """).fetchone()
    log(f"- Culprit Alpha (4-Level Compound Slice) Verification in 1M CSV:")
    log(f"    * Rows: {alpha_1m[0]:,}")
    log(f"    * Mean List Price: ${alpha_1m[1]:,}")
    log(f"    * Mean Discount %: {alpha_1m[2]}% (Runaway Exception: 55% - 70%)")
    log(f"    * Defensible Gap Sum: ${alpha_1m[3]:,}")
    log(f"    * Actionable Opportunity (40%): ${alpha_1m[4]:,}")

    # 2. Verify 15M Parquet
    log("\n#### 2. Verifying dataset_stress_15m_wide.parquet")
    parquet_path_escaped = str(PARQUET_FILE).replace("\\", "/")
    
    t_pq_0 = time.time()
    res_15m = con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path_escaped}')").fetchone()[0]
    t_pq_1 = time.time()
    log(f"- Verified Row Count: {res_15m:,} (Expected: 15,000,000) in {t_pq_1 - t_pq_0:.2f}s -> {'PASS' if res_15m == 15000000 else 'FAIL'}")

    cols_15m = [col[0] for col in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet_path_escaped}') LIMIT 1").fetchall()]
    log(f"- Verified Column Count: {len(cols_15m)} (Expected: 87) -> {'PASS' if len(cols_15m) == 87 else 'FAIL'}")

    theater_stats_15m = con.execute(f"""
        SELECT 
            sales_theater, 
            COUNT(*) as row_cnt,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct
        FROM read_parquet('{parquet_path_escaped}')
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    log("- Top-Level Single-Dimension Aggregates (sales_theater) on 15M Parquet:")
    for row in theater_stats_15m:
        log(f"    * {row[0]}: {row[1]:,} rows, Mean Discount: {row[2]}% (Healthy Band: 10% - 15%)")

    alpha_15m = con.execute(f"""
        SELECT 
            COUNT(*) as slice_rows,
            ROUND(AVG(extended_list_amt), 2) as mean_list,
            ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
            ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
        FROM read_parquet('{parquet_path_escaped}')
        WHERE sales_theater = 'EMEA'
          AND partner_program_tier = 'Gold'
          AND contract_commitment_type = 'MultiYear'
          AND prod_family = 'EnterpriseCloud'
    """).fetchone()
    log(f"- Culprit Alpha (4-Level Compound Slice) Verification in 15M Parquet:")
    log(f"    * Rows: {alpha_15m[0]:,}")
    log(f"    * Mean List Price: ${alpha_15m[1]:,}")
    log(f"    * Mean Discount %: {alpha_15m[2]}% (Runaway Exception: 55% - 70%)")
    log(f"    * Defensible Gap Sum: ${alpha_15m[3]:,}")
    log(f"    * Actionable Opportunity (40%): ${alpha_15m[4]:,}")

    con.close()
    return "\n".join(output_lines)

def write_dataset_manifest(
    meta_1m: Dict[str, Any],
    culprits_1m: Dict[str, Any],
    meta_15m: Dict[str, Any],
    culprits_15m: Dict[str, Any],
    verification_log: str,
):
    print("\n" + "="*80)
    print("STEP 4: Writing DATASET_MANIFEST.md...")
    print("="*80)

    schema = build_pyarrow_schema()

    schema_rows = []
    canonical_grain = [
        "transaction_line_id", "invoice_id", "account_id", "customer_name",
        "parent_account_id", "transaction_date", "currency"
    ]
    numerical_cols = [
        "extended_list_amt", "net_invoiced_amt", "cogs_amt", "off_invoice_rebate",
        "fx_rate_to_reporting", "list_unit_price", "order_quantity", "base_discount_amt",
        "promo_discount_amt", "freight_shipping_amt", "tax_vat_amt", "standard_margin_amt",
        "pocket_margin_amt", "gross_booking_val", "net_booking_val", "rebate_accrual_pct",
        "payment_terms_penalty", "credit_adjustment_amt"
    ]

    for idx, name in enumerate(schema.names, 1):
        if name in canonical_grain:
            category = "Line-Grain Canonical / Identifier"
            dtype = "String / Dictionary"
        elif name in numerical_cols:
            category = "Numerical Metric / Financial Concession"
            dtype = "Float64"
        elif any(k in name for k in ["sales", "channel", "partner", "distributor", "quota", "deal_desk"]):
            category = "Sales Hierarchy Dimension"
            dtype = "Categorical Dictionary"
        elif "prod" in name:
            category = "Product Taxonomy Dimension"
            dtype = "Categorical Dictionary"
        elif "cust" in name:
            category = "Customer Classification Dimension"
            dtype = "Categorical Dictionary"
        elif any(k in name for k in ["contract", "deal", "order", "shipping", "payment", "invoice", "audit"]):
            category = "Contract & Deal Stipulation Dimension"
            dtype = "Categorical Dictionary"
        else:
            category = "Operations & Metadata Dimension"
            dtype = "Categorical Dictionary"

        schema_rows.append(f"| {idx} | `{name}` | {dtype} | {category} |")

    schema_table_str = "\n".join(schema_rows)

    manifest_md = f"""# Sift Stress Dataset Manifest

Generated at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
Project Root: `c:/Shift`
Deliverables Directory: `c:/Shift/test_deliverables/datasets/`

## 1. File Metadata Overview

| Metric | Dataset 1 (CSV) | Dataset 2 (Parquet) |
| :--- | :--- | :--- |
| **Filename** | `{meta_1m['filename']}` | `{meta_15m['filename']}` |
| **Storage Format** | {meta_1m['format']} | {meta_15m['format']} |
| **Exact Row Count** | **{meta_1m['row_count']:,}** rows | **{meta_15m['row_count']:,}** rows |
| **Total Columns** | **{meta_1m['column_count']}** columns | **{meta_15m['column_count']}** columns |
| **Categorical Columns** | 62 columns (Requirement >= 60) | 62 columns (Requirement >= 60) |
| **Numerical Metric Columns** | 18 columns (Requirement >= 15) | 18 columns (Requirement >= 15) |
| **File Size (Bytes)** | {meta_1m['file_size_bytes']:,} bytes | {meta_15m['file_size_bytes']:,} bytes |
| **File Size (Human Readable)** | {meta_1m['file_size_mb']} MB | {meta_15m.get('file_size_gb', round(meta_15m['file_size_mb']/1024, 2))} GB ({meta_15m['file_size_mb']} MB) |
| **SHA-256 Checksum** | `{meta_1m['sha256']}` | `{meta_15m['sha256']}` |
| **Generation Latency** | {meta_1m['elapsed_seconds']}s | {meta_15m['elapsed_seconds']}s |

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
| **Slice Row Count ($N$)** | **{culprits_1m['alpha']['slice_row_count']:,}** rows | **{culprits_15m['alpha']['slice_row_count']:,}** rows |
| **Mean List Price ($\\bar{{L}}$)** | ${culprits_1m['alpha']['mean_list_price']:,.2f} | ${culprits_15m['alpha']['mean_list_price']:,.2f} |
| **Mean Concession Rate ($\\bar{{r}}$)** | **{culprits_1m['alpha']['mean_discount_pct']:.2f}%** (Runaway: 55%-70%) | **{culprits_15m['alpha']['mean_discount_pct']:.2f}%** (Runaway: 55%-70%) |
| **Baseline Cohort P75 ($\\tau$)** | {culprits_1m['alpha']['baseline_cohort_p75_pct']:.2f}% | {culprits_15m['alpha']['baseline_cohort_p75_pct']:.2f}% |
| **Defensible Gap Dollar Sum ($G^{{defensible}}$)** | **${culprits_1m['alpha']['defensible_gap_sum']:,.2f}** | **${culprits_15m['alpha']['defensible_gap_sum']:,.2f}** |
| **Actionable Opportunity ($G^{{actionable}} = G^{{def}} \\\\times 0.40$)** | **${culprits_1m['alpha']['actionable_opp_sum']:,.2f}** | **${culprits_15m['alpha']['actionable_opp_sum']:,.2f}** |

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
| **Slice Row Count ($N$)** | **{culprits_1m['beta']['slice_row_count']:,}** rows | **{culprits_15m['beta']['slice_row_count']:,}** rows |
| **Mean List Price ($\\bar{{L}}$)** | ${culprits_1m['beta']['mean_list_price']:,.2f} | ${culprits_15m['beta']['mean_list_price']:,.2f} |
| **Mean Concession Rate ($\\bar{{r}}$)** | **{culprits_1m['beta']['mean_discount_pct']:.2f}%** (Runaway: 58%-72%) | **{culprits_15m['beta']['mean_discount_pct']:.2f}%** (Runaway: 58%-72%) |
| **Baseline Cohort P75 ($\\tau$)** | {culprits_1m['beta']['baseline_cohort_p75_pct']:.2f}% | {culprits_15m['beta']['baseline_cohort_p75_pct']:.2f}% |
| **Defensible Gap Dollar Sum ($G^{{defensible}}$)** | **${culprits_1m['beta']['defensible_gap_sum']:,.2f}** | **${culprits_15m['beta']['defensible_gap_sum']:,.2f}** |
| **Actionable Opportunity ($G^{{actionable}} = G^{{def}} \\\\times 0.40$)** | **${culprits_1m['beta']['actionable_opp_sum']:,.2f}** | **${culprits_15m['beta']['actionable_opp_sum']:,.2f}** |

#### Culprit Gamma (3-Level Compound Slice)
- **Mathematical Definition:**
  `sales_theater == 'APAC'` AND
  `prod_deployment_mode == 'Sovereign Air-Gap'` AND
  `contract_sla_tier == 'Ultra Five-Nines'`
- **Ground Truth Values:**

| Metric | Dataset 1M (CSV) | Dataset 15M (Parquet) |
| :--- | :--- | :--- |
| **Slice Row Count ($N$)** | **{culprits_1m['gamma']['slice_row_count']:,}** rows | **{culprits_15m['gamma']['slice_row_count']:,}** rows |
| **Mean List Price ($\\bar{{L}}$)** | ${culprits_1m['gamma']['mean_list_price']:,.2f} | ${culprits_15m['gamma']['mean_list_price']:,.2f} |
| **Mean Concession Rate ($\\bar{{r}}$)** | **{culprits_1m['gamma']['mean_discount_pct']:.2f}%** (Runaway: 52%-66%) | **{culprits_15m['gamma']['mean_discount_pct']:.2f}%** (Runaway: 52%-66%) |
| **Baseline Cohort P75 ($\\tau$)** | {culprits_1m['gamma']['baseline_cohort_p75_pct']:.2f}% | {culprits_15m['gamma']['baseline_cohort_p75_pct']:.2f}% |
| **Defensible Gap Dollar Sum ($G^{{defensible}}$)** | **${culprits_1m['gamma']['defensible_gap_sum']:,.2f}** | **${culprits_15m['gamma']['defensible_gap_sum']:,.2f}** |
| **Actionable Opportunity ($G^{{actionable}} = G^{{def}} \\\\times 0.40$)** | **${culprits_1m['gamma']['actionable_opp_sum']:,.2f}** | **${culprits_15m['gamma']['actionable_opp_sum']:,.2f}** |

---

## 3. Complete Column Schema Table (87 Columns)

All 87 columns are fully compatible with Sift canonical ingestion, LOAO comparability categorization, diagnostic beam search, and Decoupled Engine B margin bridges.

| # | Column Name | Data Type | Business Classification |
| :--- | :--- | :--- | :--- |
{schema_table_str}

---

## 4. In-Process DuckDB Verification Log

```text
{verification_log}
```

---

## 5. Automated Python Verification Code

To independently reproduce the verification of row counts, column counts, and culprit signatures, execute:

```python
import duckdb

con = duckdb.connect(":memory:")

# 1. Verify 1M CSV
print("Verifying 1M CSV...")
csv_rows = con.execute("SELECT COUNT(*) FROM read_csv_auto(\x27c:/Shift/test_deliverables/datasets/dataset_stress_1m_wide.csv\x27, header=True)").fetchone()[0]
print(f"Row count 1M CSV: {{csv_rows:,}}")

# 2. Verify 15M Parquet
print("Verifying 15M Parquet...")
pq_rows = con.execute("SELECT COUNT(*) FROM read_parquet(\x27c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet\x27)").fetchone()[0]
print(f"Row count 15M Parquet: {{pq_rows:,}}")

# 3. Verify Culprit Alpha 4-level signature in 15M Parquet
alpha_res = con.execute(\'\'\'
    SELECT 
        COUNT(*) as slice_rows,
        ROUND(AVG(extended_list_amt), 2) as mean_list,
        ROUND(AVG((extended_list_amt - net_invoiced_amt) / extended_list_amt) * 100, 2) as mean_disc_pct,
        ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt), 2) as def_gap,
        ROUND(SUM(GREATEST(0.0, ((extended_list_amt - net_invoiced_amt) / extended_list_amt) - 0.1500) * extended_list_amt) * 0.40, 2) as act_opp
    FROM read_parquet(\x27c:/Shift/test_deliverables/datasets/dataset_stress_15m_wide.parquet\x27)
    WHERE sales_theater = \x27EMEA\x27
      AND partner_program_tier = \x27Gold\x27
      AND contract_commitment_type = \x27MultiYear\x27
      AND prod_family = \x27EnterpriseCloud\x27
\'\'\').fetchone()

print(f"Culprit Alpha: Rows={{alpha_res[0]:,}}, MeanDisc={{alpha_res[2]}}%, DefGap=${{alpha_res[3]:,}}, ActOpp=${{alpha_res[4]:,}}")
con.close()
```
"""

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        f.write(manifest_md.strip() + "\n")
    print(f"-> Manifest written successfully to {MANIFEST_FILE}")


def main():
    print("="*80)
    print("Project Sift: Massive High-Dimensional Synthetic Stress Dataset Generator")
    print("="*80)
    t_start = time.time()

    meta_1m, culprits_1m = generate_dataset_1m_csv()
    meta_15m, culprits_15m = generate_dataset_15m_parquet()
    verification_log = verify_stress_datasets(meta_1m, meta_15m)
    write_dataset_manifest(meta_1m, culprits_1m, meta_15m, culprits_15m, verification_log)

    t_end = time.time()
    print("\n" + "="*80)
    print(f"ALL STRESS DATASETS AND MANIFEST GENERATED & VERIFIED IN {t_end - t_start:.2f}s!")
    print("="*80)


if __name__ == "__main__":
    main()
