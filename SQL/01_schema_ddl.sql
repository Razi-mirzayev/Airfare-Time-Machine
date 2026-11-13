-- ============================================================================
-- PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
-- PHASE 2: DATABASE DESIGN AND DDL (MySQL 8.0)
-- FILE: 01_schema_ddl.sql
-- DESCRIPTION: Creates the normalized Star/Snowflake relational database schema
--              with Primary Keys, Foreign Keys, Constraints, Generated Columns,
--              and Analytical Indexes.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS airfare_time_machine
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE airfare_time_machine;

-- Drop tables in reverse dependency order for idempotent execution
DROP TABLE IF EXISTS fact_flight_prices;
DROP TABLE IF EXISTS fact_daily_fares;
DROP TABLE IF EXISTS dim_routes;
DROP TABLE IF EXISTS dim_airlines;
DROP TABLE IF EXISTS dim_airports;

-- ============================================================================
-- 1. DIMENSION TABLE: dim_airports (16 US Major Hub Airports)
-- ============================================================================
CREATE TABLE dim_airports (
    iata            CHAR(3)         NOT NULL COMMENT '3-letter IATA airport code (Primary Key)',
    airport_name    VARCHAR(100)    NOT NULL COMMENT 'Official full name of the airport',
    city            VARCHAR(50)     NOT NULL COMMENT 'Metropolitan city served by the airport',
    state           CHAR(2)         NOT NULL COMMENT '2-letter US State/District code',
    latitude        DECIMAL(8, 4)   NOT NULL COMMENT 'Geographic latitude in decimal degrees',
    longitude       DECIMAL(8, 4)   NOT NULL COMMENT 'Geographic longitude in decimal degrees',
    timezone        VARCHAR(50)     NOT NULL COMMENT 'IANA timezone identifier (e.g., America/New_York)',
    CONSTRAINT pk_dim_airports PRIMARY KEY (iata),
    CONSTRAINT chk_airport_lat CHECK (latitude BETWEEN -90.0 AND 90.0),
    CONSTRAINT chk_airport_lon CHECK (longitude BETWEEN -180.0 AND 180.0)
) ENGINE=InnoDB COMMENT='Dimension table storing US airport metadata and coordinates';

-- ============================================================================
-- 2. DIMENSION TABLE: dim_airlines (17 Unique Carriers / Combinations)
-- Why created? Normalizes repetitive airline string names out of 38.58M+ fact
-- rows into a compact 1-byte TINYINT UNSIGNED foreign key, and enriches each
-- carrier with its business model classification (carrier_type).
-- ============================================================================
CREATE TABLE dim_airlines (
    airline_id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Surrogate Primary Key',
    airline_name        VARCHAR(80)      NOT NULL COMMENT 'Airline or multi-carrier combination name',
    carrier_type        ENUM(
                            'Legacy',
                            'Low-Cost',
                            'Ultra Low-Cost',
                            'Regional / Semi-Private',
                            'Multi-Carrier'
                        )                NOT NULL COMMENT 'Business model segment of the airline',
    is_multi_carrier    BOOLEAN          NOT NULL DEFAULT FALSE COMMENT 'TRUE if itinerary combines two airlines',
    CONSTRAINT pk_dim_airlines PRIMARY KEY (airline_id),
    CONSTRAINT uq_dim_airlines_name UNIQUE (airline_name)
) ENGINE=InnoDB COMMENT='Dimension table for airlines and business model segmentation';

-- ============================================================================
-- 3. DIMENSION TABLE: dim_routes (50 Directional US Domestic Routes)
-- 3NF Normalization Note:
-- origin_city and destination_city from routes.csv are intentionally removed
-- to eliminate transitive dependency (origin_iata -> dim_airports.city).
-- ============================================================================
CREATE TABLE dim_routes (
    route_code          CHAR(7)             NOT NULL COMMENT 'Directional route code (e.g., ATL-DFW)',
    origin_iata         CHAR(3)             NOT NULL COMMENT 'Origin airport IATA code (FK -> dim_airports)',
    destination_iata    CHAR(3)             NOT NULL COMMENT 'Destination airport IATA code (FK -> dim_airports)',
    distance_miles      SMALLINT UNSIGNED   NOT NULL COMMENT 'Great-circle flight distance in miles',
    distance_haul       VARCHAR(25) GENERATED ALWAYS AS (
                            CASE
                                WHEN distance_miles < 500 THEN 'Short-Haul (<500 mi)'
                                WHEN distance_miles <= 1500 THEN 'Medium-Haul (500-1500 mi)'
                                ELSE 'Long-Haul (>1500 mi)'
                            END
                        ) STORED COMMENT 'Computed haul category based on distance_miles',
    price_observations  INT UNSIGNED        NOT NULL COMMENT 'Total granular observations in flight_prices',
    airlines_count      TINYINT UNSIGNED    NOT NULL COMMENT 'Number of distinct airlines serving the route',
    pct_nonstop         DECIMAL(4, 1)       NOT NULL COMMENT 'Percentage of nonstop flight observations (0-100)',
    median_price_usd    SMALLINT UNSIGNED   NOT NULL COMMENT 'Overall historical median ticket price in USD',
    CONSTRAINT pk_dim_routes PRIMARY KEY (route_code),
    CONSTRAINT uq_dim_routes_od UNIQUE (origin_iata, destination_iata),
    CONSTRAINT fk_routes_origin FOREIGN KEY (origin_iata)
        REFERENCES dim_airports (iata) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_routes_destination FOREIGN KEY (destination_iata)
        REFERENCES dim_airports (iata) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_routes_different_airports CHECK (origin_iata <> destination_iata),
    CONSTRAINT chk_routes_distance CHECK (distance_miles > 0),
    CONSTRAINT chk_routes_pct_nonstop CHECK (pct_nonstop BETWEEN 0.0 AND 100.0)
) ENGINE=InnoDB COMMENT='Dimension table for directional flight routes';

-- ============================================================================
-- 4. FACT TABLE: fact_daily_fares (1,683,033 Daily Route-Departure Summaries)
-- Granularity: One row per (search_date, route_code, departure_date).
-- 3NF Normalization Note:
-- origin and destination columns from daily_fares.csv are removed because they
-- are functionally dependent on route_code -> dim_routes.
-- ============================================================================
CREATE TABLE fact_daily_fares (
    daily_fare_id           BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT 'Surrogate Primary Key',
    search_date             DATE                NOT NULL COMMENT 'Date when flight prices were searched',
    route_code              CHAR(7)             NOT NULL COMMENT 'Route identifier (FK -> dim_routes)',
    departure_date          DATE                NOT NULL COMMENT 'Scheduled flight departure date',
    days_before_departure   SMALLINT UNSIGNED   NOT NULL COMMENT 'Lead time in days (departure_date - search_date)',
    itineraries_count       TINYINT UNSIGNED    NOT NULL COMMENT 'Number of available flight itineraries found',
    airlines_count          TINYINT UNSIGNED    NOT NULL COMMENT 'Number of competing airlines on that date',
    min_price_usd           SMALLINT UNSIGNED   NOT NULL COMMENT 'Lowest total fare (any stops) in USD',
    min_nonstop_price_usd   SMALLINT UNSIGNED   NULL     COMMENT 'Lowest nonstop fare in USD (NULL if no nonstop flights exist)',
    median_price_usd        SMALLINT UNSIGNED   NOT NULL COMMENT 'Median fare across all itineraries in USD',
    max_price_usd           SMALLINT UNSIGNED   NOT NULL COMMENT 'Highest fare across all itineraries in USD',
    cheapest_airline_id     TINYINT UNSIGNED    NOT NULL COMMENT 'Airline offering min_price_usd (FK -> dim_airlines)',
    CONSTRAINT pk_fact_daily_fares PRIMARY KEY (daily_fare_id),
    CONSTRAINT uq_daily_fares_grain UNIQUE (search_date, route_code, departure_date),
    CONSTRAINT fk_daily_fares_route FOREIGN KEY (route_code)
        REFERENCES dim_routes (route_code) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_daily_fares_airline FOREIGN KEY (cheapest_airline_id)
        REFERENCES dim_airlines (airline_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_daily_price_order CHECK (
        min_price_usd > 0
        AND median_price_usd >= min_price_usd
        AND max_price_usd >= median_price_usd
    ),
    CONSTRAINT chk_daily_lead_time CHECK (days_before_departure BETWEEN 1 AND 365)
) ENGINE=InnoDB COMMENT='Daily aggregated fare metrics per route and departure date';

-- Analytical Indexes for fact_daily_fares
CREATE INDEX idx_daily_route_dep ON fact_daily_fares (route_code, departure_date);
CREATE INDEX idx_daily_lead_time ON fact_daily_fares (days_before_departure, min_price_usd, median_price_usd);
CREATE INDEX idx_daily_dep_date ON fact_daily_fares (departure_date, median_price_usd);
CREATE INDEX idx_daily_cheapest_airline ON fact_daily_fares (cheapest_airline_id, min_price_usd);

-- ============================================================================
-- 5. FACT TABLE: fact_flight_prices (Granular Flight Itinerary Observations)
-- Granularity: One row per (search_date, itinerary_id).
-- ============================================================================
CREATE TABLE fact_flight_prices (
    search_date             DATE                NOT NULL COMMENT 'Date when the itinerary was observed',
    itinerary_id            CHAR(16)            NOT NULL COMMENT 'Unique 16-char hash of the flight itinerary',
    searched_at_utc         DATETIME(6)         NOT NULL COMMENT 'Exact UTC timestamp of price observation',
    route_code              CHAR(7)             NOT NULL COMMENT 'Route identifier (FK -> dim_routes)',
    departure_date          DATE                NOT NULL COMMENT 'Scheduled flight departure date',
    days_before_departure   SMALLINT UNSIGNED   NOT NULL COMMENT 'Lead time in days (departure_date - search_date)',
    airline_id              TINYINT UNSIGNED    NOT NULL COMMENT 'Operating airline (FK -> dim_airlines)',
    departure_time          TIME                NOT NULL COMMENT 'Local departure time (HH:MM:00)',
    arrival_time            TIME                NOT NULL COMMENT 'Local arrival time (HH:MM:00)',
    arrival_day_offset      TINYINT UNSIGNED    NOT NULL COMMENT '0 = same day, 1 = next day (+1), 2 = +2 days',
    duration_minutes        SMALLINT UNSIGNED   NOT NULL COMMENT 'Total travel time in minutes including layovers',
    stops                   TINYINT UNSIGNED    NOT NULL COMMENT 'Number of stops (0 = nonstop, 1 = 1 stop, 2 = 2 stops)',
    price_usd               SMALLINT UNSIGNED   NOT NULL COMMENT 'Observed ticket price in USD',
    CONSTRAINT pk_fact_flight_prices PRIMARY KEY (search_date, itinerary_id),
    CONSTRAINT fk_flight_prices_route FOREIGN KEY (route_code)
        REFERENCES dim_routes (route_code) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_flight_prices_airline FOREIGN KEY (airline_id)
        REFERENCES dim_airlines (airline_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_flight_stops CHECK (stops IN (0, 1, 2)),
    CONSTRAINT chk_flight_duration CHECK (duration_minutes > 0),
    CONSTRAINT chk_flight_price CHECK (price_usd > 0)
) ENGINE=InnoDB COMMENT='Granular flight itinerary observations across search dates';

-- Analytical Indexes for fact_flight_prices
CREATE INDEX idx_fp_route_airline ON fact_flight_prices (route_code, airline_id, price_usd);
CREATE INDEX idx_fp_lead_stops ON fact_flight_prices (days_before_departure, stops, price_usd);
CREATE INDEX idx_fp_dep_date ON fact_flight_prices (departure_date, price_usd);
CREATE INDEX idx_fp_itinerary ON fact_flight_prices (itinerary_id, days_before_departure);
