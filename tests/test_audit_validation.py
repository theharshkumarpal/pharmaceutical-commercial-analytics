"""
tests/test_audit_validation.py
------------------------------
Rigorous, independent audit test suite verifying:
1. Exact record counts and uniqueness
2. Financial reconciliation (Gross, Returns, Discounts, Net, COGS, Margin)
3. Returns and reverse logistics sign consistency
4. Referential integrity across all 7 dimension tables
5. ABC/Pareto ranking and cumulative revenue calculations
6. Distributor concentration calculations
7. Headcount-normalized sales force effectiveness
8. Customer RFM segmentation completeness
9. SQL vs Python analytical reconciliation
10. Forecasting evaluation file exists and contains expected models
11. Edge case: date range boundaries
12. Edge case: discount rate sanity bounds
13. Edge case: data type consistency
"""

import os
import sqlite3
import unittest
import json
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
PROCESSED_CSV = os.path.join(BASE_DIR, "data", "processed", "cleaned_sales.csv")

class TestIndependentAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(DB_PATH)
        cls.df_csv = pd.read_csv(PROCESSED_CSV)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_record_counts_and_uniqueness(self):
        """Audit 1: Fact table record count matches cleaned CSV and has zero duplicate transaction IDs."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fact_sales;")
        db_count = cur.fetchone()[0]
        self.assertEqual(db_count, len(self.df_csv), "DB count does not match CSV count.")
        self.assertEqual(db_count, 28500, "Fact table count is not 28,500.")

        cur.execute("""
            SELECT transaction_id, COUNT(*) 
            FROM fact_sales 
            GROUP BY transaction_id 
            HAVING COUNT(*) > 1;
        """)
        dups = cur.fetchall()
        self.assertEqual(len(dups), 0, f"Found {len(dups)} duplicate transaction IDs.")

    def test_financial_reconciliation_math(self):
        """Audit 2: Gross Margin = Net - COGS, and financial totals are in expected range."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                SUM(gross_sales_usd),
                SUM(return_value_usd),
                SUM(net_sales_usd),
                SUM(cogs_usd),
                SUM(gross_margin_usd)
            FROM fact_sales;
        """)
        gross, returns, net, cogs, margin = cur.fetchone()

        # Structural validations (range-based, not hardcoded to specific cents)
        self.assertGreater(gross, 1.4e9, "Gross sales should exceed $1.4B")
        self.assertLess(gross, 1.6e9, "Gross sales should not exceed $1.6B")
        self.assertGreater(returns, 2.0e6, "Returns should exceed $2M")
        self.assertGreater(net, 1.2e9, "Net sales should exceed $1.2B")
        self.assertLess(net, 1.3e9, "Net sales should not exceed $1.3B")
        
        # Gross Margin = Net - COGS exactly (within floating-point tolerance)
        self.assertAlmostEqual(margin, net - cogs, delta=1.0,
                               msg="Gross Margin != Net Sales - COGS")
        
        # GTN Realization Rate should be between 80-90%
        gtn_realization = net / gross * 100
        self.assertGreater(gtn_realization, 80.0, "GTN realization too low")
        self.assertLess(gtn_realization, 90.0, "GTN realization too high")

    def test_returns_and_reverse_logistics_logic(self):
        """Audit 3: Returns have net_units < 0, positive return_value_usd, and explicit return reasons."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) 
            FROM fact_sales 
            WHERE net_units < 0 AND (return_value_usd <= 0 OR return_reason IS NULL OR return_reason = 'N/A - Standard Sale');
        """)
        invalid_returns = cur.fetchone()[0]
        self.assertEqual(invalid_returns, 0, "Found invalid return transactions with missing reason or non-positive value.")

    def test_referential_integrity_all_dimensions(self):
        """Audit 4: Ensure zero orphaned foreign keys across all 7 dimensions."""
        dims = [
            ("dim_date", "date_key"),
            ("dim_product", "product_key"),
            ("dim_geography", "geography_key"),
            ("dim_customer", "customer_key"),
            ("dim_distributor", "distributor_key"),
            ("dim_sales_rep", "sales_rep_key"),
            ("dim_channel", "channel_key"),
        ]
        cur = self.conn.cursor()
        for table, key in dims:
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM fact_sales f 
                LEFT JOIN {table} d ON f.{key} = d.{key} 
                WHERE d.{key} IS NULL;
            """)
            orphans = cur.fetchone()[0]
            self.assertEqual(orphans, 0, f"Referential integrity failure: {orphans} orphaned keys on {table}.{key}")

    def test_product_abc_pareto_math(self):
        """Audit 5: Top 4 products generate ~64% of revenue (Pareto concentration)."""
        cur = self.conn.cursor()
        cur.execute("""
            WITH prod_rev AS (
                SELECT product_key, SUM(net_sales_usd) AS rev
                FROM fact_sales
                GROUP BY product_key
            )
            SELECT rev * 100.0 / (SELECT SUM(rev) FROM prod_rev) AS share
            FROM prod_rev
            ORDER BY rev DESC;
        """)
        shares = [r[0] for r in cur.fetchall()]
        top4_share = sum(shares[:4])
        # Pareto: top 4 of 9 products should account for >60% of revenue
        self.assertGreater(top4_share, 60.0, "Top 4 products should generate >60% of revenue")
        self.assertLess(top4_share, 70.0, "Top 4 products should not exceed 70% — verify data distribution")

    def test_distributor_concentration_math(self):
        """Audit 6: Top 3 distributor share is verified as reasonable."""
        cur = self.conn.cursor()
        cur.execute("""
            WITH dist_rev AS (
                SELECT distributor_key, SUM(net_sales_usd) AS rev
                FROM fact_sales
                GROUP BY distributor_key
            )
            SELECT rev * 100.0 / (SELECT SUM(rev) FROM dist_rev) AS share
            FROM dist_rev
            ORDER BY rev DESC;
        """)
        shares = [r[0] for r in cur.fetchall()]
        top3_share = sum(shares[:3])
        # Top 3 of 6 distributors should hold >60% of volume
        self.assertGreater(top3_share, 60.0, "Top 3 distributor share should exceed 60%")
        self.assertLess(top3_share, 85.0, "Top 3 distributor share should not exceed 85%")

    def test_sales_force_productivity_math(self):
        """Audit 7: Commercial team headcount-normalized productivity."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT r.sales_team, COUNT(DISTINCT r.sales_rep_id), SUM(f.net_sales_usd) / COUNT(DISTINCT r.sales_rep_id)
            FROM fact_sales f
            JOIN dim_sales_rep r ON f.sales_rep_key = r.sales_rep_key
            GROUP BY r.sales_team
            ORDER BY 3 DESC;
        """)
        rows = cur.fetchall()
        self.assertEqual(len(rows), 4, "Expected 4 commercial teams.")
        for team, reps, rev_per_rep in rows:
            self.assertEqual(reps, 6, f"Team {team} should have exactly 6 reps, found {reps}")
            self.assertGreater(rev_per_rep, 4.0e7, f"Rev per rep for {team} should exceed $40M")

    def test_customer_rfm_coverage(self):
        """Audit 8: All 120 customers are active in the fact table."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT customer_key) FROM fact_sales;")
        active_customers = cur.fetchone()[0]
        self.assertEqual(active_customers, 120, "All 120 customers must be active.")

    def test_sql_python_kpi_reconciliation(self):
        """Audit 9: SQL total net sales matches Python CSV sum within tolerance."""
        cur = self.conn.cursor()
        cur.execute("SELECT ROUND(SUM(net_sales_usd), 2) FROM fact_sales;")
        sql_net = cur.fetchone()[0]
        py_net = round(float(self.df_csv["net_sales_usd"].sum()), 2)
        self.assertAlmostEqual(sql_net, py_net, delta=1.0,
                               msg=f"SQL Net ({sql_net}) != Python Net ({py_net})")

    def test_forecasting_evaluation_consistency(self):
        """Audit 10: Forecast evaluation JSON exists and contains all expected models."""
        eval_path = os.path.join(BASE_DIR, "outputs", "metrics", "forecast_model_evaluation.json")
        self.assertTrue(os.path.exists(eval_path), "Evaluation metrics JSON must exist.")
        
        with open(eval_path, "r") as f:
            metrics = json.load(f)
        
        # Verify all expected models are present
        expected_models = [
            "Baseline_Naive_Persistence",
            "Baseline_6Month_Moving_Average",
            "Baseline_Seasonal_Naive",
            "Holt_Winters_Exponential_Smoothing",
            "SARIMAX_1_1_1",
        ]
        for model in expected_models:
            self.assertIn(model, metrics, f"Missing model evaluation: {model}")
        
        # Verify Holt-Winters champion beats naive baseline
        hw = metrics["Holt_Winters_Exponential_Smoothing"]
        naive = metrics["Baseline_Naive_Persistence"]
        self.assertLess(hw["MAPE_pct"], naive["MAPE_pct"],
                        "Holt-Winters should have lower MAPE than naive persistence")
        
        # Verify rolling CV results exist
        self.assertIn("Holt_Winters_Rolling_CV", metrics, "Missing rolling CV for Holt-Winters")
        self.assertIn("SARIMAX_Rolling_CV", metrics, "Missing rolling CV for SARIMAX")

    def test_date_range_boundaries(self):
        """Audit 11: Edge case — all transactions fall within 2023-01-01 to 2025-12-31."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT MIN(d.full_date), MAX(d.full_date)
            FROM fact_sales f
            JOIN dim_date d ON f.date_key = d.date_key;
        """)
        min_date, max_date = cur.fetchone()
        self.assertGreaterEqual(min_date, "2023-01-01", "Earliest transaction before 2023-01-01")
        self.assertLessEqual(max_date, "2025-12-31", "Latest transaction after 2025-12-31")

    def test_discount_rate_sanity_bounds(self):
        """Audit 12: Edge case — all discount rates are between 2% and 40%."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM fact_sales
            WHERE contract_discount_pct < 2.0 OR contract_discount_pct > 40.0;
        """)
        out_of_range = cur.fetchone()[0]
        self.assertEqual(out_of_range, 0,
                         f"{out_of_range} rows have discount rates outside [2%, 40%]")

    def test_data_type_consistency(self):
        """Audit 13: Edge case — critical numeric columns have no NULL values."""
        cur = self.conn.cursor()
        numeric_cols = ["units_ordered", "units_returned", "net_units",
                        "gross_sales_usd", "net_sales_usd", "cogs_usd"]
        for col in numeric_cols:
            cur.execute(f"SELECT COUNT(*) FROM fact_sales WHERE {col} IS NULL;")
            nulls = cur.fetchone()[0]
            self.assertEqual(nulls, 0, f"Found {nulls} NULLs in fact_sales.{col}")

if __name__ == "__main__":
    unittest.main()
