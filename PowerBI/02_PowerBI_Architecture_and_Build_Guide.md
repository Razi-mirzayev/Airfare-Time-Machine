# Power BI Dashboard Architecture & Build Guide
## Project: Airfare Time Machine – US Flight Price Analysis

This document specifies the **Star Schema Data Model**, **Relationships**, **DAX Architecture**, and **3-Page Executive Layout** for the Power BI Dashboard.

---

## 1. Star Schema Data Model in Power BI

To achieve sub-second interactivity across **38,584,829 flight observations** and **1,683,033 daily route summaries**, the Power BI model uses a **Hybrid Star Schema**:

### Dimension Tables (1-Side of Relationships)
1. **`dim_airports`** (`iata` PK): 16 US major airports with geographic coordinates (`latitude`, `longitude`) categorized as *Data Category: Latitude / Longitude* for native Power BI Map visuals.
2. **`dim_routes`** (`route_code` PK): 50 directional routes with `distance_miles`, `distance_haul`, `pct_nonstop`, and `median_price_usd`.
3. **`dim_airlines`** (`airline_id` PK): 17 airlines / combinations categorized by `carrier_type` (*Ultra Low-Cost*, *Low-Cost*, *Legacy*, *Regional*, *Multi-Carrier*).
4. **`dim_calendar`** (`Date` PK): Continuous date table (`2026-03-01` to `2027-03-31`) marked as the official **Date Table**, containing `Year`, `Month Name`, `Month Number`, `Year-Month`, `Day of Week Name`, `ISO Day of Week` (for proper Monday–Sunday sorting), and `Season`.

### Fact Tables (*-Side of Relationships)
5. **`fact_daily_fares`**: 1,683,033 daily route-departure summaries (`min_price_usd`, `min_nonstop_price_usd`, `median_price_usd`, `max_price_usd`, `days_before_departure`, `cheapest_airline_id`).
6. **`fact_flight_prices_agg` / `fact_flight_prices`**: Granular itinerary-level metrics aggregated by `(route_code, airline_id, stops, departure_time_bucket, duration_bucket)` for instant slicing of airline, stop, and duration visuals.

### Model Relationships
| From Table (Many `*`) | From Column | To Table (One `1`) | To Column | Cardinality | Cross-Filter Direction | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `fact_daily_fares` | `route_code` | `dim_routes` | `route_code` | `*:1` | Single | **Active** |
| `fact_daily_fares` | `cheapest_airline_id` | `dim_airlines` | `airline_id` | `*:1` | Single | **Active** |
| `fact_daily_fares` | `departure_date` | `dim_calendar` | `Date` | `*:1` | Single | **Active** |
| `fact_flight_prices` | `route_code` | `dim_routes` | `route_code` | `*:1` | Single | **Active** |
| `fact_flight_prices` | `airline_id` | `dim_airlines` | `airline_id` | `*:1` | Single | **Active** |
| `dim_routes` | `origin_iata` | `dim_airports` | `iata` | `*:1` | Single | **Active** |
| `dim_routes` | `destination_iata` | `dim_airports` | `iata` | `*:1` | Single | *Inactive (`USERELATIONSHIP`)* |

---

## 2. Dashboard Page Architecture (3 Interactive Pages)

### Page 1: Executive Overview & Market Landscape
- **Top Header & Slicer Bar:**
  - Slicers: `Haul Category` (*Short / Medium / Long-Haul*), `Origin City`, `Destination City`, `Carrier Type`, `Departure Month`.
- **Row 1 – 6 Executive KPI Cards:**
  1. **Average Ticket Price:** `$209.85` (Sub-label: *Granular Mean | $176.00 Median*)
  2. **Avg Daily Median Fare:** `$195.77` (Sub-label: *Across 1.68M Route-Days*)
  3. **Cheapest Flight:** `$19.00` (Sub-label: *Frontier Airlines | Nonstop Promo*)
  4. **Most Expensive Flight:** `$5,046.00` (Sub-label: *American Airlines | Last-Minute*)
  5. **Optimal Sweet Spot Savings:** `34.7% (-$98.67)` (Sub-label: *31–60 Days vs. Last Minute*)
  6. **Direct (Nonstop) Share:** `90.14%` (Sub-label: *Avg Nonstop Premium: +$14.09*)
- **Row 2 – Core Visuals:**
  - **Visual 1 (Left – Clustered Horizontal Bar & Dot Chart):** *Airline Price Comparison & Daily Cheapest Win Share (%)* (`Frontier $131` winning `48.1%` of days vs. `Delta $231`, `American $226`, `United $205`).
  - **Visual 2 (Right – Azure Map / Route Network Map):** *US Hub Airport & Route Price Map* — Bubble size = `price_observations`, Color = `median_price_usd` (`$109 LAX-SFO` in Teal to `$292 SFO-JFK` in Coral Red).
- **Row 3 – Time & Route Ranking:**
  - **Visual 3 (Left – Multi-Line Area Chart):** *Monthly Price Trends (`2026-04` to `2027-03`)* showing Summer Peak (`June $226.74`), September Low (`$180.23`), and Holiday Peak (`Dec $208.75`).
  - **Visual 4 (Right – Matrix Table with Data Bars):** *Top Cheapest & Most Expensive Routes* showing `Route`, `Distance`, `Median Fare ($)`, `Price per Mile ($/mi)`, and `Nonstop %`.

---

### Page 2: The Airfare Time Machine (Booking Window & Schedule Optimizer)
- **Visual 1 (Full-Width Hero Line Chart):** *Booking Time Analysis (`180` down to `7` Days Before Departure)* with vertical reference lines at **Day 49 (Global Minimum: `$182.17`)**, **Day 21**, **Day 14**, and **Day 7 (`$292.65`)** illustrating ATPCO advance-purchase bucket expirations.
- **Visual 2 (Bottom Left – Column Chart):** *Departure Day-of-Week Price Comparison* (`Tuesday $163.19` and `Wednesday $165.75` highlighted in green vs. `Sunday $250.79` in red).
- **Visual 3 (Bottom Center – Clustered Bar Chart):** *Buyer Persona Pricing by Haul Category* comparing *Smart Planner (31–60d)*, *Early Bird (121–180d)*, and *Last-Minute (7–14d)*.
- **Visual 4 (Bottom Right – Column/Line Combo):** *Departure Time-of-Day Analysis* (`Evening $198.89` and `Early Morning $201.15` vs. `Morning Peak $224.48`).

---

### Page 3: Flight Duration, Stops & Distance Yield Explorer
- **Visual 1 (Top Left – Scatter Plot):** *Distance (`distance_miles`) vs. Median Price (`$`) and Yield (`$/mile`)* colored by `distance_haul` (*Economies of Distance*: `$0.395/mi` Short-Haul vs. `$0.110/mi` Long-Haul).
- **Visual 2 (Top Right – Combo Bar Chart):** *Direct (`0 Stops`: `$210.78`, `3.15h`) vs. Connecting (`1 Stop`: `$201.53`, `8.45h` | `2 Stops`: `$191.93`, `11.17h`)* flight comparison.
- **Visual 3 (Bottom Left – Horizontal Bar Chart):** *Top 10 Routes by Nonstop Convenience Premium* (`SFO-EWR +$79.61`, `EWR-SFO +$76.97`, `LAX-BOS +$41.38`).
- **Visual 4 (Bottom Right – Bar Chart):** *Flight Duration Buckets Analysis* (`<=2h: $151.85`, `2–4h: $192.45`, `4–6h: $276.28`, `>6h Layover: $259.55`).
