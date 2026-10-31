"""
src/generate_commercial_data.py
-------------------------------
Generates an enterprise-grade, realistic pharmaceutical commercial sales dataset
with authentic business mechanics and edge cases:
- Multi-market launch timings (unequal date windows): US/DE/UK (36m), FR (30m), JP (24m), CA (18m)
- Returns/refunds with negative quantities and negative financial impact
- Tiered pricing & customer discounts (Hospitals vs. Retailers vs. Specialty)
- Distributor channel dynamics (McKesson, AmerisourceBergen/Cencora, Cardinal, Alliance, Medipal)
- Sales representatives with designated territories and teams
- Specific data-quality anomalies to validate our robust cleaning pipeline
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Fix seed for strict reproducibility
np.random.seed(42)
random.seed(42)

TOTAL_RECORDS = 28500
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "pharma_commercial_sales_raw.csv")

# 1. Product Portfolio (Aligning with CNS / Psychiatric portfolio + Specialty/Oncology additions)
PRODUCTS = [
    {"product_id": "PRD-CNS-001", "product_name": "AmphetaDex", "generic_name": "amphetamine", "therapeutic_area": "CNS / Psychiatry", "form": "Capsule", "wac_price": 285.00, "base_cost": 42.00, "return_rate": 0.022},
    {"product_id": "PRD-CNS-002", "product_name": "DexMethyl", "generic_name": "methylphenidate", "therapeutic_area": "CNS / Psychiatry", "form": "Extended Release Tablet", "wac_price": 195.00, "base_cost": 28.00, "return_rate": 0.018},
    {"product_id": "PRD-CNS-003", "product_name": "AlprazPlus", "generic_name": "alprazolam", "therapeutic_area": "CNS / Psychiatry", "form": "Tablet", "wac_price": 115.00, "base_cost": 15.00, "return_rate": 0.015},
    {"product_id": "PRD-CNS-004", "product_name": "EscitaloPro", "generic_name": "escitalopram", "therapeutic_area": "CNS / Psychiatry", "form": "Tablet", "wac_price": 145.00, "base_cost": 20.00, "return_rate": 0.019},
    {"product_id": "PRD-CNS-005", "product_name": "OlanzRx", "generic_name": "olanzapine", "therapeutic_area": "CNS / Psychiatry", "form": "Oral Disintegrating Tablet", "wac_price": 420.00, "base_cost": 65.00, "return_rate": 0.025},
    {"product_id": "PRD-CNS-006", "product_name": "QuetiapMax", "generic_name": "quetiapine", "therapeutic_area": "CNS / Psychiatry", "form": "Extended Release Tablet", "wac_price": 380.00, "base_cost": 55.00, "return_rate": 0.028},
    {"product_id": "PRD-ONC-007", "product_name": "OncoShield", "generic_name": "osimertinib-analog", "therapeutic_area": "Oncology", "form": "Injection Vial", "wac_price": 3850.00, "base_cost": 620.00, "return_rate": 0.008},
    {"product_id": "PRD-ONC-008", "product_name": "ImmunoPax", "generic_name": "pembrolizumab-biosimilar", "therapeutic_area": "Oncology", "form": "Infusion Bag", "wac_price": 5400.00, "base_cost": 890.00, "return_rate": 0.005},
    {"product_id": "PRD-IMM-009", "product_name": "RheumaCure", "generic_name": "adalimumab-biosimilar", "therapeutic_area": "Immunology", "form": "Auto-injector Pen", "wac_price": 2150.00, "base_cost": 310.00, "return_rate": 0.012},
]

# 2. Geographies & Unequal Market Launch Windows
GEOGRAPHIES = {
    "US": {"country": "United States", "region": "North America", "start_date": "2023-01-01", "weight": 0.44, "currency": "USD", "fx": 1.00},
    "DE": {"country": "Germany", "region": "Europe", "start_date": "2023-01-01", "weight": 0.16, "currency": "EUR", "fx": 1.08},
    "UK": {"country": "United Kingdom", "region": "Europe", "start_date": "2023-01-01", "weight": 0.13, "currency": "GBP", "fx": 1.28},
    "FR": {"country": "France", "region": "Europe", "start_date": "2023-07-01", "weight": 0.11, "currency": "EUR", "fx": 1.08}, # 30 months
    "JP": {"country": "Japan", "region": "Asia-Pacific", "start_date": "2024-01-01", "weight": 0.10, "currency": "JPY", "fx": 0.0067}, # 24 months
    "CA": {"country": "Canada", "region": "North America", "start_date": "2024-06-01", "weight": 0.06, "currency": "CAD", "fx": 0.74}, # 18 months
}

# 3. Channels
CHANNELS = [
    {"channel_id": "CHN-01", "channel_name": "Hospital Direct Tender", "weight": 0.32, "discount_mean": 0.22, "discount_std": 0.04},
    {"channel_id": "CHN-02", "channel_name": "Wholesale Distributor", "weight": 0.40, "discount_mean": 0.15, "discount_std": 0.03},
    {"channel_id": "CHN-03", "channel_name": "Retail Pharmacy Chain", "weight": 0.20, "discount_mean": 0.10, "discount_std": 0.02},
    {"channel_id": "CHN-04", "channel_name": "Specialty Mail Order", "weight": 0.08, "discount_mean": 0.08, "discount_std": 0.02},
]

# 4. Distributors
DISTRIBUTORS = [
    {"distributor_id": "DST-001", "name": "McKesson Corp", "countries": ["US", "CA"], "weight": 0.35},
    {"distributor_id": "DST-002", "name": "AmerisourceBergen (Cencora)", "countries": ["US", "UK", "FR"], "weight": 0.25},
    {"distributor_id": "DST-003", "name": "Cardinal Health", "countries": ["US"], "weight": 0.18},
    {"distributor_id": "DST-004", "name": "Alliance Healthcare", "countries": ["UK", "DE", "FR"], "weight": 0.12},
    {"distributor_id": "DST-005", "name": "Medipal Holdings", "countries": ["JP"], "weight": 0.06},
    {"distributor_id": "DST-006", "name": "Direct Pharma Logistics", "countries": ["US", "DE", "UK", "FR", "JP", "CA"], "weight": 0.04},
]

# 5. Customer Segments (Accounts)
CUSTOMER_TYPES = [
    {"type": "Academic Medical Center", "weight": 0.22, "vol_mult": 2.5},
    {"type": "Integrated Delivery Network (IDN)", "weight": 0.30, "vol_mult": 3.0},
    {"type": "Community Hospital", "weight": 0.20, "vol_mult": 1.2},
    {"type": "National Retail Pharmacy", "weight": 0.18, "vol_mult": 2.0},
    {"type": "Specialty Oncology Clinic", "weight": 0.10, "vol_mult": 1.5},
]

# Generate fixed list of 120 key institutional accounts
CUSTOMERS = []
for i in range(1, 121):
    ctype = random.choices([ct["type"] for ct in CUSTOMER_TYPES], weights=[ct["weight"] for ct in CUSTOMER_TYPES])[0]
    c_country = random.choices(list(GEOGRAPHIES.keys()), weights=[g["weight"] for g in GEOGRAPHIES.values()])[0]
    CUSTOMERS.append({
        "customer_id": f"CUST-{i:04d}",
        "customer_name": f"{c_country} {ctype.split()[0]} Account #{i}",
        "customer_type": ctype,
        "country": c_country,
    })

# 6. Sales Representatives & Teams (24 Reps across 4 Commercial Teams)
TEAMS = ["Team Alpha - CNS North", "Team Beta - CNS South", "Team Gamma - Specialty / Oncology", "Team Delta - Commercial Accounts"]
SALES_REPS = []
for i in range(1, 25):
    t_name = TEAMS[(i - 1) % len(TEAMS)]
    t_country = "US" if i <= 14 else ("DE" if i <= 17 else ("UK" if i <= 20 else ("FR" if i <= 22 else "JP")))
    SALES_REPS.append({
        "rep_id": f"REP-{i:03d}",
        "rep_name": f"Representative_{i:02d}",
        "team_name": t_name,
        "country": t_country,
        "experience_years": random.randint(2, 15),
        "quota_annual_usd": random.choice([2500000, 3200000, 4500000, 6000000]),
    })

def generate_dataset():
    records = []
    end_date = datetime(2025, 12, 31)
    
    country_codes = list(GEOGRAPHIES.keys())
    country_weights = [GEOGRAPHIES[c]["weight"] for c in country_codes]
    
    prod_weights = [0.22, 0.18, 0.15, 0.14, 0.10, 0.09, 0.05, 0.04, 0.03] # Pareto distributed
    
    for row_id in range(1, TOTAL_RECORDS + 1):
        transaction_id = f"TXN-{row_id:06d}"
        
        # Pick country
        c_code = random.choices(country_codes, weights=country_weights)[0]
        c_meta = GEOGRAPHIES[c_code]
        start_d = datetime.strptime(c_meta["start_date"], "%Y-%m-%d")
        
        # Date between start_date and 2025-12-31
        days_span = (end_date - start_d).days
        txn_date = start_d + timedelta(days=random.randint(0, days_span))
        
        # Pick product
        prod = random.choices(PRODUCTS, weights=prod_weights)[0]
        
        # Pick channel
        chn = random.choices(CHANNELS, weights=[c["weight"] for c in CHANNELS])[0]
        
        # Pick distributor matching country
        avail_dist = [d for d in DISTRIBUTORS if c_code in d["countries"]]
        dist = random.choice(avail_dist) if avail_dist else DISTRIBUTORS[0]
        
        # Pick customer (prefer same country)
        same_c_custs = [c for c in CUSTOMERS if c["country"] == c_code]
        cust = random.choice(same_c_custs) if same_c_custs else random.choice(CUSTOMERS)
        
        # Pick sales rep (prefer matching country)
        avail_reps = [r for r in SALES_REPS if r["country"] == c_code]
        rep = random.choice(avail_reps) if avail_reps else random.choice(SALES_REPS)
        
        # Pricing & Volume
        is_oncology = "Oncology" in prod["therapeutic_area"] or "Immunology" in prod["therapeutic_area"]
        base_units = random.randint(5, 40) if is_oncology else random.randint(20, 350)
        
        # Seasonal bump in Q4 for commercial channel loading
        if txn_date.month in [10, 11, 12]:
            base_units = int(base_units * random.uniform(1.15, 1.35))
        
        # Return probability
        is_return = random.random() < prod["return_rate"]
        
        wac_price = prod["wac_price"]
        # Discount based on channel
        discount_rate = max(0.02, min(0.40, np.random.normal(chn["discount_mean"], chn["discount_std"])))
        net_unit_price = round(wac_price * (1 - discount_rate), 2)
        
        if is_return:
            # Reverse logistics event: negative units and negative gross/net
            units_sold = -random.randint(1, max(1, int(base_units * 0.25)))
            return_reason = random.choice(["Damaged in Transit", "Recall / Batch Expiry", "Customer Overstock Return", "Temperature Excursion"])
            gross_sales = round(units_sold * wac_price, 2)
            net_sales = round(units_sold * net_unit_price, 2)
            return_amount = abs(net_sales)
        else:
            units_sold = base_units
            return_reason = None
            gross_sales = round(units_sold * wac_price, 2)
            net_sales = round(units_sold * net_unit_price, 2)
            return_amount = 0.00
            
        cogs = round(units_sold * prod["base_cost"], 2)
        
        record = {
            "transaction_id": transaction_id,
            "transaction_date": txn_date.strftime("%Y-%m-%d"),
            "product_id": prod["product_id"],
            "product_name": prod["product_name"],
            "generic_name": prod["generic_name"],
            "therapeutic_area": prod["therapeutic_area"],
            "dosage_form": prod["form"],
            "customer_id": cust["customer_id"],
            "customer_name": cust["customer_name"],
            "customer_type": cust["customer_type"],
            "distributor_id": dist["distributor_id"],
            "distributor_name": dist["name"],
            "sales_rep_id": rep["rep_id"],
            "sales_rep_name": rep["rep_name"],
            "sales_team": rep["team_name"],
            "sales_channel_id": chn["channel_id"],
            "sales_channel_name": chn["channel_name"],
            "country_code": c_code,
            "country_name": c_meta["country"],
            "region": c_meta["region"],
            "currency": c_meta["currency"],
            "units_ordered": units_sold if units_sold > 0 else 0,
            "units_returned": abs(units_sold) if units_sold < 0 else 0,
            "net_units": units_sold,
            "unit_wac_price_usd": wac_price,
            "contract_discount_pct": round(discount_rate * 100, 2),
            "unit_net_price_usd": net_unit_price,
            "gross_sales_usd": gross_sales if gross_sales > 0 else 0.0,
            "return_value_usd": return_amount,
            "net_sales_usd": net_sales,
            "cogs_usd": cogs,
            "gross_margin_usd": round(net_sales - cogs, 2),
            "return_reason": return_reason,
        }
        records.append(record)

    df = pd.DataFrame(records)
    
    # Introduce deliberate real-world data quality anomalies for preprocessing to catch and document:
    # 1. 25 Duplicate rows
    dup_indices = random.sample(range(len(df)), 25)
    duplicates = df.iloc[dup_indices].copy()
    
    # 2. 15 Missing / Inconsistent country casing
    for idx in random.sample(range(len(df)), 15):
        df.at[idx, "country_name"] = df.at[idx, "country_name"].lower() if random.random() > 0.5 else "   " + df.at[idx, "country_name"] + " "
        
    # 3. 20 Missing customer names (customer_id present)
    for idx in random.sample(range(len(df)), 20):
        df.at[idx, "customer_name"] = np.nan
        
    # 4. 10 Missing return reasons for actual returns
    return_indices = df[df["units_returned"] > 0].index.tolist()
    for idx in random.sample(return_indices, min(10, len(return_indices))):
        df.at[idx, "return_reason"] = np.nan
        
    # Combine duplicates
    df = pd.concat([df, duplicates], ignore_index=True)
    
    # Save raw CSV
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Generated raw commercial sales dataset with {len(df):,} records at {OUTPUT_PATH}")
    return df

if __name__ == "__main__":
    generate_dataset()
