# Unified Cloud Kitchen Platform - Backend

## Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- pip

### Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your database credentials and secrets
```

### Database Setup

```bash
# Create the database
createdb cloud_kitchen

# Run migrations
alembic upgrade head
```

### Running

```bash
uvicorn app.main:app --reload --port 8000
```

### Testing

```bash
pytest tests/ -v
```

### API Documentation

When running in development mode, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get tokens
- `POST /api/auth/logout` - Logout
- `POST /api/auth/verify-email` - Verify email address
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset password with token
- `POST /api/auth/change-password` - Change password (authenticated)
- `GET /api/auth/me` - Get current user profile

### Health
- `GET /health` - Health check
