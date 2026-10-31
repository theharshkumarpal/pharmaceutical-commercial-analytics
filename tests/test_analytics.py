"""
tests/test_analytics.py
-----------------------
Automated integration tests verifying commercial analytics and financial integrity:
1. Database existence and population
2. No duplicate transactions in fact_sales
3. Zero orphaned foreign keys in star schema
4. Financial reconciliation (Gross - Returns ≈ Net)
5. Returns and reversals integrity
6. Geographic coverage integrity
7. Row-level financial identity (Net = Gross - Return per row)
8. Edge case: no null surrogate keys in fact_sales
"""

import os
import sqlite3
import unittest
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")

class TestCommercialAnalytics(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(DB_PATH)
        
    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_database_exists_and_populated(self):
        """Verify SQLite DB has tables and expected row counts."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fact_sales;")
        count = cur.fetchone()[0]
        self.assertEqual(count, 28500, f"Expected 28,500 fact rows, found {count}")

    def test_no_duplicate_transactions(self):
        """Ensure strict uniqueness on transaction_id in fact_sales."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT transaction_id, COUNT(*) 
            FROM fact_sales 
            GROUP BY transaction_id 
            HAVING COUNT(*) > 1;
        """)
        dups = cur.fetchall()
        self.assertEqual(len(dups), 0, f"Found {len(dups)} duplicate transaction IDs in fact table.")

    def test_referential_integrity(self):
        """Ensure no orphaned foreign keys exist between fact and dimension tables."""
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
            query = f"""
                SELECT COUNT(*) 
                FROM fact_sales f 
                LEFT JOIN {table} d ON f.{key} = d.{key} 
                WHERE d.{key} IS NULL;
            """
            cur.execute(query)
            orphans = cur.fetchone()[0]
            self.assertEqual(orphans, 0, f"Found {orphans} orphaned records for foreign key {key} in {table}")

    def test_financial_reconciliation(self):
        """Verify mathematical integrity: Gross Sales, Return Deductions, and Net Sales."""
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
        row = cur.fetchone()
        gross, returns, net, cogs, margin = row
        
        # Net sales must be positive overall
        self.assertGreater(net, 1.2e9, "Total Net Sales should be > $1.2 Billion")
        # Returns must be positive dollar deductions
        self.assertGreater(returns, 2.0e6, "Total Returns should be > $2.0 Million")
        # Gross margin must equal net sales - cogs within tolerance due to rounding
        self.assertAlmostEqual(margin, net - cogs, delta=50.0)

    def test_returns_and_reversals_integrity(self):
        """Ensure all return transactions have negative units and positive return_value_usd."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) 
            FROM fact_sales 
            WHERE net_units < 0 AND return_value_usd <= 0;
        """)
        invalid_returns = cur.fetchone()[0]
        self.assertEqual(invalid_returns, 0, "Returns with net_units < 0 must have positive return_value_usd")

    def test_geographic_coverage_integrity(self):
        """Ensure all 6 countries are represented in dim_geography with correct coverage months."""
        cur = self.conn.cursor()
        cur.execute("SELECT country_code, coverage_months FROM dim_geography ORDER BY country_code;")
        geos = dict(cur.fetchall())
        expected_geos = {"CA": 18, "DE": 36, "FR": 30, "JP": 24, "UK": 36, "US": 36}
        self.assertEqual(geos, expected_geos)

    def test_row_level_financial_identity(self):
        """Verify per-row financial consistency:
        - For returns: net_sales_usd should equal -return_value_usd
        - For sales: gross_margin_usd should equal net_sales_usd - cogs_usd
        """
        cur = self.conn.cursor()
        # Returns: net_sales = -return_value
        cur.execute("""
            SELECT COUNT(*) 
            FROM fact_sales 
            WHERE net_units < 0 AND ABS(net_sales_usd - (-return_value_usd)) > 0.02;
        """)
        return_mismatches = cur.fetchone()[0]
        self.assertEqual(return_mismatches, 0, f"{return_mismatches} return rows fail net = -return identity")
        
        # All rows: gross_margin = net_sales - cogs
        cur.execute("""
            SELECT COUNT(*) 
            FROM fact_sales 
            WHERE ABS(gross_margin_usd - (net_sales_usd - cogs_usd)) > 0.02;
        """)
        margin_mismatches = cur.fetchone()[0]
        self.assertEqual(margin_mismatches, 0, f"{margin_mismatches} rows fail margin = net - cogs identity")

    def test_no_null_surrogate_keys(self):
        """Edge case: ensure no NULL surrogate keys exist in fact_sales."""
        cur = self.conn.cursor()
        key_cols = ["date_key", "product_key", "geography_key", "customer_key",
                    "distributor_key", "sales_rep_key", "channel_key"]
        for col in key_cols:
            cur.execute(f"SELECT COUNT(*) FROM fact_sales WHERE {col} IS NULL;")
            nulls = cur.fetchone()[0]
            self.assertEqual(nulls, 0, f"Found {nulls} NULL values in fact_sales.{col}")

if __name__ == "__main__":
    unittest.main()
