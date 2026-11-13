# Dataset Directory – Airfare Time Machine

## Overview
This folder contains the dataset files from the Kaggle repository:
**[Airfare Time Machine – US Flight Prices](https://www.kaggle.com/datasets/pooyanayebi/airfare-time-machine-us-flight-prices)**

| File Name | Rows | Columns | Size | Tracked in Git? |
| :--- | :---: | :---: | :---: | :---: |
| `airports.csv` | 16 | 7 | 1.45 KB | Yes |
| `routes.csv` | 50 | 10 | 3.04 KB | Yes |
| `daily_fares.csv` | 1,683,033 | 13 | 127.2 MB | Ignored (`>100 MB` GitHub limit) |
| `flight_prices.parquet` | 38,584,829 | 15 | 94.8 MB | Ignored (`>50 MB` GitHub limit) |

## Reproducing the Full Pipeline Locally
1. Download the archive from [Kaggle](https://www.kaggle.com/datasets/pooyanayebi/airfare-time-machine-us-flight-prices).
2. Extract `daily_fares.csv` and `flight_prices.parquet` into this `Dataset/` folder alongside `airports.csv` and `routes.csv`.
3. Run the SQL scripts in `SQL/` or the Python scripts in `Python/` and `Machine_Learning/`.
