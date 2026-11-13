-- ============================================================================
-- PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
-- PHASE 2: DATA CLEANING, NORMALIZATION & IMPORT PIPELINE (MySQL 8.0)
-- FILE: 02_data_cleaning_and_import.sql
-- DESCRIPTION: Populates Dimension tables, stages raw CSV data, executes SQL
--              data cleaning transformations, loads normalized Fact tables,
--              and runs post-load Data Quality Audit checks.
-- ============================================================================

USE airfare_time_machine;

-- Enable local file import if loading via MySQL CLI / Workbench
-- SET GLOBAL local_infile = 1;

-- ============================================================================
-- STEP 1: POPULATE dim_airports (16 US Major Hub Airports)
-- ============================================================================
TRUNCATE TABLE fact_flight_prices;
TRUNCATE TABLE fact_daily_fares;
DELETE FROM dim_routes;
DELETE FROM dim_airlines;
DELETE FROM dim_airports;

INSERT INTO dim_airports (iata, airport_name, city, state, latitude, longitude, timezone) VALUES
('ATL', 'Hartsfield-Jackson Atlanta International Airport', 'Atlanta',       'GA', 33.6367,  -84.4281, 'America/New_York'),
('BOS', 'Boston Logan International Airport',               'Boston',        'MA', 42.3620,  -71.0079, 'America/New_York'),
('DCA', 'Ronald Reagan Washington National Airport',        'Washington',    'DC', 38.8521,  -77.0377, 'America/New_York'),
('DEN', 'Denver International Airport',                     'Denver',        'CO', 39.8600, -104.6738, 'America/Denver'),
('DFW', 'Dallas/Fort Worth International Airport',          'Dallas',        'TX', 32.8968,  -97.0380, 'America/Chicago'),
('EWR', 'Newark Liberty International Airport',             'Newark',        'NJ', 40.6894,  -74.1705, 'America/New_York'),
('IAH', 'George Bush Intercontinental Airport',             'Houston',       'TX', 29.9844,  -95.3414, 'America/Chicago'),
('JFK', 'John F. Kennedy International Airport',            'New York',      'NY', 40.6394,  -73.7793, 'America/New_York'),
('LAS', 'Harry Reid International Airport',                 'Las Vegas',     'NV', 36.0834, -115.1518, 'America/Los_Angeles'),
('LAX', 'Los Angeles International Airport',                'Los Angeles',   'CA', 33.9425, -118.4080, 'America/Los_Angeles'),
('LGA', 'LaGuardia Airport',                                'New York',      'NY', 40.7772,  -73.8726, 'America/New_York'),
('MSP', 'Minneapolis-Saint Paul International Airport',     'Minneapolis',   'MN', 44.8801,  -93.2217, 'America/Chicago'),
('ORD', 'Chicago O''Hare International Airport',            'Chicago',       'IL', 41.9786,  -87.9048, 'America/Chicago'),
('PHX', 'Phoenix Sky Harbor International Airport',         'Phoenix',       'AZ', 33.4353, -112.0059, 'America/Phoenix'),
('SEA', 'Seattle-Tacoma International Airport',             'Seattle',       'WA', 47.4479, -122.3103, 'America/Los_Angeles'),
('SFO', 'San Francisco International Airport',              'San Francisco', 'CA', 37.6198, -122.3748, 'America/Los_Angeles');

-- ============================================================================
-- STEP 2: POPULATE dim_airlines (17 Distinct Carriers & Business Models)
-- Data Cleaning & Enrichment Logic:
-- Standardized the 17 unique airline strings found across daily_fares.csv and
-- flight_prices.parquet into 5 aviation business model segments:
--   1. Legacy: Full-service network carriers (American, Delta, United, Alaska)
--   2. Low-Cost: Traditional LCCs (Southwest, JetBlue, Sun Country)
--   3. Ultra Low-Cost (ULCC): Unbundled bare-fare carriers (Frontier, Spirit)
--   4. Regional / Semi-Private: Commuter & hop-on jet carriers (JSX, Contour, etc.)
--   5. Multi-Carrier: Interline/codeshare connecting itineraries (contains '+')
-- ============================================================================
INSERT INTO dim_airlines (airline_id, airline_name, carrier_type, is_multi_carrier) VALUES
(1,  'American Airlines',                   'Legacy',                  FALSE),
(2,  'Delta Air Lines',                     'Legacy',                  FALSE),
(3,  'United Airlines',                     'Legacy',                  FALSE),
(4,  'Alaska Airlines',                     'Legacy',                  FALSE),
(5,  'Southwest Airlines',                  'Low-Cost',                FALSE),
(6,  'JetBlue Airways',                     'Low-Cost',                FALSE),
(7,  'Sun Country Airlines',                'Low-Cost',                FALSE),
(8,  'Frontier Airlines',                   'Ultra Low-Cost',          FALSE),
(9,  'Spirit Airlines',                     'Ultra Low-Cost',          FALSE),
(10, 'Contour Airlines',                    'Regional / Semi-Private', FALSE),
(11, 'JSX',                                 'Regional / Semi-Private', FALSE),
(12, 'Key Lime Air',                        'Regional / Semi-Private', FALSE),
(13, 'Southern Airways Express',            'Regional / Semi-Private', FALSE),
(14, 'Alaska Airlines + American Airlines', 'Multi-Carrier',           TRUE),
(15, 'Alaska Airlines + Hawaiian Airlines', 'Multi-Carrier',           TRUE),
(16, 'American Airlines + Alaska Airlines', 'Multi-Carrier',           TRUE),
(17, 'Cape Air + JetBlue Airways',          'Multi-Carrier',           TRUE);

-- ============================================================================
-- STEP 3: POPULATE dim_routes (50 Directional US Domestic Routes)
-- 3NF Normalization Applied:
-- origin_city and destination_city are omitted here because they belong to
-- dim_airports and are retrieved via JOIN on origin_iata / destination_iata.
-- ============================================================================
INSERT INTO dim_routes (route_code, origin_iata, destination_iata, distance_miles, price_observations, airlines_count, pct_nonstop, median_price_usd) VALUES
('ATL-DFW', 'ATL', 'DFW',  730,  634705,  9, 94.8, 154),
('ATL-LAX', 'ATL', 'LAX', 1942,  731724, 11, 60.8, 269),
('BOS-DCA', 'BOS', 'DCA',  398,  858585,  6, 97.4, 134),
('BOS-LAX', 'BOS', 'LAX', 2605,  673173, 10, 71.8, 219),
('BOS-ORD', 'BOS', 'ORD',  864,  831029,  9, 98.2, 138),
('DCA-BOS', 'DCA', 'BOS',  398,  845831,  5, 97.1, 142),
('DCA-ORD', 'DCA', 'ORD',  611,  829881,  8, 91.5, 154),
('DEN-LAX', 'DEN', 'LAX',  861,  736681,  6, 98.2, 149),
('DEN-ORD', 'DEN', 'ORD',  886,  665017,  8, 95.3, 143),
('DEN-SFO', 'DEN', 'SFO',  965,  621054,  9, 85.0, 169),
('DFW-ATL', 'DFW', 'ATL',  730,  636251,  8, 94.6, 159),
('DFW-LAX', 'DFW', 'LAX', 1232,  716855,  9, 81.9, 275),
('DFW-ORD', 'DFW', 'ORD',  802,  773523,  9, 95.2, 180),
('EWR-LAX', 'EWR', 'LAX', 2449,  562355,  9, 76.9, 249),
('EWR-SFO', 'EWR', 'SFO', 2559,  680098, 10, 57.0, 279),
('IAH-LAX', 'IAH', 'LAX', 1376,  511166,  9, 88.6, 193),
('JFK-LAX', 'JFK', 'LAX', 2469, 1041599,  7, 93.6, 279),
('JFK-SFO', 'JFK', 'SFO', 2580,  761633,  7, 87.9, 284),
('LAS-LAX', 'LAS', 'LAX',  236,  826013,  9, 99.3, 116),
('LAX-ATL', 'LAX', 'ATL', 1942,  732983, 11, 60.2, 269),
('LAX-BOS', 'LAX', 'BOS', 2605,  709397, 10, 67.8, 224),
('LAX-DEN', 'LAX', 'DEN',  861,  738770,  8, 98.4, 155),
('LAX-DFW', 'LAX', 'DFW', 1232,  708776,  9, 82.1, 264),
('LAX-EWR', 'LAX', 'EWR', 2449,  557389,  9, 76.7, 261),
('LAX-IAH', 'LAX', 'IAH', 1376,  515012,  7, 87.9, 193),
('LAX-JFK', 'LAX', 'JFK', 2469, 1042032,  7, 92.8, 284),
('LAX-LAS', 'LAX', 'LAS',  236,  835479, 10, 99.2, 118),
('LAX-ORD', 'LAX', 'ORD', 1741,  825820, 10, 95.9, 199),
('LAX-PHX', 'LAX', 'PHX',  370,  708886,  8, 98.6, 126),
('LAX-SEA', 'LAX', 'SEA',  955,  827223,  7, 91.7, 179),
('LAX-SFO', 'LAX', 'SFO',  338, 1218059,  7, 99.9, 109),
('LGA-ORD', 'LGA', 'ORD',  731, 1110956,  7, 98.7, 144),
('MSP-ORD', 'MSP', 'ORD',  334,  668088,  8, 97.4, 158),
('ORD-BOS', 'ORD', 'BOS',  864,  824732,  9, 98.5, 138),
('ORD-DCA', 'ORD', 'DCA',  611,  818731,  7, 91.4, 150),
('ORD-DEN', 'ORD', 'DEN',  886,  662524,  8, 95.4, 149),
('ORD-DFW', 'ORD', 'DFW',  802,  775317,  9, 94.9, 179),
('ORD-LAX', 'ORD', 'LAX', 1741,  832327, 10, 96.0, 191),
('ORD-LGA', 'ORD', 'LGA',  731, 1113363,  7, 98.3, 144),
('ORD-MSP', 'ORD', 'MSP',  334,  666761,  8, 97.0, 158),
('ORD-SFO', 'ORD', 'SFO', 1842,  760879,  9, 83.6, 188),
('PHX-LAX', 'PHX', 'LAX',  370,  684576,  9, 97.7, 125),
('SEA-LAX', 'SEA', 'LAX',  955,  820025,  8, 92.5, 179),
('SEA-SFO', 'SEA', 'SFO',  679,  725820,  8, 94.9, 134),
('SFO-DEN', 'SFO', 'DEN',  965,  619464,  9, 85.1, 174),
('SFO-EWR', 'SFO', 'EWR', 2559,  666127,  9, 58.4, 291),
('SFO-JFK', 'SFO', 'JFK', 2580,  766330,  7, 86.8, 292),
('SFO-LAX', 'SFO', 'LAX',  338, 1225123,  7, 99.9, 109),
('SFO-ORD', 'SFO', 'ORD', 1842,  765360,  9, 82.5, 204),
('SFO-SEA', 'SFO', 'SEA',  679,  721327,  8, 95.5, 134);

-- ============================================================================
-- STEP 4: STAGING, CLEANING & IMPORT OF daily_fares.csv (1,683,033 rows)
-- Why use a Staging Table?
-- In raw daily_fares.csv:
--   1. `min_nonstop_price_usd` has 87 empty strings ('') when no nonstop flight
--      was available on that date/route. We convert '' -> NULL via NULLIF().
--   2. `cheapest_airline` is a text string that must be mapped to `airline_id`.
--   3. `origin` and `destination` are redundant (3NF normalization).
-- ============================================================================
DROP TEMPORARY TABLE IF EXISTS stg_daily_fares;
CREATE TEMPORARY TABLE stg_daily_fares (
    search_date             DATE,
    route_code              CHAR(7),
    origin_unused           CHAR(3),
    destination_unused      CHAR(3),
    departure_date          DATE,
    days_before_departure   SMALLINT UNSIGNED,
    itineraries_count       TINYINT UNSIGNED,
    airlines_count          TINYINT UNSIGNED,
    min_price_usd           SMALLINT UNSIGNED,
    min_nonstop_price_usd   SMALLINT UNSIGNED NULL,
    median_price_usd        SMALLINT UNSIGNED,
    max_price_usd           SMALLINT UNSIGNED,
    cheapest_airline_name   VARCHAR(80)
);

-- Load raw CSV into staging table (adjust path if needed on your machine)
LOAD DATA LOCAL INFILE 'C:/Users/Mrzayev/.gemini/antigravity/scratch/Airfare-Time-Machine/Dataset/daily_fares.csv'
INTO TABLE stg_daily_fares
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    @search_date,
    @route,
    @origin,
    @destination,
    @departure_date,
    @days_before_departure,
    @itineraries,
    @airlines,
    @min_price_usd,
    @min_nonstop_price_usd,
    @median_price_usd,
    @max_price_usd,
    @cheapest_airline
)
SET
    search_date           = STR_TO_DATE(TRIM(@search_date), '%Y-%m-%d'),
    route_code            = TRIM(@route),
    origin_unused         = TRIM(@origin),
    destination_unused    = TRIM(@destination),
    departure_date        = STR_TO_DATE(TRIM(@departure_date), '%Y-%m-%d'),
    days_before_departure = CAST(@days_before_departure AS UNSIGNED),
    itineraries_count     = CAST(@itineraries AS UNSIGNED),
    airlines_count        = CAST(@airlines AS UNSIGNED),
    min_price_usd         = CAST(@min_price_usd AS UNSIGNED),
    -- DATA CLEANING RULE: Convert empty string '' to SQL NULL (87 rows where no nonstop existed)
    min_nonstop_price_usd = CAST(NULLIF(TRIM(@min_nonstop_price_usd), '') AS UNSIGNED),
    median_price_usd      = CAST(@median_price_usd AS UNSIGNED),
    max_price_usd         = CAST(@max_price_usd AS UNSIGNED),
    cheapest_airline_name = TRIM(REPLACE(@cheapest_airline, '\r', ''));

-- Insert cleaned & normalized records into fact_daily_fares
INSERT INTO fact_daily_fares (
    search_date,
    route_code,
    departure_date,
    days_before_departure,
    itineraries_count,
    airlines_count,
    min_price_usd,
    min_nonstop_price_usd,
    median_price_usd,
    max_price_usd,
    cheapest_airline_id
)
SELECT
    s.search_date,
    s.route_code,
    s.departure_date,
    s.days_before_departure,
    s.itineraries_count,
    s.airlines_count,
    s.min_price_usd,
    s.min_nonstop_price_usd,
    s.median_price_usd,
    s.max_price_usd,
    a.airline_id
FROM stg_daily_fares s
INNER JOIN dim_airlines a
    ON s.cheapest_airline_name = a.airline_name;

DROP TEMPORARY TABLE IF EXISTS stg_daily_fares;

-- ============================================================================
-- STEP 5: DATA QUALITY & INTEGRITY VERIFICATION QUERIES
-- After loading, we verify row counts, NULL semantics, and referential integrity.
-- ============================================================================

-- 5.1 Check row counts across all core tables
SELECT 'dim_airports' AS table_name, COUNT(*) AS row_count FROM dim_airports
UNION ALL
SELECT 'dim_airlines', COUNT(*) FROM dim_airlines
UNION ALL
SELECT 'dim_routes', COUNT(*) FROM dim_routes
UNION ALL
SELECT 'fact_daily_fares', COUNT(*) FROM fact_daily_fares
UNION ALL
SELECT 'fact_flight_prices', COUNT(*) FROM fact_flight_prices;

-- 5.2 Audit the 87 rows where min_nonstop_price_usd is NULL
-- Business validation: Verify which routes and airlines account for the 87 dates
-- without nonstop flight availability.
SELECT
    r.route_code,
    ao.city AS origin_city,
    ad.city AS destination_city,
    r.pct_nonstop AS route_historical_nonstop_pct,
    COUNT(*) AS days_without_nonstop,
    MIN(f.min_price_usd) AS min_connecting_price_usd,
    MAX(f.min_price_usd) AS max_connecting_price_usd
FROM fact_daily_fares f
INNER JOIN dim_routes r ON f.route_code = r.route_code
INNER JOIN dim_airports ao ON r.origin_iata = ao.iata
INNER JOIN dim_airports ad ON r.destination_iata = ad.iata
WHERE f.min_nonstop_price_usd IS NULL
GROUP BY r.route_code, ao.city, ad.city, r.pct_nonstop
ORDER BY days_without_nonstop DESC;

-- 5.3 Verify price logical consistency (min <= median <= max, and min_nonstop >= min)
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN min_price_usd > median_price_usd OR median_price_usd > max_price_usd THEN 1 ELSE 0 END) AS invalid_price_order_rows,
    SUM(CASE WHEN min_nonstop_price_usd IS NOT NULL AND min_nonstop_price_usd < min_price_usd THEN 1 ELSE 0 END) AS invalid_nonstop_min_rows,
    SUM(CASE WHEN DATEDIFF(departure_date, search_date) <> days_before_departure THEN 1 ELSE 0 END) AS date_math_mismatch_rows
FROM fact_daily_fares;
