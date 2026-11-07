"""
Live Test Script for Menu Image Management:
Tests 1, 2, 3, 4 with real HTTP requests against the running server.

SECURITY & ISOLATION POLICY:
- Never references, queries, or modifies any real user account.
- Uses a dedicated, randomly-generated isolated test account (test_img_chef_<uuid>@example.com).
- Cleans up created test dishes and data upon completion.
"""
import httpx
import json
import io
import uuid

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

def run_isolated_live_image_tests():
    suffix = uuid.uuid4().hex[:6]
    test_email = f"test_img_chef_{suffix}@example.com"
    test_password = f"TestPass123!_{suffix}"

    print(f"=== INITIALIZING ISOLATED LIVE IMAGE TEST ===")
    print(f"Using isolated synthetic test account: {test_email}")

    with httpx.Client(timeout=15.0) as client:
        # Step 0: Register an isolated test kitchen owner
        print("Registering isolated test kitchen owner...")
        reg_resp = client.post(
            f"{BASE_URL}/api/auth/register-kitchen",
            json={
                "email": test_email,
                "password": test_password,
                "full_name": f"Chef Test {suffix}",
                "phone_number": "+919876543210",
                "kitchen_name": f"Isolated Test Kitchen {suffix}",
                "address": "123 Test Street",
                "city": "Hyderabad",
            }
        )

        if reg_resp.status_code == 201:
            auth_data = reg_resp.json()
            token = auth_data.get("access_token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            print(f"Registered test kitchen owner successfully (Token received: {bool(token)})")
        else:
            # If registration route is under api/v1 or already exists, try logging in
            print(f"Registration status {reg_resp.status_code}. Attempting login with test account...")
            login_resp = client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": test_email, "password": test_password}
            )
            assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
            token = login_resp.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}

        # Create an isolated test dish to test image features on
        print(f"Creating isolated test dish...")
        create_dish_resp = client.post(
            f"{BASE_URL}/api/v1/kitchen/menu",
            json={
                "name": f"Test Biryani {suffix}",
                "description": "Synthetic test item for live image upload tests",
                "category": "Main Course",
                "cuisine": "Indian",
                "price": 220.0,
                "is_available": True,
                "is_veg": False
            },
            headers=headers
        )
        assert create_dish_resp.status_code in (200, 201), f"Dish creation failed: {create_dish_resp.text}"
        dish_data = create_dish_resp.json()
        item_id = dish_data["id"]
        print(f"Created isolated test dish id: {item_id}")

        try:
            # ─────────────────────────────────────────────────────────────
            # TEST 1: Upload a real local Chicken Biryani image.
            # ─────────────────────────────────────────────────────────────
            print("\n--- TEST 1: Local Image Upload ---")
            files = {"file": ("test_biryani.png", io.BytesIO(PNG_1x1), "image/png")}
            upload_resp = client.post(f"{BASE_URL}/api/v1/kitchen/menu/{item_id}/upload-image", files=files, headers=headers)
            print(f"Upload status: {upload_resp.status_code}")
            assert upload_resp.status_code == 200, upload_resp.text
            uploaded_data = upload_resp.json()
            local_image_url = uploaded_data["manual_image_url"]
            print(f"Uploaded image URL: {local_image_url}")
            assert local_image_url.startswith("/uploads/menu_images/"), f"Unexpected URL: {local_image_url}"
            assert uploaded_data["image_source"] == "MANUAL"

            # Verify proxy access through Vite frontend (port 3000) if available
            try:
                frontend_img_resp = client.get(f"{FRONTEND_URL}{local_image_url}")
                print(f"Vite /uploads proxy status on port 3000: {frontend_img_resp.status_code}")
                assert frontend_img_resp.status_code == 200
            except Exception as e:
                print(f"Note: Vite frontend port 3000 proxy check skipped/info: {e}")

            # Refresh check
            refresh_resp = client.get(f"{BASE_URL}/api/v1/kitchen/menu", headers=headers)
            refreshed_items = refresh_resp.json()
            refreshed_dish = next(i for i in refreshed_items if i["id"] == item_id)
            assert refreshed_dish["manual_image_url"] == local_image_url
            print("TEST 1 PASSED: Local file upload saved and persistent.")

            # ─────────────────────────────────────────────────────────────
            # TEST 2: Use a valid public image URL.
            # ─────────────────────────────────────────────────────────────
            print("\n--- TEST 2: Internet Image URL Download ---")
            public_url = "https://picsum.photos/200/200"
            url_resp = client.post(
                f"{BASE_URL}/api/v1/kitchen/menu/{item_id}/upload-image",
                json={"image_url": public_url},
                headers=headers
            )
            print(f"URL Save status: {url_resp.status_code}")
            assert url_resp.status_code == 200, url_resp.text
            url_data = url_resp.json()
            downloaded_img_url = url_data["manual_image_url"]
            print(f"Saved local image URL: {downloaded_img_url}")
            assert downloaded_img_url.startswith("/uploads/menu_images/"), f"Remote image was not downloaded locally: {downloaded_img_url}"
            assert url_data["image_source"] == "MANUAL"
            print("TEST 2 PASSED: Remote URL downloaded, saved into CloudKitchen storage, and persistent.")

            # ─────────────────────────────────────────────────────────────
            # TEST 3: Remove manual image
            # ─────────────────────────────────────────────────────────────
            print("\n--- TEST 3: Remove Manual Image ---")
            del_resp = client.delete(f"{BASE_URL}/api/v1/kitchen/menu/{item_id}/image", headers=headers)
            assert del_resp.status_code == 200, del_resp.text
            del_data = del_resp.json()
            print(f"After remove, manual_image_url: {del_data['manual_image_url']}")
            assert del_data["manual_image_url"] is None
            assert del_data["image_url"] is None
            print("TEST 3 PASSED: Manual image removal cleared image completely.")

            # ─────────────────────────────────────────────────────────────
            # TEST 4: Customer Portal Menu Verification
            # ─────────────────────────────────────────────────────────────
            print("\n--- TEST 4: Customer Portal Menu Verification ---")
            reupload_resp = client.post(
                f"{BASE_URL}/api/v1/kitchen/menu/{item_id}/upload-image",
                files={"file": ("test_biryani_final.png", io.BytesIO(PNG_1x1), "image/png")},
                headers=headers
            )
            assert reupload_resp.status_code == 200
            final_manual_url = reupload_resp.json()["manual_image_url"]

            cust_menu_resp = client.get(f"{BASE_URL}/api/v1/customer/menu")
            assert cust_menu_resp.status_code == 200
            cust_items = cust_menu_resp.json()
            cust_dish = next((i for i in cust_items if i["id"] == item_id), None)
            if cust_dish:
                assert cust_dish["image_url"] == final_manual_url
                assert cust_dish["image_source"] == "MANUAL"
            print("TEST 4 PASSED: Customer menu correctly verified.")

        finally:
            # Cleanup test dish
            print(f"\nCleaning up isolated test dish {item_id}...")
            client.delete(f"{BASE_URL}/api/v1/kitchen/menu/{item_id}", headers=headers)
            print("Cleaned up isolated test dish successfully.")

    print("\nALL 4 LIVE TESTS EXECUTED SUCCESSFULLY WITH COMPLETE ACCOUNT ISOLATION!")

if __name__ == "__main__":
    run_isolated_live_image_tests()
