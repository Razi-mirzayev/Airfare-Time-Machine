# Data Dictionary & Relational Schema Guide
## Project: Airfare Time Machine – US Flight Price Analysis

This document provides the complete technical reference for both the **Raw Kaggle Dataset Files** and the **Normalized MySQL 8.0 Star Schema Database**.

---

## 1. Raw Dataset Files Overview

Source: [Kaggle – Airfare Time Machine: US Flight Prices](https://www.kaggle.com/datasets/pooyanayebi/airfare-time-machine-us-flight-prices)

| File Name | Format | Size | Rows | Columns | Primary Key / Grain |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `airports.csv` | CSV | 1.45 KB | 16 | 7 | `iata` (Airport code) |
| `routes.csv` | CSV | 3.04 KB | 50 | 10 | `route` (Directional origin-destination pair) |
| `daily_fares.csv` | CSV | 127.2 MB | 1,683,033 | 13 | `(search_date, route, departure_date)` |
| `flight_prices.parquet` | Parquet | 94.8 MB | 38,584,829 | 15 | `(search_date, itinerary_id)` |

---

## 2. Normalized MySQL 8.0 Database Schema (`airfare_time_machine`)

### 2.1 Dimension Table: `dim_airports` (16 Rows)
| Column | Data Type | Nullable | Key | Description |
| :--- | :--- | :---: | :---: | :--- |
| `iata` | `CHAR(3)` | `NO` | `PK` | 3-letter IATA airport code (`ATL`, `BOS`, `JFK`, `LAX`, etc.) |
| `airport_name` | `VARCHAR(100)` | `NO` | | Official full name of the airport |
| `city` | `VARCHAR(50)` | `NO` | | Metropolitan city served |
| `state` | `CHAR(2)` | `NO` | | 2-letter US State / District code |
| `latitude` | `DECIMAL(8,4)` | `NO` | | Geographic latitude in decimal degrees |
| `longitude` | `DECIMAL(8,4)` | `NO` | | Geographic longitude in decimal degrees |
| `timezone` | `VARCHAR(50)` | `NO` | | IANA timezone string (`America/New_York`, etc.) |

### 2.2 Dimension Table: `dim_airlines` (17 Rows)
| Column | Data Type | Nullable | Key | Description |
| :--- | :--- | :---: | :---: | :--- |
| `airline_id` | `TINYINT UNSIGNED` | `NO` | `PK` | Surrogate primary key (`1..17`) |
| `airline_name` | `VARCHAR(80)` | `NO` | `UQ` | Airline or multi-carrier combination name |
| `carrier_type` | `ENUM(...)` | `NO` | | `Legacy`, `Low-Cost`, `Ultra Low-Cost`, `Regional / Semi-Private`, `Multi-Carrier` |
| `is_multi_carrier` | `BOOLEAN` | `NO` | | `TRUE` if itinerary combines two carriers (`+`) |

### 2.3 Dimension Table: `dim_routes` (50 Rows)
| Column | Data Type | Nullable | Key | Description |
| :--- | :--- | :---: | :---: | :--- |
| `route_code` | `CHAR(7)` | `NO` | `PK` | Directional code (`ATL-DFW`, `JFK-LAX`, etc.) |
| `origin_iata` | `CHAR(3)` | `NO` | `FK` | References `dim_airports(iata)` |
| `destination_iata` | `CHAR(3)` | `NO` | `FK` | References `dim_airports(iata)` |
| `distance_miles` | `SMALLINT UNSIGNED` | `NO` | | Great-circle distance in miles (`236` to `2,605`) |
| `distance_haul` | `VARCHAR(25)` | `NO` | | Stored Generated Column: `Short-Haul (<500 mi)`, `Medium-Haul (500-1500 mi)`, `Long-Haul (>1500 mi)` |
| `price_observations` | `INT UNSIGNED` | `NO` | | Total granular flight observations (`Sum = 38,584,829`) |
| `airlines_count` | `TINYINT UNSIGNED` | `NO` | | Number of competing airlines serving the route (`5` to `11`) |
| `pct_nonstop` | `DECIMAL(4,1)` | `NO` | | Percentage of nonstop flight observations (`57.0%` to `99.9%`) |
| `median_price_usd` | `SMALLINT UNSIGNED` | `NO` | | Historical route median fare (`$109` to `$292`) |

### 2.4 Fact Table: `fact_daily_fares` (1,683,033 Rows)
| Column | Data Type | Nullable | Key | Description |
| :--- | :--- | :---: | :---: | :--- |
| `daily_fare_id` | `BIGINT UNSIGNED` | `NO` | `PK` | Auto-increment surrogate key |
| `search_date` | `DATE` | `NO` | `UQ` | Date when fares were scraped (`2026-03-12` to `2026-09-30`) |
| `route_code` | `CHAR(7)` | `NO` | `FK, UQ` | References `dim_routes(route_code)` |
| `departure_date` | `DATE` | `NO` | `UQ` | Scheduled flight date (`2026-03-19` to `2027-03-29`) |
| `days_before_departure` | `SMALLINT UNSIGNED` | `NO` | | Lead time in days (`7` to `180`) |
| `itineraries_count` | `TINYINT UNSIGNED` | `NO` | | Number of flight options available (`3` to `64`) |
| `airlines_count` | `TINYINT UNSIGNED` | `NO` | | Number of airlines offering flights on that day (`2` to `8`) |
| `min_price_usd` | `SMALLINT UNSIGNED` | `NO` | | Lowest fare across all itineraries (`$19` to `$803`) |
| `min_nonstop_price_usd` | `SMALLINT UNSIGNED` | `YES` | | Lowest nonstop fare (`NULL` on 87 rows where no nonstop flight operated) |
| `median_price_usd` | `SMALLINT UNSIGNED` | `NO` | | Daily median fare (`$49` to `$1,567`) |
| `max_price_usd` | `SMALLINT UNSIGNED` | `NO` | | Daily highest fare (`$59` to `$5,046`) |
| `cheapest_airline_id` | `TINYINT UNSIGNED` | `NO` | `FK` | Airline offering `min_price_usd` -> `dim_airlines(airline_id)` |

### 2.5 Fact Table: `fact_flight_prices` (38,584,829 Rows)
| Column | Data Type | Nullable | Key | Description |
| :--- | :--- | :---: | :---: | :--- |
| `search_date` | `DATE` | `NO` | `PK` | Observation date |
| `itinerary_id` | `CHAR(16)` | `NO` | `PK` | 16-char hex hash uniquely identifying a specific flight itinerary |
| `searched_at_utc` | `DATETIME(6)` | `NO` | | Exact UTC timestamp of observation |
| `route_code` | `CHAR(7)` | `NO` | `FK` | References `dim_routes(route_code)` |
| `departure_date` | `DATE` | `NO` | | Scheduled departure date |
| `days_before_departure` | `SMALLINT UNSIGNED` | `NO` | | Lead time in days (`7` to `180`) |
| `airline_id` | `TINYINT UNSIGNED` | `NO` | `FK` | Operating airline -> `dim_airlines(airline_id)` |
| `departure_time` | `TIME` | `NO` | | Local departure time (`HH:MM:00`) |
| `arrival_time` | `TIME` | `NO` | | Local arrival time (`HH:MM:00`) |
| `arrival_day_offset` | `TINYINT UNSIGNED` | `NO` | | `0` = same day, `1` = next day (+1), `2` = +2 days |
| `duration_minutes` | `SMALLINT UNSIGNED` | `NO` | | Total travel duration in minutes (`60` to `2,504`) |
| `stops` | `TINYINT UNSIGNED` | `NO` | | Number of layover stops (`0`, `1`, `2`) |
| `price_usd` | `SMALLINT UNSIGNED` | `NO` | | Observed ticket price in USD (`$19` to `$5,046`) |
