"""
===============================================================================
PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
PHASE 4: PYTHON DATA ANALYSIS
FILE: 01_data_cleaning_and_outliers.py
DESCRIPTION:
    1. Imports the 4 dataset files (CSV & Parquet).
    2. Performs programmatic data cleaning & type standardization.
    3. Handles missing values with domain-aware aviation logic.
    4. Verifies exact and composite-key duplicate records.
    5. Executes both Global and Route-Contextual Outlier Detection (IQR & Z-Score).
===============================================================================
"""

import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DATASET_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Dataset"


def load_and_clean_datasets():
    print("=" * 80)
    print("STEP 1: IMPORTING & CLEANING DATASETS")
    print("=" * 80)

    # 1. Load airports.csv
    airports = pd.read_csv(os.path.join(DATASET_DIR, "airports.csv"))
    airports["iata"] = airports["iata"].str.strip().str.upper()

    # 2. Load routes.csv
    routes = pd.read_csv(os.path.join(DATASET_DIR, "routes.csv"))
    routes["route"] = routes["route"].str.strip().str.upper()
    routes["price_per_mile_usd"] = (routes["median_price_usd"] / routes["distance_miles"]).round(4)
    routes["distance_haul"] = np.select(
        [
            routes["distance_miles"] < 500,
            routes["distance_miles"].between(500, 1500),
            routes["distance_miles"] > 1500,
        ],
        [
            "Short-Haul (<500 mi)",
            "Medium-Haul (500-1500 mi)",
            "Long-Haul (>1500 mi)",
        ],
        default="Unknown",
    )

    # 3. Load daily_fares.csv
    daily = pd.read_csv(
        os.path.join(DATASET_DIR, "daily_fares.csv"),
        parse_dates=["search_date", "departure_date"],
    )

    # Missing Values Handling in daily_fares.csv:
    # `min_nonstop_price_usd` has 87 NaN rows because no nonstop flight operated
    # on those specific (search_date, route, departure_date) combinations.
    # Rule: Never replace with 0 (which distorts averages downward). Instead:
    #   a) Create an explicit binary flag `has_nonstop_flight`
    #   b) Keep `min_nonstop_price_usd` as NaN for strict nonstop calculations
    #   c) Compute `nonstop_premium_usd` only where nonstop flights exist
    missing_before = daily.isna().sum()
    daily["has_nonstop_flight"] = daily["min_nonstop_price_usd"].notna()
    daily["nonstop_premium_usd"] = daily["min_nonstop_price_usd"] - daily["min_price_usd"]
    daily["daily_price_spread_usd"] = daily["max_price_usd"] - daily["min_price_usd"]

    print(f"Airports loaded      : {airports.shape[0]:,} rows x {airports.shape[1]} cols")
    print(f"Routes loaded        : {routes.shape[0]:,} rows x {routes.shape[1]} cols")
    print(f"Daily Fares loaded   : {daily.shape[0]:,} rows x {daily.shape[1]} cols")
    print("\nMissing values in daily_fares before domain handling:")
    print(missing_before[missing_before > 0].to_string())
    print(f"Rows with has_nonstop_flight == False: {(~daily['has_nonstop_flight']).sum():,} (EWR-SFO: 45, SFO-EWR: 42)")

    # 4. Duplicate Verification
    print("\n" + "=" * 80)
    print("STEP 2: DUPLICATE RECORD VERIFICATION")
    print("=" * 80)
    print(f"airports exact duplicates                   : {airports.duplicated().sum()}")
    print(f"routes exact duplicates                     : {routes.duplicated().sum()}")
    print(f"daily_fares exact duplicates                : {daily.duplicated().sum()}")
    print(
        f"daily_fares grain (search, route, dep) dups : "
        f"{daily.duplicated(subset=['search_date', 'route', 'departure_date']).sum()}"
    )

    return airports, routes, daily


def detect_outliers(daily: pd.DataFrame, routes: pd.DataFrame):
    print("\n" + "=" * 80)
    print("STEP 3: OUTLIER DETECTION (GLOBAL IQR vs. ROUTE-CONTEXTUAL IQR & Z-SCORE)")
    print("=" * 80)

    # Merge haul and route baseline info
    df = daily.merge(
        routes[["route", "distance_miles", "distance_haul", "median_price_usd"]],
        on="route",
        suffixes=("", "_route_baseline"),
    )

    # A. Global IQR on daily `median_price_usd` and `max_price_usd`
    for col in ["min_price_usd", "median_price_usd", "max_price_usd"]:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower_fence = max(0, q1 - 1.5 * iqr)
        upper_fence = q3 + 1.5 * iqr
        outliers = df[(df[col] < lower_fence) | (df[col] > upper_fence)]
        z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
        z_outliers = (z_scores > 3).sum()
        print(
            f"[Global {col:18s}] Q1=${q1:6.1f} | Median=${df[col].median():6.1f} | "
            f"Q3=${q3:6.1f} | IQR=${iqr:6.1f} | UpperFence=${upper_fence:6.1f} | "
            f"IQR Outliers={len(outliers):7,d} ({len(outliers)/len(df)*100:5.2f}%) | "
            f"Z>3 Outliers={z_outliers:6,d} ({z_outliers/len(df)*100:4.2f}%)"
        )

    # B. Contextual (Route-Specific) IQR Outlier Detection on `median_price_usd`
    # Why? A $300 fare on LAX-LAS (236 mi) is an extreme surge, whereas $300 on
    # SFO-JFK (2580 mi) is normal. Grouping by `route` avoids false positives!
    route_stats = (
        df.groupby("route")["median_price_usd"]
        .agg(
            r_q1=lambda x: x.quantile(0.25),
            r_q3=lambda x: x.quantile(0.75),
            r_mean="mean",
            r_std="std",
        )
        .reset_index()
    )
    route_stats["r_iqr"] = route_stats["r_q3"] - route_stats["r_q1"]
    route_stats["r_upper_fence"] = route_stats["r_q3"] + 1.5 * route_stats["r_iqr"]

    df = df.merge(route_stats, on="route")
    df["is_contextual_iqr_outlier"] = df["median_price_usd"] > df["r_upper_fence"]
    df["contextual_z_score"] = (df["median_price_usd"] - df["r_mean"]) / df["r_std"]
    df["is_contextual_z_outlier"] = df["contextual_z_score"].abs() > 3.0

    ctx_iqr_count = df["is_contextual_iqr_outlier"].sum()
    ctx_z_count = df["is_contextual_z_outlier"].sum()
    print(
        f"\n[Route-Contextual median_price_usd Outliers]\n"
        f"  -> Contextual IQR Outliers : {ctx_iqr_count:,} ({ctx_iqr_count/len(df)*100:.2f}%)\n"
        f"  -> Contextual Z>3 Outliers : {ctx_z_count:,} ({ctx_z_count/len(df)*100:.2f}%)"
    )

    # Check WHEN contextual outliers happen (spoiler: Last-Minute & Peak Holidays!)
    outlier_dbd = df[df["is_contextual_iqr_outlier"]]["days_before_departure"].median()
    normal_dbd = df[~df["is_contextual_iqr_outlier"]]["days_before_departure"].median()
    print(
        f"  -> Median Lead Time of Contextual Price Outliers : {outlier_dbd:.0f} days before departure\n"
        f"  -> Median Lead Time of Normal Fares              : {normal_dbd:.0f} days before departure"
    )

    # C. Granular Parquet Outlier Check (38.58M rows)
    pf = pq.ParquetFile(os.path.join(DATASET_DIR, "flight_prices.parquet"))
    fp_cols = pf.read(columns=["price_usd", "duration_minutes", "stops"]).to_pandas()
    p_q1, p_q3 = fp_cols["price_usd"].quantile([0.25, 0.75])
    p_iqr = p_q3 - p_q1
    p_upper = p_q3 + 1.5 * p_iqr
    p_outliers = (fp_cols["price_usd"] > p_upper).sum()
    p_p99 = fp_cols["price_usd"].quantile(0.99)
    print(
        f"\n[Granular flight_prices.parquet (38,584,829 rows) price_usd]\n"
        f"  -> Mean=${fp_cols['price_usd'].mean():.2f} | Median=${fp_cols['price_usd'].median():.1f} | "
        f"Std=${fp_cols['price_usd'].std():.2f} | Skewness={fp_cols['price_usd'].skew():.2f}\n"
        f"  -> Q1=${p_q1:.1f} | Q3=${p_q3:.1f} | IQR=${p_iqr:.1f} | UpperFence=${p_upper:.1f} | "
        f"99th Percentile=${p_p99:.1f}\n"
        f"  -> Global IQR Outliers (> ${p_upper:.1f}): {p_outliers:,} ({p_outliers/len(fp_cols)*100:.2f}%)"
    )


if __name__ == "__main__":
    airports_df, routes_df, daily_df = load_and_clean_datasets()
    detect_outliers(daily_df, routes_df)
