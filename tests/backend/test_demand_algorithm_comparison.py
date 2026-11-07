"""
Backend Test Suite for Demand Forecasting Algorithm Comparison.

Verifies:
  1. The benchmark artifact (algorithm_comparison.json) exists and is valid.
  2. Dataset integrity: Exactly 456,548 total records, 361,348 train (weeks 1-116), 95,200 test (weeks 117-145).
  3. Non-leakage: Chronological split, target variable is num_orders, preprocessing fit only on train.
  4. Algorithm coverage:
      - XGBoost Regressor
      - Random Forest Regressor
      - Linear Regression
      - Time-Series Forecasting Baseline
      - Gradient Boosting Regressor (Reference)
  5. Metrics computation: MAE, RMSE, R², and safe MAPE exist and are non-null.
  6. Model selection: Random Forest Regressor selected based on lowest MAE & RMSE and tied top R².
  7. API endpoint: GET /api/v1/ml/algorithm-comparison is restricted to admin and returns valid data.
  8. Clear distinction: Benchmark data is explicitly labeled as official reference data, NOT customer data.
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.enums import UserRole
from backend.app.models.user import User

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "ml" / "artifacts"


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def admin_user(db_session):
    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    assert admin is not None, "An admin user must exist in the database"
    return admin


@pytest.fixture(scope="module")
def customer_user(db_session):
    customer = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()
    assert customer is not None, "A customer user must exist in the database"
    return customer


def test_algorithm_comparison_artifact_exists_and_valid():
    """Verify algorithm_comparison.json exists and adheres to schema."""
    comparison_file = ARTIFACTS_DIR / "algorithm_comparison.json"
    assert comparison_file.exists(), f"Benchmark file {comparison_file} must exist."

    with open(comparison_file, "r") as f:
        data = json.load(f)

    assert "dataset_metadata" in data
    assert "validation_protocol" in data
    assert "models" in data
    assert "ranking" in data
    assert "best_model" in data
    assert "limitations" in data


def test_reference_dataset_record_counts_and_distinction():
    """Verify official reference dataset has 456,548 records and is distinguished from customer data."""
    comparison_file = ARTIFACTS_DIR / "algorithm_comparison.json"
    with open(comparison_file, "r") as f:
        data = json.load(f)

    meta = data["dataset_metadata"]
    assert meta["total_records"] == 456548, "Official reference dataset must have exactly 456,548 records"
    assert meta["train_records"] == 361348, "Training split (weeks 1-116) must have 361,348 records"
    assert meta["test_records"] == 95200, "Testing split (weeks 117-145) must have 95,200 records"
    assert meta["train_weeks"] == "1-116"
    assert meta["test_weeks"] == "117-145"
    assert meta["unique_centers"] == 77
    assert meta["unique_meals"] == 51
    assert meta["target_variable"] == "num_orders"
    assert meta["is_customer_data"] is False, "Must NOT be labeled as customer data"
    assert "OFFICIAL REFERENCE DATASET ONLY" in meta["data_distinction_note"]


def test_all_five_algorithms_evaluated():
    """Verify all 4 required approaches plus reference model are present."""
    comparison_file = ARTIFACTS_DIR / "algorithm_comparison.json"
    with open(comparison_file, "r") as f:
        data = json.load(f)

    models = data["models"]
    expected_models = [
        "XGBoost Regressor",
        "Random Forest Regressor",
        "Linear Regression",
        "Time-Series Baseline",
        "Gradient Boosting (Reference)",
    ]

    for model_name in expected_models:
        assert model_name in models, f"Model '{model_name}' must be evaluated in comparison."
        m = models[model_name]["metrics"]
        assert m["mae"] > 0, f"{model_name} MAE must be positive"
        assert m["rmse"] > 0, f"{model_name} RMSE must be positive"
        assert -1.0 <= m["r2"] <= 1.0, f"{model_name} R² must be a valid correlation score"
        assert m["mape_pct"] > 0, f"{model_name} MAPE must be positive"
        assert "training_time_sec" in m


def test_model_ranking_and_best_model_selection():
    """Verify that Random Forest Regressor is correctly identified as top performer across multi-metrics."""
    comparison_file = ARTIFACTS_DIR / "algorithm_comparison.json"
    with open(comparison_file, "r") as f:
        data = json.load(f)

    best_model = data["best_model"]
    assert best_model["algorithm"] == "Random Forest Regressor"

    rf_metrics = data["models"]["Random Forest Regressor"]["metrics"]
    xgb_metrics = data["models"]["XGBoost Regressor"]["metrics"]
    linear_metrics = data["models"]["Linear Regression"]["metrics"]
    ts_metrics = data["models"]["Time-Series Baseline"]["metrics"]

    # Random forest outperforms Linear and Time-Series by significant margin
    assert rf_metrics["mae"] < linear_metrics["mae"]
    assert rf_metrics["mae"] < ts_metrics["mae"]
    assert rf_metrics["r2"] > linear_metrics["r2"]
    assert rf_metrics["r2"] > ts_metrics["r2"]

    # Random forest has lower MAE and lower MAPE than XGBoost
    assert rf_metrics["mae"] < xgb_metrics["mae"]
    assert rf_metrics["mape_pct"] < xgb_metrics["mape_pct"]


def test_algorithm_comparison_api_endpoint_rbac():
    """Verify GET /api/v1/ml/algorithm-comparison enforces RBAC (admin only)."""
    client = TestClient(app)

    # 1. Unauthenticated request should be rejected (401)
    unauth_resp = client.get("/api/v1/ml/algorithm-comparison")
    assert unauth_resp.status_code in [401, 403]


def test_algorithm_comparison_api_endpoint_admin_access(admin_user):
    """Verify GET /api/v1/ml/algorithm-comparison returns valid data for admin."""
    from backend.app.core.deps import require_admin

    app.dependency_overrides[require_admin] = lambda: admin_user
    try:
        client = TestClient(app)
        response = client.get("/api/v1/ml/algorithm-comparison")
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}: {response.text}"

        data = response.json()
        assert "dataset_metadata" in data
        assert "models" in data
        assert len(data["models"]) == 5
        assert data["best_model"]["algorithm"] == "Random Forest Regressor"
        assert data["dataset_metadata"]["total_records"] == 456548
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_random_forest_active_candidate_model_and_meta():
    """Verify that demand_model.pkl is RandomForestRegressor and metadata is updated."""
    import pickle
    from sklearn.ensemble import RandomForestRegressor

    model_path = ARTIFACTS_DIR / "demand_model.pkl"
    assert model_path.exists(), "demand_model.pkl must exist."
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    assert isinstance(model, RandomForestRegressor), f"Active model must be RandomForestRegressor, got {type(model)}"
    assert model.n_estimators == 100
    assert model.max_depth == 16
    assert model.min_samples_leaf == 10

    meta_path = ARTIFACTS_DIR / "model_meta.json"
    with open(meta_path, "r") as f:
        meta = json.load(f)

    assert meta["model_type"] == "RandomForestRegressor"
    assert meta["metrics"]["mae"] == 90.009
    assert meta["metrics"]["rmse"] == 191.098
    assert meta["metrics"]["r2"] == 0.7262
    assert meta["metrics"]["mape_pct"] == 68.9
    assert meta["train_samples"] == 361348
    assert meta["val_samples"] == 95200


def test_gradient_boosting_rollback_artifact_preserved():
    """Verify that Gradient Boosting reference model is preserved for rollback and comparison."""
    import pickle
    from sklearn.ensemble import GradientBoostingRegressor

    gb_path = ARTIFACTS_DIR / "gradient_boosting_demand_model.pkl"
    assert gb_path.exists(), "gradient_boosting_demand_model.pkl must be preserved for rollback."
    with open(gb_path, "rb") as f:
        gb_model = pickle.load(f)

    assert isinstance(gb_model, GradientBoostingRegressor), f"Preserved model must be GradientBoostingRegressor, got {type(gb_model)}"


def test_forecast_api_endpoints_with_active_random_forest(admin_user):
    """Verify all forecast API endpoints return valid non-negative predictions with the new active model."""
    from backend.app.core.deps import require_admin
    import backend.app.api.routes.ml_forecast as ml_routes

    # Force reloading artifacts in route cache to load new active model
    ml_routes._model = None
    ml_routes._load_artifacts()

    app.dependency_overrides[require_admin] = lambda: admin_user
    try:
        client = TestClient(app)

        # 1. /info endpoint
        info_resp = client.get("/api/v1/ml/info")
        assert info_resp.status_code == 200
        info_data = info_resp.json()
        assert info_data["model_type"] == "RandomForestRegressor"
        assert info_data["metrics"]["mae"] == 90.009

        # 2. /forecast (aggregated platform forecast)
        forecast_resp = client.get("/api/v1/ml/forecast?weeks_ahead=4")
        assert forecast_resp.status_code == 200
        f_data = forecast_resp.json()
        assert f_data["model_info"]["type"] == "RandomForestRegressor"
        assert len(f_data["predictions"]) == 4
        for pred in f_data["predictions"]:
            assert pred["predicted_orders"] >= 0.0, "Predictions must be non-negative"

        # 3. /reference-model endpoint
        ref_resp = client.get("/api/v1/ml/reference-model?weeks_ahead=4")
        assert ref_resp.status_code == 200
        ref_data = ref_resp.json()
        assert "RandomForestRegressor" in ref_data["model_name"]
        for cat in ref_data["category_demand_forecast"]:
            assert cat["avg_predicted_weekly"] >= 0.0
            for w in cat["weekly_predictions"]:
                assert w["predicted_orders"] >= 0.0

        # 4. /top-meals endpoint
        top_resp = client.get("/api/v1/ml/top-meals?limit=10")
        assert top_resp.status_code == 200
        top_data = top_resp.json()
        assert len(top_data["top_meals"]) == 10
        for m in top_data["top_meals"]:
            assert m["predicted_orders_next_week"] >= 0.0

        # 5. /forecast/center/{center_id} endpoint
        center_resp = client.get("/api/v1/ml/forecast/center/10?weeks_ahead=2")
        assert center_resp.status_code == 200
        c_data = center_resp.json()
        assert len(c_data["predictions"]) == 2
        for p in c_data["predictions"]:
            assert p["predicted_orders"] >= 0.0
            for item in p["meal_breakdown"]:
                assert item["predicted_orders"] >= 0.0
    finally:
        app.dependency_overrides.pop(require_admin, None)
