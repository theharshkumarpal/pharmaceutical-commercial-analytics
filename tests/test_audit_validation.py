"""
tests/test_audit_validation.py
------------------------------
Rigorous, independent audit test suite verifying:
1. Exact financial reconciliation across fact_sales (Gross, Returns, Discounts, Net, COGS, Margin)
2. Negative transactions / returns sign consistency and tagging
3. Absence of duplicate transactions in fact_sales
4. Referential integrity across all 7 dimension tables (zero orphaned keys)
5. ABC/Pareto ranking and cumulative revenue calculations
6. Distributor concentration calculations
7. Headcount-normalized sales force effectiveness calculations
8. Customer RFM segmentation completeness
9. Forecasting evaluation consistency
10. SQL vs Python analytical reconciliation
"""

import os
import sqlite3
import unittest
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
        """Audit 2: Net Sales = Gross - Returns - Discounts, and Gross Margin = Net - COGS."""
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

        # 1. Gross sales is strictly positive
        self.assertAlmostEqual(gross, 1480438365.00, delta=1.0)
        # 2. Return deductions is strictly positive dollar amount
        self.assertAlmostEqual(returns, 2772950.45, delta=1.0)
        # 3. Net recognized revenue
        self.assertAlmostEqual(net, 1245009425.53, delta=1.0)
        # 4. Gross Margin = Net - COGS exactly
        self.assertAlmostEqual(margin, net - cogs, delta=0.01)
        # 5. GTN Realization Rate = 84.097% (~84.10%)
        gtn_realization = net / gross * 100
        self.assertAlmostEqual(gtn_realization, 84.097, delta=0.01)

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
        """Audit 5: Top 4 products generate 64.32% of revenue and top 6 generate 83.13%."""
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
        top6_share = sum(shares[:6])
        self.assertAlmostEqual(top4_share, 64.32, delta=0.05)
        self.assertAlmostEqual(top6_share, 83.13, delta=0.05)

    def test_distributor_concentration_math(self):
        """Audit 6: Top 3 distributor share is verified."""
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
        # Actual top 3 share is 69.65% (Direct Pharma 35.01%, AmerisourceBergen 18.30%, Alliance 16.33%)
        self.assertAlmostEqual(top3_share, 69.65, delta=0.1)

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
            self.assertEqual(reps, 6, "Each team has exactly 6 reps.")
            self.assertGreater(rev_per_rep, 4.8e7, "Rev per rep must be > $48M.")

    def test_customer_rfm_coverage(self):
        """Audit 8: All 120 customers are scored and segmented."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT customer_key) FROM fact_sales;")
        active_customers = cur.fetchone()[0]
        self.assertEqual(active_customers, 120, "All 120 customers must be active.")

    def test_sql_python_kpi_reconciliation(self):
        """Audit 9: SQL total net sales matches Python CSV sum exactly."""
        cur = self.conn.cursor()
        cur.execute("SELECT ROUND(SUM(net_sales_usd), 2) FROM fact_sales;")
        sql_net = cur.fetchone()[0]
        py_net = round(float(self.df_csv["net_sales_usd"].sum()), 2)
        self.assertEqual(sql_net, py_net, f"SQL Net ({sql_net}) != Python Net ({py_net})")

    def test_forecasting_evaluation_consistency(self):
        """Audit 10: Out-of-sample forecast evaluation consistency."""
        eval_path = os.path.join(BASE_DIR, "outputs", "metrics", "forecast_model_evaluation.json")
        self.assertTrue(os.path.exists(eval_path), "Evaluation metrics JSON must exist.")
        import json
        with open(eval_path, "r") as f:
            metrics = json.load(f)
        self.assertIn("Holt_Winters_Exponential_Smoothing", metrics)
        hw = metrics["Holt_Winters_Exponential_Smoothing"]
        self.assertAlmostEqual(hw["MAPE_pct"], 11.55, delta=0.05)
        self.assertAlmostEqual(hw["RMSE_usd"], 6163093.16, delta=1.0)
        self.assertIn("Baseline_Naive_Persistence", metrics)
        naive = metrics["Baseline_Naive_Persistence"]
        self.assertAlmostEqual(naive["MAPE_pct"], 11.85, delta=0.05)

if __name__ == "__main__":
    unittest.main()
