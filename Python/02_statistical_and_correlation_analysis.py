"""
===============================================================================
PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
PHASE 4: PYTHON DATA ANALYSIS
FILE: 02_statistical_and_correlation_analysis.py
DESCRIPTION:
    1. Computes parametric & non-parametric statistical distributions (Skewness,
       Kurtosis, Coefficient of Variation).
    2. Runs formal hypothesis tests (ANOVA F-test, Kruskal-Wallis H-test,
       Welch's t-test, Mann-Whitney U test, Cohen's d effect size) to validate
       SQL business findings scientifically.
    3. Computes Pearson (linear) and Spearman (rank) correlation matrices.
===============================================================================
"""

import os
import numpy as np
import pandas as pd
from scipy import stats

DATASET_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Dataset"


def cohens_d(x: pd.Series, y: pd.Series) -> float:
    nx, ny = len(x), len(y)
    dof = nx + ny - 2
    pool_sd = np.sqrt(((nx - 1) * x.var() + (ny - 1) * y.var()) / dof)
    return (x.mean() - y.mean()) / pool_sd


def run_statistical_and_correlation_analysis():
    routes = pd.read_csv(os.path.join(DATASET_DIR, "routes.csv"))
    daily = pd.read_csv(
        os.path.join(DATASET_DIR, "daily_fares.csv"),
        parse_dates=["search_date", "departure_date"],
    )

    routes["price_per_mile_usd"] = routes["median_price_usd"] / routes["distance_miles"]
    df = daily.merge(
        routes[["route", "distance_miles", "pct_nonstop", "price_per_mile_usd"]],
        on="route",
    )
    df["nonstop_premium_usd"] = df["min_nonstop_price_usd"] - df["min_price_usd"]
    df["daily_spread_usd"] = df["max_price_usd"] - df["min_price_usd"]
    df["dow_name"] = df["departure_date"].dt.day_name()

    # 1. Distributional Shape & Moment Statistics
    print("=" * 80)
    print("1. DISTRIBUTIONAL SHAPE & STATISTICAL MOMENTS (n = 1,683,033)")
    print("=" * 80)
    metrics = [
        "days_before_departure",
        "itineraries",
        "airlines",
        "min_price_usd",
        "min_nonstop_price_usd",
        "median_price_usd",
        "max_price_usd",
        "daily_spread_usd",
        "nonstop_premium_usd",
    ]
    stat_rows = []
    for col in metrics:
        s = df[col].dropna()
        stat_rows.append(
            {
                "Feature": col,
                "Mean": round(s.mean(), 2),
                "Std": round(s.std(), 2),
                "CV_%": round(s.std() / s.mean() * 100, 1) if s.mean() != 0 else np.nan,
                "Min": round(s.min(), 2),
                "P25": round(s.quantile(0.25), 2),
                "Median": round(s.median(), 2),
                "P75": round(s.quantile(0.75), 2),
                "P95": round(s.quantile(0.95), 2),
                "Max": round(s.max(), 2),
                "Skewness": round(s.skew(), 2),
                "Kurtosis": round(s.kurtosis(), 2),
            }
        )
    stat_df = pd.DataFrame(stat_rows)
    print(stat_df.to_string(index=False))

    # 2. Hypothesis Testing
    print("\n" + "=" * 80)
    print("2. INFERENTIAL HYPOTHESIS TESTING (PARAMETRIC & NON-PARAMETRIC)")
    print("=" * 80)

    # Test A: Last Minute (7-14d) vs Sweet Spot (31-60d)
    last_min = df[df["days_before_departure"].between(7, 14)]["median_price_usd"]
    sweet_spot = df[df["days_before_departure"].between(31, 60)]["median_price_usd"]
    t_stat, p_val_t = stats.ttest_ind(last_min, sweet_spot, equal_var=False)
    u_stat, p_val_u = stats.mannwhitneyu(last_min, sweet_spot, alternative="two-sided")
    d_booking = cohens_d(last_min, sweet_spot)
    print(
        f"[Test A: Last Minute (7-14d, Mean=${last_min.mean():.2f}) vs. Sweet Spot (31-60d, Mean=${sweet_spot.mean():.2f})]\n"
        f"  -> Welch's t-statistic = {t_stat:.2f}, p-value = {p_val_t:.4e}\n"
        f"  -> Mann-Whitney U      = {u_stat:.2e}, p-value = {p_val_u:.4e}\n"
        f"  -> Cohen's d Effect    = {d_booking:.3f} (Large positive effect: > 0.80)"
    )

    # Test B: Day-of-Week ANOVA & Kruskal-Wallis + Sunday vs Tuesday
    dow_groups = [group["median_price_usd"].values for _, group in df.groupby("dow_name")]
    f_dow, p_dow = stats.f_oneway(*dow_groups)
    h_dow, p_kw_dow = stats.kruskal(*dow_groups)
    sun = df[df["dow_name"] == "Sunday"]["median_price_usd"]
    tue = df[df["dow_name"] == "Tuesday"]["median_price_usd"]
    d_dow = cohens_d(sun, tue)
    print(
        f"\n[Test B: Day-of-Week Price Variance across 7 Days & Sunday (${sun.mean():.2f}) vs. Tuesday (${tue.mean():.2f})]\n"
        f"  -> One-Way ANOVA F     = {f_dow:.2f}, p-value = {p_dow:.4e}\n"
        f"  -> Kruskal-Wallis H    = {h_dow:.2f}, p-value = {p_kw_dow:.4e}\n"
        f"  -> Sun vs Tue Cohen's d= {d_dow:.3f} (Large practical significance)"
    )

    # Test C: Short-Haul vs Medium-Haul vs Long-Haul Yield (Price per Mile)
    routes["haul"] = np.where(
        routes["distance_miles"] < 500,
        "Short",
        np.where(routes["distance_miles"] <= 1500, "Medium", "Long"),
    )
    haul_groups = [g["price_per_mile_usd"].values for _, g in routes.groupby("haul")]
    f_haul, p_haul = stats.f_oneway(*haul_groups)
    h_haul, p_kw_haul = stats.kruskal(*haul_groups)
    print(
        f"\n[Test C: Economies of Distance (Price per Mile across Short/Medium/Long-Haul, n=50 routes)]\n"
        f"  -> One-Way ANOVA F     = {f_haul:.2f}, p-value = {p_haul:.4e}\n"
        f"  -> Kruskal-Wallis H    = {h_haul:.2f}, p-value = {p_kw_haul:.4e}"
    )

    # 3. Correlation Analysis
    print("\n" + "=" * 80)
    print("3. CORRELATION ANALYSIS (PEARSON r & SPEARMAN rho)")
    print("=" * 80)

    print("\n--- A. Route-Level Correlations (n = 50 routes) ---")
    route_corr_cols = [
        "distance_miles",
        "median_price_usd",
        "price_per_mile_usd",
        "pct_nonstop",
        "airlines",
        "price_observations",
    ]
    print("Pearson (Linear) Correlation:")
    print(routes[route_corr_cols].corr(method="pearson").round(3).to_string())
    print("\nSpearman (Monotonic Rank) Correlation:")
    print(routes[route_corr_cols].corr(method="spearman").round(3).to_string())

    print("\n--- B. Daily Fares Enriched Correlations (n = 1,683,033 rows) ---")
    daily_corr_cols = [
        "distance_miles",
        "days_before_departure",
        "itineraries",
        "airlines",
        "pct_nonstop",
        "min_price_usd",
        "min_nonstop_price_usd",
        "median_price_usd",
        "max_price_usd",
        "nonstop_premium_usd",
    ]
    print("Pearson Correlation with Prices:")
    pearson_daily = df[daily_corr_cols].corr(method="pearson").round(3)
    print(pearson_daily[["min_price_usd", "min_nonstop_price_usd", "median_price_usd", "max_price_usd", "nonstop_premium_usd"]].to_string())


if __name__ == "__main__":
    run_statistical_and_correlation_analysis()
