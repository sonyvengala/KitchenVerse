"""
Test end-to-end registration, console verification, and kitchen portal authorization.
"""
import uuid
import httpx

BASE_URL = "http://localhost:3000"

def test_full_kitchen_lifecycle():
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"chef_{unique_suffix}@example.com"
    password = "SecurePassword123!"
    
    print(f"1. Registering new kitchen owner: {email}...")
    reg_payload = {
        "email": email,
        "password": password,
        "full_name": f"Chef {unique_suffix.capitalize()}",
        "phone_number": "+1234567890",
        "kitchen_name": f"Spice Haven {unique_suffix.capitalize()}",
        "address": "456 Gourmet Ave",
        "city": "Metropolis",
    }
    
    session = httpx.Client()
    reg_resp = session.post(f"{BASE_URL}/api/auth/register-kitchen", json=reg_payload)
    print(f"   Registration status: {reg_resp.status_code}")
    assert reg_resp.status_code == 201, f"Expected 201, got {reg_resp.status_code}: {reg_resp.text}"
    user_data = reg_resp.json()
    print(f"   User role: {user_data.get('role')}, is_verified: {user_data.get('is_verified')}")
    assert user_data.get('role') == 'KITCHEN_OWNER'
    assert user_data.get('is_verified') is False
    
    # 2. Check database directly to retrieve the generated verification token
    import psycopg
    conn = psycopg.connect("postgresql://postgres:postgres@localhost:5433/cloudkitchen_db")
    cur = conn.cursor()
    cur.execute("SELECT id, is_verified, verification_token FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    if row:
        user_id, is_verified, token = row
        print(f"2. DB State: user_id={user_id}, is_verified={is_verified}, token={token[:12]}...")
        assert not is_verified
        assert token is not None
        
        # 3. Simulate email verification via frontend route endpoint
        print(f"3. Verifying email with token: {token[:12]}...")
        verify_resp = session.post(f"{BASE_URL}/api/auth/verify-email", json={"token": token})
        print(f"   Verification response: {verify_resp.status_code}, {verify_resp.json()}")
        assert verify_resp.status_code == 200
        
        # 4. Confirm in DB that is_verified is now True and token is cleared
        cur.execute("SELECT is_verified, verification_token FROM users WHERE email = %s", (email,))
        row_after = cur.fetchone()
        if row_after:
            is_verified_after, token_after = row_after
            print(f"4. DB State After Verification: is_verified={is_verified_after}, token={token_after}")
            assert is_verified_after is True
            assert token_after is None
    conn.close()
    
    # 5. Check /auth/me to verify user profile reflects verified status
    me_resp = session.get(f"{BASE_URL}/api/auth/me")
    print(f"5. /api/auth/me response: {me_resp.status_code}")
    me_data = me_resp.json()
    print(f"   is_verified: {me_data.get('is_verified')}, is_email_verified: {me_data.get('is_email_verified')}")
    assert me_data.get('is_verified') is True
    assert me_data.get('is_email_verified') is True
    
    # 6. Test Kitchen Owner Portal access
    dash_resp = session.get(f"{BASE_URL}/api/v1/kitchen/dashboard")
    print(f"6. /api/v1/kitchen/dashboard status: {dash_resp.status_code}")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    print(f"   Kitchen name: {dash_data.get('kitchen_name')}")
    
    # 7. Test RBAC isolation: Kitchen Owner accessing Admin endpoint must be blocked (403)
    admin_resp = session.get(f"{BASE_URL}/api/v1/test-rbac/admin")
    print(f"7. Admin access status: {admin_resp.status_code}")
    assert admin_resp.status_code == 403
    
    print("\nALL VERIFICATION STEPS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_full_kitchen_lifecycle()
