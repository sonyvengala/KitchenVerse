"""
Comprehensive Live Auth & Session Routing Verification Script.
Tests:
- Login for all 3 roles (ADMIN, KITCHEN_OWNER, CUSTOMER).
- Authoritative role verification via /api/v1/auth/me.
- Session cookie & token based authentication.
- Server-side RBAC boundary enforcement (access granted vs access denied).
- Session restoration across requests.
- Complete logout invalidation.
- Cross-role tests.
"""
import httpx
import sys

BASE_URL = "http://localhost:8000"

def log(msg):
    print(f"[TEST] {msg}")

def assert_eq(actual, expected, desc):
    if actual != expected:
        print(f"[FAIL] {desc} (expected {expected}, got {actual})")
        sys.exit(1)
    print(f"[PASS] {desc}")

def run_tests():
    session = httpx.Client()

    # Credentials
    ADMIN_EMAIL = "admin@cloudkitchen.com"
    ADMIN_PASS = "AdminPass123!"

    KO_EMAIL = "synth_chef_e0cd2f@example.com"
    KO_PASS = "SecurePass123!"

    CUST_EMAIL = "synth_cust_e0cd2f@example.com"
    CUST_PASS = "SecurePass123!"

    print("\n" + "="*60)
    print("STEP 9A & 10: TESTING ADMIN ROLE & CROSS-ROLE ISOLATION")
    print("="*60)

    # 1. Admin Login
    r_login = session.post(f"{BASE_URL}/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert_eq(r_login.status_code, 200, "Admin login returns 200")
    admin_data = r_login.json()
    assert_eq(admin_data["role"], "ADMIN", "Admin role in login response is ADMIN")
    admin_token = admin_data["access_token"]

    # 2. Session Restoration (/me)
    r_me = session.get(f"{BASE_URL}/api/v1/auth/me")
    assert_eq(r_me.status_code, 200, "Admin session restored via /me returns 200")
    assert_eq(r_me.json()["role"], "ADMIN", "Admin authoritative role from backend is ADMIN")

    # 3. RBAC: Admin can access Admin Dashboard
    r_admin_dash = session.get(f"{BASE_URL}/api/v1/admin/dashboard")
    assert_eq(r_admin_dash.status_code, 200, "Admin can access Admin Dashboard")

    # 4. RBAC: Admin CANNOT access Kitchen Dashboard
    r_ko_dash = session.get(f"{BASE_URL}/api/v1/kitchen/dashboard")
    assert_eq(r_ko_dash.status_code, 403, "Admin is forbidden (403) from Kitchen Owner Dashboard")

    # 5. Logout Admin
    r_logout = session.post(f"{BASE_URL}/api/v1/auth/logout")
    assert_eq(r_logout.status_code, 200, "Admin logout returns 200")

    # 6. Verify session revoked after logout
    r_me_after = session.get(f"{BASE_URL}/api/v1/auth/me")
    assert_eq(r_me_after.status_code, 401, "Admin session is invalidated (401) after logout")

    print("\n" + "="*60)
    print("STEP 9B & 10: TESTING KITCHEN OWNER ROLE & CROSS-ROLE ISOLATION")
    print("="*60)

    # 1. Kitchen Owner Login
    r_login = session.post(f"{BASE_URL}/api/v1/auth/login", json={"email": KO_EMAIL, "password": KO_PASS})
    assert_eq(r_login.status_code, 200, "Kitchen Owner login returns 200")
    ko_data = r_login.json()
    assert_eq(ko_data["role"], "KITCHEN_OWNER", "Kitchen Owner role in login response is KITCHEN_OWNER")

    # 2. Session Restoration (/me)
    r_me = session.get(f"{BASE_URL}/api/v1/auth/me")
    assert_eq(r_me.status_code, 200, "Kitchen Owner session restored via /me returns 200")
    assert_eq(r_me.json()["role"], "KITCHEN_OWNER", "Kitchen Owner authoritative role from backend is KITCHEN_OWNER")

    # 3. RBAC: Kitchen Owner can access Kitchen Dashboard
    r_ko_dash = session.get(f"{BASE_URL}/api/v1/kitchen/dashboard")
    assert_eq(r_ko_dash.status_code, 200, "Kitchen Owner can access Kitchen Dashboard")

    # 4. RBAC: Kitchen Owner CANNOT access Admin Dashboard
    r_admin_dash = session.get(f"{BASE_URL}/api/v1/admin/dashboard")
    assert_eq(r_admin_dash.status_code, 403, "Kitchen Owner is forbidden (403) from Admin Dashboard")

    # 5. Logout Kitchen Owner
    r_logout = session.post(f"{BASE_URL}/api/v1/auth/logout")
    assert_eq(r_logout.status_code, 200, "Kitchen Owner logout returns 200")

    # 6. Verify session revoked after logout
    r_me_after = session.get(f"{BASE_URL}/api/v1/auth/me")
    assert_eq(r_me_after.status_code, 401, "Kitchen Owner session is invalidated (401) after logout")

    print("\n" + "="*60)
    print("STEP 9C & 10: TESTING CUSTOMER ROLE & CROSS-ROLE ISOLATION")
    print("="*60)

    # 1. Customer Login
    r_login = session.post(f"{BASE_URL}/api/v1/auth/login", json={"email": CUST_EMAIL, "password": CUST_PASS})
    assert_eq(r_login.status_code, 200, "Customer login returns 200")
    cust_data = r_login.json()
    assert_eq(cust_data["role"], "CUSTOMER", "Customer role in login response is CUSTOMER")

    # 2. Session Restoration (/me)
    r_me = session.get(f"{BASE_URL}/api/v1/auth/me")
    assert_eq(r_me.status_code, 200, "Customer session restored via /me returns 200")
    assert_eq(r_me.json()["role"], "CUSTOMER", "Customer authoritative role from backend is CUSTOMER")

    # 3. RBAC: Customer CANNOT access Admin Dashboard
    r_admin_dash = session.get(f"{BASE_URL}/api/v1/admin/dashboard")
    assert_eq(r_admin_dash.status_code, 403, "Customer is forbidden (403) from Admin Dashboard")

    # 4. RBAC: Customer CANNOT access Kitchen Dashboard
    r_ko_dash = session.get(f"{BASE_URL}/api/v1/kitchen/dashboard")
    assert_eq(r_ko_dash.status_code, 403, "Customer is forbidden (403) from Kitchen Owner Dashboard")

    # 5. RBAC: Customer can access Customer Profile & Orders
    r_cust_orders = session.get(f"{BASE_URL}/api/v1/customer/orders")
    assert_eq(r_cust_orders.status_code, 200, "Customer can access Customer Orders")

    # 6. Logout Customer
    r_logout = session.post(f"{BASE_URL}/api/v1/auth/logout")
    assert_eq(r_logout.status_code, 200, "Customer logout returns 200")

    # 7. Verify session revoked after logout
    r_me_after = session.get(f"{BASE_URL}/api/v1/auth/me")
    assert_eq(r_me_after.status_code, 401, "Customer session is invalidated (401) after logout")

    print("ALL LIVE BACKEND SESSION & ROLE RBAC TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
