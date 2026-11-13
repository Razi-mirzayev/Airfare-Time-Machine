"""
===============================================================================
PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
PHASE 5: POWER BI DATA MODEL EXPORTER & EXECUTIVE DASHBOARD PREVIEW GENERATOR
FILE: 04_generate_powerbi_exports_and_preview.py
DESCRIPTION:
    1. Exports pre-modeled Star Schema CSV tables to `PowerBI/Data_Model_Exports/`
       for instant, memory-efficient import into Power BI Desktop.
    2. Renders a high-resolution (300 DPI) Executive Power BI Dashboard canvas
       (`Images/09_powerbi_executive_dashboard_preview.png`) showcasing KPI Cards,
       US Route Network Map, Booking Time Curve, Airline Comparison, Monthly
       Trends, Day-of-Week, and Flight Duration Analysis.
===============================================================================
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches

DATASET_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Dataset"
PBI_EXPORT_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\PowerBI\Data_Model_Exports"
IMAGES_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Images"

os.makedirs(PBI_EXPORT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)


def build_powerbi_exports_and_dashboard():
    airports = pd.read_csv(os.path.join(DATASET_DIR, "airports.csv"))
    routes = pd.read_csv(os.path.join(DATASET_DIR, "routes.csv"))
    daily = pd.read_csv(
        os.path.join(DATASET_DIR, "daily_fares.csv"),
        parse_dates=["search_date", "departure_date"],
    )

    # 1. Enrich & Export Star Schema Dimension Tables
    routes["price_per_mile_usd"] = (routes["median_price_usd"] / routes["distance_miles"]).round(4)
    routes["distance_haul"] = np.select(
        [
            routes["distance_miles"] < 500,
            routes["distance_miles"].between(500, 1500),
            routes["distance_miles"] > 1500,
        ],
        ["Short-Haul (<500 mi)", "Medium-Haul (500-1500 mi)", "Long-Haul (>1500 mi)"],
        default="Other",
    )
    airports.to_csv(os.path.join(PBI_EXPORT_DIR, "dim_airports.csv"), index=False)
    routes.to_csv(os.path.join(PBI_EXPORT_DIR, "dim_routes.csv"), index=False)

    # Create Calendar Dimension (`dim_calendar.csv`)
    dates = pd.date_range("2026-03-01", "2027-03-31", freq="D")
    dim_calendar = pd.DataFrame({"Date": dates})
    dim_calendar["Year"] = dim_calendar["Date"].dt.year
    dim_calendar["Month_Num"] = dim_calendar["Date"].dt.month
    dim_calendar["Month_Name"] = dim_calendar["Date"].dt.strftime("%b")
    dim_calendar["Year_Month"] = dim_calendar["Date"].dt.strftime("%Y-%m")
    dim_calendar["ISO_Day_Of_Week"] = dim_calendar["Date"].dt.dayofweek + 1
    dim_calendar["Day_Name"] = dim_calendar["Date"].dt.day_name()
    dim_calendar["Is_Weekend"] = dim_calendar["ISO_Day_Of_Week"].isin([5, 6, 7])
    dim_calendar.to_csv(os.path.join(PBI_EXPORT_DIR, "dim_calendar.csv"), index=False)

    # Create Aggregated Booking Window by Route (`agg_booking_curve_by_route.csv`)
    agg_booking = (
        daily.groupby(["route", "days_before_departure"])
        .agg(
            observations=("min_price_usd", "count"),
            avg_min_price_usd=("min_price_usd", "mean"),
            avg_nonstop_price_usd=("min_nonstop_price_usd", "mean"),
            avg_median_price_usd=("median_price_usd", "mean"),
            avg_max_price_usd=("max_price_usd", "mean"),
        )
        .round(2)
        .reset_index()
    )
    agg_booking.to_csv(os.path.join(PBI_EXPORT_DIR, "agg_booking_curve_by_route.csv"), index=False)

    # Create Aggregated Monthly Trends by Route (`agg_monthly_route_trends.csv`)
    daily["year_month"] = daily["departure_date"].dt.strftime("%Y-%m")
    agg_monthly = (
        daily.groupby(["route", "year_month"])
        .agg(
            observations=("min_price_usd", "count"),
            avg_min_price_usd=("min_price_usd", "mean"),
            avg_nonstop_price_usd=("min_nonstop_price_usd", "mean"),
            avg_median_price_usd=("median_price_usd", "mean"),
        )
        .round(2)
        .reset_index()
    )
    agg_monthly.to_csv(os.path.join(PBI_EXPORT_DIR, "agg_monthly_route_trends.csv"), index=False)
    print("Exported Star Schema tables to:", PBI_EXPORT_DIR)

    # =========================================================================
    # 2. GENERATE HIGH-RESOLUTION POWER BI EXECUTIVE DASHBOARD PREVIEW
    # =========================================================================
    print("Rendering 09_powerbi_executive_dashboard_preview.png ...")
    fig = plt.figure(figsize=(20, 12.5), dpi=300, facecolor="#F1F5F9")
    gs = gridspec.GridSpec(
        4,
        12,
        figure=fig,
        height_ratios=[0.65, 0.95, 2.5, 2.3],
        hspace=0.38,
        wspace=0.45,
    )

    # --- ROW 0: TOP BANNER & SLICER BAR ---
    ax_hdr = fig.add_subplot(gs[0, :])
    ax_hdr.set_facecolor("#0F172A")
    ax_hdr.set_xticks([])
    ax_hdr.set_yticks([])
    for spine in ax_hdr.spines.values():
        spine.set_visible(False)

    ax_hdr.text(
        0.015,
        0.62,
        "AIRFARE TIME MACHINE  |  US DOMESTIC FLIGHT PRICE ANALYTICS",
        color="#FFFFFF",
        fontsize=16,
        fontweight="bold",
        va="center",
    )
    ax_hdr.text(
        0.015,
        0.22,
        "Power BI Executive Dashboard  •  38.58M Flight Observations  •  1.68M Daily Route Summaries  •  50 US Hub Routes",
        color="#94A3B8",
        fontsize=10,
        va="center",
    )

    slicers = [
        ("Haul Category: All (3)", 0.56),
        ("Carrier Type: All (5)", 0.69),
        ("Origin Hub: All (16)", 0.81),
        ("Period: 2026–2027", 0.91),
    ]
    for label, xpos in slicers:
        ax_hdr.text(
            xpos,
            0.48,
            f"  {label}  ▼  ",
            color="#E2E8F0",
            fontsize=9.5,
            fontweight="bold",
            va="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1E293B", edgecolor="#38BDF8", lw=1.0),
        )

    # --- ROW 1: 6 KPI CARDS ---
    kpis = [
        ("AVERAGE TICKET PRICE", "$209.85", "Median: $176.00 | 38.58M Flights", "#1D3557"),
        ("CHEAPEST FLIGHT", "$19.00", "Frontier Airlines (Nonstop Promo)", "#2A9D8F"),
        ("MOST EXPENSIVE FLIGHT", "$5,046.00", "American Airlines (Last-Minute)", "#E63946"),
        ("OPTIMAL BOOKING WINDOW", "31–60 Days", "Saves $98.67 (-34.7%) vs Last Min", "#2A9D8F"),
        ("CHEAPEST DAY TO FLY", "Tuesday ($163)", "Sunday ($251) is +53.7% pricier", "#457B9D"),
        ("DIRECT (NONSTOP) SHARE", "90.14%", "Avg Nonstop Premium: +$14.09", "#1D3557"),
    ]
    for idx, (title, value, sub, accent) in enumerate(kpis):
        ax_kpi = fig.add_subplot(gs[1, idx * 2 : (idx + 1) * 2])
        ax_kpi.set_facecolor("#FFFFFF")
        ax_kpi.set_xticks([])
        ax_kpi.set_yticks([])
        for sp in ax_kpi.spines.values():
            sp.set_edgecolor("#CBD5E1")
            sp.set_linewidth(1.0)
        ax_kpi.spines["top"].set_edgecolor(accent)
        ax_kpi.spines["top"].set_linewidth(4.0)

        ax_kpi.text(0.08, 0.78, title, color="#64748B", fontsize=8.5, fontweight="bold", va="center")
        ax_kpi.text(0.08, 0.43, value, color=accent, fontsize=18, fontweight="bold", va="center")
        ax_kpi.text(0.08, 0.14, sub, color="#475569", fontsize=8, va="center")

    # --- ROW 2, COL 0..4: BOOKING WINDOW J-CURVE ---
    ax_p1 = fig.add_subplot(gs[2, 0:5])
    ax_p1.set_facecolor("#FFFFFF")
    dbd = (
        daily.groupby("days_before_departure")
        .agg(med=("median_price_usd", "mean"), mn=("min_price_usd", "mean"), ns=("min_nonstop_price_usd", "mean"))
        .reset_index()
    )
    ax_p1.plot(dbd["days_before_departure"], dbd["med"], color="#1D3557", lw=2.3, label="Median Fare ($)")
    ax_p1.plot(dbd["days_before_departure"], dbd["ns"], color="#2A9D8F", lw=1.8, ls="--", label="Nonstop Min ($)")
    ax_p1.plot(dbd["days_before_departure"], dbd["mn"], color="#E76F51", lw=1.8, label="Overall Min ($)")
    ax_p1.axvspan(31, 60, color="#2A9D8F", alpha=0.15, label="Sweet Spot (31-60d)")
    ax_p1.axvspan(7, 14, color="#E63946", alpha=0.15, label="Last Minute (7-14d)")
    ax_p1.invert_xaxis()
    ax_p1.set_title("Booking Time Analysis: 180 -> 7 Days Countdown", fontsize=11, fontweight="bold", color="#0F172A")
    ax_p1.set_xlabel("Days Before Departure", fontsize=9)
    ax_p1.set_ylabel("USD ($)", fontsize=9)
    ax_p1.legend(loc="upper left", fontsize=7.5, frameon=True)
    ax_p1.grid(True, linestyle=":", alpha=0.6)

    # --- ROW 2, COL 5..8: US ROUTE NETWORK & HUB MAP ---
    ax_map = fig.add_subplot(gs[2, 5:9])
    ax_map.set_facecolor("#F8FAFC")
    ap_coords = airports.set_index("iata")[["latitude", "longitude", "city"]].to_dict("index")
    for _, r in routes.iterrows():
        o, d = r["origin"], r["destination"]
        if o in ap_coords and d in ap_coords:
            lon1, lat1 = ap_coords[o]["longitude"], ap_coords[o]["latitude"]
            lon2, lat2 = ap_coords[d]["longitude"], ap_coords[d]["latitude"]
            col = "#E63946" if r["median_price_usd"] >= 250 else "#457B9D" if r["median_price_usd"] >= 160 else "#2A9D8F"
            ax_map.plot([lon1, lon2], [lat1, lat2], color=col, alpha=0.35, lw=1.2, zorder=1)

    for iata, info in ap_coords.items():
        ax_map.scatter(info["longitude"], info["latitude"], s=75, color="#0F172A", edgecolor="#38BDF8", lw=1.5, zorder=3)
        ax_map.text(info["longitude"] + 0.6, info["latitude"] + 0.4, iata, fontsize=7.5, fontweight="bold", color="#0F172A", zorder=4)

    ax_map.set_xlim(-127, -66)
    ax_map.set_ylim(25, 50)
    ax_map.set_title("US Route Network Map (Colored by Median Fare Tier)", fontsize=11, fontweight="bold", color="#0F172A")
    ax_map.set_xlabel("Longitude", fontsize=8.5)
    ax_map.set_ylabel("Latitude", fontsize=8.5)
    p_low = mpatches.Patch(color="#2A9D8F", label="<$160 (Short-Haul)")
    p_mid = mpatches.Patch(color="#457B9D", label="$160–$249 (Mid-Haul)")
    p_high = mpatches.Patch(color="#E63946", label=">=$250 (Transcon)")
    ax_map.legend(handles=[p_low, p_mid, p_high], loc="lower left", fontsize=7.5)
    ax_map.grid(True, linestyle=":", alpha=0.4)

    # --- ROW 2, COL 9..12: AIRLINE PRICE COMPARISON ---
    ax_al = fig.add_subplot(gs[2, 9:12])
    ax_al.set_facecolor("#FFFFFF")
    al_names = ["Frontier", "Spirit", "Southwest", "Alaska", "United", "American", "Delta", "JetBlue", "JSX"]
    al_prices = [131.1, 134.3, 155.8, 191.0, 204.7, 225.6, 231.3, 254.0, 301.2]
    al_cols = ["#2A9D8F", "#2A9D8F", "#E9C46A", "#457B9D", "#1D3557", "#1D3557", "#1D3557", "#E9C46A", "#E63946"]
    bars = ax_al.barh(al_names, al_prices, color=al_cols, edgecolor="black", height=0.65)
    for b, v in zip(bars, al_prices):
        ax_al.text(v + 4, b.get_y() + b.get_height() / 2, f"${v:.0f}", va="center", fontsize=8, fontweight="bold")
    ax_al.set_xlim(0, 345)
    ax_al.set_title("Airline Average Ticket Price ($)", fontsize=11, fontweight="bold", color="#0F172A")
    ax_al.set_xlabel("Avg Price ($)", fontsize=9)
    ax_al.grid(True, axis="x", linestyle=":", alpha=0.6)

    # --- ROW 3, COL 0..4: MONTHLY SEASONAL PRICE TRENDS ---
    ax_m = fig.add_subplot(gs[3, 0:4])
    ax_m.set_facecolor("#FFFFFF")
    m_df = (
        daily[daily["year_month"] >= "2026-04"]
        .groupby("year_month")
        .agg(med=("median_price_usd", "mean"), mn=("min_price_usd", "mean"))
        .reset_index()
        .sort_values("year_month")
    )
    short_m = [x[2:] for x in m_df["year_month"]]
    ax_m.plot(short_m, m_df["med"], marker="o", color="#1D3557", lw=2.2, label="Avg Median ($)")
    ax_m.plot(short_m, m_df["mn"], marker="s", color="#2A9D8F", lw=1.8, ls="--", label="Avg Min ($)")
    ax_m.set_title("Monthly Price Trends (Apr 2026 – Mar 2027)", fontsize=11, fontweight="bold", color="#0F172A")
    ax_m.set_ylabel("USD ($)", fontsize=9)
    ax_m.tick_params(axis="x", rotation=35, labelsize=8)
    ax_m.legend(loc="upper right", fontsize=8)
    ax_m.grid(True, linestyle=":", alpha=0.6)

    # --- ROW 3, COL 4..8: DEPARTURE DAY OF WEEK & FLIGHT DURATION ---
    ax_dow = fig.add_subplot(gs[3, 4:8])
    ax_dow.set_facecolor("#FFFFFF")
    dows = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_vals = [204.3, 163.2, 165.8, 191.6, 203.9, 190.8, 250.8]
    dow_c = ["#457B9D", "#2A9D8F", "#2A9D8F", "#457B9D", "#E76F51", "#457B9D", "#E63946"]
    b_dow = ax_dow.bar(dows, dow_vals, color=dow_c, edgecolor="black", width=0.6)
    for b, v in zip(b_dow, dow_vals):
        ax_dow.text(b.get_x() + b.get_width() / 2, v + 4, f"${v:.0f}", ha="center", fontsize=8.5, fontweight="bold")
    ax_dow.set_ylim(0, 285)
    ax_dow.set_title("Avg Median Fare by Departure Day of Week ($)", fontsize=11, fontweight="bold", color="#0F172A")
    ax_dow.set_ylabel("Median Price ($)", fontsize=9)
    ax_dow.grid(True, axis="y", linestyle=":", alpha=0.6)

    # --- ROW 3, COL 8..12: FLIGHT DURATION & STOPS ANALYSIS ---
    ax_dur = fig.add_subplot(gs[3, 8:12])
    ax_dur.set_facecolor("#FFFFFF")
    dur_labels = ["<=2h\n(Nonstop)", "2h–4h\n(Mid-Haul)", "4h–6h\n(Transcon)", ">6h\n(Layover)"]
    dur_prices = [151.9, 192.4, 276.3, 259.6]
    dur_c = ["#2A9D8F", "#457B9D", "#1D3557", "#E76F51"]
    b_dur = ax_dur.bar(dur_labels, dur_prices, color=dur_c, edgecolor="black", width=0.55)
    for b, v in zip(b_dur, dur_prices):
        ax_dur.text(b.get_x() + b.get_width() / 2, v + 5, f"${v:.1f}", ha="center", fontsize=8.5, fontweight="bold")
    ax_dur.set_ylim(0, 315)
    ax_dur.set_title("Flight Duration Analysis: Avg Ticket Price ($)", fontsize=11, fontweight="bold", color="#0F172A")
    ax_dur.set_ylabel("Avg Price ($)", fontsize=9)
    ax_dur.grid(True, axis="y", linestyle=":", alpha=0.6)

    out_path = os.path.join(IMAGES_DIR, "09_powerbi_executive_dashboard_preview.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="#F1F5F9")
    plt.close()
    print("Dashboard preview saved to:", out_path)


if __name__ == "__main__":
    build_powerbi_exports_and_dashboard()
