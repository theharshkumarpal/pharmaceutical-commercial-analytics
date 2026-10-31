"""
tests/test_sql_etl_consistency.py
---------------------------------
Independent test comparing SQL-only ETL vs Python ETL output:
1. Builds a temporary SQLite database directly executing:
   - sql/02_schema.sql
   - sql/03_transformations.sql
2. Ingests cleaned transactions into staging and runs SQL transformations.
3. Compares the resulting database against the Python preprocessing target (pharma_commercial.db):
   - Table row counts (all 7 dimensions and fact_sales)
   - Fact table financial totals to the exact cent:
     * gross_sales_usd
     * contract_discount_usd
     * return_value_usd
     * net_sales_usd
     * cogs_usd
     * gross_margin_usd
   - Uniqueness (zero duplicate transaction_ids)
   - Foreign key integrity (zero orphaned keys)
   - Reconciliation status distribution (PASS and CORRECTED counts)
"""

import unittest
import sqlite3
import os
import tempfile
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROD_DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
CLEAN_CSV_PATH = os.path.join(BASE_DIR, "data", "processed", "cleaned_sales.csv")
SCHEMA_SQL = os.path.join(BASE_DIR, "sql", "02_schema.sql")
TRANSFORM_SQL = os.path.join(BASE_DIR, "sql", "03_transformations.sql")


class TestSqlEtlConsistency(unittest.TestCase):

    def setUp(self):
        self.assertTrue(os.path.exists(PROD_DB_PATH), f"Production database {PROD_DB_PATH} must exist")
        self.assertTrue(os.path.exists(CLEAN_CSV_PATH), f"Cleaned CSV {CLEAN_CSV_PATH} must exist")

    def test_sql_etl_and_python_etl_consistency(self):
        """Build temp DB strictly via SQL scripts and verify exact equivalence with Python DB."""
        clean_df = pd.read_csv(CLEAN_CSV_PATH)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            temp_db_path = tmp_db.name

        try:
            conn = sqlite3.connect(temp_db_path)

            # 1. Execute 02_schema.sql
            with open(SCHEMA_SQL, "r") as f:
                conn.executescript(f.read())

            # 2. Stage cleaned data into stg_commercial_sales
            clean_df.to_sql("stg_commercial_sales", conn, if_exists="append", index=False)

            # 3. Execute 03_transformations.sql
            with open(TRANSFORM_SQL, "r") as f:
                conn.executescript(f.read())

            # 4. Compare with Production Database
            prod_conn = sqlite3.connect(PROD_DB_PATH)

            # A. Record Counts for All Tables
            tables = [
                "dim_date", "dim_geography", "dim_product", "dim_customer",
                "dim_distributor", "dim_sales_rep", "dim_channel", "fact_sales"
            ]
            for table in tables:
                sql_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                prod_count = prod_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(sql_count, prod_count, f"Row count mismatch on {table}: SQL={sql_count}, Prod={prod_count}")

            # B. Fact Table Financial Totals (Exact Cent)
            financial_cols = [
                "gross_sales_usd",
                "contract_discount_usd",
                "return_value_usd",
                "net_sales_usd",
                "cogs_usd",
                "gross_margin_usd",
            ]
            for col in financial_cols:
                sql_sum = conn.execute(f"SELECT ROUND(SUM({col}), 2) FROM fact_sales").fetchone()[0]
                prod_sum = prod_conn.execute(f"SELECT ROUND(SUM({col}), 2) FROM fact_sales").fetchone()[0]
                self.assertAlmostEqual(
                    sql_sum, prod_sum, places=2,
                    msg=f"Financial total mismatch on {col}: SQL={sql_sum}, Prod={prod_sum}"
                )

            # C. Uniqueness check
            dup_check = conn.execute("""
                SELECT transaction_id, COUNT(*)
                FROM fact_sales
                GROUP BY transaction_id
                HAVING COUNT(*) > 1
            """).fetchall()
            self.assertEqual(len(dup_check), 0, "SQL ETL must produce zero duplicate transaction IDs")

            # D. Foreign key referential integrity
            fk_checks = [
                ("date_key", "dim_date"),
                ("geography_key", "dim_geography"),
                ("product_key", "dim_product"),
                ("customer_key", "dim_customer"),
                ("distributor_key", "dim_distributor"),
                ("sales_rep_key", "dim_sales_rep"),
                ("channel_key", "dim_channel"),
            ]
            for fk, dim_tbl in fk_checks:
                orphans = conn.execute(f"""
                    SELECT COUNT(*)
                    FROM fact_sales f
                    LEFT JOIN {dim_tbl} d ON f.{fk} = d.{fk}
                    WHERE d.{fk} IS NULL
                """).fetchone()[0]
                self.assertEqual(orphans, 0, f"Found {orphans} orphaned keys on {fk} -> {dim_tbl}")

            # E. Status Distributions
            for status_col in ["reconciliation_status", "financial_reconciliation_status", "data_quality_status", "anomaly_flag", "cogs_source_type"]:
                sql_dist = dict(conn.execute(f"SELECT {status_col}, COUNT(*) FROM fact_sales GROUP BY {status_col}").fetchall())
                prod_dist = dict(prod_conn.execute(f"SELECT {status_col}, COUNT(*) FROM fact_sales GROUP BY {status_col}").fetchall())
                self.assertEqual(sql_dist, prod_dist, f"Distribution mismatch on {status_col}: SQL={sql_dist}, Prod={prod_dist}")

            # F. Strict Row-Level Equality on All Shared Business-Critical Fields
            critical_cols = [
                "transaction_id",
                "contract_discount_usd",
                "reconciliation_status",
                "financial_reconciliation_status",
                "data_quality_status",
                "anomaly_flag",
                "cogs_source_type",
                "gross_sales_usd",
                "return_value_usd",
                "net_sales_usd",
                "cogs_usd",
                "gross_margin_usd",
            ]
            sql_rows = pd.read_sql_query(f"SELECT {', '.join(critical_cols)} FROM fact_sales ORDER BY transaction_id", conn)
            prod_rows = pd.read_sql_query(f"SELECT {', '.join(critical_cols)} FROM fact_sales ORDER BY transaction_id", prod_conn)

            # Assert identical row counts
            self.assertEqual(len(sql_rows), len(prod_rows), "Row counts must be identical")
            self.assertEqual(len(sql_rows), 28500, "Fact table must have exactly 28,500 rows")

            # Check zero missing values across all critical columns
            for col in critical_cols:
                self.assertEqual(sql_rows[col].isna().sum(), 0, f"Found unexpected NULLs in SQL {col}")
                self.assertEqual(prod_rows[col].isna().sum(), 0, f"Found unexpected NULLs in Prod {col}")

            # Categorical string exact match
            for col in ["transaction_id", "reconciliation_status", "financial_reconciliation_status", "data_quality_status", "anomaly_flag", "cogs_source_type"]:
                mismatches = (sql_rows[col] != prod_rows[col]).sum()
                self.assertEqual(mismatches, 0, f"Found {mismatches} row-level mismatches in {col}")

            # Numeric exact match
            for col in ["contract_discount_usd", "gross_sales_usd", "return_value_usd", "net_sales_usd", "cogs_usd", "gross_margin_usd"]:
                diffs = (sql_rows[col] - prod_rows[col]).abs()
                max_diff = diffs.max()
                self.assertLessEqual(max_diff, 1e-4, f"Max difference in {col} exceeded tolerance: {max_diff}")

            conn.close()
            prod_conn.close()

        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


if __name__ == "__main__":
    unittest.main()
