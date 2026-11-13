-- ============================================================================
-- PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
-- PHASE 3: BUSINESS DATA ANALYSIS (MySQL 8.0)
-- FILE: 04_business_analysis_queries.sql
-- DESCRIPTION: 10 comprehensive analytical SQL queries answering key aviation
--              pricing, route competition, booking window, seasonality, and
--              traveler strategy questions.
-- ============================================================================

USE airfare_time_machine;

-- ============================================================================
-- ANALYSIS 1: AIRLINE PRICE COMPARISON & MARKET POSITIONING
-- Business Question:
-- How do airlines and business models (Ultra Low-Cost, Low-Cost, Legacy,
-- Regional, Multi-Carrier) compare in average ticket price, nonstop rate,
-- observation share, and frequency of winning the "daily cheapest airline" spot?
--
-- SQL Techniques Used:
-- CTEs (WITH), INNER JOIN, LEFT JOIN, GROUP BY, Aggregate Functions (COUNT,
-- AVG, MIN, MAX, STDDEV_POP), Window Functions (SUM() OVER, RANK() OVER).
-- ============================================================================
WITH airline_flight_stats AS (
    SELECT
        al.airline_id,
        al.airline_name,
        al.carrier_type,
        COUNT(*)                                                    AS total_observations,
        COUNT(DISTINCT fp.route_code)                               AS routes_served,
        ROUND(AVG(fp.price_usd), 2)                                 AS avg_price_usd,
        MIN(fp.price_usd)                                           AS min_price_usd,
        MAX(fp.price_usd)                                           AS max_price_usd,
        ROUND(STDDEV_POP(fp.price_usd), 2)                          AS std_price_usd,
        ROUND(
            SUM(CASE WHEN fp.stops = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        )                                                           AS nonstop_pct,
        ROUND(AVG(fp.duration_minutes), 1)                          AS avg_duration_min
    FROM fact_flight_prices fp
    INNER JOIN dim_airlines al ON fp.airline_id = al.airline_id
    GROUP BY al.airline_id, al.airline_name, al.carrier_type
),
daily_cheapest_wins AS (
    SELECT
        cheapest_airline_id,
        COUNT(*) AS days_won_cheapest
    FROM fact_daily_fares
    GROUP BY cheapest_airline_id
)
SELECT
    afs.airline_name,
    afs.carrier_type,
    afs.routes_served,
    afs.total_observations,
    ROUND(
        afs.total_observations * 100.0 / SUM(afs.total_observations) OVER (), 2
    )                                                               AS observation_share_pct,
    afs.avg_price_usd,
    afs.min_price_usd,
    afs.max_price_usd,
    afs.std_price_usd,
    afs.nonstop_pct,
    afs.avg_duration_min,
    COALESCE(dcw.days_won_cheapest, 0)                              AS days_won_cheapest,
    ROUND(
        COALESCE(dcw.days_won_cheapest, 0) * 100.0
        / (SELECT COUNT(*) FROM fact_daily_fares), 2
    )                                                               AS cheapest_win_rate_pct,
    RANK() OVER (ORDER BY afs.avg_price_usd ASC)                    AS affordability_rank
FROM airline_flight_stats afs
LEFT JOIN daily_cheapest_wins dcw
    ON afs.airline_id = dcw.cheapest_airline_id
ORDER BY afs.avg_price_usd ASC;


-- ============================================================================
-- ANALYSIS 2: ROUTE PRICE & COMPETITION ANALYSIS
-- Business Question:
-- How does carrier competition density (number of competing airlines) and
-- nonstop availability affect route pricing and daily price dispersion?
--
-- SQL Techniques Used:
-- Multiple INNER JOINs, GROUP BY, HAVING, CASE WHEN, Subquery comparison,
-- Window Functions (AVG() OVER PARTITION BY).
-- ============================================================================
SELECT
    r.route_code,
    CONCAT(ao.city, ' (', r.origin_iata, ') -> ', ad.city, ' (', r.destination_iata, ')') AS route_description,
    r.distance_miles,
    r.distance_haul,
    r.airlines_count                                                AS total_competing_airlines,
    CASE
        WHEN r.airlines_count >= 9 THEN 'High Competition (9-11)'
        WHEN r.airlines_count >= 7 THEN 'Moderate Competition (7-8)'
        ELSE 'Low Competition (5-6)'
    END                                                             AS competition_tier,
    r.pct_nonstop,
    ROUND(AVG(df.min_price_usd), 2)                                 AS avg_daily_min_usd,
    ROUND(AVG(df.median_price_usd), 2)                              AS avg_daily_median_usd,
    ROUND(AVG(df.max_price_usd), 2)                                 AS avg_daily_max_usd,
    ROUND(AVG(df.max_price_usd - df.min_price_usd), 2)              AS avg_daily_spread_usd,
    ROUND(
        AVG(df.median_price_usd) - AVG(AVG(df.median_price_usd)) OVER (PARTITION BY r.distance_haul),
        2
    )                                                               AS diff_vs_haul_avg_usd
FROM dim_routes r
INNER JOIN dim_airports ao    ON r.origin_iata = ao.iata
INNER JOIN dim_airports ad    ON r.destination_iata = ad.iata
INNER JOIN fact_daily_fares df ON r.route_code = df.route_code
GROUP BY
    r.route_code, ao.city, r.origin_iata, ad.city, r.destination_iata,
    r.distance_miles, r.distance_haul, r.airlines_count, r.pct_nonstop
HAVING COUNT(df.daily_fare_id) >= 30000
ORDER BY avg_daily_median_usd DESC;


-- ============================================================================
-- ANALYSIS 3: DEPARTURE DATE & DAY-OF-WEEK ANALYSIS
-- Business Question:
-- Which days of the week (Monday through Sunday) are the cheapest and most
-- expensive to fly, and what is the weekend vs. mid-week price premium?
--
-- SQL Techniques Used:
-- Date Functions (WEEKDAY, DAYNAME), CASE WHEN, Window Functions (RANK() OVER,
-- MIN() OVER), Aggregate Functions.
-- ============================================================================
WITH dow_metrics AS (
    SELECT
        WEEKDAY(departure_date) + 1                                 AS iso_day_of_week,
        DAYNAME(departure_date)                                     AS departure_day_name,
        CASE
            WHEN WEEKDAY(departure_date) IN (1, 2) THEN 'Mid-Week Low (Tue-Wed)'
            WHEN WEEKDAY(departure_date) IN (4, 6) THEN 'Peak Leisure/Return (Fri & Sun)'
            ELSE 'Standard Shoulder (Mon, Thu, Sat)'
        END                                                         AS day_demand_segment,
        COUNT(*)                                                    AS total_route_days,
        ROUND(AVG(min_price_usd), 2)                                AS avg_min_price_usd,
        ROUND(AVG(median_price_usd), 2)                             AS avg_median_price_usd,
        ROUND(AVG(min_nonstop_price_usd), 2)                        AS avg_nonstop_price_usd,
        ROUND(AVG(max_price_usd), 2)                                AS avg_max_price_usd
    FROM fact_daily_fares
    GROUP BY
        WEEKDAY(departure_date) + 1,
        DAYNAME(departure_date),
        day_demand_segment
)
SELECT
    iso_day_of_week,
    departure_day_name,
    day_demand_segment,
    total_route_days,
    avg_min_price_usd,
    avg_median_price_usd,
    avg_nonstop_price_usd,
    avg_max_price_usd,
    ROUND(
        avg_median_price_usd - MIN(avg_median_price_usd) OVER (), 2
    )                                                               AS premium_over_cheapest_day_usd,
    ROUND(
        (avg_median_price_usd - MIN(avg_median_price_usd) OVER ())
        / MIN(avg_median_price_usd) OVER () * 100, 2
    )                                                               AS premium_over_cheapest_day_pct,
    RANK() OVER (ORDER BY avg_median_price_usd ASC)                 AS cheapest_day_rank
FROM dow_metrics
ORDER BY iso_day_of_week ASC;


-- ============================================================================
-- ANALYSIS 4: BOOKING TIME ANALYSIS ("THE AIRFARE TIME MACHINE")
-- Business Question:
-- How do ticket prices evolve from 180 days before departure down to 7 days
-- before departure? What is the exact "Sweet Spot" booking window before prices
-- surge for last-minute travelers?
--
-- SQL Techniques Used:
-- CTE, CASE WHEN bucketing, Window Functions (LAG() OVER, FIRST_VALUE() OVER,
-- RANK() OVER).
-- ============================================================================
WITH booking_window_summary AS (
    SELECT
        CASE
            WHEN days_before_departure BETWEEN 7 AND 14   THEN '1. Last Minute (7-14 Days)'
            WHEN days_before_departure BETWEEN 15 AND 30  THEN '2. Short Term (15-30 Days)'
            WHEN days_before_departure BETWEEN 31 AND 60  THEN '3. Sweet Spot (31-60 Days)'
            WHEN days_before_departure BETWEEN 61 AND 90  THEN '4. Optimal Advance (61-90 Days)'
            WHEN days_before_departure BETWEEN 91 AND 120 THEN '5. Early Bird (91-120 Days)'
            ELSE '6. Far Advance (121-180 Days)'
        END                                                         AS booking_window_bucket,
        COUNT(*)                                                    AS observations,
        ROUND(AVG(itineraries_count), 2)                            AS avg_available_itineraries,
        ROUND(AVG(min_price_usd), 2)                                AS avg_min_price_usd,
        ROUND(AVG(median_price_usd), 2)                             AS avg_median_price_usd,
        ROUND(AVG(min_nonstop_price_usd), 2)                        AS avg_nonstop_price_usd,
        ROUND(AVG(max_price_usd), 2)                                AS avg_max_price_usd
    FROM fact_daily_fares
    GROUP BY booking_window_bucket
)
SELECT
    booking_window_bucket,
    observations,
    avg_available_itineraries,
    avg_min_price_usd,
    avg_median_price_usd,
    avg_nonstop_price_usd,
    avg_max_price_usd,
    ROUND(
        FIRST_VALUE(avg_median_price_usd) OVER (ORDER BY booking_window_bucket ASC)
        - avg_median_price_usd, 2
    )                                                               AS savings_vs_last_minute_usd,
    ROUND(
        (FIRST_VALUE(avg_median_price_usd) OVER (ORDER BY booking_window_bucket ASC) - avg_median_price_usd)
        / FIRST_VALUE(avg_median_price_usd) OVER (ORDER BY booking_window_bucket ASC) * 100, 2
    )                                                               AS savings_vs_last_minute_pct,
    RANK() OVER (ORDER BY avg_median_price_usd ASC)                 AS cheapest_window_rank
FROM booking_window_summary
ORDER BY booking_window_bucket ASC;


-- ============================================================================
-- ANALYSIS 5: SEASONAL & MONTHLY PRICE TRENDS
-- Business Question:
-- How do airfares fluctuate across months and seasons (Spring, Summer Peak,
-- Fall Shoulder, Holiday Season, Winter), and what is the Month-over-Month
-- (MoM) price growth rate?
--
-- SQL Techniques Used:
-- CTE, DATE_FORMAT, LAG() Window Function for Month-over-Month (MoM) change,
-- AVG() OVER() for seasonal index calculation.
-- ============================================================================
WITH monthly_trends AS (
    SELECT
        DATE_FORMAT(departure_date, '%Y-%m')                        AS departure_year_month,
        MONTHNAME(MIN(departure_date))                              AS month_name,
        CASE
            WHEN MONTH(departure_date) IN (6, 7, 8)   THEN 'Peak Summer (Jun-Aug)'
            WHEN MONTH(departure_date) IN (11, 12)    THEN 'Holiday Season (Nov-Dec)'
            WHEN MONTH(departure_date) IN (3, 4, 5)   THEN 'Spring Travel (Mar-May)'
            ELSE 'Off-Peak / Winter-Fall (Jan, Feb, Sep, Oct)'
        END                                                         AS season_category,
        COUNT(*)                                                    AS observations,
        COUNT(DISTINCT departure_date)                              AS distinct_departure_days,
        ROUND(AVG(min_price_usd), 2)                                AS avg_min_price_usd,
        ROUND(AVG(median_price_usd), 2)                             AS avg_median_price_usd,
        ROUND(AVG(min_nonstop_price_usd), 2)                        AS avg_nonstop_price_usd
    FROM fact_daily_fares
    GROUP BY DATE_FORMAT(departure_date, '%Y-%m'), season_category
)
SELECT
    departure_year_month,
    month_name,
    season_category,
    observations,
    distinct_departure_days,
    avg_min_price_usd,
    avg_median_price_usd,
    avg_nonstop_price_usd,
    LAG(avg_median_price_usd) OVER (ORDER BY departure_year_month)  AS prev_month_median_usd,
    ROUND(
        (avg_median_price_usd - LAG(avg_median_price_usd) OVER (ORDER BY departure_year_month))
        / NULLIF(LAG(avg_median_price_usd) OVER (ORDER BY departure_year_month), 0) * 100,
        2
    )                                                               AS mom_median_change_pct,
    ROUND(
        avg_median_price_usd / AVG(avg_median_price_usd) OVER () * 100, 1
    )                                                               AS seasonal_price_index
FROM monthly_trends
ORDER BY departure_year_month ASC;


-- ============================================================================
-- ANALYSIS 6: DIRECT (NONSTOP) VS. CONNECTING FLIGHTS
-- Business Question:
-- How do nonstop flights (0 stops) compare to 1-stop and 2-stop connecting
-- flights in price and travel duration, and what is the average "Nonstop
-- Convenience Premium" travelers pay to avoid a layover?
--
-- SQL Techniques Used:
-- Part A: Granular stops comparison on fact_flight_prices (CASE WHEN, Window).
-- Part B: Route-level Nonstop Premium analysis on fact_daily_fares.
-- ============================================================================
-- Part 6A: Granular Stops Breakdown
SELECT
    stops,
    CASE
        WHEN stops = 0 THEN 'Direct / Nonstop (0 Stops)'
        WHEN stops = 1 THEN 'Connecting (1 Stop)'
        ELSE 'Multi-Stop (2 Stops)'
    END                                                             AS flight_type,
    COUNT(*)                                                        AS total_observations,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)              AS share_of_flights_pct,
    ROUND(AVG(price_usd), 2)                                        AS avg_price_usd,
    MIN(price_usd)                                                  AS min_price_usd,
    MAX(price_usd)                                                  AS max_price_usd,
    ROUND(AVG(duration_minutes), 1)                                 AS avg_duration_minutes,
    ROUND(AVG(duration_minutes) / 60.0, 2)                          AS avg_duration_hours
FROM fact_flight_prices
GROUP BY stops
ORDER BY stops ASC;

-- Part 6B: Top 10 Routes with the Highest Nonstop Price Premium (min_nonstop - min_price)
SELECT
    df.route_code,
    CONCAT(ao.city, ' -> ', ad.city)                                AS route_name,
    r.distance_miles,
    r.pct_nonstop,
    COUNT(*)                                                        AS valid_days,
    ROUND(AVG(df.min_price_usd), 2)                                 AS avg_overall_min_usd,
    ROUND(AVG(df.min_nonstop_price_usd), 2)                         AS avg_nonstop_min_usd,
    ROUND(AVG(df.min_nonstop_price_usd - df.min_price_usd), 2)      AS avg_nonstop_premium_usd,
    ROUND(
        SUM(CASE WHEN df.min_nonstop_price_usd > df.min_price_usd THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 2
    )                                                               AS pct_days_connecting_is_cheaper
FROM fact_daily_fares df
INNER JOIN dim_routes r    ON df.route_code = r.route_code
INNER JOIN dim_airports ao ON r.origin_iata = ao.iata
INNER JOIN dim_airports ad ON r.destination_iata = ad.iata
WHERE df.min_nonstop_price_usd IS NOT NULL
GROUP BY df.route_code, ao.city, ad.city, r.distance_miles, r.pct_nonstop
ORDER BY avg_nonstop_premium_usd DESC
LIMIT 10;


-- ============================================================================
-- ANALYSIS 7: FLIGHT DURATION, DEPARTURE TIME-OF-DAY & RED-EYE ANALYSIS
-- Business Question:
-- How do flight duration and departure time of day (Early Morning, Morning,
-- Afternoon, Evening, Night/Red-Eye) impact ticket prices?
--
-- SQL Techniques Used:
-- CASE WHEN time bucketing, HOUR(), GROUP BY, Window Functions (SUM() OVER,
-- RANK() OVER).
-- ============================================================================
SELECT
    CASE
        WHEN HOUR(departure_time) BETWEEN 5 AND 8   THEN '1. Early Morning (05:00-08:59)'
        WHEN HOUR(departure_time) BETWEEN 9 AND 11  THEN '2. Morning (09:00-11:59)'
        WHEN HOUR(departure_time) BETWEEN 12 AND 16 THEN '3. Afternoon (12:00-16:59)'
        WHEN HOUR(departure_time) BETWEEN 17 AND 20 THEN '4. Evening (17:00-20:59)'
        ELSE '5. Night / Red-Eye (21:00-04:59)'
    END                                                             AS departure_time_bucket,
    COUNT(*)                                                        AS observations,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)              AS schedule_share_pct,
    ROUND(AVG(price_usd), 2)                                        AS avg_price_usd,
    ROUND(AVG(duration_minutes), 1)                                 AS avg_duration_minutes,
    ROUND(
        SUM(CASE WHEN stops = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
    )                                                               AS nonstop_pct,
    ROUND(
        SUM(CASE WHEN arrival_day_offset > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
    )                                                               AS next_day_arrival_pct,
    RANK() OVER (ORDER BY AVG(price_usd) ASC)                       AS cheapest_time_rank
FROM fact_flight_prices
GROUP BY departure_time_bucket
ORDER BY departure_time_bucket ASC;


-- ============================================================================
-- ANALYSIS 8: DISTANCE AND TICKET PRICE RELATIONSHIP (YIELD / PRICE PER MILE)
-- Business Question:
-- How strongly does flight distance drive ticket prices, and how does airline
-- yield (Price per Mile in USD) behave across Short-Haul (<500 mi),
-- Medium-Haul (500-1500 mi), and Long-Haul (>1500 mi) routes?
--
-- SQL Techniques Used:
-- Generated Column (distance_haul), INNER JOIN, GROUP BY, Aggregate Functions.
-- ============================================================================
SELECT
    r.distance_haul,
    COUNT(DISTINCT r.route_code)                                    AS route_count,
    ROUND(AVG(r.distance_miles), 0)                                 AS avg_distance_miles,
    MIN(r.distance_miles)                                           AS min_distance_miles,
    MAX(r.distance_miles)                                           AS max_distance_miles,
    ROUND(AVG(r.median_price_usd), 2)                               AS avg_route_median_price_usd,
    ROUND(AVG(r.median_price_usd / r.distance_miles), 4)            AS avg_price_per_mile_usd,
    ROUND(AVG(r.pct_nonstop), 1)                                    AS avg_nonstop_pct,
    ROUND(AVG(r.airlines_count), 1)                                 AS avg_competing_airlines
FROM dim_routes r
GROUP BY r.distance_haul
ORDER BY avg_distance_miles ASC;


-- ============================================================================
-- ANALYSIS 9: CHEAPEST AND MOST EXPENSIVE ROUTES (ABSOLUTE & PER-MILE)
-- Business Question:
-- Which US domestic routes are the top 5 cheapest and top 5 most expensive
-- both in absolute median ticket price ($) and in cost efficiency ($/mile)?
--
-- SQL Techniques Used:
-- CTE, Window Functions (ROW_NUMBER() OVER), UNION ALL, Subquery filtering.
-- ============================================================================
WITH ranked_routes AS (
    SELECT
        r.route_code,
        CONCAT(ao.city, ' (', r.origin_iata, ') -> ', ad.city, ' (', r.destination_iata, ')') AS route_name,
        r.distance_miles,
        r.airlines_count,
        r.pct_nonstop,
        r.median_price_usd,
        ROUND(r.median_price_usd / r.distance_miles, 4)             AS price_per_mile_usd,
        ROW_NUMBER() OVER (ORDER BY r.median_price_usd ASC, r.distance_miles ASC)   AS rn_cheapest_abs,
        ROW_NUMBER() OVER (ORDER BY r.median_price_usd DESC, r.distance_miles DESC) AS rn_expensive_abs,
        ROW_NUMBER() OVER (ORDER BY (r.median_price_usd / r.distance_miles) ASC)    AS rn_cheapest_ppm,
        ROW_NUMBER() OVER (ORDER BY (r.median_price_usd / r.distance_miles) DESC)   AS rn_expensive_ppm
    FROM dim_routes r
    INNER JOIN dim_airports ao ON r.origin_iata = ao.iata
    INNER JOIN dim_airports ad ON r.destination_iata = ad.iata
)
SELECT
    CASE
        WHEN rn_cheapest_abs <= 5  THEN '1. Top 5 Cheapest (Absolute $)'
        WHEN rn_expensive_abs <= 5 THEN '2. Top 5 Most Expensive (Absolute $)'
    END                                                             AS category,
    route_code,
    route_name,
    distance_miles,
    airlines_count,
    pct_nonstop,
    median_price_usd,
    price_per_mile_usd
FROM ranked_routes
WHERE rn_cheapest_abs <= 5 OR rn_expensive_abs <= 5
ORDER BY category ASC, median_price_usd ASC;


-- ============================================================================
-- ANALYSIS 10: CUSTOMER BOOKING PRICE PATTERNS (BUYER PERSONA SIMULATION)
-- Business Question:
-- Since the dataset tracks supply-side fare curves across booking windows,
-- how much do different customer booking personas (Last-Minute Business
-- Travelers [7-14d], Smart Leisure Planners [31-60d], and Ultra-Early Planners
-- [121-180d]) pay across Short-Haul, Medium-Haul, and Long-Haul routes?
--
-- SQL Techniques Used:
-- CTE, Conditional Aggregation (PIVOT via AVG(CASE WHEN ...)), INNER JOIN.
-- ============================================================================
WITH persona_pricing AS (
    SELECT
        r.distance_haul,
        df.days_before_departure,
        df.min_price_usd,
        df.median_price_usd,
        df.min_nonstop_price_usd
    FROM fact_daily_fares df
    INNER JOIN dim_routes r ON df.route_code = r.route_code
)
SELECT
    distance_haul,
    ROUND(AVG(CASE WHEN days_before_departure BETWEEN 7 AND 14    THEN median_price_usd END), 2) AS last_minute_7_14d_median_usd,
    ROUND(AVG(CASE WHEN days_before_departure BETWEEN 31 AND 60   THEN median_price_usd END), 2) AS smart_planner_31_60d_median_usd,
    ROUND(AVG(CASE WHEN days_before_departure BETWEEN 121 AND 180 THEN median_price_usd END), 2) AS early_bird_121_180d_median_usd,
    ROUND(
        AVG(CASE WHEN days_before_departure BETWEEN 7 AND 14  THEN median_price_usd END)
        - AVG(CASE WHEN days_before_departure BETWEEN 31 AND 60 THEN median_price_usd END),
        2
    )                                                               AS smart_vs_last_minute_savings_usd,
    ROUND(
        AVG(CASE WHEN days_before_departure BETWEEN 121 AND 180 THEN median_price_usd END)
        - AVG(CASE WHEN days_before_departure BETWEEN 31 AND 60   THEN median_price_usd END),
        2
    )                                                               AS early_bird_overpayment_usd
FROM persona_pricing
GROUP BY distance_haul
ORDER BY last_minute_7_14d_median_usd ASC;
