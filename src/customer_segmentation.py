"""
src/customer_segmentation.py
----------------------------
Executes statistical RFM customer segmentation and K-Means account clustering
for institutional healthcare accounts (Academic Medical Centers, IDNs, Retailers).
Saves customer segment profile tables to outputs/reports/ and metrics to outputs/metrics/.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
REPORTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")
METRICS_DIR = os.path.join(BASE_DIR, "outputs", "metrics")

def run_customer_segmentation():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(METRICS_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    # RFM Feature Extraction
    query = """
    SELECT 
        c.customer_id,
        c.customer_name,
        c.customer_type,
        c.country_code,
        CAST(julianday('2025-12-31') - julianday(MAX(d.full_date)) AS INTEGER) AS recency_days,
        COUNT(DISTINCT f.sales_fact_id) AS frequency_orders,
        SUM(f.net_units) AS total_units_purchased,
        ROUND(SUM(f.net_sales_usd), 2) AS monetary_value_usd,
        ROUND(SUM(f.net_sales_usd) / NULLIF(COUNT(DISTINCT f.sales_fact_id), 0), 2) AS aov_usd
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.net_units > 0
    GROUP BY c.customer_id, c.customer_name, c.customer_type, c.country_code
    """
    rfm_df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 1. Rule-based RFM Scoring (Quartiles)
    rfm_df["r_score"] = pd.qcut(rfm_df["recency_days"], q=4, labels=[4, 3, 2, 1]) # Lower days = higher score
    rfm_df["f_score"] = pd.qcut(rfm_df["frequency_orders"].rank(method="first"), q=4, labels=[1, 2, 3, 4])
    rfm_df["m_score"] = pd.qcut(rfm_df["monetary_value_usd"].rank(method="first"), q=4, labels=[1, 2, 3, 4])
    
    # RFM Segment Classification
    def assign_segment(row):
        r, f, m = int(row["r_score"]), int(row["f_score"]), int(row["m_score"])
        if r >= 3 and f >= 3 and m >= 3:
            return "Tier 1: Strategic Key Account (Champion)"
        elif r >= 3 and f >= 2:
            return "Tier 2: Loyal Growth Account"
        elif r <= 2 and m >= 3:
            return "Tier 3: At-Risk High-Value Account"
        elif r >= 3 and f <= 2:
            return "Tier 4: Promising Developing Account"
        else:
            return "Tier 5: Low-Engagement Account"
            
    rfm_df["rfm_segment"] = rfm_df.apply(assign_segment, axis=1)
    
    # 2. Defensible K-Means Clustering (k=4) on standardized Log-transformed RFM features
    features = ["recency_days", "frequency_orders", "monetary_value_usd"]
    X = np.log1p(rfm_df[features])
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    rfm_df["cluster_id"] = kmeans.fit_predict(X_scaled)
    
    # Cluster profiling
    cluster_profiles = rfm_df.groupby("cluster_id").agg({
        "customer_id": "count",
        "recency_days": "mean",
        "frequency_orders": "mean",
        "monetary_value_usd": ["mean", "sum"],
        "aov_usd": "mean"
    }).round(2)
    cluster_profiles.columns = ["account_count", "mean_recency_days", "mean_order_freq", "mean_spend_usd", "total_spend_usd", "mean_aov_usd"]
    cluster_profiles = cluster_profiles.sort_values("mean_spend_usd", ascending=False).reset_index()
    
    # Map business cluster names
    cluster_labels = {
        cluster_profiles.iloc[0]["cluster_id"]: "Cluster 1: Enterprise Health Systems (High Volume, High Spend)",
        cluster_profiles.iloc[1]["cluster_id"]: "Cluster 2: Frequent Mid-Tier Accounts",
        cluster_profiles.iloc[2]["cluster_id"]: "Cluster 3: Moderate Regular Buyers",
        cluster_profiles.iloc[3]["cluster_id"]: "Cluster 4: Lapsed / Low-Velocity Clinics"
    }
    rfm_df["cluster_name"] = rfm_df["cluster_id"].map(cluster_labels)
    
    # Save output reports
    report_csv = os.path.join(REPORTS_DIR, "customer_rfm_segmentation.csv")
    rfm_df.to_csv(report_csv, index=False)
    print(f"Customer RFM segmentation saved to {report_csv}")
    
    # Segment summary
    seg_summary = rfm_df.groupby("rfm_segment").agg({
        "customer_id": "count",
        "monetary_value_usd": ["sum", "mean"],
        "frequency_orders": "mean",
        "recency_days": "mean"
    }).round(2)
    seg_summary.columns = ["account_count", "total_revenue_usd", "mean_revenue_usd", "mean_orders", "mean_recency_days"]
    seg_summary["revenue_share_pct"] = (seg_summary["total_revenue_usd"] / rfm_df["monetary_value_usd"].sum() * 100).round(2)
    
    summary_csv = os.path.join(REPORTS_DIR, "rfm_segment_summary.csv")
    seg_summary.to_csv(summary_csv)
    print(f"Segment summary saved to {summary_csv}")
    return rfm_df

if __name__ == "__main__":
    run_customer_segmentation()
