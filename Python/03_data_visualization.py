"""
===============================================================================
PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
PHASE 4: PYTHON DATA ANALYSIS
FILE: 03_data_visualization.py
DESCRIPTION:
    Generates 8 publication-grade, portfolio-ready visualizations (300 DPI)
    using Matplotlib and Seaborn, aligned 100% with SQL findings:
      1. 01_booking_window_j_curve.png
      2. 02_airline_price_comparison.png
      3. 03_day_of_week_and_time_analysis.png
      4. 04_seasonal_monthly_trends.png
      5. 05_distance_vs_price_and_yield.png
      6. 06_direct_vs_connecting_premium.png
      7. 07_outlier_distribution_analysis.png
      8. 08_correlation_matrix_heatmap.png
===============================================================================
"""

import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
import seaborn as sns

# Set global visual theme
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#CCCCCC"
plt.rcParams["axes.linewidth"] = 0.8
sns.set_theme(style="whitegrid", palette="deep")

DATASET_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Dataset"
IMAGES_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Images"
os.makedirs(IMAGES_DIR, exist_ok=True)


def generate_all_visualizations():
    print("Loading datasets for visualization...")
    routes = pd.read_csv(os.path.join(DATASET_DIR, "routes.csv"))
    daily = pd.read_csv(
        os.path.join(DATASET_DIR, "daily_fares.csv"),
        parse_dates=["search_date", "departure_date"],
    )
    pf = pq.ParquetFile(os.path.join(DATASET_DIR, "flight_prices.parquet"))

    routes["price_per_mile_usd"] = routes["median_price_usd"] / routes["distance_miles"]
    routes["distance_haul"] = np.select(
        [
            routes["distance_miles"] < 500,
            routes["distance_miles"].between(500, 1500),
            routes["distance_miles"] > 1500,
        ],
        ["Short-Haul (<500 mi)", "Medium-Haul (500-1500 mi)", "Long-Haul (>1500 mi)"],
        default="Other",
    )

    # =========================================================================
    # CHART 1: THE AIRFARE TIME MACHINE CURVE (180 -> 7 Days Before Departure)
    # =========================================================================
    print("Generating Chart 1: 01_booking_window_j_curve.png ...")
    dbd = (
        daily.groupby("days_before_departure")
        .agg(
            avg_median=("median_price_usd", "mean"),
            avg_min=("min_price_usd", "mean"),
            avg_nonstop=("min_nonstop_price_usd", "mean"),
            p25_median=("median_price_usd", lambda x: x.quantile(0.25)),
            p75_median=("median_price_usd", lambda x: x.quantile(0.75)),
        )
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(13, 6.5), dpi=300)
    ax.plot(
        dbd["days_before_departure"],
        dbd["avg_median"],
        color="#1B365D",
        linewidth=2.8,
        label="Average Daily Median Fare ($)",
    )
    ax.plot(
        dbd["days_before_departure"],
        dbd["avg_nonstop"],
        color="#008080",
        linewidth=2.2,
        linestyle="--",
        label="Average Nonstop Min Fare ($)",
    )
    ax.plot(
        dbd["days_before_departure"],
        dbd["avg_min"],
        color="#E07A5F",
        linewidth=2.2,
        label="Average Overall Min Fare ($)",
    )

    # Highlight Sweet Spot (31-60 days) and Last-Minute Surge (7-14 days)
    ax.axvspan(31, 60, color="#2A9D8F", alpha=0.15, label="Sweet Spot Window (31–60 Days: $185.40 Median)")
    ax.axvspan(7, 14, color="#E63946", alpha=0.15, label="Last-Minute Surge (7–14 Days: $284.07 Median)")

    # Annotate exact minimum (Day 49) and maximum (Day 7)
    ax.scatter([49], [182.17], color="#2A9D8F", s=90, zorder=5)
    ax.annotate(
        "Optimal Day 49\nMedian: $182.17\nMin: $108.78",
        xy=(49, 182.17),
        xytext=(68, 215),
        arrowprops=dict(arrowstyle="->", color="#2A9D8F", lw=1.5),
        fontsize=10,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#E8F8F5", edgecolor="#2A9D8F"),
    )

    ax.scatter([7], [292.65], color="#E63946", s=90, zorder=5)
    ax.annotate(
        "7 Days Before Departure\nMedian: $292.65 (+60.6%)",
        xy=(7, 292.65),
        xytext=(28, 282),
        arrowprops=dict(arrowstyle="->", color="#E63946", lw=1.5),
        fontsize=10,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#FDEDEC", edgecolor="#E63946"),
    )

    ax.invert_xaxis()  # Show countdown from 180 days down to 7 days
    ax.set_title(
        "Airfare Time Machine: Evolution of US Flight Prices from 180 to 7 Days Before Departure",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Days Before Departure (Countdown to Flight ->)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Ticket Price (USD $)", fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", frameon=True, fontsize=9.5)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "01_booking_window_j_curve.png"), dpi=300)
    plt.close()

    # =========================================================================
    # CHART 2: AIRLINE PRICE COMPARISON & CHEAPEST-DAY WIN SHARE
    # =========================================================================
    print("Generating Chart 2: 02_airline_price_comparison.png ...")
    fp_airline = pf.read(columns=["airline", "price_usd", "stops"]).to_pandas()
    major_airlines = [
        "Frontier Airlines",
        "Spirit Airlines",
        "Southwest Airlines",
        "Alaska Airlines",
        "United Airlines",
        "Sun Country Airlines",
        "American Airlines",
        "Delta Air Lines",
        "JetBlue Airways",
        "JSX",
    ]
    sub_al = fp_airline[fp_airline["airline"].isin(major_airlines)].copy()
    al_stats = (
        sub_al.groupby("airline")
        .agg(
            avg_price=("price_usd", "mean"),
            median_price=("price_usd", "median"),
            nonstop_pct=("stops", lambda x: (x == 0).mean() * 100),
            obs=("price_usd", "count"),
        )
        .reset_index()
        .sort_values("avg_price", ascending=True)
    )

    cheapest_wins = (
        daily["cheapest_airline"]
        .value_counts(normalize=True)
        .mul(100)
        .rename("win_pct")
        .reset_index()
    )
    cheapest_wins.columns = ["airline", "win_pct"]
    al_stats = al_stats.merge(cheapest_wins, on="airline", how="left").fillna(0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300, sharey=True)
    colors = [
        "#2A9D8F" if a in ["Frontier Airlines", "Spirit Airlines"]
        else "#E9C46A" if a in ["Southwest Airlines", "JetBlue Airways", "Sun Country Airlines"]
        else "#264653"
        for a in al_stats["airline"]
    ]

    bars1 = ax1.barh(al_stats["airline"], al_stats["avg_price"], color=colors, edgecolor="black", alpha=0.88)
    ax1.scatter(al_stats["median_price"], al_stats["airline"], color="#E63946", s=55, zorder=5, label="Median Fare ($)")
    for bar, val in zip(bars1, al_stats["avg_price"]):
        ax1.text(val + 4, bar.get_y() + bar.get_height() / 2, f"${val:.0f}", va="center", fontsize=9.5, fontweight="bold")
    ax1.set_xlim(0, 345)
    ax1.set_title("Average & Median Ticket Price by Airline ($)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Price (USD $)", fontsize=10.5, fontweight="bold")
    ax1.legend(loc="lower right")

    bars2 = ax2.barh(al_stats["airline"], al_stats["win_pct"], color="#457B9D", edgecolor="black", alpha=0.88)
    for bar, val in zip(bars2, al_stats["win_pct"]):
        ax2.text(val + 0.8, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", fontsize=9.5, fontweight="bold")
    ax2.set_xlim(0, 56)
    ax2.set_title("Share of Days Winning 'Cheapest Airline' (%)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Share of Daily Cheapest Fares (%)", fontsize=10.5, fontweight="bold")

    fig.suptitle(
        "Airline Market Positioning: Average Fare vs. Daily Price Leadership (38.58M Observations)",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "02_airline_price_comparison.png"), dpi=300, bbox_inches="tight")
    plt.close()
    del fp_airline, sub_al

    # =========================================================================
    # CHART 3: DAY-OF-WEEK & DEPARTURE TIME-OF-DAY ANALYSIS
    # =========================================================================
    print("Generating Chart 3: 03_day_of_week_and_time_analysis.png ...")
    daily["dow_num"] = daily["departure_date"].dt.dayofweek
    daily["dow_name"] = daily["departure_date"].dt.day_name()
    dow_df = (
        daily.groupby(["dow_num", "dow_name"])
        .agg(avg_median=("median_price_usd", "mean"), avg_min=("min_price_usd", "mean"))
        .reset_index()
        .sort_values("dow_num")
    )

    tod_summary = pd.DataFrame(
        {
            "bucket": [
                "Early Morning\n(05:00-08:59)",
                "Morning\n(09:00-11:59)",
                "Afternoon\n(12:00-16:59)",
                "Evening\n(17:00-20:59)",
                "Night / Red-Eye\n(21:00-04:59)",
            ],
            "avg_price": [201.15, 224.48, 216.44, 198.89, 209.66],
            "median_price": [169.0, 185.0, 180.0, 168.0, 181.0],
        }
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), dpi=300)
    dow_colors = ["#2A9D8F" if d in ["Tuesday", "Wednesday"] else "#E63946" if d == "Sunday" else "#457B9D" for d in dow_df["dow_name"]]
    b1 = ax1.bar(dow_df["dow_name"], dow_df["avg_median"], color=dow_colors, edgecolor="black", alpha=0.9)
    for bar, val in zip(b1, dow_df["avg_median"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, val + 3, f"${val:.1f}", ha="center", fontsize=9.5, fontweight="bold")
    ax1.set_ylim(0, 280)
    ax1.set_title("Average Median Price by Departure Day of Week", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Average Median Price ($)", fontsize=10.5, fontweight="bold")
    ax1.tick_params(axis="x", rotation=25)

    tod_colors = ["#2A9D8F", "#E63946", "#F4A261", "#2A9D8F", "#457B9D"]
    b2 = ax2.bar(tod_summary["bucket"], tod_summary["avg_price"], color=tod_colors, edgecolor="black", alpha=0.9)
    for bar, val in zip(b2, tod_summary["avg_price"]):
        ax2.text(bar.get_x() + bar.get_width() / 2, val + 3, f"${val:.1f}", ha="center", fontsize=9.5, fontweight="bold")
    ax2.set_ylim(0, 260)
    ax2.set_title("Average Ticket Price by Departure Time of Day", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Average Ticket Price ($)", fontsize=10.5, fontweight="bold")

    fig.suptitle("When to Fly: Day-of-Week & Time-of-Day Price Differentials", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "03_day_of_week_and_time_analysis.png"), dpi=300, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # CHART 4: SEASONAL & MONTHLY PRICE TRENDS
    # =========================================================================
    print("Generating Chart 4: 04_seasonal_monthly_trends.png ...")
    daily["year_month"] = daily["departure_date"].dt.strftime("%Y-%m")
    # Filter to full calendar months (2026-04 through 2027-03) to avoid censored March 2026
    m_df = (
        daily[daily["year_month"] >= "2026-04"]
        .groupby("year_month")
        .agg(
            avg_median=("median_price_usd", "mean"),
            avg_nonstop=("min_nonstop_price_usd", "mean"),
            avg_min=("min_price_usd", "mean"),
        )
        .reset_index()
        .sort_values("year_month")
    )

    fig, ax = plt.subplots(figsize=(13, 6), dpi=300)
    ax.plot(m_df["year_month"], m_df["avg_median"], marker="o", linewidth=2.6, color="#1D3557", label="Avg Median Fare ($)")
    ax.plot(m_df["year_month"], m_df["avg_nonstop"], marker="s", linewidth=2.2, linestyle="--", color="#2A9D8F", label="Avg Nonstop Min Fare ($)")
    ax.plot(m_df["year_month"], m_df["avg_min"], marker="^", linewidth=2.2, color="#E76F51", label="Avg Overall Min Fare ($)")

    for i, row in m_df.iterrows():
        ax.text(i, row["avg_median"] + 4, f"${row['avg_median']:.0f}", ha="center", fontsize=9, fontweight="bold", color="#1D3557")

    ax.axvspan(1.8, 3.2, color="#F4A261", alpha=0.2, label="Summer Peak (Jun–Jul)")
    ax.axvspan(6.8, 8.2, color="#E63946", alpha=0.15, label="Holiday Season (Nov–Dec)")
    ax.set_ylim(95, 250)
    ax.set_title("Seasonal Airfare Trends Across a Full 12-Month Cycle (Apr 2026 – Mar 2027)", fontsize=13.5, fontweight="bold")
    ax.set_xlabel("Departure Month (YYYY-MM)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Ticket Price (USD $)", fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "04_seasonal_monthly_trends.png"), dpi=300)
    plt.close()

    # =========================================================================
    # CHART 5: DISTANCE VS. PRICE & ECONOMIES OF DISTANCE (PRICE PER MILE)
    # =========================================================================
    print("Generating Chart 5: 05_distance_vs_price_and_yield.png ...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)

    sns.regplot(
        data=routes,
        x="distance_miles",
        y="median_price_usd",
        ax=ax1,
        scatter_kws={"s": 70, "color": "#1D3557", "alpha": 0.8},
        line_kws={"color": "#E63946", "linewidth": 2.2},
    )
    ax1.set_title("Flight Distance vs. Median Price (r = +0.887)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Route Distance (Miles)", fontsize=10.5, fontweight="bold")
    ax1.set_ylabel("Route Median Price ($)", fontsize=10.5, fontweight="bold")

    sns.scatterplot(
        data=routes,
        x="distance_miles",
        y="price_per_mile_usd",
        hue="distance_haul",
        s=90,
        palette={"Short-Haul (<500 mi)": "#E63946", "Medium-Haul (500-1500 mi)": "#F4A261", "Long-Haul (>1500 mi)": "#2A9D8F"},
        ax=ax2,
    )
    ax2.set_title("Economies of Distance: Price per Mile vs. Distance (r = -0.776)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Route Distance (Miles)", fontsize=10.5, fontweight="bold")
    ax2.set_ylabel("Median Price per Mile ($ / Mile)", fontsize=10.5, fontweight="bold")
    ax2.legend(title="Haul Category")

    fig.suptitle("Aviation Economics: Total Fare Scales Linearly While Yield ($/Mile) Drops Sharply", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "05_distance_vs_price_and_yield.png"), dpi=300, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # CHART 6: DIRECT VS. CONNECTING FLIGHTS & TOP NONSTOP PREMIUM ROUTES
    # =========================================================================
    print("Generating Chart 6: 06_direct_vs_connecting_premium.png ...")
    valid_ns = daily[daily["min_nonstop_price_usd"].notna()].copy()
    valid_ns["ns_premium"] = valid_ns["min_nonstop_price_usd"] - valid_ns["min_price_usd"]
    top_ns = (
        valid_ns.groupby("route")["ns_premium"]
        .mean()
        .reset_index()
        .sort_values("ns_premium", ascending=False)
        .head(10)
    )

    stops_df = pd.DataFrame(
        {
            "Stops": ["0 Stops\n(Nonstop: 90.1%)", "1 Stop\n(Connecting: 9.7%)", "2 Stops\n(Multi-Stop: 0.15%)"],
            "Avg_Price": [210.78, 201.53, 191.93],
            "Avg_Hours": [3.15, 8.45, 11.17],
        }
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), dpi=300)
    b1 = ax1.bar(stops_df["Stops"], stops_df["Avg_Price"], color=["#2A9D8F", "#457B9D", "#E76F51"], width=0.55, edgecolor="black")
    for bar, pr, hr in zip(b1, stops_df["Avg_Price"], stops_df["Avg_Hours"]):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            pr + 5,
            f"${pr:.1f}\n({hr:.1f} hrs)",
            ha="center",
            fontsize=9.5,
            fontweight="bold",
        )
    ax1.set_ylim(0, 260)
    ax1.set_title("Global Average Fare & Travel Time by Number of Stops", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Average Ticket Price ($)", fontsize=10.5, fontweight="bold")

    b2 = ax2.barh(top_ns["route"][::-1], top_ns["ns_premium"][::-1], color="#E63946", edgecolor="black", alpha=0.88)
    for bar, val in zip(b2, top_ns["ns_premium"][::-1]):
        ax2.text(val + 1.2, bar.get_y() + bar.get_height() / 2, f"+${val:.2f}", va="center", fontsize=9.5, fontweight="bold")
    ax2.set_xlim(0, 92)
    ax2.set_title("Top 10 Routes with Highest Nonstop Convenience Premium ($)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Avg Nonstop Premium over Cheapest Connecting Flight ($)", fontsize=10.5, fontweight="bold")

    fig.suptitle("Direct vs. Connecting Flights: Time Penalty vs. Nonstop Price Premium", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "06_direct_vs_connecting_premium.png"), dpi=300, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # CHART 7: OUTLIER & DISTRIBUTION ANALYSIS ACROSS HAUL CATEGORIES
    # =========================================================================
    print("Generating Chart 7: 07_outlier_distribution_analysis.png ...")
    merged_haul = daily.merge(routes[["route", "distance_haul"]], on="route")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), dpi=300)

    sns.histplot(daily["median_price_usd"], bins=60, kde=True, color="#1D3557", ax=ax1)
    ax1.axvline(daily["median_price_usd"].mean(), color="#E63946", linestyle="--", lw=2, label=f"Mean: ${daily['median_price_usd'].mean():.1f}")
    ax1.axvline(daily["median_price_usd"].median(), color="#2A9D8F", linestyle="-", lw=2, label=f"Median: ${daily['median_price_usd'].median():.1f}")
    ax1.axvline(402.5, color="#F4A261", linestyle=":", lw=2.2, label="Global IQR Upper Fence: $402.5")
    ax1.set_xlim(40, 800)
    ax1.set_title("Right-Skewed Distribution of Daily Median Fares (Skew = 1.62)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Daily Median Price ($)", fontsize=10.5, fontweight="bold")
    ax1.legend()

    sns.boxplot(
        data=merged_haul,
        x="distance_haul",
        y="median_price_usd",
        hue="distance_haul",
        order=["Short-Haul (<500 mi)", "Medium-Haul (500-1500 mi)", "Long-Haul (>1500 mi)"],
        palette=["#2A9D8F", "#E9C46A", "#E76F51"],
        legend=False,
        flierprops={"marker": "o", "markersize": 2, "alpha": 0.25},
        ax=ax2,
    )
    ax2.set_ylim(40, 900)
    ax2.set_title("Contextual Fare Distributions & Outliers by Haul Category", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Route Haul Category", fontsize=10.5, fontweight="bold")
    ax2.set_ylabel("Daily Median Price ($)", fontsize=10.5, fontweight="bold")

    fig.suptitle("Statistical Distribution & Contextual Outlier Analysis (1.68M Daily Fare Summaries)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "07_outlier_distribution_analysis.png"), dpi=300, bbox_inches="tight")
    plt.close()

    # =========================================================================
    # CHART 8: CORRELATION MATRIX HEATMAP
    # =========================================================================
    print("Generating Chart 8: 08_correlation_matrix_heatmap.png ...")
    merged_corr = daily.merge(routes[["route", "distance_miles", "pct_nonstop", "price_per_mile_usd"]], on="route")
    merged_corr["nonstop_premium_usd"] = merged_corr["min_nonstop_price_usd"] - merged_corr["min_price_usd"]
    corr_cols = [
        "distance_miles",
        "pct_nonstop",
        "days_before_departure",
        "itineraries",
        "airlines",
        "min_price_usd",
        "min_nonstop_price_usd",
        "median_price_usd",
        "max_price_usd",
        "nonstop_premium_usd",
    ]
    corr_matrix = merged_corr[corr_cols].corr(method="pearson")

    fig, ax = plt.subplots(figsize=(10.5, 8.5), dpi=300)
    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        center=0,
        linewidths=0.6,
        cbar_kws={"shrink": 0.82},
        ax=ax,
    )
    ax.set_title("Pearson Correlation Matrix of Route, Competition & Fare Features", fontsize=13.5, fontweight="bold", pad=14)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "08_correlation_matrix_heatmap.png"), dpi=300)
    plt.close()
    print("All 8 visualizations successfully saved to:", IMAGES_DIR)


if __name__ == "__main__":
    generate_all_visualizations()
