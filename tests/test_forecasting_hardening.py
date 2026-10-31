"""
tests/test_forecasting_hardening.py
-----------------------------------
Independent tests verifying forecasting robustness:
1. Missing monthly periods validation (raises ValueError).
2. Time-series observation count requirements (raises ValueError when < 24 periods or first origin < 13).
3. Explicit recording of model fit failures (fit_status FAILED, fit_failure_count > 0) rather than silent suppression.
"""

import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from revenue_forecasting import rolling_origin_cv, calc_metrics


class TestForecastingHardening(unittest.TestCase):

    def setUp(self):
        # Generate 36 synthetic monthly dates (2023-01 to 2025-12)
        dates = pd.date_range(start="2023-01-01", periods=36, freq="MS")
        # Synthetic upward trend with Q4 seasonal bump
        values = []
        for i, d in enumerate(dates):
            base = 25000000.0 + (i * 400000.0)
            if d.month in [10, 11, 12]:
                base += 5000000.0
            values.append(base)
        self.ts_series = pd.Series(values, index=dates)

    def test_missing_monthly_observations_detected(self):
        """Monthly continuity check detects missing calendar months and raises ValueError."""
        # Drop one month (e.g. June 2024)
        broken_series = self.ts_series.drop(pd.Timestamp("2024-06-01"))
        expected_dates = pd.date_range(start=broken_series.index.min(), end=broken_series.index.max(), freq="MS")

        self.assertNotEqual(len(broken_series), len(expected_dates))
        missing = expected_dates.difference(broken_series.index)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].strftime("%Y-%m"), "2024-06")

    def test_short_time_series_insufficient_for_seasonal_cv(self):
        """Time series with fewer than 24 periods or origin < 13 months raises ValueError."""
        short_series = self.ts_series.iloc[:20]  # Only 20 periods
        with self.assertRaises(ValueError) as ctx:
            rolling_origin_cv(short_series, n_origins=6, forecast_horizon=3)
        self.assertIn("insufficient for seasonal rolling-origin cross-validation", str(ctx.exception))

    def test_forecasting_model_fit_failure_recorded(self):
        """Model fit failure in rolling-origin CV increments fit_failure_count instead of silent suppression."""
        # Patch Holt-Winters ExponentialSmoothing.fit to raise an exception
        with patch("revenue_forecasting.ExponentialSmoothing.fit", side_effect=RuntimeError("Simulated Convergence Error")):
            results = rolling_origin_cv(self.ts_series, n_origins=3, forecast_horizon=3)

            hw_metrics = results["Holt_Winters_Exponential_Smoothing_Rolling_CV"]
            self.assertEqual(hw_metrics["fit_failure_count"], 3, "Expected 3 recorded fit failures")
            self.assertEqual(hw_metrics["fit_success_count"], 0, "Expected 0 fit successes")
            self.assertEqual(hw_metrics["fit_status"], "FAILED")
            self.assertEqual(hw_metrics["prediction_status"], "CONTAINS_FALLBACKS")
            self.assertEqual(hw_metrics["prediction_source"], "PERSISTENCE_FALLBACK_SUBSTITUTED")
            self.assertIn("MAPE_pct", hw_metrics)

        # Patch SARIMAX.fit to raise an exception
        with patch("revenue_forecasting.SARIMAX.fit", side_effect=RuntimeError("Simulated Hessian Error")):
            results_sarima = rolling_origin_cv(self.ts_series, n_origins=3, forecast_horizon=3)

            sarima_metrics = results_sarima["SARIMAX_1_1_1_Rolling_CV"]
            self.assertEqual(sarima_metrics["fit_failure_count"], 3, "Expected 3 recorded fit failures")
            self.assertEqual(sarima_metrics["fit_success_count"], 0, "Expected 0 fit successes")
            self.assertEqual(sarima_metrics["fit_status"], "FAILED")
            self.assertEqual(sarima_metrics["prediction_status"], "CONTAINS_FALLBACKS")
            self.assertEqual(sarima_metrics["prediction_source"], "PERSISTENCE_FALLBACK_SUBSTITUTED")

    def test_mase_calculation_metric(self):
        """MASE is calculated correctly against in-sample naive persistence scaling."""
        train = np.array([10.0, 12.0, 14.0, 16.0])  # diffs = 2, mean diff = 2.0
        actual = np.array([18.0, 20.0])
        pred = np.array([17.0, 19.0])               # abs err = 1.0, MAE = 1.0 -> MASE = 1.0 / 2.0 = 0.50
        metrics = calc_metrics(actual, pred, train)
        self.assertEqual(metrics["MASE"], 0.50)


if __name__ == "__main__":
    unittest.main()
