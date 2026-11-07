# KitchenVerse

> **Multiple Kitchens. One Destination.**

A production-oriented, multi-tenant kitchen management and customer ordering platform featuring real-time state machines, kitchen operations management, demand forecasting ML, and three role-specific portals (Customer, Kitchen Owner, Administrator).

---

## 🏛️ Architecture Overview

The system is organized into modular services with strict separation of concerns:

- **Customer Portal**: Mobile-first responsive web client for browsing kitchens, menus, placing orders, real-time order tracking, reviews, and notifications.
- **Kitchen Owner Portal**: Operations dashboard for order queue management, kitchen-defined ingredient configuration, inventory ledger, restocking recommendations, waste tracking, and demand analytics.
- **Admin Portal**: Platform-level oversight for kitchen onboarding, order/payment monitoring, platform-wide demand analytics, complaints, and audit logging.
- **Backend API**: High-performance FastAPI application providing server-side authorization (RBAC), session management via secure HttpOnly cookies, normalized PostgreSQL schema with SQLAlchemy ORM, and WebSocket real-time event broadcasting.
- **Demand Forecasting ML Engine**: Chronologically validated machine learning models (Baseline, Gradient Boosting / CatBoost / LightGBM) trained exclusively on official fulfilment center and meal historical datasets to forecast order demand without data leakage.

```
c:\MYAPP/
├── frontend/          # React 18 + TypeScript + Vite + Vanilla CSS
│   ├── src/
│   │   ├── components/
│   │   ├── pages/     # Customer, Kitchen, Admin views
│   │   ├── services/  # API and WebSocket clients
│   │   └── context/   # Auth and Real-time context
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/       # API routers (auth, customer, kitchen, admin, orders, etc.)
│   │   ├── core/      # Config, security, session, RBAC, database engine
│   │   ├── models/    # SQLAlchemy 2.0 ORM models
│   │   ├── schemas/   # Pydantic schemas (request/response validation)
│   │   ├── services/  # Business logic (Order state machine, Inventory, Payments, etc.)
│   │   └── websockets/# Real-time pub/sub event dispatcher
│   └── tests/         # Pytest test suite
├── database/          # Database migrations (Alembic)
├── ml/                # Demand forecasting ML pipeline
│   ├── dataset.py     # Schema validation and dataset ingestion
│   ├── features.py    # Temporal and rolling feature engineering
│   ├── train.py       # Time-aware training and model comparison
│   ├── predict.py     # Batch and online inference service
│   └── artifacts/     # Persisted model binaries and metrics
├── data/              # Official datasets (train.csv, meal_info.csv, etc.)
├── config/            # Platform configuration and logging presets
└── docs/              # System architecture and API documentation
```

---

## 🎨 Design System

Adheres strictly to the food-tech SaaS palette:
- **Primary**: `#166534` (Deep Forest Green)
- **Accent**: `#F97316` (Warm Saffron / Orange)
- **Background**: `#FFFDF8` (Soft Cream / Off-White)
- **Text**: `#172033` (Deep Slate / Charcoal)
- **Success**: `#16A34A`
- **Warning**: `#EAB308`
- **Error**: `#DC2626`
- **Surface**: `#FFFFFF`

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Docker & Docker Compose (optional for local PostgreSQL)

### 1. Environment Setup
```bash
cp .env.example .env
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 4. Running via Docker Compose
```bash
docker compose up -d
```
