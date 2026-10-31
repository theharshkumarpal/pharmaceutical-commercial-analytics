"""
src/revenue_forecasting.py
--------------------------
Monthly revenue forecasting and time-series model evaluation for pharmaceutical commercial sales.

Methodology:
- Extracts monthly net revenue time series (36 periods: 2023-01 through 2025-12).
- Strict temporal train/test split:
  Train: First 30 months (2023-01 to 2025-06)
  Test: Final 6 months (2025-07 to 2025-12)
- Zero data leakage: No future observations leak into historical training windows.
- Models evaluated across identical evaluation windows:
  1. Baseline Naive Persistence (Last Known Observation)
  2. Baseline 6-Month Moving Average
  3. Baseline Seasonal Naive (12-Month Seasonal Lag Benchmark)
  4. Holt-Winters Exponential Smoothing (Damped Additive Trend, seasonal=None)
  5. SARIMAX(1,1,1) Auto-Regressive Moving Average
- Comprehensive error metrics:
  - MAE (Mean Absolute Error, USD)
  - RMSE (Root Mean Squared Error, USD)
  - MAPE (Mean Absolute Percentage Error, %)
  - MASE (Mean Absolute Scaled Error, scaled by in-sample naive persistence MAE)
- Rolling-origin cross-validation: 6 expanding origins with a 3-month forecast horizon,
  evaluated symmetrically across all 5 candidate models.
"""

import os
import json
import sqlite3
import logging
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
METRICS_DIR = os.path.join(BASE_DIR, "outputs", "metrics")
REPORTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")


def calc_metrics(actual, pred, train_series=None) -> dict:
    """
    Calculate MAE, RMSE, MAPE, and MASE forecast evaluation metrics.

    MASE formula (Hyndman & Koehler, 2006):
        MASE = MAE / (1/(T-1) * sum(|y_t - y_{t-1}|))
    where the denominator is the mean absolute error of the one-step naive persistence forecast on the training set.
    """
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mae = float(np.mean(np.abs(actual - pred)))
    rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
    mape = float(np.mean(np.abs((actual - pred) / actual)) * 100) if np.all(actual != 0) else np.nan

    mase = np.nan
    if train_series is not None and len(train_series) > 1:
        train_vals = np.asarray(train_series, dtype=float)
        in_sample_scale = float(np.mean(np.abs(np.diff(train_vals))))
        if in_sample_scale > 0:
            mase = round(float(mae / in_sample_scale), 2)

    return {
        "MAE_usd": round(mae, 2),
        "RMSE_usd": round(rmse, 2),
        "MAPE_pct": round(mape, 2),
        "MASE": mase,
    }


def rolling_origin_cv(ts_series: pd.Series, n_origins: int = 6, forecast_horizon: int = 3) -> dict:
    """
    Symmetric rolling-origin cross-validation evaluated across all 5 candidate models
    over identical expanding training origins and test forecast horizons.

    Args:
        ts_series: Full monthly time series (length >= 24).
        n_origins: Number of expanding historical origins (default: 6).
        forecast_horizon: Steps ahead to forecast at each origin (default: 3).

    Returns:
        Dictionary mapping model names to their average cross-validation metrics and fit status.
    """
    n = len(ts_series)
    # Ensure earliest origin has at least 13 months of training data (enough for 12m seasonal lag)
    first_train_end = n - n_origins - forecast_horizon + 1
    if n < 24 or first_train_end < 13:
        raise ValueError(
            f"Series length ({n}) insufficient for seasonal rolling-origin cross-validation "
            f"(requires >= 24 monthly periods with earliest origin >= 13 months, found first_train_end={first_train_end})"
        )

    model_keys = [
        "Baseline_Seasonal_Naive",
        "Holt_Winters_Exponential_Smoothing",
        "SARIMAX_1_1_1",
        "Baseline_6Month_Moving_Average",
        "Baseline_Naive_Persistence",
    ]
    cv_records = {k: [] for k in model_keys}
    fit_success_count = {k: 0 for k in model_keys}
    fit_failure_count = {k: 0 for k in model_keys}

    for i in range(n_origins):
        train_end = first_train_end + i
        if train_end + forecast_horizon > n:
            break

        train_slice = ts_series.iloc[:train_end]
        test_slice = ts_series.iloc[train_end:train_end + forecast_horizon]

        # 1. Seasonal Naive: for each step h, look back 12 months prior
        sn_preds = []
        for h in range(forecast_horizon):
            lookback_idx = train_end + h - 12
            sn_preds.append(ts_series.iloc[lookback_idx])
        fit_success_count["Baseline_Seasonal_Naive"] += 1

        # 2. Holt-Winters
        try:
            hw_fit = ExponentialSmoothing(train_slice, trend="add", seasonal=None, damped_trend=True).fit()
            hw_preds = hw_fit.forecast(forecast_horizon).values
            fit_success_count["Holt_Winters_Exponential_Smoothing"] += 1
        except Exception as e:
            logger.warning("Holt-Winters fit failed at origin %d: %s. Using persistence fallback.", i, e)
            fit_failure_count["Holt_Winters_Exponential_Smoothing"] += 1
            hw_preds = np.full(forecast_horizon, train_slice.iloc[-1])

        # 3. SARIMAX
        try:
            sarima_fit = SARIMAX(train_slice, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            sarima_preds = sarima_fit.forecast(forecast_horizon).values
            fit_success_count["SARIMAX_1_1_1"] += 1
        except Exception as e:
            logger.warning("SARIMAX fit failed at origin %d: %s. Using persistence fallback.", i, e)
            fit_failure_count["SARIMAX_1_1_1"] += 1
            sarima_preds = np.full(forecast_horizon, train_slice.iloc[-1])

        # 4. Moving Average (6-month)
        ma_preds = np.full(forecast_horizon, train_slice.iloc[-6:].mean())
        fit_success_count["Baseline_6Month_Moving_Average"] += 1

        # 5. Naive Persistence
        naive_preds = np.full(forecast_horizon, train_slice.iloc[-1])
        fit_success_count["Baseline_Naive_Persistence"] += 1

        step_preds = {
            "Baseline_Seasonal_Naive": np.array(sn_preds),
            "Holt_Winters_Exponential_Smoothing": hw_preds,
            "SARIMAX_1_1_1": sarima_preds,
            "Baseline_6Month_Moving_Average": ma_preds,
            "Baseline_Naive_Persistence": naive_preds,
        }

        for k in model_keys:
            m = calc_metrics(test_slice.values, step_preds[k], train_slice)
            cv_records[k].append(m)

    summary_results = {}
    for k in model_keys:
        recs = cv_records[k]
        if not recs:
            continue
        is_parametric = k in ["Holt_Winters_Exponential_Smoothing", "SARIMAX_1_1_1"]
        if is_parametric:
            fit_stat = "SUCCESS" if fit_failure_count[k] == 0 else ("FAILED" if fit_success_count[k] == 0 else "PARTIAL_FAILURE")
            pred_stat = "SUCCESS" if fit_failure_count[k] == 0 else "CONTAINS_FALLBACKS"
            pred_src = "MODEL_FORECAST" if fit_failure_count[k] == 0 else "PERSISTENCE_FALLBACK_SUBSTITUTED"
        else:
            fit_stat = "NOT_APPLICABLE"
            pred_stat = "SUCCESS"
            pred_src = k.upper()

        summary_results[k + "_Rolling_CV"] = {
            "MAE_usd": round(float(np.mean([r["MAE_usd"] for r in recs])), 2),
            "RMSE_usd": round(float(np.mean([r["RMSE_usd"] for r in recs])), 2),
            "MAPE_pct": round(float(np.mean([r["MAPE_pct"] for r in recs])), 2),
            "MASE": round(float(np.mean([r["MASE"] for r in recs])), 2),
            "n_origins": len(recs),
            "forecast_horizon_months": forecast_horizon,
            "fit_success_count": fit_success_count[k],
            "fit_failure_count": fit_failure_count[k],
            "fit_status": fit_stat,
            "prediction_status": pred_stat,
            "prediction_source": pred_src,
        }

    return summary_results


def run_revenue_forecasting():
    os.makedirs(METRICS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT
        d.year_month,
        MIN(d.full_date) AS month_start_date,
        ROUND(SUM(f.net_sales_usd), 2) AS net_sales_usd,
        SUM(f.net_units) AS net_units,
        COUNT(DISTINCT f.sales_fact_id) AS transaction_count
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year_month
    ORDER BY d.year_month ASC
    """
    ts_df = pd.read_sql_query(query, conn)
    conn.close()

    ts_df["month_start_date"] = pd.to_datetime(ts_df["month_start_date"])
    ts_df.sort_values("month_start_date", inplace=True)

    # Validate monthly continuity and missing periods
    expected_dates = pd.date_range(start=ts_df["month_start_date"].min(), end=ts_df["month_start_date"].max(), freq="MS")
    if len(ts_df) != len(expected_dates):
        missing_periods = expected_dates.difference(ts_df["month_start_date"])
        raise ValueError(f"Time series has missing monthly periods ({len(missing_periods)} missing): {missing_periods.strftime('%Y-%m').tolist()}")

    ts_df.set_index("month_start_date", inplace=True)
    ts_series = ts_df["net_sales_usd"]

    logger.info("Time series: %d monthly observations (%s to %s)",
                len(ts_series), ts_df["year_month"].iloc[0], ts_df["year_month"].iloc[-1])

    # 36 months total. Split: 30 train, 6 test (H2 2025)
    train_size = 30
    train = ts_series.iloc[:train_size]
    test = ts_series.iloc[train_size:]

    logger.info("Train/test split: %d train months, %d test months", len(train), len(test))

    # 1. Baseline 1: Naive Persistence (Last Known Value)
    pred_naive = [train.iloc[-1]] * len(test)

    # 2. Baseline 2: 6-Month Rolling Moving Average
    pred_ma = [train.iloc[-6:].mean()] * len(test)

    # 3. Baseline 3: Seasonal Naive (same month prior year)
    pred_seasonal_naive = []
    for i in range(len(test)):
        month_idx = train_size + i
        lookback_idx = month_idx - 12
        pred_seasonal_naive.append(ts_series.iloc[lookback_idx])

    # 4. Model 1: Holt-Winters Exponential Smoothing (Damped Additive Trend)
    hw_fit_status = "SUCCESS"
    hw_prediction_status = "SUCCESS"
    hw_prediction_source = "MODEL_FORECAST"
    try:
        hw_model = ExponentialSmoothing(train, trend="add", seasonal=None, damped_trend=True).fit()
        pred_hw = hw_model.forecast(len(test))
    except Exception as e:
        logger.warning("Fixed-split Holt-Winters fit failed: %s. Using persistence fallback.", e)
        hw_fit_status = "FAILED"
        hw_prediction_status = "FALLBACK"
        hw_prediction_source = "PERSISTENCE_FALLBACK"
        pred_hw = pd.Series([train.iloc[-1]] * len(test), index=test.index)

    # 5. Model 2: SARIMAX (p=1, d=1, q=1)
    sarima_fit_status = "SUCCESS"
    sarima_prediction_status = "SUCCESS"
    sarima_prediction_source = "MODEL_FORECAST"
    try:
        sarima_model = SARIMAX(train, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        pred_sarima = sarima_model.forecast(len(test))
    except Exception as e:
        logger.warning("Fixed-split SARIMAX fit failed: %s. Using persistence fallback.", e)
        sarima_fit_status = "FAILED"
        sarima_prediction_status = "FALLBACK"
        sarima_prediction_source = "PERSISTENCE_FALLBACK"
        pred_sarima = pd.Series([train.iloc[-1]] * len(test), index=test.index)

    # Fixed-Split Metrics Calculation (All 5 models evaluated on identical test window)
    evaluations = {
        "Baseline_Seasonal_Naive": {
            **calc_metrics(test.values, np.array(pred_seasonal_naive), train),
            "fit_status": "NOT_APPLICABLE",
            "prediction_status": "SUCCESS",
            "prediction_source": "SEASONAL_LAG_12M",
        },
        "Holt_Winters_Exponential_Smoothing": {
            **calc_metrics(test.values, pred_hw.values, train),
            "fit_status": hw_fit_status,
            "prediction_status": hw_prediction_status,
            "prediction_source": hw_prediction_source,
        },
        "SARIMAX_1_1_1": {
            **calc_metrics(test.values, pred_sarima.values, train),
            "fit_status": sarima_fit_status,
            "prediction_status": sarima_prediction_status,
            "prediction_source": sarima_prediction_source,
        },
        "Baseline_Naive_Persistence": {
            **calc_metrics(test.values, np.array(pred_naive), train),
            "fit_status": "NOT_APPLICABLE",
            "prediction_status": "SUCCESS",
            "prediction_source": "LAST_KNOWN_OBSERVATION",
        },
        "Baseline_6Month_Moving_Average": {
            **calc_metrics(test.values, np.array(pred_ma), train),
            "fit_status": "NOT_APPLICABLE",
            "prediction_status": "SUCCESS",
            "prediction_source": "ROLLING_WINDOW_6M",
        },
    }

    # Rolling-Origin Cross-Validation (6 origins × 3-step forecast) across ALL models
    logger.info("Running symmetric rolling-origin cross-validation (6 origins × 3-step horizon)...")
    rolling_cv_results = rolling_origin_cv(ts_series, n_origins=6, forecast_horizon=3)

    # Build Comparison Dataframe
    comparison_df = pd.DataFrame({
        "year_month": ts_df["year_month"].iloc[train_size:].values,
        "actual_net_sales_usd": test.values,
        "pred_seasonal_naive_usd": np.round(pred_seasonal_naive, 2),
        "pred_holt_winters_usd": np.round(pred_hw.values, 2),
        "pred_sarimax_usd": np.round(pred_sarima.values, 2),
        "pred_moving_average_usd": np.round(pred_ma, 2),
        "pred_naive_usd": np.round(pred_naive, 2),
    })

    # Generate 12-Month Out-of-Sample Forward Forecast for FY2026 using both Seasonal Naive & Holt-Winters
    # For full 2026 forward forecast:
    future_dates = pd.date_range(start="2026-01-01", periods=12, freq="MS")
    # Seasonal Naive forward forecast uses FY2025 actuals
    future_sn = ts_series.iloc[-12:].values
    # Holt-Winters fit on full 36-month series
    full_hw = ExponentialSmoothing(ts_series, trend="add", seasonal=None, damped_trend=True).fit()
    future_hw = full_hw.forecast(12).values

    forecast_2026_df = pd.DataFrame({
        "forecast_month": future_dates.strftime("%Y-%m"),
        "projected_seasonal_naive_usd": np.round(future_sn, 2),
        "projected_holt_winters_usd": np.round(future_hw, 2),
    })

    # Save outputs
    all_evaluations = {**evaluations, **rolling_cv_results}
    eval_file = os.path.join(METRICS_DIR, "forecast_model_evaluation.json")
    with open(eval_file, "w") as f:
        json.dump(all_evaluations, f, indent=2)

    comp_file = os.path.join(REPORTS_DIR, "forecast_test_set_comparison.csv")
    comparison_df.to_csv(comp_file, index=False)

    f2026_file = os.path.join(REPORTS_DIR, "forecast_fy2026_projections.csv")
    forecast_2026_df.to_csv(f2026_file, index=False)

    print("\n--- REVENUE FORECASTING BENCHMARK (FIXED 6-MONTH TEST SET: H2 2025) ---")
    for model_name, m in evaluations.items():
        print(f"{model_name:38s} | MAPE: {m['MAPE_pct']:5.2f}% | MASE: {m['MASE']:4.2f} | MAE: ${m['MAE_usd']:,.2f} | RMSE: ${m['RMSE_usd']:,.2f}")

    print("\n--- ROLLING-ORIGIN CROSS-VALIDATION (6 ORIGINS × 3-MONTH HORIZONS) ---")
    for model_name, m in rolling_cv_results.items():
        print(f"{model_name:38s} | Avg MAPE: {m['MAPE_pct']:5.2f}% | Avg MASE: {m['MASE']:4.2f} | Avg RMSE: ${m['RMSE_usd']:,.2f}")

    print(f"\nSaved evaluation metrics to {eval_file}")
    print(f"Saved comparison tables to {comp_file} and {f2026_file}")

    return all_evaluations, comparison_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    run_revenue_forecasting()
