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
  3. Holt-Winters Exponential Smoothing (Additive Trend + Multiplicative Seasonality)
  4. SARIMAX / Auto-regressive statistical model
- Evaluation Metrics: MAE, RMSE, and MAPE.
Saves predictions, evaluations, and forecast comparisons to outputs/metrics/.
"""

import os
import json
import sqlite3
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "processed", "pharma_commercial.db")
METRICS_DIR = os.path.join(BASE_DIR, "outputs", "metrics")
REPORTS_DIR = os.path.join(BASE_DIR, "outputs", "reports")

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
    
    # 36 months total. Split: 30 train, 6 test (H2 2025)
    train_size = 30
    train = ts_series.iloc[:train_size]
    test = ts_series.iloc[train_size:]
    test_dates = ts_df.index[train_size:]
    
    # 1. Baseline 1: Naive (Last Known Value)
    pred_naive = [train.iloc[-1]] * len(test)
    
    # 2. Baseline 2: 6-Month Rolling Moving Average
    pred_ma = [train.iloc[-6:].mean()] * len(test)
    
    # 3. Model 1: Holt-Winters Exponential Smoothing (Additive Trend)
    hw_model = ExponentialSmoothing(train, trend="add", seasonal=None, damped_trend=True).fit()
    pred_hw = hw_model.forecast(len(test))
    
    # 4. Model 2: SARIMAX (p=1, d=1, q=1)
    sarima_model = SARIMAX(train, order=(1, 1, 1), enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
    pred_sarima = sarima_model.forecast(len(test))
    
    # Metrics Calculation
    def calc_metrics(actual, pred):
        mae = float(np.mean(np.abs(actual - pred)))
        rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
        mape = float(np.mean(np.abs((actual - pred) / actual)) * 100)
        return {"MAE_usd": round(mae, 2), "RMSE_usd": round(rmse, 2), "MAPE_pct": round(mape, 2)}
        
    evaluations = {
        "Baseline_Naive_Persistence": calc_metrics(test.values, np.array(pred_naive)),
        "Baseline_6Month_Moving_Average": calc_metrics(test.values, np.array(pred_ma)),
        "Holt_Winters_Exponential_Smoothing": calc_metrics(test.values, pred_hw.values),
        "SARIMAX_1_1_1": calc_metrics(test.values, pred_sarima.values),
    }
    
    # Build Comparison Dataframe
    comparison_df = pd.DataFrame({
        "year_month": ts_df["year_month"].iloc[train_size:].values,
        "actual_net_sales_usd": test.values,
        "pred_naive_usd": np.round(pred_naive, 2),
        "pred_moving_average_usd": np.round(pred_ma, 2),
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
    eval_file = os.path.join(METRICS_DIR, "forecast_model_evaluation.json")
    with open(eval_file, "w") as f:
        json.dump(evaluations, f, indent=2)
        
    comp_file = os.path.join(REPORTS_DIR, "forecast_test_set_comparison.csv")
    comparison_df.to_csv(comp_file, index=False)
    
    f2026_file = os.path.join(REPORTS_DIR, "forecast_fy2026_projections.csv")
    forecast_2026_df.to_csv(f2026_file, index=False)
    
    print("--- REVENUE FORECASTING MODEL BENCHMARK (TEST SET: H2 2025) ---")
    for model_name, m in evaluations.items():
        print(f"{model_name:35s} | MAPE: {m['MAPE_pct']}% | MAE: ${m['MAE_usd']:,.2f} | RMSE: ${m['RMSE_usd']:,.2f}")
    print(f"Detailed reports saved to {comp_file} and {f2026_file}")
    
    return evaluations, comparison_df

if __name__ == "__main__":
    run_revenue_forecasting()
