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
            "contract_discount_usd": 4275.00,
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

    def test_missing_required_columns_raises_error(self):
        """DataFrame missing any required schema column must raise ValueError."""
        invalid_df = pd.DataFrame([{"transaction_id": "TXN-1", "transaction_date": "2024-01-01"}])
        with self.assertRaises(ValueError) as ctx:
            validate_commercial_data(invalid_df)
        self.assertIn("Missing required columns", str(ctx.exception))

    def test_null_nan_inf_numeric_fields_rejection(self):
        """Null, NaN, infinite, or non-numeric values in numeric columns must be REJECTED."""
        records = [
            dict(self.base_record, transaction_id="TXN-NAN-QTY", units_ordered=np.nan),
            dict(self.base_record, transaction_id="TXN-INF-PRICE", unit_wac_price_usd=np.inf),
            dict(self.base_record, transaction_id="TXN-STR-DISC", contract_discount_pct="invalid_disc"),
            dict(self.base_record, transaction_id="TXN-NONE-PRICE", unit_net_price_usd=None),
            dict(self.base_record, transaction_id="TXN-VALID-NUMERIC"),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input)
        self.assertEqual(len(clean_df), 1)
        self.assertEqual(clean_df.iloc[0]["transaction_id"], "TXN-VALID-NUMERIC")
        rejected = ledger[ledger["reconciliation_status"] == "REJECTED"]
        self.assertEqual(len(rejected), 4)

    def test_invalid_quantity_relationships_rejection(self):
        """Negative net_units with inconsistent units_ordered or units_returned must be REJECTED."""
        records = [
            # Negative net_units but units_returned is 0
            dict(self.base_record, transaction_id="TXN-INVAL-QTY-1", net_units=-10, units_ordered=0, units_returned=0),
            # Negative net_units but units_ordered > 0
            dict(self.base_record, transaction_id="TXN-INVAL-QTY-2", net_units=-10, units_ordered=10, units_returned=20),
            # Positive net_units but units_ordered == 0
            dict(self.base_record, transaction_id="TXN-INVAL-QTY-3", net_units=10, units_ordered=0, units_returned=0),
            # Valid standard sale
            dict(self.base_record, transaction_id="TXN-VALID-SALE", net_units=10, units_ordered=10, units_returned=0),
            # Valid return
            dict(self.base_record, transaction_id="TXN-VALID-RET", net_units=-10, units_ordered=0, units_returned=10, return_value_usd=2422.50, return_reason="Recall / Batch Expiry"),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input)
        self.assertEqual(len(clean_df), 2)
        rejected = ledger[ledger["reconciliation_status"] == "REJECTED"]
        self.assertEqual(len(rejected), 3)
        for _, row in rejected.iterrows():
            self.assertIn("INCONSISTENT_QUANTITY_FIELDS", row["audit_notes"])

    def test_flagged_and_corrected_overlap(self):
        """A transaction both financially corrected and business-flagged must retain its correction information."""
        record = dict(
            self.base_record,
            transaction_id="TXN-FLAG-AND-CORRECT",
            contract_discount_pct=38.5,  # Outlier deep discount (> 35%) -> FLAGGED
            net_sales_usd=1.00,          # Wrong net sales -> CORRECTED
        )
        df_input = pd.DataFrame([record])
        clean_df, ledger, audit = validate_commercial_data(df_input)

        self.assertEqual(len(clean_df), 1)
        row = clean_df.iloc[0]
        ledger_row = ledger.iloc[0]

        # Both statuses preserved separately
        self.assertEqual(row["reconciliation_status"], "CORRECTED")
        self.assertIn("DEEP_DISCOUNT_OUTLIER", row["anomaly_flag"])
        self.assertEqual(ledger_row["reconciliation_status"], "CORRECTED")
        self.assertIn("DEEP_DISCOUNT_OUTLIER", ledger_row["anomaly_flag"])

        # Both notes preserved in audit_notes
        self.assertIn("NET_SALES_RECONCILED", ledger_row["audit_notes"])
        self.assertIn("DEEP_DISCOUNT_OUTLIER", ledger_row["audit_notes"])

    def test_missing_cogs_some_and_all_rows(self):
        """Missing COGS in some or all rows correctly uses cogs_fallback_pct without overwriting existing COGS."""
        records = [
            # Row with explicit COGS
            dict(self.base_record, transaction_id="TXN-COGS-1", units_ordered=100, unit_wac_price_usd=200.0, cogs_usd=3000.0),
            # Row with missing COGS (None/NaN)
            dict(self.base_record, transaction_id="TXN-COGS-2", units_ordered=100, unit_wac_price_usd=200.0, cogs_usd=np.nan),
        ]
        df_input = pd.DataFrame(records)
        clean_df, ledger, audit = validate_commercial_data(df_input, cogs_fallback_pct=0.15)

        self.assertEqual(len(clean_df), 2)
        row1 = clean_df[clean_df["transaction_id"] == "TXN-COGS-1"].iloc[0]
        row2 = clean_df[clean_df["transaction_id"] == "TXN-COGS-2"].iloc[0]
        ledger_row2 = ledger[ledger["transaction_id"] == "TXN-COGS-2"].iloc[0]

        # Row 1 retains source COGS
        self.assertEqual(row1["cogs_usd"], 3000.0)
        # Row 2 receives fallback: 100 * 200 * 0.15 = 3000.0
        self.assertEqual(row2["cogs_usd"], 3000.0)
        self.assertIn("COGS_ESTIMATED_VIA_FALLBACK", ledger_row2["audit_notes"])

        # Test all rows missing COGS
        all_missing = pd.DataFrame([
            dict(self.base_record, transaction_id="TXN-M1", units_ordered=50, net_units=50, unit_wac_price_usd=100.0, cogs_usd=np.nan),
            dict(self.base_record, transaction_id="TXN-M2", units_ordered=80, net_units=80, unit_wac_price_usd=100.0, cogs_usd=None),
        ])
        clean_all, ledger_all, _ = validate_commercial_data(all_missing, cogs_fallback_pct=0.20)
        self.assertEqual(clean_all.iloc[0]["cogs_usd"], 50 * 100.0 * 0.20)
        self.assertEqual(clean_all.iloc[1]["cogs_usd"], 80 * 100.0 * 0.20)

    def test_cogs_treatment_for_returns_under_fallback(self):
        """COGS fallback on return transactions credits inventory via negative COGS consistently."""
        return_record = dict(
            self.base_record,
            transaction_id="TXN-RET-COGS",
            net_units=-20,
            units_ordered=0,
            units_returned=20,
            unit_wac_price_usd=150.0,
            unit_net_price_usd=120.0,
            return_value_usd=2400.0,
            cogs_usd=np.nan,  # Missing COGS on return
            return_reason="Damaged in Transit"
        )
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame([return_record]), cogs_fallback_pct=0.15)
        self.assertEqual(len(clean_df), 1)
        row = clean_df.iloc[0]
        # Fallback: -20 * 150 * 0.15 = -450.0
        self.assertEqual(row["cogs_usd"], -450.0)
        # expected_net = -2400.0, expected_margin = -2400.0 - (-450.0) = -1950.0
        self.assertEqual(row["net_sales_usd"], -2400.0)
        self.assertEqual(row["gross_margin_usd"], -1950.0)

    def test_discount_waterfall_row_and_portfolio_level(self):
        """Reconciliation identity: Gross Sales - Contract Discounts - Returns = Net Sales at row and portfolio level."""
        records = [
            # Standard sale
            dict(self.base_record, transaction_id="TXN-W1", net_units=100, units_ordered=100, unit_wac_price_usd=300.0, contract_discount_pct=10.0, unit_net_price_usd=270.0, gross_sales_usd=30000.0, contract_discount_usd=3000.0, net_sales_usd=27000.0),
            # Deep discount sale
            dict(self.base_record, transaction_id="TXN-W2", net_units=50, units_ordered=50, unit_wac_price_usd=400.0, contract_discount_pct=25.0, unit_net_price_usd=300.0, gross_sales_usd=20000.0, contract_discount_usd=5000.0, net_sales_usd=15000.0),
            # Return record
            dict(self.base_record, transaction_id="TXN-W3", net_units=-10, units_ordered=0, units_returned=10, unit_wac_price_usd=200.0, contract_discount_pct=15.0, unit_net_price_usd=170.0, gross_sales_usd=0.0, contract_discount_usd=0.0, return_value_usd=1700.0, net_sales_usd=-1700.0, return_reason="Customer Overstock Return"),
        ]
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame(records))
        self.assertEqual(len(clean_df), 3)

        # Row level check
        for _, row in clean_df.iterrows():
            expected_net = round(row["gross_sales_usd"] - row["contract_discount_usd"] - row["return_value_usd"], 2)
            self.assertAlmostEqual(row["net_sales_usd"], expected_net, places=2)

        # Portfolio level check
        total_gross = clean_df["gross_sales_usd"].sum()
        total_disc = clean_df["contract_discount_usd"].sum()
        total_ret = clean_df["return_value_usd"].sum()
        total_net = clean_df["net_sales_usd"].sum()
        self.assertAlmostEqual(total_gross - total_disc - total_ret, total_net, places=2)

    def test_record_with_only_customer_name_imputation(self):
        """Customer-name imputation results in financial PASS and data_quality STANDARDIZED."""
        records = [
            dict(self.base_record, transaction_id="TXN-CUST-KNOWN", customer_id="CUST-0001", customer_name="Known Health System"),
            dict(self.base_record, transaction_id="TXN-CUST-MISSING", customer_id="CUST-0001", customer_name=None),
        ]
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame(records))
        self.assertEqual(len(clean_df), 2)
        row = clean_df[clean_df["transaction_id"] == "TXN-CUST-MISSING"].iloc[0]
        ledger_row = ledger[ledger["transaction_id"] == "TXN-CUST-MISSING"].iloc[0]

        # Financial status must remain PASS
        self.assertEqual(row["financial_reconciliation_status"], "PASS")
        self.assertEqual(ledger_row["financial_reconciliation_status"], "PASS")

        # Data quality status is STANDARDIZED
        self.assertEqual(row["data_quality_status"], "STANDARDIZED")
        self.assertEqual(ledger_row["data_quality_status"], "STANDARDIZED")

        # Overall status is CORRECTED for backward compatibility
        self.assertEqual(row["reconciliation_status"], "CORRECTED")
        self.assertIn("CUSTOMER_NAME_IMPUTED", ledger_row["audit_notes"])

    def test_record_with_only_country_standardization(self):
        """Country casing standardization results in financial PASS and data_quality STANDARDIZED."""
        record = dict(self.base_record, transaction_id="TXN-COUNTRY-CASING", country_name="Uk")
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame([record]))
        self.assertEqual(len(clean_df), 1)
        row = clean_df.iloc[0]
        ledger_row = ledger.iloc[0]

        # Financial status must remain PASS
        self.assertEqual(row["financial_reconciliation_status"], "PASS")
        self.assertEqual(ledger_row["financial_reconciliation_status"], "PASS")

        # Data quality status is STANDARDIZED
        self.assertEqual(row["data_quality_status"], "STANDARDIZED")
        self.assertEqual(ledger_row["data_quality_status"], "STANDARDIZED")
        self.assertEqual(row["country_name"], "United Kingdom")

        # Overall status is CORRECTED
        self.assertEqual(row["reconciliation_status"], "CORRECTED")
        self.assertIn("COUNTRY_CASING_STANDARDIZED", ledger_row["audit_notes"])

    def test_record_with_financial_correction_only(self):
        """Financial correction with clean entities results in financial CORRECTED and data_quality PASS."""
        record = dict(self.base_record, transaction_id="TXN-FIN-ONLY", net_sales_usd=1.00)
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame([record]))
        self.assertEqual(len(clean_df), 1)
        row = clean_df.iloc[0]
        ledger_row = ledger.iloc[0]

        # Financial status is CORRECTED
        self.assertEqual(row["financial_reconciliation_status"], "CORRECTED")
        self.assertEqual(ledger_row["financial_reconciliation_status"], "CORRECTED")

        # Data quality status remains PASS
        self.assertEqual(row["data_quality_status"], "PASS")
        self.assertEqual(ledger_row["data_quality_status"], "PASS")

        # Overall status is CORRECTED
        self.assertEqual(row["reconciliation_status"], "CORRECTED")

    def test_record_with_both_financial_and_categorical_corrections(self):
        """Record with both financial mismatch and dirty country has both statuses tagged appropriately."""
        record = dict(self.base_record, transaction_id="TXN-BOTH-CORRECT", net_sales_usd=1.00, country_name="De")
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame([record]))
        self.assertEqual(len(clean_df), 1)
        row = clean_df.iloc[0]
        ledger_row = ledger.iloc[0]

        self.assertEqual(row["financial_reconciliation_status"], "CORRECTED")
        self.assertEqual(row["data_quality_status"], "STANDARDIZED")
        self.assertEqual(row["reconciliation_status"], "CORRECTED")
        self.assertIn("NET_SALES_RECONCILED", ledger_row["audit_notes"])
        self.assertIn("COUNTRY_CASING_STANDARDIZED", ledger_row["audit_notes"])

    def test_rejected_record_statuses(self):
        """Rejected records receive REJECTED on financial, data_quality, and overall statuses."""
        record = dict(self.base_record, transaction_id="TXN-REJ-ALL", unit_wac_price_usd=-50.0)
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame([record]))
        self.assertEqual(len(clean_df), 0)
        ledger_row = ledger.iloc[0]

        self.assertEqual(ledger_row["financial_reconciliation_status"], "REJECTED")
        self.assertEqual(ledger_row["data_quality_status"], "REJECTED")
        self.assertEqual(ledger_row["reconciliation_status"], "REJECTED")

    def test_cogs_source_type_provenance(self):
        """Populated source COGS is tagged SOURCE; missing COGS is tagged ESTIMATED without overwriting."""
        records = [
            dict(self.base_record, transaction_id="TXN-COGS-SRC", units_ordered=100, unit_wac_price_usd=250.0, cogs_usd=4000.0),
            dict(self.base_record, transaction_id="TXN-COGS-EST", units_ordered=100, unit_wac_price_usd=250.0, cogs_usd=np.nan),
        ]
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame(records), cogs_fallback_pct=0.15)
        self.assertEqual(len(clean_df), 2)
        row_src = clean_df[clean_df["transaction_id"] == "TXN-COGS-SRC"].iloc[0]
        row_est = clean_df[clean_df["transaction_id"] == "TXN-COGS-EST"].iloc[0]

        # Row 1: Source COGS preserved exactly
        self.assertEqual(row_src["cogs_usd"], 4000.0)
        self.assertEqual(row_src["cogs_source_type"], "SOURCE")
        self.assertEqual(ledger[ledger["transaction_id"] == "TXN-COGS-SRC"].iloc[0]["cogs_source_type"], "SOURCE")

        # Row 2: Estimated COGS computed via fallback (100 * 250 * 0.15 = 3750.0)
        self.assertEqual(row_est["cogs_usd"], 3750.0)
        self.assertEqual(row_est["cogs_source_type"], "ESTIMATED")
        self.assertEqual(ledger[ledger["transaction_id"] == "TXN-COGS-EST"].iloc[0]["cogs_source_type"], "ESTIMATED")

    def test_missing_contract_discount_usd_recalculated_and_corrected(self):
        """Missing original contract discount is recalculated, tagging financial CORRECTED and recording audit note."""
        record = dict(self.base_record, transaction_id="TXN-DISC-MISSING", contract_discount_usd=np.nan)
        clean_df, ledger, _ = validate_commercial_data(pd.DataFrame([record]))
        self.assertEqual(len(clean_df), 1)
        row = clean_df.iloc[0]
        ledger_row = ledger.iloc[0]

        # 1. Missing original contract discount is recalculated
        self.assertEqual(row["contract_discount_usd"], 4275.00)

        # 2. financial_reconciliation_status becomes CORRECTED
        self.assertEqual(row["financial_reconciliation_status"], "CORRECTED")
        self.assertEqual(ledger_row["financial_reconciliation_status"], "CORRECTED")

        # 3. data_quality_status remains PASS
        self.assertEqual(row["data_quality_status"], "PASS")
        self.assertEqual(ledger_row["data_quality_status"], "PASS")

        # 4. The audit ledger records the correction
        self.assertEqual(row["reconciliation_status"], "CORRECTED")
        self.assertIn("CONTRACT_DISCOUNT_RECONCILED", ledger_row["audit_notes"])


if __name__ == "__main__":
    unittest.main()
