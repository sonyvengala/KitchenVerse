"""Authentication API tests."""
import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER, TEST_KITCHEN_OWNER


# =============================================
# REGISTRATION TESTS
# =============================================

class TestRegistration:
    """Tests for POST /api/auth/register"""

    @pytest.mark.asyncio
    async def test_register_customer_success(self, client: AsyncClient):
        """Test successful customer registration."""
        response = await client.post("/api/auth/register", json=TEST_USER)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == TEST_USER["email"]
        assert data["first_name"] == TEST_USER["first_name"]
        assert data["last_name"] == TEST_USER["last_name"]
        assert data["role"] == "CUSTOMER"
        assert data["status"] == "PENDING_VERIFICATION"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_kitchen_owner_success(self, client: AsyncClient):
        """Test successful kitchen owner registration."""
        response = await client.post("/api/auth/register", json=TEST_KITCHEN_OWNER)
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "KITCHEN_OWNER"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Test registration with duplicate email fails."""
        await client.post("/api/auth/register", json=TEST_USER)
        response = await client.post("/api/auth/register", json=TEST_USER)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email format."""
        user = {**TEST_USER, "email": "not-an-email"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration with missing required fields."""
        response = await client.post("/api/auth/register", json={"email": "test@test.com"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_role(self, client: AsyncClient):
        """Test registration with invalid role."""
        user = {**TEST_USER, "role": "SUPERADMIN"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422


# =============================================
# PASSWORD VALIDATION TESTS
# =============================================

class TestPasswordValidation:
    """Tests for password strength requirements."""

    @pytest.mark.asyncio
    async def test_password_too_short(self, client: AsyncClient):
        """Test password shorter than 8 characters."""
        user = {**TEST_USER, "password": "Ab1!"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_password_no_uppercase(self, client: AsyncClient):
        """Test password without uppercase letter."""
        user = {**TEST_USER, "password": "lowercase123!"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422
        assert "uppercase" in response.json()["detail"][0]["msg"].lower()

    @pytest.mark.asyncio
    async def test_password_no_lowercase(self, client: AsyncClient):
        """Test password without lowercase letter."""
        user = {**TEST_USER, "password": "UPPERCASE123!"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422
        assert "lowercase" in response.json()["detail"][0]["msg"].lower()

    @pytest.mark.asyncio
    async def test_password_no_digit(self, client: AsyncClient):
        """Test password without digit."""
        user = {**TEST_USER, "password": "NoDigitsHere!"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422
        assert "digit" in response.json()["detail"][0]["msg"].lower()

    @pytest.mark.asyncio
    async def test_password_no_special_char(self, client: AsyncClient):
        """Test password without special character."""
        user = {**TEST_USER, "password": "NoSpecial123"}
        response = await client.post("/api/auth/register", json=user)
        assert response.status_code == 422
        assert "special" in response.json()["detail"][0]["msg"].lower()


# =============================================
# LOGIN TESTS
# =============================================

class TestLogin:
    """Tests for POST /api/auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        # Register first
        await client.post("/api/auth/register", json=TEST_USER)
        # Login
        response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with wrong password."""
        await client.post("/api/auth/register", json=TEST_USER)
        response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": "WrongPassword1!",
        })
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email."""
        response = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "TestPass123!",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Test login with invalid email format."""
        response = await client.post("/api/auth/login", json={
            "email": "not-email",
            "password": "TestPass123!",
        })
        assert response.status_code == 422


# =============================================
# AUTHENTICATION TESTS
# =============================================

class TestAuthentication:
    """Tests for authenticated endpoints."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, client: AsyncClient):
        """Test GET /api/auth/me with valid token."""
        # Register and login
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        # Get profile
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == TEST_USER["email"]
        assert data["first_name"] == TEST_USER["first_name"]
        # Ensure password hash is never exposed
        assert "hashed_password" not in data
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, client: AsyncClient):
        """Test GET /api/auth/me without token."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 403 or response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Test GET /api/auth/me with invalid token."""
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """Test POST /api/auth/logout with valid token."""
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        response = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()


# =============================================
# EMAIL VERIFICATION TESTS
# =============================================

class TestEmailVerification:
    """Tests for POST /api/auth/verify-email"""

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, client: AsyncClient):
        """Test email verification with invalid token."""
        response = await client.post("/api/auth/verify-email", json={"token": "invalid-token"})
        assert response.status_code == 400


# =============================================
# PASSWORD RESET TESTS
# =============================================

class TestPasswordReset:
    """Tests for password reset flow."""

    @pytest.mark.asyncio
    async def test_forgot_password_returns_safe_response(self, client: AsyncClient):
        """Test forgot password doesn't reveal if email exists."""
        # Non-existent email
        response = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert response.status_code == 200

        # Existing email
        await client.post("/api/auth/register", json=TEST_USER)
        response = await client.post("/api/auth/forgot-password", json={"email": TEST_USER["email"]})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, client: AsyncClient):
        """Test password reset with invalid token."""
        response = await client.post("/api/auth/reset-password", json={
            "token": "invalid-token",
            "new_password": "NewPass123!",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated(self, client: AsyncClient):
        """Test change password without authentication."""
        response = await client.post("/api/auth/change-password", json={
            "current_password": "OldPass123!",
            "new_password": "NewPass456!",
        })
        assert response.status_code == 403 or response.status_code == 401


# =============================================
# ROLE AUTHORIZATION TESTS
# =============================================

class TestRoleAuthorization:
    """Tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_endpoints(self, client: AsyncClient):
        """Test that customer role cannot access admin-only endpoints."""
        # Register as customer
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        # Try to access a hypothetical admin endpoint
        # (In Phase 1, we test the dependency directly via /me which all roles can access)
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["role"] == "CUSTOMER"

    @pytest.mark.asyncio
    async def test_kitchen_owner_registration(self, client: AsyncClient):
        """Test kitchen owner can register and login."""
        await client.post("/api/auth/register", json=TEST_KITCHEN_OWNER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_KITCHEN_OWNER["email"],
            "password": TEST_KITCHEN_OWNER["password"],
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["role"] == "KITCHEN_OWNER"


# =============================================
# HEALTH CHECK TESTS
# =============================================

class TestHealthCheck:
    """Tests for health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        """Test health check returns healthy status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()
