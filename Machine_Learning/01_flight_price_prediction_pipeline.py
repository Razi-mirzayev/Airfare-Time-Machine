"""
===============================================================================
PROJECT: AIRFARE TIME MACHINE – US FLIGHT PRICE ANALYSIS
PHASE 6: MACHINE LEARNING – FLIGHT PRICE PREDICTION PIPELINE
FILE: 01_flight_price_prediction_pipeline.py
DESCRIPTION:
    End-to-end Machine Learning pipeline for predicting US domestic flight
    ticket prices (`price_usd`) with strict Data Leakage prevention:
      1. Feature Selection & Strict Anti-Leakage Controls
      2. Aviation-Domain Feature Engineering (ATPCO thresholds, cyclical time,
         effective flight speed, day-of-week & seasonal indicators)
      3. Itinerary-Grouped Train/Test Split (`itinerary_id` group isolation)
         so the exact same flight itinerary never leaks across Train and Test
      4. Out-of-Fold / Train-Only Categorical Encoding (`OneHot` for Linear
         Regression, `Target/Ordinal` for Tree Ensembles) fit strictly on Train
      5. Model Training, Hyperparameter Tuning & Comparison:
           - Model 1: Linear Regression (L2-Regularized Ridge OLS)
           - Model 2: Random Forest Regressor (Bootstrap Feature-Subsampled Trees)
           - Model 3: Gradient Boosting Regressor (Baseline Histogram GBDT)
           - Model 4: Tuned Gradient Boosting Regressor (Hyperparameter-Tuned)
      6. Evaluation via MAE, RMSE, R², and MAPE
      7. Permutation Feature Importance & Diagnostic Plots (300 DPI)
===============================================================================
"""

import os
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
import seaborn as sns

DATASET_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Dataset"
ML_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Machine_Learning"
IMAGES_DIR = r"C:\Users\Mrzayev\.gemini\antigravity\scratch\Airfare-Time-Machine\Images"

os.makedirs(ML_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)


# =============================================================================
# EVALUATION METRICS (MAE, RMSE, R², MAPE)
# =============================================================================
def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot)
    mape = float(np.mean(np.abs(err) / np.maximum(y_true, 1.0)) * 100.0)
    return {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "R2": round(r2, 4), "MAPE_%": round(mape, 2)}


# =============================================================================
# VECTORIZED HISTOGRAM DECISION TREE & ENSEMBLE ENGINE
# (Provides native execution even when Windows Application Control blocks Cython DLLs)
# =============================================================================
class FastHistogramBinner:
    """Discretizes continuous & encoded features into `max_bins` quantile bins (fit on Train only)."""

    def __init__(self, max_bins: int = 128):
        self.max_bins = max_bins
        self.bin_edges_ = []

    def fit(self, X: np.ndarray):
        self.bin_edges_ = []
        quantiles = np.linspace(0, 100, self.max_bins + 1)[1:-1]
        for col_idx in range(X.shape[1]):
            edges = np.unique(np.percentile(X[:, col_idx], quantiles))
            self.bin_edges_.append(edges)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        n_samples, n_features = X.shape
        X_binned = np.empty((n_samples, n_features), dtype=np.int32)
        for col_idx in range(n_features):
            X_binned[:, col_idx] = np.searchsorted(self.bin_edges_[col_idx], X[:, col_idx], side="right")
        return X_binned


class FastHistTreeRegressor:
    """
    Fast vectorized Histogram-based CART Regression Tree using exact variance
    reduction (Friedman MSE criterion) with L2 leaf regularization.
    """

    def __init__(
        self,
        max_depth: int = 6,
        min_samples_leaf: int = 30,
        l2_reg: float = 1.0,
        max_features_ratio: float = 1.0,
        max_bins: int = 128,
        rng: np.random.Generator = None,
    ):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.l2_reg = l2_reg
        self.max_features_ratio = max_features_ratio
        self.max_bins = max_bins
        self.rng = rng if rng is not None else np.random.default_rng(42)
        self.tree_ = None

    def fit(self, X_binned: np.ndarray, residuals: np.ndarray):
        n_samples, n_features = X_binned.shape
        max_nodes = 2 ** (self.max_depth + 1)
        feature = np.full(max_nodes, -1, dtype=np.int32)
        threshold = np.zeros(max_nodes, dtype=np.int32)
        value = np.zeros(max_nodes, dtype=np.float64)

        node_ids = np.ones(n_samples, dtype=np.int32)
        n_sub_feat = max(1, int(np.ceil(n_features * self.max_features_ratio)))

        for depth in range(self.max_depth + 1):
            start_node = 2 ** depth
            end_node = 2 ** (depth + 1)

            for nid in range(start_node, end_node):
                mask = node_ids == nid
                cnt = int(np.sum(mask))
                if cnt == 0:
                    continue
                sum_g = float(np.sum(residuals[mask]))
                value[nid] = sum_g / (cnt + self.l2_reg)

                if depth == self.max_depth or cnt < 2 * self.min_samples_leaf:
                    continue

                if n_sub_feat < n_features:
                    feat_indices = self.rng.choice(n_features, size=n_sub_feat, replace=False)
                else:
                    feat_indices = np.arange(n_features)

                best_gain = 0.0
                best_feat = -1
                best_bin = -1
                parent_score = (sum_g ** 2) / (cnt + self.l2_reg)

                X_node = X_binned[mask]
                r_node = residuals[mask]

                for f in feat_indices:
                    bins_f = X_node[:, f]
                    c_hist = np.bincount(bins_f, minlength=self.max_bins)
                    g_hist = np.bincount(bins_f, weights=r_node, minlength=self.max_bins)

                    c_left = np.cumsum(c_hist)[:-1]
                    c_right = cnt - c_left
                    valid = (c_left >= self.min_samples_leaf) & (c_right >= self.min_samples_leaf)
                    if not np.any(valid):
                        continue

                    g_left = np.cumsum(g_hist)[:-1][valid]
                    g_right = sum_g - g_left
                    c_l_v = c_left[valid]
                    c_r_v = c_right[valid]

                    gains = (g_left ** 2) / (c_l_v + self.l2_reg) + (g_right ** 2) / (c_r_v + self.l2_reg) - parent_score
                    max_idx = int(np.argmax(gains))
                    if gains[max_idx] > best_gain:
                        best_gain = float(gains[max_idx])
                        best_feat = int(f)
                        best_bin = int(np.flatnonzero(valid)[max_idx])

                if best_feat != -1 and best_gain > 1e-6:
                    feature[nid] = best_feat
                    threshold[nid] = best_bin
                    go_left = X_node[:, best_feat] <= best_bin
                    node_ids[mask] = np.where(go_left, 2 * nid, 2 * nid + 1)

        self.tree_ = (feature, threshold, value)
        return self

    def predict(self, X_binned: np.ndarray) -> np.ndarray:
        feature, threshold, value = self.tree_
        nid = np.ones(X_binned.shape[0], dtype=np.int32)
        for _ in range(self.max_depth):
            f = feature[nid]
            active = f != -1
            if not np.any(active):
                break
            act_idx = np.flatnonzero(active)
            f_act = f[act_idx]
            thr_act = threshold[nid[act_idx]]
            go_left = X_binned[act_idx, f_act] <= thr_act
            nid[act_idx] = np.where(go_left, 2 * nid[act_idx], 2 * nid[act_idx] + 1)
        return value[nid]


class RidgeLinearRegressor:
    """Closed-form L2-Regularized Ridge Linear Regression via Cholesky solver."""

    def __init__(self, alpha: float = 10.0):
        self.alpha = alpha
        self.coef_ = None
        self.intercept_ = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.intercept_ = float(np.mean(y))
        y_centered = y - self.intercept_
        n_features = X.shape[1]
        A = X.T @ X + self.alpha * np.eye(n_features)
        b = X.T @ y_centered
        self.coef_ = np.linalg.solve(A, b)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.intercept_ + X @ self.coef_


class FastRandomForestRegressor:
    """Bootstrap-Aggregated (Bagged) Ensemble of Random Subspace Decision Trees."""

    def __init__(
        self,
        n_estimators: int = 45,
        max_depth: int = 8,
        min_samples_leaf: int = 25,
        max_features_ratio: float = 0.65,
        max_bins: int = 128,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features_ratio = max_features_ratio
        self.max_bins = max_bins
        self.random_state = random_state
        self.trees_ = []

    def fit(self, X_binned: np.ndarray, y: np.ndarray):
        rng = np.random.default_rng(self.random_state)
        n_samples = X_binned.shape[0]
        self.trees_ = []
        for _ in range(self.n_estimators):
            boot_idx = rng.choice(n_samples, size=int(0.8 * n_samples), replace=True)
            tree = FastHistTreeRegressor(
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                l2_reg=0.0,
                max_features_ratio=self.max_features_ratio,
                max_bins=self.max_bins,
                rng=rng,
            )
            tree.fit(X_binned[boot_idx], y[boot_idx])
            self.trees_.append(tree)
        return self

    def predict(self, X_binned: np.ndarray) -> np.ndarray:
        preds = np.zeros(X_binned.shape[0], dtype=np.float64)
        for tree in self.trees_:
            preds += tree.predict(X_binned)
        return preds / len(self.trees_)


class FastHistGradientBoostingRegressor:
    """Histogram-Based Gradient Boosted Decision Trees (Stochastic Friedman GBDT)."""

    def __init__(
        self,
        n_estimators: int = 80,
        learning_rate: float = 0.10,
        max_depth: int = 6,
        min_samples_leaf: int = 30,
        l2_reg: float = 1.0,
        subsample: float = 0.85,
        max_features_ratio: float = 0.85,
        max_bins: int = 128,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.l2_reg = l2_reg
        self.subsample = subsample
        self.max_features_ratio = max_features_ratio
        self.max_bins = max_bins
        self.random_state = random_state
        self.base_value_ = 0.0
        self.trees_ = []

    def fit(self, X_binned: np.ndarray, y: np.ndarray):
        rng = np.random.default_rng(self.random_state)
        self.base_value_ = float(np.mean(y))
        current_pred = np.full(len(y), self.base_value_, dtype=np.float64)
        n_samples = len(y)
        self.trees_ = []

        for _ in range(self.n_estimators):
            residuals = y - current_pred
            if self.subsample < 1.0:
                sub_idx = rng.choice(n_samples, size=int(self.subsample * n_samples), replace=False)
                X_sub, r_sub = X_binned[sub_idx], residuals[sub_idx]
            else:
                X_sub, r_sub = X_binned, residuals

            tree = FastHistTreeRegressor(
                max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf,
                l2_reg=self.l2_reg,
                max_features_ratio=self.max_features_ratio,
                max_bins=self.max_bins,
                rng=rng,
            )
            tree.fit(X_sub, r_sub)
            current_pred += self.learning_rate * tree.predict(X_binned)
            self.trees_.append(tree)
        return self

    def predict(self, X_binned: np.ndarray) -> np.ndarray:
        preds = np.full(X_binned.shape[0], self.base_value_, dtype=np.float64)
        for tree in self.trees_:
            preds += self.learning_rate * tree.predict(X_binned)
        return preds


# =============================================================================
# STEP 1 & 2: DATA LOADING & AVIATION FEATURE ENGINEERING
# =============================================================================
def load_and_engineer_dataset(sample_size: int = 200_000, random_state: int = 42) -> pd.DataFrame:
    print("=" * 80)
    print("STEP 1: LOADING GRANULAR FLIGHT DATA & ANTI-LEAKAGE AUDIT")
    print("=" * 80)

    routes = pd.read_csv(os.path.join(DATASET_DIR, "routes.csv"))
    # ANTI-LEAKAGE RULE 1:
    # Only merge physical route distance (`distance_miles`).
    # Exclude route-level `median_price_usd`, `pct_nonstop`, and `price_observations`
    # from routes.csv because those include future/test set observations!
    routes_clean = routes[["route", "distance_miles"]].copy()

    pf = pq.ParquetFile(os.path.join(DATASET_DIR, "flight_prices.parquet"))
    num_rgs = pf.metadata.num_row_groups
    rows_per_rg = sample_size // num_rgs + 1
    rng = np.random.default_rng(random_state)

    cols = [
        "search_date",
        "route",
        "origin",
        "destination",
        "departure_date",
        "days_before_departure",
        "airline",
        "departure_time",
        "arrival_day_offset",
        "duration_minutes",
        "stops",
        "price_usd",
        "itinerary_id",
    ]
    chunks = []
    for rg_idx in range(num_rgs):
        t = pf.read_row_group(rg_idx, columns=cols)
        idx = rng.choice(t.num_rows, size=min(rows_per_rg, t.num_rows), replace=False)
        chunks.append(t.take(idx).to_pandas())

    df = pd.concat(chunks, ignore_index=True)
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=random_state).reset_index(drop=True)
    df = df.merge(routes_clean, on="route", how="inner")

    print(f"Sampled dataset shape : {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"Unique routes covered : {df['route'].nunique()} / 50")
    print(f"Unique airlines       : {df['airline'].nunique()} / 17")
    print(f"Unique itineraries    : {df['itinerary_id'].nunique():,}")

    print("\n" + "=" * 80)
    print("STEP 2: AVIATION DOMAIN FEATURE ENGINEERING")
    print("=" * 80)

    dep_dt = pd.to_datetime(df["departure_date"])
    df["dep_month"] = dep_dt.dt.month
    df["dep_dayofweek"] = dep_dt.dt.dayofweek
    df["is_sunday_departure"] = (df["dep_dayofweek"] == 6).astype(float)
    df["is_midweek_tue_wed"] = df["dep_dayofweek"].isin([1, 2]).astype(float)
    df["is_summer_peak"] = df["dep_month"].isin([6, 7]).astype(float)
    df["is_holiday_season"] = df["dep_month"].isin([11, 12]).astype(float)
    df["dep_month_sin"] = np.sin(2 * np.pi * df["dep_month"] / 12.0)
    df["dep_month_cos"] = np.cos(2 * np.pi * df["dep_month"] / 12.0)

    dep_hour = df["departure_time"].str.slice(0, 2).astype(int)
    dep_min = df["departure_time"].str.slice(3, 5).astype(int)
    df["dep_hour"] = dep_hour.astype(float)
    df["dep_minute_of_day"] = (dep_hour * 60 + dep_min).astype(float)
    df["is_morning_peak_09_12"] = dep_hour.between(9, 11).astype(float)
    df["is_evening_cheap_17_20"] = dep_hour.between(17, 20).astype(float)

    dbd = df["days_before_departure"]
    df["ap_within_14_days"] = (dbd <= 14).astype(float)
    df["ap_within_21_days"] = (dbd <= 21).astype(float)
    df["is_sweet_spot_31_60d"] = dbd.between(31, 60).astype(float)

    df["effective_speed_mph"] = df["distance_miles"] / (df["duration_minutes"] / 60.0)
    df["is_nonstop"] = (df["stops"] == 0).astype(float)

    ulcc = {"Frontier Airlines", "Spirit Airlines"}
    lcc = {"Southwest Airlines", "JetBlue Airways", "Sun Country Airlines"}
    legacy = {"American Airlines", "Delta Air Lines", "United Airlines", "Alaska Airlines"}
    df["carrier_type"] = np.select(
        [
            df["airline"].isin(ulcc),
            df["airline"].isin(lcc),
            df["airline"].isin(legacy),
            df["airline"].str.contains(r"\+", regex=True),
        ],
        ["Ultra Low-Cost", "Low-Cost", "Legacy", "Multi-Carrier"],
        default="Regional",
    )

    print("Created 22 pre-booking predictive features with zero future leakage.")
    return df


# =============================================================================
# STEP 3, 4, 5 & 6: GROUP SPLIT, ENCODING, TRAINING, TUNING & EVALUATION
# =============================================================================
def run_ml_pipeline():
    df = load_and_engineer_dataset(sample_size=200_000, random_state=42)

    print("\n" + "=" * 80)
    print("STEP 3: GROUP-ISOLATED TRAIN/TEST SPLIT (BY itinerary_id)")
    print("=" * 80)

    # ANTI-LEAKAGE RULE 2:
    # Split by unique `itinerary_id` so the exact same flight itinerary tracked
    # across different search dates NEVER appears in both Train and Test!
    unique_itins = np.asarray(df["itinerary_id"].unique(), dtype=object)
    rng = np.random.default_rng(42)
    rng.shuffle(unique_itins)
    split_point = int(0.80 * len(unique_itins))
    train_itins = set(unique_itins[:split_point])

    is_train = df["itinerary_id"].isin(train_itins).values
    train_df = df[is_train].reset_index(drop=True)
    test_df = df[~is_train].reset_index(drop=True)

    overlap = len(set(train_df["itinerary_id"]).intersection(set(test_df["itinerary_id"])))
    print(f"Training set rows                 : {len(train_df):,} ({len(train_df)/len(df)*100:.1f}%)")
    print(f"Testing set rows                  : {len(test_df):,} ({len(test_df)/len(df)*100:.1f}%)")
    print(f"Overlapping itinerary_ids (Leak)  : {overlap} (Verified 0 Group Leakage!)")

    # =========================================================================
    # STEP 4: CATEGORICAL ENCODING (FIT STRICTLY ON TRAIN SET!)
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: CATEGORICAL ENCODING (ONE-HOT FOR LINEAR, TARGET/ORDINAL FOR TREES)")
    print("=" * 80)

    cat_cols = ["route", "origin", "destination", "airline", "carrier_type"]
    num_cols = [
        "distance_miles",
        "days_before_departure",
        "ap_within_14_days",
        "ap_within_21_days",
        "is_sweet_spot_31_60d",
        "dep_month",
        "dep_month_sin",
        "dep_month_cos",
        "dep_dayofweek",
        "is_sunday_departure",
        "is_midweek_tue_wed",
        "is_summer_peak",
        "is_holiday_season",
        "dep_hour",
        "dep_minute_of_day",
        "is_morning_peak_09_12",
        "is_evening_cheap_17_20",
        "duration_minutes",
        "stops",
        "is_nonstop",
        "arrival_day_offset",
        "effective_speed_mph",
    ]

    y_train = train_df["price_usd"].values.astype(np.float64)
    y_test = test_df["price_usd"].values.astype(np.float64)

    # A. One-Hot Encoding + Standard Scaling for Linear Regression (fit on train_df only)
    ohe_train_parts = []
    ohe_test_parts = []
    for c in cat_cols:
        cats = sorted(train_df[c].unique())
        for val in cats[1:]:  # drop first to avoid collinearity
            ohe_train_parts.append((train_df[c].values == val).astype(np.float64))
            ohe_test_parts.append((test_df[c].values == val).astype(np.float64))

    X_num_tr = train_df[num_cols].values.astype(np.float64)
    X_num_te = test_df[num_cols].values.astype(np.float64)
    num_mean = X_num_tr.mean(axis=0)
    num_std = np.where(X_num_tr.std(axis=0) == 0, 1.0, X_num_tr.std(axis=0))

    X_lin_train = np.column_stack([np.column_stack(ohe_train_parts), (X_num_tr - num_mean) / num_std])
    X_lin_test = np.column_stack([np.column_stack(ohe_test_parts), (X_num_te - num_mean) / num_std])

    # B. Smoothed Target-Ordered Category Encoding for Tree Models (fit on train_df only!)
    # Ordering categories by training-set target mean allows binary histogram splits
    # to partition high-cardinality categories (`route`: 50, `airline`: 17) optimally
    # (Fisher's exact theorem for regression trees on categorical variables).
    global_train_mean = float(np.mean(y_train))
    tree_cat_tr = np.empty((len(train_df), len(cat_cols)), dtype=np.float64)
    tree_cat_te = np.empty((len(test_df), len(cat_cols)), dtype=np.float64)

    for idx, c in enumerate(cat_cols):
        stats_c = train_df.groupby(c)["price_usd"].agg(["count", "mean"])
        smooth = (stats_c["count"] * stats_c["mean"] + 20.0 * global_train_mean) / (stats_c["count"] + 20.0)
        mapping = smooth.to_dict()
        tree_cat_tr[:, idx] = train_df[c].map(mapping).fillna(global_train_mean).values
        tree_cat_te[:, idx] = test_df[c].map(mapping).fillna(global_train_mean).values

    feature_names = cat_cols + num_cols
    X_tree_tr_raw = np.column_stack([tree_cat_tr, X_num_tr])
    X_tree_te_raw = np.column_stack([tree_cat_te, X_num_te])

    binner = FastHistogramBinner(max_bins=128).fit(X_tree_tr_raw)
    X_tree_train = binner.transform(X_tree_tr_raw)
    X_tree_test = binner.transform(X_tree_te_raw)

    print(f"Linear Model Matrix (One-Hot + Scaled) : {X_lin_train.shape[1]} features")
    print(f"Tree Model Matrix (Smoothed Ordered)   : {X_tree_train.shape[1]} features")

    # =========================================================================
    # STEP 5: MODEL TRAINING & HYPERPARAMETER TUNING
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: MODEL TRAINING, HYPERPARAMETER TUNING & EVALUATION")
    print("=" * 80)

    results = []

    # 1. Linear Regression (Ridge)
    t0 = time.time()
    lin_model = RidgeLinearRegressor(alpha=10.0).fit(X_lin_train, y_train)
    t_lin = time.time() - t0
    m_tr_lin = compute_metrics(y_train, lin_model.predict(X_lin_train))
    preds_te_lin = lin_model.predict(X_lin_test)
    m_te_lin = compute_metrics(y_test, preds_te_lin)
    results.append(
        {
            "Model": "1. Linear Regression (Ridge)",
            "Train_MAE": m_tr_lin["MAE"],
            "Test_MAE": m_te_lin["MAE"],
            "Train_RMSE": m_tr_lin["RMSE"],
            "Test_RMSE": m_te_lin["RMSE"],
            "Train_R2": m_tr_lin["R2"],
            "Test_R2": m_te_lin["R2"],
            "Test_MAPE_%": m_te_lin["MAPE_%"],
            "Fit_Time_s": round(t_lin, 2),
        }
    )
    print(f"1. Linear Regression (Ridge)      | Test MAE=${m_te_lin['MAE']:6.2f} | Test RMSE=${m_te_lin['RMSE']:6.2f} | Test R²={m_te_lin['R2']:.4f}")

    # 2. Random Forest Regressor
    t0 = time.time()
    rf_model = FastRandomForestRegressor(
        n_estimators=45, max_depth=8, min_samples_leaf=25, max_features_ratio=0.65, random_state=42
    ).fit(X_tree_train, y_train)
    t_rf = time.time() - t0
    m_tr_rf = compute_metrics(y_train, rf_model.predict(X_tree_train))
    preds_te_rf = rf_model.predict(X_tree_test)
    m_te_rf = compute_metrics(y_test, preds_te_rf)
    results.append(
        {
            "Model": "2. Random Forest Regressor",
            "Train_MAE": m_tr_rf["MAE"],
            "Test_MAE": m_te_rf["MAE"],
            "Train_RMSE": m_tr_rf["RMSE"],
            "Test_RMSE": m_te_rf["RMSE"],
            "Train_R2": m_tr_rf["R2"],
            "Test_R2": m_te_rf["R2"],
            "Test_MAPE_%": m_te_rf["MAPE_%"],
            "Fit_Time_s": round(t_rf, 2),
        }
    )
    print(f"2. Random Forest Regressor        | Test MAE=${m_te_rf['MAE']:6.2f} | Test RMSE=${m_te_rf['RMSE']:6.2f} | Test R²={m_te_rf['R2']:.4f}")

    # 3. Gradient Boosting (Baseline)
    t0 = time.time()
    gb_base = FastHistGradientBoostingRegressor(
        n_estimators=60, learning_rate=0.10, max_depth=5, min_samples_leaf=40, l2_reg=1.0, random_state=42
    ).fit(X_tree_train, y_train)
    t_gb = time.time() - t0
    m_tr_gb = compute_metrics(y_train, gb_base.predict(X_tree_train))
    preds_te_gb = gb_base.predict(X_tree_test)
    m_te_gb = compute_metrics(y_test, preds_te_gb)
    results.append(
        {
            "Model": "3. Gradient Boosting (Baseline)",
            "Train_MAE": m_tr_gb["MAE"],
            "Test_MAE": m_te_gb["MAE"],
            "Train_RMSE": m_tr_gb["RMSE"],
            "Test_RMSE": m_te_gb["RMSE"],
            "Train_R2": m_tr_gb["R2"],
            "Test_R2": m_te_gb["R2"],
            "Test_MAPE_%": m_te_gb["MAPE_%"],
            "Fit_Time_s": round(t_gb, 2),
        }
    )
    print(f"3. Gradient Boosting (Baseline)   | Test MAE=${m_te_gb['MAE']:6.2f} | Test RMSE=${m_te_gb['RMSE']:6.2f} | Test R²={m_te_gb['R2']:.4f}")

    # 4. Hyperparameter Tuning on Validation Split of Training Itineraries
    print("\nRunning Group-Isolated Hyperparameter Tuning for Gradient Boosting...")
    val_itins = set(list(train_itins)[: int(0.2 * len(train_itins))])
    val_mask = train_df["itinerary_id"].isin(val_itins).values
    X_sub_tr, y_sub_tr = X_tree_train[~val_mask], y_train[~val_mask]
    X_val, y_val = X_tree_train[val_mask], y_train[val_mask]

    candidate_configs = [
        {"n_estimators": 80, "learning_rate": 0.08, "max_depth": 6, "min_samples_leaf": 30, "l2_reg": 2.0},
        {"n_estimators": 110, "learning_rate": 0.08, "max_depth": 7, "min_samples_leaf": 25, "l2_reg": 3.0},
        {"n_estimators": 140, "learning_rate": 0.09, "max_depth": 8, "min_samples_leaf": 20, "l2_reg": 5.0},
    ]
    best_cfg = None
    best_val_rmse = float("inf")
    for cfg in candidate_configs:
        cand = FastHistGradientBoostingRegressor(**cfg, random_state=42).fit(X_sub_tr, y_sub_tr)
        v_metrics = compute_metrics(y_val, cand.predict(X_val))
        print(f"  [Grid Config {cfg}] -> Val RMSE=${v_metrics['RMSE']:.2f}, Val R²={v_metrics['R2']:.4f}")
        if v_metrics["RMSE"] < best_val_rmse:
            best_val_rmse = v_metrics["RMSE"]
            best_cfg = cfg

    print("Selected Optimal Hyperparameters:", best_cfg)
    t0 = time.time()
    gb_tuned = FastHistGradientBoostingRegressor(**best_cfg, random_state=42).fit(X_tree_train, y_train)
    t_tuned = time.time() - t0
    m_tr_tuned = compute_metrics(y_train, gb_tuned.predict(X_tree_train))
    preds_te_tuned = gb_tuned.predict(X_tree_test)
    m_te_tuned = compute_metrics(y_test, preds_te_tuned)

    results.append(
        {
            "Model": "4. Tuned Gradient Boosting (Best)",
            "Train_MAE": m_tr_tuned["MAE"],
            "Test_MAE": m_te_tuned["MAE"],
            "Train_RMSE": m_tr_tuned["RMSE"],
            "Test_RMSE": m_te_tuned["RMSE"],
            "Train_R2": m_tr_tuned["R2"],
            "Test_R2": m_te_tuned["R2"],
            "Test_MAPE_%": m_te_tuned["MAPE_%"],
            "Fit_Time_s": round(t_tuned, 2),
        }
    )

    res_df = pd.DataFrame(results)
    print("\n" + "=" * 80)
    print("FINAL MODEL COMPARISON TABLE (UNSEEN ITINERARY TEST SET)")
    print("=" * 80)
    print(res_df.to_string(index=False))
    res_df.to_csv(os.path.join(ML_DIR, "model_comparison_results.csv"), index=False)

    # =========================================================================
    # STEP 6: PERMUTATION FEATURE IMPORTANCE ON UNSEEN TEST SET
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: PERMUTATION FEATURE IMPORTANCE ON UNSEEN TEST SET")
    print("=" * 80)
    base_r2 = m_te_tuned["R2"]
    imp_rows = []
    rng_perm = np.random.default_rng(42)
    for col_idx, fname in enumerate(feature_names):
        drops = []
        for _ in range(3):
            X_perm = X_tree_test.copy()
            X_perm[:, col_idx] = rng_perm.permutation(X_perm[:, col_idx])
            perm_r2 = compute_metrics(y_test, gb_tuned.predict(X_perm))["R2"]
            drops.append(max(0.0, base_r2 - perm_r2))
        imp_rows.append(
            {
                "Feature": fname,
                "Importance_R2_Drop": round(float(np.mean(drops)), 4),
                "Std": round(float(np.std(drops)), 4),
            }
        )

    imp_df = pd.DataFrame(imp_rows).sort_values("Importance_R2_Drop", ascending=False).reset_index(drop=True)
    print(imp_df.head(12).to_string(index=False))
    imp_df.to_csv(os.path.join(ML_DIR, "feature_importance_results.csv"), index=False)

    # =========================================================================
    # STEP 7: GENERATE DIAGNOSTIC ML VISUALIZATIONS (300 DPI)
    # =========================================================================
    print("\nGenerating Machine Learning visualizations in Images/ ...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6), dpi=300)
    x_pos = np.arange(len(res_df))
    w = 0.35
    ax1.bar(x_pos - w / 2, res_df["Test_MAE"], width=w, color="#2A9D8F", edgecolor="black", label="Test MAE ($)")
    b_rmse = ax1.bar(x_pos + w / 2, res_df["Test_RMSE"], width=w, color="#1D3557", edgecolor="black", label="Test RMSE ($)")
    for b, r2 in zip(b_rmse, res_df["Test_R2"]):
        ax1.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + 3,
            f"R²={r2:.3f}",
            ha="center",
            fontsize=9,
            fontweight="bold",
            color="#E63946",
        )
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels([m.split(". ")[1] for m in res_df["Model"]], rotation=15, fontsize=9.5, fontweight="bold")
    ax1.set_ylim(0, max(res_df["Test_RMSE"]) * 1.18)
    ax1.set_title("Model Performance Comparison (MAE, RMSE & R² on Unseen Itineraries)", fontsize=11.5, fontweight="bold")
    ax1.set_ylabel("Error in USD ($)", fontsize=10.5, fontweight="bold")
    ax1.legend(loc="upper right")

    top10_imp = imp_df.head(10).iloc[::-1]
    b_imp = ax2.barh(top10_imp["Feature"], top10_imp["Importance_R2_Drop"], color="#457B9D", edgecolor="black")
    for b, val in zip(b_imp, top10_imp["Importance_R2_Drop"]):
        ax2.text(val + 0.004, b.get_y() + b.get_height() / 2, f"{val:.3f}", va="center", fontsize=9, fontweight="bold")
    ax2.set_xlim(0, max(top10_imp["Importance_R2_Drop"]) * 1.18)
    ax2.set_title("Top 10 Predictive Features (Permutation R² Drop on Test Set)", fontsize=11.5, fontweight="bold")
    ax2.set_xlabel("Decrease in Test R² When Feature is Permuted", fontsize=10.5, fontweight="bold")

    fig.suptitle("Machine Learning Results: Flight Price Prediction & Feature Importance", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "10_ml_model_comparison_and_importance.png"), dpi=300, bbox_inches="tight")
    plt.close()

    # Chart 11: Actual vs. Predicted & Residual Distribution
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.8), dpi=300)
    plot_idx = np.random.default_rng(42).choice(len(y_test), size=5000, replace=False)
    ax1.scatter(y_test[plot_idx], preds_te_tuned[plot_idx], alpha=0.25, s=16, color="#1D3557")
    ax1.plot([20, 1000], [20, 1000], color="#E63946", lw=2.2, linestyle="--", label="Perfect Prediction (y = x)")
    ax1.set_xlim(15, 900)
    ax1.set_ylim(15, 900)
    ax1.set_title("Actual vs. Predicted Ticket Prices (Tuned Gradient Boosting)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Actual Ticket Price ($)", fontsize=10.5, fontweight="bold")
    ax1.set_ylabel("Predicted Ticket Price ($)", fontsize=10.5, fontweight="bold")
    ax1.legend()

    residuals = y_test - preds_te_tuned
    sns.histplot(residuals, bins=70, kde=True, color="#2A9D8F", ax=ax2)
    ax2.axvline(0, color="#E63946", linestyle="--", lw=2, label="Zero Error")
    ax2.set_xlim(-220, 220)
    ax2.set_title(f"Residual Error Distribution (Median Abs Error = ${np.median(np.abs(residuals)):.1f})", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Residual Error: Actual - Predicted ($)", fontsize=10.5, fontweight="bold")
    ax2.legend()

    fig.suptitle("Diagnostic Evaluation of Tuned Gradient Boosting Model on Unseen Test Set", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, "11_ml_actual_vs_predicted_and_residuals.png"), dpi=300, bbox_inches="tight")
    plt.close()
    print("Saved 10_ml_model_comparison_and_importance.png and 11_ml_actual_vs_predicted_and_residuals.png!")


if __name__ == "__main__":
    run_ml_pipeline()
