"""
KitchenVerse — ML Demand Forecasting Pipeline.
Active Model: Random Forest Regressor (Evaluated Top Candidate).

Supports both Random Forest Regressor (default active candidate) and
Gradient Boosting Regressor (preserved for rollback and comparison).

Dataset Features (456,548 records, 145 weeks):
  - week (1-145): chronological ordering — strict time-aware split enforced
  - center_id, meal_id, checkout_price, base_price, emailer_for_promotion, homepage_featured
  - Joined: category, cuisine (from meal_info.csv), city_code, region_code, center_type, op_area (from fulfilment_center_info.csv)

Target: num_orders (weekly demand per center-meal pair)

Time-aware validation:
  - Train weeks 1-116 (80%), Validation weeks 117-145 (20%)
  - Zero cross-time shuffle — chronological integrity and non-leakage strictly preserved
"""

import os
import sys
import json
import time
import pickle
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True, parents=True)

DATA_DIR = Path(__file__).parent.parent / "data"

TRAIN_SPLIT_WEEK = 116  # 80% of 145 weeks


def load_and_merge_data() -> pd.DataFrame:
    print("[1/5] Loading official fulfillment datasets...")
    train = pd.read_csv(DATA_DIR / "train.csv")
    meal_info = pd.read_csv(DATA_DIR / "meal_info.csv")
    center_info = pd.read_csv(DATA_DIR / "fulfilment_center_info.csv")
    print(f"  train.csv shape: {train.shape}")

    # Merge meal info (category + cuisine)
    df = train.merge(meal_info, on="meal_id", how="left")
    # Merge center info (city_code, region_code, center_type, op_area)
    df = df.merge(center_info, on="center_id", how="left")
    print(f"  Merged shape: {df.shape} (456,548 total records)")
    return df


def engineer_features(df: pd.DataFrame):
    print("[2/5] Engineering domain features (strict train-only fit)...")
    # Discount percentage feature
    df["discount_pct"] = np.where(
        df["base_price"] > 0,
        (df["base_price"] - df["checkout_price"]) / df["base_price"],
        0.0,
    )
    df["discount_pct"] = df["discount_pct"].clip(0, 1)

    # Price ratio
    df["price_ratio"] = df["checkout_price"] / df["base_price"].replace(0, 1)

    # Log-scale price features to reduce skew
    df["log_checkout_price"] = np.log1p(df["checkout_price"])
    df["log_base_price"] = np.log1p(df["base_price"])

    # Seasonality features (week-based)
    df["week_sin"] = np.sin(2 * np.pi * df["week"] / 52)
    df["week_cos"] = np.cos(2 * np.pi * df["week"] / 52)
    df["week_quarter"] = (df["week"] - 1) // 13 + 1  # Q1-Q4 quarterly cycle

    # Promotion combo
    df["is_promoted"] = ((df["emailer_for_promotion"] == 1) | (df["homepage_featured"] == 1)).astype(int)
    df["promotion_intensity"] = df["emailer_for_promotion"] + df["homepage_featured"] * 2

    # Fit label encoders strictly on training slice (week <= TRAIN_SPLIT_WEEK)
    train_mask = df["week"] <= TRAIN_SPLIT_WEEK
    label_encoders = {}
    for col in ["category", "cuisine", "center_type"]:
        le = LabelEncoder()
        train_vals = df.loc[train_mask, col].fillna("Unknown").astype(str)
        le.fit(train_vals)
        label_encoders[col] = le

        classes_set = set(le.classes_)
        df[col + "_enc"] = df[col].fillna("Unknown").astype(str).map(
            lambda x: le.transform([x])[0] if x in classes_set else 0
        )

    feature_cols = [
        "week", "week_sin", "week_cos", "week_quarter",
        "center_id", "meal_id",
        "checkout_price", "base_price",
        "log_checkout_price", "log_base_price",
        "discount_pct", "price_ratio",
        "emailer_for_promotion", "homepage_featured",
        "is_promoted", "promotion_intensity",
        "category_enc", "cuisine_enc", "center_type_enc",
        "city_code", "region_code", "op_area",
    ]
    print(f"  Feature count: {len(feature_cols)}")
    return df, feature_cols, label_encoders


def time_aware_split(df: pd.DataFrame, feature_cols: list):
    """Strict chronological split — no shuffle, zero future leakage."""
    print(f"[3/5] Time-aware split: train weeks 1-{TRAIN_SPLIT_WEEK}, val weeks {TRAIN_SPLIT_WEEK+1}-145...")
    train = df[df["week"] <= TRAIN_SPLIT_WEEK].copy()
    val = df[df["week"] > TRAIN_SPLIT_WEEK].copy()

    X_train = train[feature_cols]
    y_train = train["num_orders"]
    X_val = val[feature_cols]
    y_val = val["num_orders"]
    print(f"  Train size: {len(X_train):,} | Val size: {len(X_val):,}")
    return X_train, y_train, X_val, y_val, val


def train_model(X_train, y_train, model_type: str = "random_forest"):
    t0 = time.time()
    if model_type == "random_forest":
        print("[4/5] Training candidate active model: RandomForestRegressor...")
        hyperparams = {
            "n_estimators": 100,
            "max_depth": 16,
            "min_samples_leaf": 10,
            "max_features": 0.8,
            "random_state": 42,
            "n_jobs": -1,
        }
        model = RandomForestRegressor(**hyperparams)
    elif model_type == "gradient_boosting":
        print("[4/5] Training reference model: GradientBoostingRegressor...")
        hyperparams = {
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.08,
            "subsample": 0.8,
            "min_samples_leaf": 20,
            "loss": "huber",
            "random_state": 42,
        }
        model = GradientBoostingRegressor(**hyperparams)
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Expected 'random_forest' or 'gradient_boosting'.")

    model.fit(X_train, y_train)
    elapsed = time.time() - t0
    print(f"  Training complete in {elapsed:.1f}s")
    return model, hyperparams, elapsed


def evaluate_model(model, X_val, y_val, feature_cols):
    print("[5/5] Evaluating on held-out validation set (Weeks 117-145, no leakage)...")
    y_pred = model.predict(X_val).clip(0)

    mae = mean_absolute_error(y_val, y_pred)
    rmse = np.sqrt(mean_squared_error(y_val, y_pred))
    r2 = r2_score(y_val, y_pred)

    # Safe MAPE handling zero/near-zero actuals
    denom = np.maximum(np.abs(y_val), 1.0)
    mape = np.mean(np.abs(y_val - y_pred) / denom) * 100.0

    print(f"  MAE  : {mae:.3f}")
    print(f"  RMSE : {rmse:.3f}")
    print(f"  R²   : {r2:.4f}")
    print(f"  MAPE : {mape:.2f}%")

    # Feature importances
    importances = dict(zip(feature_cols, [float(x) for x in model.feature_importances_]))
    top_features = dict(sorted(importances.items(), key=lambda x: -x[1])[:10])

    return {
        "mae": round(float(mae), 3),
        "rmse": round(float(rmse), 3),
        "r2": round(float(r2), 4),
        "mape_pct": round(float(mape), 2),
        "top_features": top_features,
    }


def save_artifacts(model, model_type: str, hyperparams: dict, label_encoders, feature_cols, metrics, elapsed_time: float, df):
    print("Saving artifacts...")

    # Backup existing active model if present
    active_path = ARTIFACTS_DIR / "demand_model.pkl"
    if active_path.exists() and not (ARTIFACTS_DIR / "gradient_boosting_demand_model.pkl").exists():
        import shutil
        shutil.copy(active_path, ARTIFACTS_DIR / "gradient_boosting_demand_model.pkl")
        print("  Preserved previous active model to gradient_boosting_demand_model.pkl")

    # Save active model as demand_model.pkl
    with open(active_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  Saved active model to: {active_path}")

    # Also save dedicated named model artifact
    named_model_path = ARTIFACTS_DIR / f"{model_type}_demand_model.pkl"
    with open(named_model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  Saved {model_type} artifact to: {named_model_path}")

    # Save encoders
    with open(ARTIFACTS_DIR / "label_encoders.pkl", "wb") as f:
        pickle.dump(label_encoders, f)

    # Save feature list
    with open(ARTIFACTS_DIR / "feature_cols.json", "w") as f:
        json.dump(feature_cols, f)

    # Save center meta (for API queries)
    center_info = pd.read_csv(DATA_DIR / "fulfilment_center_info.csv")
    meal_info = pd.read_csv(DATA_DIR / "meal_info.csv")
    center_info.to_json(ARTIFACTS_DIR / "center_info.json", orient="records")
    meal_info.to_json(ARTIFACTS_DIR / "meal_info.json", orient="records")

    model_display_name = "RandomForestRegressor" if model_type == "random_forest" else "GradientBoostingRegressor"

    # Save active training metadata (for /api/v1/ml/info and admin portal)
    meta = {
        "model_type": model_display_name,
        "target": "num_orders",
        "train_weeks": f"1-{TRAIN_SPLIT_WEEK}",
        "val_weeks": f"{TRAIN_SPLIT_WEEK+1}-145",
        "train_samples": int((df["week"] <= TRAIN_SPLIT_WEEK).sum()),
        "val_samples": int((df["week"] > TRAIN_SPLIT_WEEK).sum()),
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "metrics": metrics,
        "hyperparameters": hyperparams,
        "training_time_sec": round(elapsed_time, 2),
        "validation_strategy": "Strict time-aware split (no shuffle, zero future leakage)",
        "dataset_source": "Official fulfillment center + meal_info supplementary dataset (456,548 records)",
        "is_customer_data": False,
        "trained_at": pd.Timestamp.now().isoformat(),
    }
    with open(ARTIFACTS_DIR / "model_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Save weekly actuals summary for visualization (last 20 weeks per center)
    weekly_summary = (
        df.groupby(["week", "center_id"])["num_orders"]
        .sum()
        .reset_index()
        .rename(columns={"num_orders": "total_orders"})
    )
    weekly_summary.to_json(ARTIFACTS_DIR / "weekly_actuals.json", orient="records")

    print(f"\nArtifacts successfully saved to: {ARTIFACTS_DIR}")
    print(f"Active Model: {model_display_name} | MAE: {metrics['mae']} | RMSE: {metrics['rmse']} | R²: {metrics['r2']} | MAPE: {metrics['mape_pct']}%")


def main():
    parser = argparse.ArgumentParser(description="KitchenVerse Demand Forecasting Training Pipeline")
    parser.add_argument(
        "--model",
        choices=["random_forest", "gradient_boosting"],
        default="random_forest",
        help="Model algorithm to train as candidate active model (default: random_forest)",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("KITCHENVERSE — DEMAND FORECASTING PIPELINE")
    print(f"Candidate Active Model: {args.model.upper()}")
    print("Official Reference Dataset (456,548 records, 145 weeks)")
    print("=" * 65)

    df = load_and_merge_data()
    df, feature_cols, label_encoders = engineer_features(df)
    X_train, y_train, X_val, y_val, val_df = time_aware_split(df, feature_cols)
    model, hyperparams, elapsed = train_model(X_train, y_train, model_type=args.model)
    metrics = evaluate_model(model, X_val, y_val, feature_cols)
    save_artifacts(model, args.model, hyperparams, label_encoders, feature_cols, metrics, elapsed, df)
    print("\n[OK] Pipeline completed successfully.")


if __name__ == "__main__":
    main()
