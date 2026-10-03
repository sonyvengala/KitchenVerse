"""Admin API tests."""
import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER, TEST_KITCHEN_OWNER


# Helper to get admin token (requires admin user in DB)
async def get_admin_token(client: AsyncClient) -> str:
    """Get admin token - requires admin user to exist in DB."""
    # For testing, we'll need to create an admin user first
    # This is a placeholder - in real tests, you'd create admin via bootstrap script
    pass


class TestAdminAuthorization:
    """Tests for admin endpoint authorization."""

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_dashboard(self, client: AsyncClient):
        """Test that CUSTOMER role cannot access admin dashboard."""
        # Register as customer
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        # Try to access admin dashboard
        response = await client.get(
            "/api/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "Admin role required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_kitchen_owner_cannot_access_admin_dashboard(self, client: AsyncClient):
        """Test that KITCHEN_OWNER role cannot access admin dashboard."""
        # Register as kitchen owner
        await client.post("/api/auth/register", json=TEST_KITCHEN_OWNER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_KITCHEN_OWNER["email"],
            "password": TEST_KITCHEN_OWNER["password"],
        })
        token = login_response.json()["access_token"]

        # Try to access admin dashboard
        response = await client.get(
            "/api/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "Admin role required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_admin(self, client: AsyncClient):
        """Test that unauthenticated users cannot access admin endpoints."""
        response = await client.get("/api/admin/dashboard")
        assert response.status_code == 403 or response.status_code == 401

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_users(self, client: AsyncClient):
        """Test that CUSTOMER cannot access admin users endpoint."""
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_kitchens(self, client: AsyncClient):
        """Test that CUSTOMER cannot access admin kitchens endpoint."""
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/admin/kitchens",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_orders(self, client: AsyncClient):
        """Test that CUSTOMER cannot access admin orders endpoint."""
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/admin/orders",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_analytics(self, client: AsyncClient):
        """Test that CUSTOMER cannot access admin analytics endpoint."""
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/admin/analytics",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_customer_cannot_access_admin_audit_logs(self, client: AsyncClient):
        """Test that CUSTOMER cannot access admin audit logs endpoint."""
        await client.post("/api/auth/register", json=TEST_USER)
        login_response = await client.post("/api/auth/login", json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
        })
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
