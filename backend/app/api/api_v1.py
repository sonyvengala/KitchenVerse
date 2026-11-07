"""
API v1 Router aggregation.
"""
from fastapi import APIRouter
from backend.app.api.routes import health, auth, customer, kitchen, admin, protected_test, ml_forecast, websockets

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(customer.router)
api_router.include_router(kitchen.router)
api_router.include_router(admin.router)
api_router.include_router(ml_forecast.router)
api_router.include_router(protected_test.router)
api_router.include_router(websockets.router)
