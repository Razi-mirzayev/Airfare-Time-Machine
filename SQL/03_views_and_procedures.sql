-- ============================================================================
-- PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
-- PHASE 2: ANALYTICAL VIEWS & STORED PROCEDURES (MySQL 8.0)
-- FILE: 03_views_and_procedures.sql
-- DESCRIPTION: Reusable analytical Views that pre-join Fact & Dimension tables
--              with derived business metrics, plus parameterized Stored
--              Procedures for route-level decision support.
-- ============================================================================

USE airfare_time_machine;

-- ============================================================================
-- 1. VIEW: vw_routes_enriched
-- Purpose: Reconstructs the full route context from normalized 3NF tables and
--          adds derived aviation KPIs (price per mile, competition tier).
-- ============================================================================
CREATE OR REPLACE VIEW vw_routes_enriched AS
SELECT
    r.route_code,
    r.origin_iata,
    ao.airport_name                                         AS origin_airport_name,
    ao.city                                                 AS origin_city,
    ao.state                                                AS origin_state,
    ao.timezone                                             AS origin_timezone,
    r.destination_iata,
    ad.airport_name                                         AS destination_airport_name,
    ad.city                                                 AS destination_city,
    ad.state                                                AS destination_state,
    ad.timezone                                             AS destination_timezone,
    r.distance_miles,
    r.distance_haul,
    r.price_observations,
    r.airlines_count,
    CASE
        WHEN r.airlines_count >= 9 THEN 'High Competition (9-11 Airlines)'
        WHEN r.airlines_count >= 7 THEN 'Moderate Competition (7-8 Airlines)'
        ELSE 'Low Competition (5-6 Airlines)'
    END                                                     AS competition_tier,
    r.pct_nonstop,
    r.median_price_usd,
    ROUND(r.median_price_usd / r.distance_miles, 4)         AS median_price_per_mile_usd
FROM dim_routes r
INNER JOIN dim_airports ao ON r.origin_iata = ao.iata
INNER JOIN dim_airports ad ON r.destination_iata = ad.iata;

-- ============================================================================
-- 2. VIEW: vw_daily_fares_enriched
-- Purpose: Enriches 1.68M daily fare summaries with airport geography, airline
--          business model, booking window buckets, and nonstop fare premiums.
-- ============================================================================
CREATE OR REPLACE VIEW vw_daily_fares_enriched AS
SELECT
    f.daily_fare_id,
    f.search_date,
    f.route_code,
    r.origin_iata,
    ao.city                                                 AS origin_city,
    r.destination_iata,
    ad.city                                                 AS destination_city,
    r.distance_miles,
    r.distance_haul,
    f.departure_date,
    YEAR(f.departure_date)                                  AS departure_year,
    MONTH(f.departure_date)                                 AS departure_month,
    DATE_FORMAT(f.departure_date, '%Y-%m')                  AS departure_year_month,
    DAYNAME(f.departure_date)                               AS departure_day_name,
    WEEKDAY(f.departure_date) + 1                           AS departure_iso_dow, -- 1=Mon .. 7=Sun
    CASE
        WHEN WEEKDAY(f.departure_date) IN (4, 5, 6) THEN 'Weekend (Fri-Sun)'
        ELSE 'Weekday (Mon-Thu)'
    END                                                     AS departure_day_type,
    f.days_before_departure,
    CASE
        WHEN f.days_before_departure BETWEEN 7 AND 14   THEN '1. Last Minute (7-14 Days)'
        WHEN f.days_before_departure BETWEEN 15 AND 30  THEN '2. Short Term (15-30 Days)'
        WHEN f.days_before_departure BETWEEN 31 AND 60  THEN '3. Medium Term (31-60 Days)'
        WHEN f.days_before_departure BETWEEN 61 AND 90  THEN '4. Optimal Advance (61-90 Days)'
        WHEN f.days_before_departure BETWEEN 91 AND 120 THEN '5. Early Bird (91-120 Days)'
        ELSE '6. Far Advance (121-180 Days)'
    END                                                     AS booking_window_bucket,
    f.itineraries_count,
    f.airlines_count,
    f.min_price_usd,
    f.min_nonstop_price_usd,
    f.median_price_usd,
    f.max_price_usd,
    (f.max_price_usd - f.min_price_usd)                     AS daily_price_spread_usd,
    (f.min_nonstop_price_usd - f.min_price_usd)             AS nonstop_premium_usd,
    ROUND(f.median_price_usd / r.distance_miles, 4)         AS median_price_per_mile_usd,
    al.airline_id                                           AS cheapest_airline_id,
    al.airline_name                                         AS cheapest_airline_name,
    al.carrier_type                                         AS cheapest_carrier_type
FROM fact_daily_fares f
INNER JOIN dim_routes r    ON f.route_code = r.route_code
INNER JOIN dim_airports ao ON r.origin_iata = ao.iata
INNER JOIN dim_airports ad ON r.destination_iata = ad.iata
INNER JOIN dim_airlines al ON f.cheapest_airline_id = al.airline_id;

-- ============================================================================
-- 3. VIEW: vw_flight_prices_enriched
-- Purpose: Enriches granular flight itinerary records with time-of-day buckets,
--          stop categories, airline business models, and route distance metrics.
-- ============================================================================
CREATE OR REPLACE VIEW vw_flight_prices_enriched AS
SELECT
    fp.search_date,
    fp.itinerary_id,
    fp.searched_at_utc,
    fp.route_code,
    r.origin_iata,
    ao.city                                                 AS origin_city,
    r.destination_iata,
    ad.city                                                 AS destination_city,
    r.distance_miles,
    r.distance_haul,
    fp.departure_date,
    DAYNAME(fp.departure_date)                              AS departure_day_name,
    fp.days_before_departure,
    al.airline_name,
    al.carrier_type,
    al.is_multi_carrier,
    fp.departure_time,
    CASE
        WHEN HOUR(fp.departure_time) BETWEEN 5 AND 8   THEN '1. Early Morning (05:00-08:59)'
        WHEN HOUR(fp.departure_time) BETWEEN 9 AND 11  THEN '2. Morning (09:00-11:59)'
        WHEN HOUR(fp.departure_time) BETWEEN 12 AND 16 THEN '3. Afternoon (12:00-16:59)'
        WHEN HOUR(fp.departure_time) BETWEEN 17 AND 20 THEN '4. Evening (17:00-20:59)'
        ELSE '5. Night / Red-Eye (21:00-04:59)'
    END                                                     AS departure_time_bucket,
    fp.arrival_time,
    fp.arrival_day_offset,
    fp.duration_minutes,
    ROUND(fp.duration_minutes / 60.0, 2)                    AS duration_hours,
    fp.stops,
    CASE
        WHEN fp.stops = 0 THEN 'Direct (Nonstop)'
        WHEN fp.stops = 1 THEN '1 Stop (Connecting)'
        ELSE '2 Stops (Multi-Stop)'
    END                                                     AS stop_category,
    fp.price_usd,
    ROUND(fp.price_usd / r.distance_miles, 4)               AS price_per_mile_usd
FROM fact_flight_prices fp
INNER JOIN dim_routes r    ON fp.route_code = r.route_code
INNER JOIN dim_airports ao ON r.origin_iata = ao.iata
INNER JOIN dim_airports ad ON r.destination_iata = ad.iata
INNER JOIN dim_airlines al ON fp.airline_id = al.airline_id;

-- ============================================================================
-- 4. STORED PROCEDURE: sp_get_route_booking_advisor
-- Business Purpose:
-- When a traveler or pricing analyst queries a specific route (e.g., 'JFK-LAX'),
-- this procedure analyzes all booking windows on that route and returns:
--   - Average min, median, and nonstop fares per booking window
--   - Exact dollar and percentage savings compared to Last Minute (7-14 days)
--   - Window ranking from cheapest (Rank 1) to most expensive
-- ============================================================================
DROP PROCEDURE IF EXISTS sp_get_route_booking_advisor;

DELIMITER $$
CREATE PROCEDURE sp_get_route_booking_advisor(
    IN p_route_code CHAR(7)
)
BEGIN
    WITH window_stats AS (
        SELECT
            route_code,
            origin_city,
            destination_city,
            booking_window_bucket,
            COUNT(*)                                        AS observed_days,
            ROUND(AVG(min_price_usd), 2)                    AS avg_min_price_usd,
            ROUND(AVG(median_price_usd), 2)                 AS avg_median_price_usd,
            ROUND(AVG(min_nonstop_price_usd), 2)            AS avg_nonstop_price_usd
        FROM vw_daily_fares_enriched
        WHERE route_code = UPPER(TRIM(p_route_code))
        GROUP BY route_code, origin_city, destination_city, booking_window_bucket
    ),
    baseline_last_minute AS (
        SELECT
            avg_median_price_usd AS last_minute_median_usd
        FROM window_stats
        WHERE booking_window_bucket = '1. Last Minute (7-14 Days)'
    )
    SELECT
        w.route_code,
        CONCAT(w.origin_city, ' -> ', w.destination_city)   AS route_name,
        w.booking_window_bucket,
        w.observed_days,
        w.avg_min_price_usd,
        w.avg_median_price_usd,
        w.avg_nonstop_price_usd,
        ROUND(b.last_minute_median_usd - w.avg_median_price_usd, 2) AS savings_vs_last_minute_usd,
        ROUND(
            (b.last_minute_median_usd - w.avg_median_price_usd)
            / NULLIF(b.last_minute_median_usd, 0) * 100, 2
        )                                                   AS savings_vs_last_minute_pct,
        RANK() OVER (ORDER BY w.avg_median_price_usd ASC)   AS cheapest_window_rank
    FROM window_stats w
    CROSS JOIN baseline_last_minute b
    ORDER BY cheapest_window_rank ASC;
END$$
DELIMITER ;

-- ============================================================================
-- 5. STORED PROCEDURE: sp_compare_route_carriers
-- Business Purpose:
-- Evaluates airline competition on a given route, comparing each carrier's
-- price positioning against the route-wide average using Window Functions.
-- ============================================================================
DROP PROCEDURE IF EXISTS sp_compare_route_carriers;

DELIMITER $$
CREATE PROCEDURE sp_compare_route_carriers(
    IN p_route_code CHAR(7)
)
BEGIN
    SELECT
        al.airline_name,
        al.carrier_type,
        COUNT(*)                                            AS total_observations,
        ROUND(
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2
        )                                                   AS observation_share_pct,
        MIN(fp.price_usd)                                   AS min_price_usd,
        ROUND(AVG(fp.price_usd), 2)                         AS avg_price_usd,
        MAX(fp.price_usd)                                   AS max_price_usd,
        ROUND(
            AVG(fp.price_usd) - AVG(AVG(fp.price_usd)) OVER (), 2
        )                                                   AS diff_vs_route_avg_usd,
        ROUND(
            SUM(CASE WHEN fp.stops = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
        )                                                   AS nonstop_pct,
        ROUND(AVG(fp.duration_minutes), 0)                  AS avg_duration_mins
    FROM fact_flight_prices fp
    INNER JOIN dim_airlines al ON fp.airline_id = al.airline_id
    WHERE fp.route_code = UPPER(TRIM(p_route_code))
    GROUP BY al.airline_name, al.carrier_type
    ORDER BY avg_price_usd ASC;
END$$
DELIMITER ;
