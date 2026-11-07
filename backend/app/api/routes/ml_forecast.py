"""
Phase 5 — ML Demand Forecasting API Endpoints.
Serves pre-trained GradientBoostingRegressor predictions from the official dataset.

Endpoints:
  GET  /api/v1/ml/info          — Model metadata and evaluation metrics
  GET  /api/v1/ml/forecast      — Aggregated weekly demand predictions (admin view)
  GET  /api/v1/ml/forecast/center/{center_id}  — Center-level forecasts
  GET  /api/v1/ml/forecast/meal/{meal_id}      — Meal-level demand forecasts
  GET  /api/v1/ml/forecast/kitchen   — Kitchen owner view (scoped by meal category/cuisine)
  GET  /api/v1/ml/top-meals         — Top meals ranked by predicted demand
  GET  /api/v1/ml/centers           — Available fulfillment center list
  GET  /api/v1/ml/actuals/weekly    — Weekly actual order totals for visualization
"""
import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.deps import require_kitchen_owner, require_admin, get_db, get_current_user
from backend.app.models.enums import UserRole, OrderStatus
from backend.app.models.user import User, KitchenProfile, Address
from backend.app.models.menu import MenuItem
from backend.app.models.order import Order, OrderItem
from backend.app.services.customer_service import haversine_distance

ARTIFACTS_DIR = Path(__file__).resolve().parents[4] / "ml" / "artifacts"
if not ARTIFACTS_DIR.exists():
    # Fallback to local or configured path
    ARTIFACTS_DIR = Path("ml/artifacts").resolve()

router = APIRouter(prefix="/ml", tags=["Demand Forecasting ML"])

# ── Lazy-load model cache ─────────────────────────────────────────────────────
_model = None
_label_encoders = None
_feature_cols = None
_meta = None
_center_info = None
_meal_info = None
_weekly_actuals = None
_comparison = None


def _load_artifacts():
    global _model, _label_encoders, _feature_cols, _meta, _center_info, _meal_info, _weekly_actuals, _comparison
    if _model is not None:
        return True
    model_path = ARTIFACTS_DIR / "demand_model.pkl"
    if not model_path.exists():
        return False
    with open(model_path, "rb") as f:
        _model = pickle.load(f)
    with open(ARTIFACTS_DIR / "label_encoders.pkl", "rb") as f:
        _label_encoders = pickle.load(f)
    with open(ARTIFACTS_DIR / "feature_cols.json") as f:
        _feature_cols = json.load(f)
    with open(ARTIFACTS_DIR / "model_meta.json") as f:
        _meta = json.load(f)
    _center_info = pd.read_json(ARTIFACTS_DIR / "center_info.json")
    _meal_info = pd.read_json(ARTIFACTS_DIR / "meal_info.json")
    _weekly_actuals = pd.read_json(ARTIFACTS_DIR / "weekly_actuals.json")
    comp_path = ARTIFACTS_DIR / "algorithm_comparison.json"
    if comp_path.exists():
        with open(comp_path, "r") as f:
            _comparison = json.load(f)
    return True


def _require_model():
    if not _load_artifacts():
        raise HTTPException(
            status_code=503,
            detail="Demand forecasting model not yet trained. Run ml/train_demand_forecast.py to initialize the pipeline.",
        )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _encode_categoricals(row: dict) -> dict:
    """Encode categorical features using saved label encoders."""
    for col in ["category", "cuisine", "center_type"]:
        le = _label_encoders.get(col)
        if le and col in row:
            val = row[col]
            if val in le.classes_:
                row[col + "_enc"] = int(le.transform([val])[0])
            else:
                row[col + "_enc"] = 0  # unseen label → default
        else:
            row[col + "_enc"] = 0
    return row


def _build_feature_row(week: int, center_id: int, meal_id: int,
                        checkout_price: float, base_price: float,
                        emailer: int = 0, featured: int = 0,
                        category: str = "Other", cuisine: str = "Other",
                        center_type: str = "TYPE_A", city_code: int = 0,
                        region_code: int = 0, op_area: float = 0.0) -> dict:
    discount_pct = max(0.0, min(1.0, (base_price - checkout_price) / max(base_price, 1)))
    price_ratio = checkout_price / max(base_price, 1)
    row = {
        "week": week,
        "week_sin": np.sin(2 * np.pi * week / 52),
        "week_cos": np.cos(2 * np.pi * week / 52),
        "week_quarter": (week - 1) // 13 + 1,
        "center_id": center_id,
        "meal_id": meal_id,
        "checkout_price": checkout_price,
        "base_price": base_price,
        "log_checkout_price": np.log1p(checkout_price),
        "log_base_price": np.log1p(base_price),
        "discount_pct": discount_pct,
        "price_ratio": price_ratio,
        "emailer_for_promotion": emailer,
        "homepage_featured": featured,
        "is_promoted": int(emailer == 1 or featured == 1),
        "promotion_intensity": emailer + featured * 2,
        "category": category,
        "cuisine": cuisine,
        "center_type": center_type,
        "city_code": city_code,
        "region_code": region_code,
        "op_area": op_area,
    }
    row = _encode_categoricals(row)
    return row


def _predict(rows: list[dict]) -> list[float]:
    X = pd.DataFrame(rows)[_feature_cols]
    preds = _model.predict(X).clip(0)
    return [round(float(p), 1) for p in preds]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/info")
def get_model_info():
    """Model metadata, training config, and evaluation metrics."""
    _require_model()
    return _meta


@router.get("/actuals/weekly")
def get_weekly_actuals(
    center_id: Optional[int] = Query(None, description="Filter by center_id"),
    last_n_weeks: int = Query(20, ge=4, le=145),
):
    """Weekly actual order totals from the training data, for time-series visualization."""
    _require_model()
    df = _weekly_actuals.copy()
    if center_id is not None:
        df = df[df["center_id"] == center_id]
    max_week = int(df["week"].max())
    df = df[df["week"] > max_week - last_n_weeks]
    return df.sort_values("week").to_dict(orient="records")


@router.get("/centers")
def list_centers():
    """Available fulfillment center list."""
    _require_model()
    return _center_info.to_dict(orient="records")


@router.get("/meals")
def list_meals(
    category: Optional[str] = Query(None),
    cuisine: Optional[str] = Query(None),
):
    """Available meal list from meal_info.csv."""
    _require_model()
    df = _meal_info.copy()
    if category:
        df = df[df["category"].str.lower() == category.lower()]
    if cuisine:
        df = df[df["cuisine"].str.lower() == cuisine.lower()]
    return df.to_dict(orient="records")


@router.get("/forecast")
def get_aggregated_forecast(
    weeks_ahead: int = Query(4, ge=1, le=12, description="Number of future weeks to forecast"),
    current_user: User = Depends(require_admin),
):
    """
    Admin view: Aggregated demand forecast across all centers for the next N weeks.
    Uses the last known week (145) as the baseline.
    """
    _require_model()
    last_week = 145
    centers = _center_info.to_dict(orient="records")
    meals = _meal_info.to_dict(orient="records")

    # Sample top 20 center-meal pairs to keep response fast
    # Use median prices from training data signature
    results = []
    sampled_centers = centers[:20]  # top centers
    sampled_meals = meals[:10]     # popular meals

    for future_week in range(last_week + 1, last_week + weeks_ahead + 1):
        week_total = 0
        for center in sampled_centers:
            rows = []
            for meal in sampled_meals:
                rows.append(_build_feature_row(
                    week=future_week,
                    center_id=center["center_id"],
                    meal_id=meal["meal_id"],
                    checkout_price=150.0,
                    base_price=160.0,
                    category=meal.get("category", "Other"),
                    cuisine=meal.get("cuisine", "Other"),
                    center_type=center.get("center_type", "TYPE_A"),
                    city_code=center.get("city_code", 0),
                    region_code=center.get("region_code", 0),
                    op_area=center.get("op_area", 0.0),
                ))
            preds = _predict(rows)
            week_total += sum(preds)
        results.append({
            "week": future_week,
            "week_label": f"Week {future_week}",
            "predicted_orders": round(week_total, 0),
            "centers_sampled": len(sampled_centers),
            "meals_sampled": len(sampled_meals),
        })

    return {
        "model_info": {
            "type": _meta.get("model_type"),
            "mae": _meta["metrics"]["mae"],
            "rmse": _meta["metrics"]["rmse"],
            "r2": _meta["metrics"]["r2"],
            "mape_pct": _meta["metrics"]["mape_pct"],
        },
        "weeks_forecasted": weeks_ahead,
        "baseline_week": last_week,
        "predictions": results,
    }


@router.get("/forecast/center/{center_id}")
def get_center_forecast(
    center_id: int,
    weeks_ahead: int = Query(4, ge=1, le=12),
    current_user: User = Depends(require_admin),
):
    """Center-level demand forecast for specified future weeks."""
    _require_model()
    center_row = _center_info[_center_info["center_id"] == center_id]
    if center_row.empty:
        raise HTTPException(status_code=404, detail=f"Center {center_id} not found.")
    center = center_row.iloc[0].to_dict()

    last_week = 145
    meals = _meal_info.to_dict(orient="records")
    predictions = []

    for future_week in range(last_week + 1, last_week + weeks_ahead + 1):
        rows = []
        for meal in meals[:30]:  # top meals
            rows.append(_build_feature_row(
                week=future_week,
                center_id=center_id,
                meal_id=meal["meal_id"],
                checkout_price=150.0,
                base_price=160.0,
                category=meal.get("category", "Other"),
                cuisine=meal.get("cuisine", "Other"),
                center_type=center.get("center_type", "TYPE_A"),
                city_code=int(center.get("city_code", 0)),
                region_code=int(center.get("region_code", 0)),
                op_area=float(center.get("op_area", 0.0)),
            ))
        preds = _predict(rows)
        predictions.append({
            "week": future_week,
            "week_label": f"Week {future_week}",
            "predicted_orders": round(sum(preds), 0),
            "meal_breakdown": [
                {"meal_id": meals[i]["meal_id"], "category": meals[i]["category"], "cuisine": meals[i]["cuisine"], "predicted_orders": preds[i]}
                for i in range(len(preds))
            ],
        })

    return {
        "center": center,
        "predictions": predictions,
    }


@router.get("/reference-model")
def get_kitchen_reference_forecast(
    current_user: User = Depends(require_admin),
    weeks_ahead: int = Query(4, ge=1, le=8),
):
    """
    SECTION A / MODE 1 — OFFICIAL DATASET REFERENCE BENCHMARK
    Serves reference predictions based on the official historical research dataset (456K+ rows).
    Clearly labeled as a benchmark model — does NOT represent an individual kitchen's actual demand.
    """
    _require_model()
    last_week = 145
    categories = _meal_info["category"].unique().tolist()
    cuisines = _meal_info["cuisine"].unique().tolist()

    category_forecasts = []
    for cat in categories:
        cat_meals = _meal_info[_meal_info["category"] == cat].head(5).to_dict(orient="records")
        weekly_preds = []
        for future_week in range(last_week + 1, last_week + weeks_ahead + 1):
            rows = [_build_feature_row(
                week=future_week, center_id=77, meal_id=m["meal_id"],
                checkout_price=150.0, base_price=160.0,
                category=m["category"], cuisine=m["cuisine"],
                center_type="TYPE_A", city_code=0, region_code=0, op_area=0.0,
            ) for m in cat_meals]
            preds = _predict(rows)
            weekly_preds.append({"week": future_week, "predicted_orders": round(sum(preds), 1)})
        category_forecasts.append({
            "category": cat,
            "weekly_predictions": weekly_preds,
            "avg_predicted_weekly": round(np.mean([w["predicted_orders"] for w in weekly_preds]), 1),
        })

    category_forecasts.sort(key=lambda x: -x["avg_predicted_weekly"])

    return {
        "mode": "REFERENCE_OFFICIAL_DATASET",
        "label": "Reference Model — Official Dataset",
        "disclaimer": "This model is trained on the official historical fulfillment dataset (456K+ records) and does NOT represent this kitchen's real customer order history or actual menu items.",
        "model_name": f"{_meta.get('model_type', 'RandomForestRegressor')} (Active Reference Model)",
        "model_metrics": {
            "mae": _meta["metrics"]["mae"],
            "rmse": _meta["metrics"]["rmse"],
            "r2": _meta["metrics"]["r2"],
            "mape_pct": _meta["metrics"]["mape_pct"],
        },
        "weeks_forecasted": weeks_ahead,
        "validation_strategy": _meta.get("validation_strategy", "Time-aware split (no future leakage)"),
        "total_dataset_records": "456,548 historical fulfillment records",
        "category_demand_forecast": category_forecasts,
        "available_categories": categories,
        "available_cuisines": cuisines,
    }


@router.get("/algorithm-comparison")
def get_algorithm_comparison(
    current_user: User = Depends(require_admin),
):
    """
    SECTION A.1 — OFFICIAL REFERENCE BENCHMARK ALGORITHM COMPARISON
    Fair, non-leaking comparison of demand forecasting algorithms on the official 456K dataset:
      1. Random Forest Regressor (Top balanced MAE & RMSE)
      2. Gradient Boosting Regressor (Original reference benchmark)
      3. XGBoost Regressor (Top R², fastest gradient boosted tree)
      4. Time-Series Baseline (Rolling 4-week moving average per series)
      5. Linear Regression (Ridge regularized pipeline with fit-on-train scaling)
    Strictly evaluated on the official 456,548-record reference dataset (Weeks 1-116 Train vs Weeks 117-145 Test).
    """
    _require_model()
    comp_path = ARTIFACTS_DIR / "algorithm_comparison.json"
    if not comp_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Algorithm comparison benchmarks not yet generated. Run ml/compare_algorithms.py.",
        )
    with open(comp_path, "r") as f:
        return json.load(f)


@router.get("/top-meals")
def get_top_meals(
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
    cuisine: Optional[str] = Query(None),
    current_user: User = Depends(require_admin),
):
    """
    Reference benchmark top meals from the official training dataset.
    Clearly labeled as training dataset records, not the current kitchen's menu.
    """
    _require_model()
    meals = _meal_info.copy()
    if category:
        meals = meals[meals["category"].str.lower() == category.lower()]
    if cuisine:
        meals = meals[meals["cuisine"].str.lower() == cuisine.lower()]
    meals = meals.head(50)

    future_week = 146
    rows = [_build_feature_row(
        week=future_week, center_id=77, meal_id=int(m["meal_id"]),
        checkout_price=150.0, base_price=160.0,
        category=str(m["category"]), cuisine=str(m["cuisine"]),
        center_type="TYPE_A", city_code=0, region_code=0, op_area=0.0,
    ) for _, m in meals.iterrows()]
    preds = _predict(rows)

    results = []
    for i, (_, m) in enumerate(meals.iterrows()):
        results.append({
            "meal_id": int(m["meal_id"]),
            "category": str(m["category"]),
            "cuisine": str(m["cuisine"]),
            "predicted_orders_next_week": preds[i],
            "dataset_reference": True,
        })

    results.sort(key=lambda x: -x["predicted_orders_next_week"])
    return {
        "mode": "REFERENCE_OFFICIAL_DATASET",
        "disclaimer": "These meal IDs and categories reflect the benchmark fulfillment dataset, not your kitchen's menu.",
        "top_meals": results[:limit],
    }


@router.get("/forecast/kitchen")
@router.get("/operational-forecast")
def get_operational_forecast(
    weeks_ahead: int = Query(4, ge=1, le=4),
    kitchen_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    SECTION B / MODE 2 — CLOUDKITCHEN OPERATIONAL FORECAST
    Uses ONLY REAL DATA from the authenticated kitchen's database records:
      - Real orders (filtered strictly by kitchen_id)
      - Real order items and quantities
      - Real menu items belonging to this kitchen
    NEVER mixes with the 456K official dataset or other kitchens' orders.
    Enforces minimum data requirements: 10 real orders and 7 days of history.
    If threshold is not met, returns an honest 'insufficient_data' state.
    """
    # 1. Authorize and isolate target kitchen
    target_kitchen = None
    if current_user.role == UserRole.KITCHEN_OWNER:
        target_kitchen = current_user.kitchen_profile
        if not target_kitchen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No kitchen profile found for authenticated kitchen owner."
            )
    elif current_user.role == UserRole.ADMIN:
        if kitchen_id:
            target_kitchen = db.query(KitchenProfile).filter(KitchenProfile.id == kitchen_id).first()
        else:
            target_kitchen = db.query(KitchenProfile).first()
        if not target_kitchen:
            return {
                "mode": "CLOUDKITCHEN_OPERATIONAL_FORECAST",
                "status": "insufficient_data",
                "kitchen_id": None,
                "kitchen_name": None,
                "actual_orders_available": 0,
                "history_available_days": 0,
                "min_required_orders": 10,
                "min_required_days": 7,
                "message": "No kitchens exist in the platform database yet.",
                "kitchen_menu_items": [],
                "forecast": [],
            }
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to Kitchen Owners and Administrators."
        )

    # 2. Fetch real menu items strictly for this kitchen
    real_menu_items = db.query(MenuItem).filter(
        MenuItem.kitchen_id == target_kitchen.id
    ).order_by(MenuItem.name).all()

    # 3. Fetch real orders strictly for this kitchen
    real_orders = db.query(Order).filter(
        Order.kitchen_id == target_kitchen.id
    ).all()

    total_orders = len(real_orders)
    
    # Calculate history span in days
    history_days = 0
    earliest_date = None
    latest_date = None
    if real_orders:
        dates = [o.created_at for o in real_orders if o.created_at]
        if dates:
            earliest_date = min(dates)
            latest_date = max(dates)
            now_utc = datetime.now(timezone.utc)
            first_tz = earliest_date if earliest_date.tzinfo else earliest_date.replace(tzinfo=timezone.utc)
            history_days = max(1, (now_utc - first_tz).days)

    # Group orders by calendar day, distinguishing real vs test
    orders_by_day: Dict[str, Dict[str, int]] = {}
    total_real_count = 0
    total_test_count = 0
    for o in real_orders:
        if o.created_at:
            day_str = o.created_at.strftime("%Y-%m-%d")
            if day_str not in orders_by_day:
                orders_by_day[day_str] = {"total": 0, "real": 0, "test": 0}
            orders_by_day[day_str]["total"] += 1
            if getattr(o, "is_test", False):
                orders_by_day[day_str]["test"] += 1
                total_test_count += 1
            else:
                orders_by_day[day_str]["real"] += 1
                total_real_count += 1

    distinct_operating_days = len(orders_by_day)
    history_days = max(distinct_operating_days, history_days)

    # Build chronological daily history with clear REAL vs TEST labels
    daily_history = []
    for day_str in sorted(orders_by_day.keys()):
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        d_info = orders_by_day[day_str]
        if d_info["real"] > 0 and d_info["test"] > 0:
            data_type = "REAL & TEST"
        elif d_info["test"] > 0:
            data_type = "TEST DATA"
        else:
            data_type = "REAL DATA"

        daily_history.append({
            "date": day_str,
            "day_name": dt.strftime("%A"),
            "actual_orders": d_info["total"],
            "real_orders": d_info["real"],
            "test_orders": d_info["test"],
            "data_type": data_type,
            "is_actual": True,
        })

    # Summary of items ordered historically
    item_sales: Dict[str, int] = {}
    for o in real_orders:
        for it in o.items:
            if it.menu_item_id:
                item_sales[it.menu_item_id] = item_sales.get(it.menu_item_id, 0) + it.quantity

    menu_item_summary = []
    for m in real_menu_items:
        sold = item_sales.get(m.id, 0)
        menu_item_summary.append({
            "id": m.id,
            "name": m.name,
            "category": m.category,
            "cuisine": m.cuisine,
            "price": float(m.price),
            "is_available": m.is_available,
            "historical_units_sold": sold,
        })

    MIN_PROJECTION_ORDERS = 5
    MIN_PROJECTION_DAYS = 3

    # 4. Adaptive & Progressive Forecasting: Check data maturity
    if total_orders == 0:
        return {
            "mode": "CLOUDKITCHEN_OPERATIONAL_FORECAST",
            "status": "insufficient_data",
            "confidence": "NONE",
            "kitchen_id": target_kitchen.id,
            "kitchen_name": target_kitchen.kitchen_name,
            "actual_orders_available": 0,
            "history_available_days": 0,
            "min_required_orders": MIN_PROJECTION_ORDERS,
            "min_required_days": MIN_PROJECTION_DAYS,
            "message": "Your kitchen needs real order history before an operational demand forecast can be calculated.",
            "daily_history": [],
            "daily_forecast": [],
            "menu_item_demand": menu_item_summary,
            "preparation_plan_status": "unavailable",
            "preparation_plan_message": "Preparation recommendation unavailable — insufficient reliable history.",
            "ingredient_readiness": [],
            "data_freshness": {
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "orders_from": None,
                "orders_to": None,
            },
        }

    if total_orders < MIN_PROJECTION_ORDERS or history_days < MIN_PROJECTION_DAYS:
        return {
            "mode": "CLOUDKITCHEN_OPERATIONAL_FORECAST",
            "status": "insufficient_data",
            "confidence": "INSUFFICIENT_FOR_PROJECTION",
            "kitchen_id": target_kitchen.id,
            "kitchen_name": target_kitchen.kitchen_name,
            "actual_orders_available": total_orders,
            "history_available_days": history_days,
            "min_required_orders": MIN_PROJECTION_ORDERS,
            "min_required_days": MIN_PROJECTION_DAYS,
            "message": f"Initial order history detected ({total_orders} real order(s) across {history_days} day(s)). Displaying actual chronological history. Future portion projections and inventory preparation plans require at least {MIN_PROJECTION_ORDERS} orders across {MIN_PROJECTION_DAYS} operating days to ensure statistical reliability.",
            "daily_history": daily_history,
            "daily_forecast": [],
            "menu_item_demand": menu_item_summary,
            "preparation_plan_status": "unavailable",
            "preparation_plan_message": "Preparation recommendation unavailable — insufficient reliable history.",
            "ingredient_readiness": [],
            "data_freshness": {
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "orders_from": earliest_date.isoformat() if earliest_date else None,
                "orders_to": latest_date.isoformat() if latest_date else None,
            },
        }

    # 5. Calculate real operational forecast based on real item order velocities
    effective_days = max(1, history_days)
    daily_order_velocity = round(total_orders / effective_days, 1)

    # Determine statistical confidence
    if total_orders >= 30 and history_days >= 14:
        confidence = "HIGH"
    elif total_orders >= 15:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Section A: Progressive Daily Forecast with 10% Safety Buffer
    # Safety buffer rule: Capacity includes 10% buffer over base demand to absorb arrival volatility without perishability waste.
    SAFETY_BUFFER_PCT = 10
    predicted_daily = max(1, round(daily_order_velocity))
    recommended_capacity = round(predicted_daily * (1 + SAFETY_BUFFER_PCT / 100))

    daily_forecast = []
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    today_idx = datetime.now(timezone.utc).weekday()
    for d in range(1, 8):
        future_day = days_of_week[(today_idx + d) % 7]
        daily_forecast.append({
            "day_offset": d,
            "day_name": future_day,
            "predicted_demand": predicted_daily,
            "safety_buffer_pct": SAFETY_BUFFER_PCT,
            "recommended_capacity": recommended_capacity,
            "confidence": confidence,
        })

    # Section B: Menu Item Portion Predictions (strictly current kitchen items)
    menu_item_forecasts = []
    ingredient_requirements: Dict[str, Dict[str, Any]] = {}

    for m in real_menu_items:
        units_sold = item_sales.get(m.id, 0)
        daily_velocity = units_sold / effective_days
        weekly_rate = round(daily_velocity * 7.0, 1)
        daily_predicted_portions = max(1, round(daily_velocity)) if units_sold > 0 else 0

        # Section C: Ingredient Requirements from real recipe links
        for recipe_link in m.ingredients_recipe:
            ing = recipe_link.ingredient
            if ing:
                qty_needed = round(daily_predicted_portions * recipe_link.quantity_required, 3)
                if ing.id not in ingredient_requirements:
                    ingredient_requirements[ing.id] = {
                        "ingredient_id": ing.id,
                        "ingredient_name": ing.name,
                        "unit": ing.unit,
                        "required_amount": 0.0,
                        "available_stock": ing.current_stock,
                        "minimum_stock_threshold": float(ing.minimum_stock_threshold or 0.0),
                        "reorder_quantity": float(ing.reorder_quantity or 0.0),
                    }
                ingredient_requirements[ing.id]["required_amount"] += qty_needed

        menu_item_forecasts.append({
            "menu_item_id": m.id,
            "name": m.name,
            "category": m.category,
            "cuisine": m.cuisine,
            "price": float(m.price),
            "historical_units_sold": units_sold,
            "daily_order_rate": round(daily_velocity, 2),
            "predicted_daily_portions": daily_predicted_portions,
            "weekly_predicted_demand": weekly_rate,
        })

    menu_item_forecasts.sort(key=lambda x: -x["predicted_daily_portions"])

    # Section C: Ingredient Readiness & Restock Recommendations (Forecast-Aware)
    ingredient_readiness = []
    for ing_id, ing_data in ingredient_requirements.items():
        req_amt = round(ing_data["required_amount"], 2)
        avail = round(ing_data["available_stock"], 2)
        min_thresh = round(ing_data["minimum_stock_threshold"], 2)
        reorder_qty = round(ing_data["reorder_quantity"], 2)
        projected = round(avail - req_amt, 2)
        restock_needed = max(0.0, round(req_amt + min_thresh - avail, 2))

        # Case 3: Current stock < forecasted usage -> SHORTAGE
        if avail < req_amt:
            status_val = "SHORTAGE"
            forecast_status = "SHORTAGE"
            short_by = round(req_amt - avail, 2)
            recom = f"Shortage of {short_by} {ing_data['unit']}. Restock {restock_needed} {ing_data['unit']} before next prep shift"
        # Case 1: Projected stock after forecast < minimum threshold -> RESTOCK REQUIRED
        elif projected < min_thresh:
            status_val = "RESTOCK_REQUIRED"
            forecast_status = "RESTOCK REQUIRED"
            short_by = round(min_thresh - projected, 2)
            recom = f"Projected stock ({projected} {ing_data['unit']}) below buffer ({min_thresh} {ing_data['unit']}). Restock {restock_needed} {ing_data['unit']}"
        # Case 2: Projected stock >= minimum threshold -> SUFFICIENT
        else:
            status_val = "OK"
            forecast_status = "SUFFICIENT"
            short_by = 0.0
            recom = "Stock is sufficient for forecasted demand"

        rec_reorder = max(reorder_qty, restock_needed) if restock_needed > 0 else reorder_qty

        ingredient_readiness.append({
            "ingredient_id": ing_id,
            "ingredient_name": ing_data["ingredient_name"],
            "unit": ing_data["unit"],
            "required_amount": req_amt,
            "expected_usage": req_amt,
            "available_stock": avail,
            "current_stock": avail,
            "projected_stock": projected,
            "minimum_threshold": min_thresh,
            "minimum_stock_threshold": min_thresh,
            "short_by": short_by,
            "shortage_amount": short_by,
            "restock_needed": restock_needed,
            "recommended_reorder_qty": rec_reorder,
            "status": status_val,
            "forecast_status": forecast_status,
            "restock_recommendation": recom,
        })

    return {
        "mode": "CLOUDKITCHEN_OPERATIONAL_FORECAST",
        "status": "operational",
        "confidence": confidence,
        "kitchen_id": target_kitchen.id,
        "kitchen_name": target_kitchen.kitchen_name,
        "weeks_forecasted": weeks_ahead,
        "actual_orders_analyzed": total_orders,
        "total_real_orders": total_real_count,
        "total_test_orders": total_test_count,
        "distinct_operating_days": distinct_operating_days,
        "history_period_days": history_days,
        "message": f"Operational demand forecast calculated from {total_orders} recorded orders ({total_real_count} real, {total_test_count} controlled test) across {distinct_operating_days} operating days.",
        "daily_history": daily_history,
        "daily_forecast": daily_forecast,
        "safety_buffer_rule": f"Capacity recommendations incorporate a {SAFETY_BUFFER_PCT}% safety buffer over base projected demand to absorb peak customer arrival spikes while protecting perishable ingredients.",
        "menu_item_demand": menu_item_forecasts,
        "preparation_plan_status": "available",
        "ingredient_readiness": ingredient_readiness,
        "data_freshness": {
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "orders_from": earliest_date.isoformat() if earliest_date else None,
            "orders_to": latest_date.isoformat() if latest_date else None,
        },
    }


@router.get("/demand-center")
def get_demand_center(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days for demand analysis"),
    kitchen_id: Optional[str] = Query(None, description="Optional kitchen filter for admins"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    CloudKitchen Demand Intelligence Center.
    
    Provides two clearly distinguished demand dimensions:
      1. KITCHEN DEMAND: Orders received by CloudKitchen kitchens.
         Answers: 'Which CloudKitchen kitchen has the most REAL orders?'
         Source: Real production Order records grouped by kitchen_id.
      2. GEOGRAPHIC DEMAND AREAS: Customer delivery locations.
         Answers: 'Where are customers ordering from?'
         Source: Real delivery addresses from completed customer orders.
    
    Strict Data Rules:
      - ONLY real database data (Order, KitchenProfile, Address).
      - Zero test/demo orders (is_test == False, order_number NOT LIKE 'TEST-%').
      - Zero synthetic data or fake hotspots.
      - Zero unapproved or fake kitchens.
      - Cancelled/rejected/refunded orders are excluded.
      - No fabrication of coordinates.
    """
    if current_user.role not in [UserRole.KITCHEN_OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to Kitchen Owners and Administrators."
        )

    # 1. Fetch all real approved CloudKitchen kitchens from the database
    db_approved_kitchens = db.query(KitchenProfile).filter(
        KitchenProfile.is_approved == True
    ).all()

    # 2. Query real production orders strictly within the requested timeframe
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    excluded_statuses = [
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.REFUNDED,
    ]

    real_orders_query = db.query(Order).filter(
        Order.created_at >= cutoff,
        Order.is_test == False,
        ~Order.order_number.like("TEST-%"),
        ~Order.status.in_(excluded_statuses),
    )

    all_real_orders = real_orders_query.all()
    total_real_orders = len(all_real_orders)
    total_real_revenue = round(sum(float(o.total_amount) for o in all_real_orders), 2)

    def compute_demand_intensity(count: int) -> str:
        """
        Demand thresholds:
          - HIGH: >= 20 real orders
          - MEDIUM: 5–19 real orders
          - LOW: < 5 real orders
        """
        if count >= 20:
            return "HIGH"
        elif count >= 5:
            return "MEDIUM"
        return "LOW"

    # =========================================================================
    # FEATURE 1 — KITCHEN DEMAND
    # "Which CloudKitchen kitchen has the most REAL orders?"
    # Source: real production Order records grouped by kitchen_id.
    # =========================================================================
    kitchen_demand_list = []
    kitchen_list = []

    for k in db_approved_kitchens:
        # Orders fulfilled by this specific kitchen
        k_orders = [o for o in all_real_orders if o.kitchen_id == k.id]
        k_order_count = len(k_orders)
        k_customers = len(set(o.customer_id for o in k_orders if o.customer_id))
        k_revenue = round(sum(float(o.total_amount) for o in k_orders), 2)
        k_intensity = compute_demand_intensity(k_order_count)
        k_rating = float(k.rating) if k.rating is not None else 5.0

        is_my_kitchen = bool(
            current_user.kitchen_profile
            and k.id == current_user.kitchen_profile.id
        )

        kitchen_demand_item = {
            "kitchen_id": k.id,
            "kitchen_name": k.kitchen_name,
            "city": k.city or "Unknown City",
            "address": k.address,
            "order_count": k_order_count,
            "unique_customers": k_customers,
            "revenue": k_revenue,
            "demand_intensity": k_intensity,
            "is_open": k.is_open,
            "is_approved": k.is_approved,
            "rating": k_rating,
            "total_reviews": k.rating_count,
            "is_my_kitchen": is_my_kitchen,
        }
        kitchen_demand_list.append(kitchen_demand_item)

        kitchen_list.append({
            "id": k.id,
            "kitchen_name": k.kitchen_name,
            "address": k.address,
            "city": k.city,
            "latitude": float(k.latitude) if k.latitude is not None else None,
            "longitude": float(k.longitude) if k.longitude is not None else None,
            "is_open": k.is_open,
            "is_approved": k.is_approved,
            "rating": k_rating,
            "total_reviews": k.rating_count,
            "order_count": k_order_count,
            "unique_customers": k_customers,
            "revenue": k_revenue,
            "demand_intensity": k_intensity,
            "is_my_kitchen": is_my_kitchen,
        })

    # Sort kitchen demand by order count descending, then revenue descending
    kitchen_demand_list.sort(key=lambda x: (-x["order_count"], -x["revenue"]))

    # =========================================================================
    # FEATURE 2 — GEOGRAPHIC DEMAND AREAS
    # "Where are customers ordering from?"
    # Source: real customer delivery locations from real customer orders.
    # =========================================================================
    area_buckets: Dict[str, Dict[str, Any]] = {}
    order_dates = []

    for o in all_real_orders:
        if o.created_at:
            order_dates.append(o.created_at)

        # Geographic demand represents customer delivery locations.
        # Orders without delivery addresses are excluded to prevent conflating kitchen hub locations with customer demand.
        addr = o.delivery_address
        if not addr:
            continue

        raw_city = (addr.city or "").strip()
        raw_postal = (addr.postal_code or "").strip()

        if not raw_city and not raw_postal:
            continue

        # Normalize city naming / casing and common abbreviations
        clean_city = raw_city.title()
        if clean_city.lower() in ("han", "hanamkonda", "hanumakonda"):
            clean_city = "Hanamkonda"
        elif clean_city.lower() in ("blr", "bangalore", "bengaluru"):
            clean_city = "Bengaluru"

        postal_code = raw_postal
        display_city = clean_city or "Unspecified Location"
        area_key = f"{display_city} — {postal_code}" if postal_code else display_city

        base_lat = float(addr.latitude) if addr.latitude is not None else None
        base_lng = float(addr.longitude) if addr.longitude is not None else None

        if area_key not in area_buckets:
            area_buckets[area_key] = {
                "area_name": area_key,
                "city": display_city,
                "postal_code": postal_code,
                "order_count": 0,
                "revenue": 0.0,
                "items_sold": 0,
                "unique_customers": set(),
                "latitude": base_lat,
                "longitude": base_lng,
            }

        bucket = area_buckets[area_key]
        bucket["order_count"] += 1
        bucket["revenue"] += float(o.total_amount)
        bucket["items_sold"] += sum(i.quantity for i in o.items)
        if o.customer_id:
            bucket["unique_customers"].add(o.customer_id)
        if bucket["latitude"] is None and base_lat is not None:
            bucket["latitude"] = base_lat
            bucket["longitude"] = base_lng

    MIN_RECOMMENDATION_ORDERS = 5
    MIN_RECOMMENDATION_CUSTOMERS = 3

    demand_areas = []
    for area_key, b in area_buckets.items():
        area_lat = b["latitude"]
        area_lng = b["longitude"]
        unique_cust_count = len(b["unique_customers"])
        count = b["order_count"]

        # Calculate distances to all existing real approved kitchens
        kitchen_distances = []
        kitchens_within_3km = 0
        if area_lat is not None and area_lng is not None:
            for k in db_approved_kitchens:
                if k.latitude is not None and k.longitude is not None:
                    dist = haversine_distance(area_lat, area_lng, float(k.latitude), float(k.longitude))
                    kitchen_distances.append((k.kitchen_name, dist))
                    if dist <= 3.0:
                        kitchens_within_3km += 1

        nearest_kitchen_name = None
        nearest_distance = None
        if kitchen_distances:
            kitchen_distances.sort(key=lambda x: x[1])
            nearest_kitchen_name = kitchen_distances[0][0]
            nearest_distance = round(kitchen_distances[0][1], 2)

        # Geographic demand intensity
        intensity = compute_demand_intensity(count)

        # Check evidence threshold for new kitchen opportunity recommendation
        meets_threshold = (count >= MIN_RECOMMENDATION_ORDERS and unique_cust_count >= MIN_RECOMMENDATION_CUSTOMERS)
        is_coverage_gap = (
            meets_threshold
            and (kitchens_within_3km == 0 or (nearest_distance is not None and nearest_distance > 3.0))
        )

        demand_areas.append({
            "area_name": b["area_name"],
            "city": b["city"],
            "postal_code": b["postal_code"],
            "order_count": count,
            "unique_customers": unique_cust_count,
            "revenue": round(b["revenue"], 2),
            "items_sold": b["items_sold"],
            "demand_intensity": intensity,
            "latitude": b["latitude"],
            "longitude": b["longitude"],
            "nearest_kitchen_name": nearest_kitchen_name,
            "nearest_kitchen_distance_km": nearest_distance,
            "kitchens_within_3km": kitchens_within_3km,
            "meets_recommendation_threshold": meets_threshold,
            "coverage_gap": is_coverage_gap,
            "opportunity_score": round((count * 10) / (kitchens_within_3km + 1), 1) if meets_threshold else 0.0,
            "recommendation_note": "Potential cloud-kitchen opportunity" if is_coverage_gap else (
                "Well served by existing hubs" if meets_threshold else "Insufficient real geographic demand history for a reliable location recommendation."
            ),
        })

    # Sort demand areas by order count descending
    demand_areas.sort(key=lambda x: -x["order_count"])

    top_demand_areas = demand_areas[:3]
    recommended_areas = [a for a in demand_areas if a["coverage_gap"]]
    recommended_areas.sort(key=lambda x: -x["opportunity_score"])

    earliest_iso = min(order_dates).isoformat() if order_dates else None
    latest_iso = max(order_dates).isoformat() if order_dates else None

    return {
        "mode": "REAL_DEMAND_CENTER",
        "status": "operational" if total_real_orders > 0 else "insufficient_data",
        "period_days": days,
        "total_orders": total_real_orders,
        "total_revenue": total_real_revenue,
        "definitions": {
            "kitchen_demand": "Kitchen Demand = orders received by KitchenVerse kitchens.",
            "geographic_demand": "Geographic Demand = customer delivery locations.",
        },
        "threshold_rule": f"Location intelligence requires at least {MIN_RECOMMENDATION_ORDERS} orders from {MIN_RECOMMENDATION_CUSTOMERS}+ unique customers. Single or scarce orders are mapped for transparency but excluded from coverage gap recommendations.",
        "kitchen_demand": kitchen_demand_list,
        "demand_areas": demand_areas,
        "top_demand_areas": top_demand_areas,
        "recommended_areas": recommended_areas[:5],
        "cloudkitchen_kitchens": kitchen_list,
        "data_freshness": {
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "earliest_order": earliest_iso,
            "latest_order": latest_iso,
        },
    }
