"""
src/revenue_forecasting.py
--------------------------
Defensible monthly revenue forecasting and time-series model evaluation.
Methodology:
- Extracts monthly net revenue time series (36 periods: 2023-01 through 2025-12).
- Strict temporal train/test split: Train on first 30 months (2023-01 to 2025-06), Test on last 6 months (2025-07 to 2025-12).
- Zero data leakage: No future observations leak into the training window.
- Models:
  1. Baseline Naive Persistence (Last Known Value)
  2. Baseline 6-Month Moving Average
  3. Seasonal Naive Baseline (same-month-last-year benchmark)
  4. Holt-Winters Exponential Smoothing (Damped Additive Trend, no seasonality)
  5. SARIMAX(1,1,1) Auto-regressive statistical model
- Evaluation Metrics: MAE, RMSE, and MAPE.
- Rolling-origin cross-validation for robustness assessment.
Saves predictions, evaluations, and forecast comparisons to outputs/metrics/.
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

def calc_metrics(actual, pred):
    """Calculate MAE, RMSE, and MAPE forecast evaluation metrics."""
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mae = float(np.mean(np.abs(actual - pred)))
    rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
    mape = float(np.mean(np.abs((actual - pred) / actual)) * 100) if np.all(actual != 0) else np.nan
    return {"MAE_usd": round(mae, 2), "RMSE_usd": round(rmse, 2), "MAPE_pct": round(mape, 2)}


def rolling_origin_cv(ts_series, model_type="hw", n_origins=6, forecast_horizon=3):
    """
    Rolling-origin cross-validation for time-series models.
    Trains on an expanding window, forecasts `forecast_horizon` steps, and averages error metrics.
    This provides a more robust error estimate than a single fixed split.
    
    Args:
        ts_series: Full time series (pandas Series)
        model_type: "hw" for Holt-Winters or "sarimax" for SARIMAX
        n_origins: Number of rolling origins to evaluate
        forecast_horizon: Steps ahead to forecast at each origin
    Returns:
        Dictionary with averaged MAE, RMSE, and MAPE across all origins.
    """
    n = len(ts_series)
    # Start the first origin such that the last origin uses all but forecast_horizon observations
    min_train_size = max(12, n - n_origins - forecast_horizon + 1)
    
    all_maes, all_rmses, all_mapes = [], [], []
    
    for i in range(n_origins):
        train_end = min_train_size + i
        if train_end + forecast_horizon > n:
            break
        train = ts_series.iloc[:train_end]
        test = ts_series.iloc[train_end:train_end + forecast_horizon]
        
        try:
            if model_type == "hw":
                model = ExponentialSmoothing(train, trend="add", seasonal=None, damped_trend=True).fit()
                pred = model.forecast(forecast_horizon)
            elif model_type == "sarimax":
                model = SARIMAX(train, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
                pred = model.forecast(forecast_horizon)
            else:
                continue
                
            m = calc_metrics(test.values, pred.values)
            all_maes.append(m["MAE_usd"])
            all_rmses.append(m["RMSE_usd"])
            all_mapes.append(m["MAPE_pct"])
        except Exception as e:
            logger.warning("Rolling origin %d failed for %s: %s", i, model_type, str(e))
            continue
    
    if not all_maes:
        return {"MAE_usd": np.nan, "RMSE_usd": np.nan, "MAPE_pct": np.nan, "n_origins": 0}
    
    return {
        "MAE_usd": round(float(np.mean(all_maes)), 2),
        "RMSE_usd": round(float(np.mean(all_rmses)), 2),
        "MAPE_pct": round(float(np.mean(all_mapes)), 2),
        "n_origins": len(all_maes),
    }


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
    ts_df.set_index("month_start_date", inplace=True)
    ts_series = ts_df["net_sales_usd"]
    
    logger.info("Time series: %d monthly observations (%s to %s)",
                len(ts_series), ts_df["year_month"].iloc[0], ts_df["year_month"].iloc[-1])
    
    # 36 months total. Split: 30 train, 6 test (H2 2025)
    train_size = 30
    train = ts_series.iloc[:train_size]
    test = ts_series.iloc[train_size:]
    test_dates = ts_df.index[train_size:]
    
    logger.info("Train/test split: %d train months, %d test months", len(train), len(test))
    
    # 1. Baseline 1: Naive (Last Known Value)
    pred_naive = [train.iloc[-1]] * len(test)
    
    # 2. Baseline 2: 6-Month Rolling Moving Average
    pred_ma = [train.iloc[-6:].mean()] * len(test)
    
    # 3. Baseline 3: Seasonal Naive (same month from one year ago)
    # For each test month, use the value from 12 months prior
    pred_seasonal_naive = []
    for i in range(len(test)):
        month_idx = train_size + i
        lookback_idx = month_idx - 12  # Same month, prior year
        if lookback_idx >= 0:
            pred_seasonal_naive.append(ts_series.iloc[lookback_idx])
        else:
            pred_seasonal_naive.append(train.mean())  # Fallback
    
    # 4. Model 1: Holt-Winters Exponential Smoothing (Damped Additive Trend, no seasonal component)
    hw_model = ExponentialSmoothing(train, trend="add", seasonal=None, damped_trend=True).fit()
    pred_hw = hw_model.forecast(len(test))
    
    # 5. Model 2: SARIMAX (p=1, d=1, q=1)
    sarima_model = SARIMAX(train, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    pred_sarima = sarima_model.forecast(len(test))
    
    # Fixed-Split Metrics Calculation
    evaluations = {
        "Baseline_Naive_Persistence": calc_metrics(test.values, np.array(pred_naive)),
        "Baseline_6Month_Moving_Average": calc_metrics(test.values, np.array(pred_ma)),
        "Baseline_Seasonal_Naive": calc_metrics(test.values, np.array(pred_seasonal_naive)),
        "Holt_Winters_Exponential_Smoothing": calc_metrics(test.values, pred_hw.values),
        "SARIMAX_1_1_1": calc_metrics(test.values, pred_sarima.values),
    }
    
    # Rolling-Origin Cross-Validation (6 origins × 3-step forecast)
    logger.info("Running rolling-origin cross-validation (6 origins × 3-step horizon)...")
    rolling_cv_results = {
        "Holt_Winters_Rolling_CV": rolling_origin_cv(ts_series, model_type="hw", n_origins=6, forecast_horizon=3),
        "SARIMAX_Rolling_CV": rolling_origin_cv(ts_series, model_type="sarimax", n_origins=6, forecast_horizon=3),
    }
    
    # Build Comparison Dataframe
    comparison_df = pd.DataFrame({
        "year_month": ts_df["year_month"].iloc[train_size:].values,
        "actual_net_sales_usd": test.values,
        "pred_naive_usd": np.round(pred_naive, 2),
        "pred_moving_average_usd": np.round(pred_ma, 2),
        "pred_seasonal_naive_usd": np.round(pred_seasonal_naive, 2),
        "pred_holt_winters_usd": np.round(pred_hw.values, 2),
        "pred_sarimax_usd": np.round(pred_sarima.values, 2),
    })
    
    # Generate 12-Month Out-of-Sample Forward Forecast for FY2026 using champion model
    champion_hw = ExponentialSmoothing(ts_series, trend="add", seasonal=None, damped_trend=True).fit()
    future_dates = pd.date_range(start="2026-01-01", periods=12, freq="MS")
    future_forecast = champion_hw.forecast(12)
    
    forecast_2026_df = pd.DataFrame({
        "forecast_month": future_dates.strftime("%Y-%m"),
        "projected_net_sales_usd": np.round(future_forecast.values, 2)
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
    
    print("--- REVENUE FORECASTING MODEL BENCHMARK (TEST SET: H2 2025) ---")
    for model_name, m in evaluations.items():
        print(f"{model_name:35s} | MAPE: {m['MAPE_pct']}% | MAE: ${m['MAE_usd']:,.2f} | RMSE: ${m['RMSE_usd']:,.2f}")
    print("\n--- ROLLING-ORIGIN CROSS-VALIDATION (ROBUSTNESS CHECK) ---")
    for model_name, m in rolling_cv_results.items():
        print(f"{model_name:35s} | Avg MAPE: {m['MAPE_pct']}% | Avg RMSE: ${m['RMSE_usd']:,.2f} | Origins: {m['n_origins']}")
    print(f"\nDetailed reports saved to {comp_file} and {f2026_file}")
    
    return all_evaluations, comparison_df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    run_revenue_forecasting()
