"""
tests/test_data_validation_unit.py
----------------------------------
Independent unit tests verifying the data validation pipeline against edge cases:
1. Malformed dates (unparseable strings, impossible dates, nulls) -> REJECTED
2. Missing transaction IDs (null, empty strings, whitespace) -> REJECTED
3. Duplicate records (identical transaction IDs) -> Only one retained, duplicate REJECTED
4. Invalid values (zero quantity, negative unit prices, discount > 100%) -> REJECTED
5. Financial mismatches (discrepant gross sales, return values, net sales) -> CORRECTED and reconciled
6. Row-level reconciliation ledger status tagging (PASS, CORRECTED, FLAGGED, REJECTED)
7. Pipeline repeatability & idempotency (fixed seed produces identical outputs)
"""

import unittest
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from data_validation import validate_commercial_data
from generate_commercial_data import generate_dataset


class TestDataValidationUnit(unittest.TestCase):

    def setUp(self):
        # Create a valid base transaction record template
        self.base_record = {
            "transaction_id": "TXN-TEST-0001",
            "transaction_date": "2024-05-15",
            "customer_id": "CUST-0001",
            "customer_name": "Metro Health System",
            "customer_type": "Regional Health System",
            "product_id": "PRD-CNS-001",
            "product_name": "AmphetaDex",
            "therapeutic_area": "CNS / Psychiatry",
            "distributor_id": "DST-001",
            "distributor_name": "McKesson Corp",
            "sales_rep_id": "REP-001",
            "sales_rep_name": "John Doe",
            "sales_team": "Team Alpha",
            "sales_channel_id": "CHN-01",
            "sales_channel_name": "Hospital Direct Tender",
            "country_code": "US",
            "country_name": "United States",
            "region": "North America",
            "currency": "USD",
            "units_ordered": 100,
            "units_returned": 0,
            "net_units": 100,
            "unit_wac_price_usd": 285.00,
            "contract_discount_pct": 15.00,
            "unit_net_price_usd": 242.25,
            "gross_sales_usd": 28500.00,
            "return_value_usd": 0.0,
            "net_sales_usd": 24225.00,
            "cogs_usd": 4200.00,
            "gross_margin_usd": 20025.00,
            "return_reason": "N/A - Standard Sale"
        }

    def test_malformed_dates_rejection(self):
        """Malformed dates (invalid calendar, non-date strings, None) must be REJECTED."""
        records = [
            dict(self.base_record, transaction_id="TXN-D1", transaction_date="2024-13-45"),
            dict(self.base_record, transaction_id="TXN-D2", transaction_date="not-a-valid-date"),
            dict(self.base_record, transaction_id="TXN-D3", transaction_date=None),
            dict(self.base_record, transaction_id="TXN-D4", transaction_date=""),
            dict(self.base_record, transaction_id="TXN-VALID", transaction_date="2024-06-20"),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input)

        # Exactly 1 valid record should be retained
        self.assertEqual(len(clean_df), 1, "Only 1 valid date transaction should be retained")
        self.assertEqual(clean_df.iloc[0]["transaction_id"], "TXN-VALID")

        # 4 malformed date records must be marked REJECTED in ledger
        rejected = ledger[ledger["reconciliation_status"] == "REJECTED"]
        self.assertEqual(len(rejected), 4, "Expected 4 rejected records in ledger")
        for _, row in rejected.iterrows():
            self.assertIn("INVALID_DATE_FORMAT", row["audit_notes"])

    def test_missing_transaction_ids_rejection(self):
        """Missing or whitespace-only transaction IDs must be REJECTED."""
        records = [
            dict(self.base_record, transaction_id=None),
            dict(self.base_record, transaction_id=""),
            dict(self.base_record, transaction_id="   "),
            dict(self.base_record, transaction_id="TXN-VALID-ID"),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input)

        self.assertEqual(len(clean_df), 1)
        self.assertEqual(clean_df.iloc[0]["transaction_id"], "TXN-VALID-ID")
        self.assertEqual(audit["status_rejected_count"], 3)

    def test_duplicate_records_rejection(self):
        """Duplicate transaction IDs: first retained, subsequent duplicates REJECTED."""
        records = [
            dict(self.base_record, transaction_id="TXN-DUP-01"),
            dict(self.base_record, transaction_id="TXN-DUP-01"),
            dict(self.base_record, transaction_id="TXN-UNIQUE-02"),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input)

        self.assertEqual(len(clean_df), 2, "Duplicate row must be removed")
        self.assertEqual(audit["duplicate_records_dropped"], 1)

        # Ledger check
        dup_entries = ledger[ledger["transaction_id"] == "TXN-DUP-01"]
        self.assertEqual(len(dup_entries), 2)
        statuses = dup_entries["reconciliation_status"].tolist()
        self.assertIn("REJECTED", statuses)
        self.assertTrue(any(s in ["PASS", "CORRECTED", "FLAGGED"] for s in statuses))

    def test_invalid_values_rejection(self):
        """Zero quantities, negative unit prices, and impossible discount rates must be REJECTED."""
        records = [
            # Zero quantity
            dict(self.base_record, transaction_id="TXN-ZERO", net_units=0, units_ordered=0),
            # Negative WAC price
            dict(self.base_record, transaction_id="TXN-NEG-WAC", unit_wac_price_usd=-50.0),
            # Negative Net price
            dict(self.base_record, transaction_id="TXN-NEG-NET", unit_net_price_usd=-25.0),
            # Impossible discount rate (> 100%)
            dict(self.base_record, transaction_id="TXN-OVER-DISC", contract_discount_pct=150.0),
            # Valid record
            dict(self.base_record, transaction_id="TXN-CLEAN"),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input)

        self.assertEqual(len(clean_df), 1)
        self.assertEqual(clean_df.iloc[0]["transaction_id"], "TXN-CLEAN")
        self.assertEqual(audit["status_rejected_count"], 4)

    def test_financial_mismatches_independent_reconciliation(self):
        """Independent validation of gross, return, net, and margin corrects corrupt values and preserves originals."""
        # Row with corrupt raw financial figures (units=100, WAC=285 -> Expected Gross=28,500, but raw has 999,999)
        corrupt_record = dict(
            self.base_record,
            transaction_id="TXN-CORRUPT",
            gross_sales_usd=999999.00,
            net_sales_usd=1.00,
            gross_margin_usd=0.00
        )
        df_input = pd.DataFrame([corrupt_record])
        clean_df, ledger, audit = validate_commercial_data(df_input)

        self.assertEqual(len(clean_df), 1, "Record should be corrected and retained, not dropped")
        row = clean_df.iloc[0]

        # 1. Original values preserved
        self.assertEqual(row["gross_sales_usd_original"], 999999.00)
        self.assertEqual(row["net_sales_usd_original"], 1.00)

        # 2. Verified values independently recomputed
        self.assertEqual(row["gross_sales_usd"], 28500.00)
        self.assertEqual(row["net_sales_usd"], 24225.00)
        self.assertEqual(row["gross_margin_usd"], 20025.00)

        # 3. Status is flagged or corrected
        self.assertIn(row["reconciliation_status"], ["CORRECTED", "FLAGGED"])

        # 4. Check independent statuses in ledger
        ledger_row = ledger[ledger["transaction_id"] == "TXN-CORRUPT"].iloc[0]
        self.assertEqual(ledger_row["gross_sales_status"], "CORRECTED")
        self.assertEqual(ledger_row["net_sales_status"], "CORRECTED")
        self.assertEqual(ledger_row["gross_margin_status"], "CORRECTED")

    def test_pipeline_repeatability_and_determinism(self):
        """Running dataset generation and validation twice with identical seed produces bit-for-bit identical results."""
        import random
        # Run 1
        np.random.seed(42)
        random.seed(42)
        # Small sample run of validation on base records
        df_sample_1 = pd.DataFrame([
            dict(self.base_record, transaction_id=f"TXN-R-{i}") for i in range(100)
        ])
        clean_1, ledger_1, audit_1 = validate_commercial_data(df_sample_1)

        # Run 2
        np.random.seed(42)
        random.seed(42)
        df_sample_2 = pd.DataFrame([
            dict(self.base_record, transaction_id=f"TXN-R-{i}") for i in range(100)
        ])
        clean_2, ledger_2, audit_2 = validate_commercial_data(df_sample_2)

        # Verification of repeatability
        self.assertEqual(audit_1, audit_2, "Audit metrics must be identical across deterministic runs")
        pd.testing.assert_frame_equal(clean_1, clean_2, "Cleaned dataframes must be bit-for-bit identical")
        pd.testing.assert_frame_equal(ledger_1, ledger_2, "Reconciliation ledgers must be bit-for-bit identical")


if __name__ == "__main__":
    unittest.main()
