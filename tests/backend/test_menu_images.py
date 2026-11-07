"""
Comprehensive Backend Tests for Menu Image Management.
Covers manual image upload, validation, persistence, SSRF protection, removal, and authorization:
A. Local PNG upload succeeds.
B. Local JPG upload succeeds.
C. Local WEBP upload succeeds.
D. >5MB file rejected.
E. Non-image file rejected.
F. Image persists after refresh/restart.
G. Valid remote image URL works.
H. Invalid URL rejected.
I. Remote HTML URL rejected.
J. Remote URL timeout handled.
K. SSRF/private URL rejected.
L. Empty image file rejected.
M. Image deletion/removal clears image completely.
N. Customer sees saved image.
O. Other kitchen cannot modify image.
P. No fake image URL is stored.
"""
import io
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import httpx

from backend.app.core.security import get_password_hash
from backend.app.core.config import settings
from backend.app.models.enums import UserRole
from backend.app.models.user import User, KitchenProfile, CustomerProfile
from backend.app.models.menu import MenuItem
from backend.app.services.image_service import MenuImageService, is_ip_allowed, validate_magic_bytes

# Sample valid image byte payloads
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
JPG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00/ \x00\x00\x00\x00\x00\x810\x00\x00\x00\x00\x00"


def _setup_kitchen_and_item(db: Session, email: str = "kitchen_img@test.com", item_name: str = "Chicken Biryani"):
    user = User(
        email=email,
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Chef Image",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    profile = KitchenProfile(
        user_id=user.id,
        kitchen_name="Biryani Hub",
        address="123 Food Street",
        city="Hyderabad",
        is_open=True,
        is_approved=True,
    )
    db.add(profile)
    db.flush()

    item = MenuItem(
        kitchen_id=profile.id,
        name=item_name,
        description="Authentic royal chicken biryani with aromatics",
        category="Rice Bowl",
        cuisine="Indian",
        price=280.0,
        is_available=True,
        is_veg=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return user, profile, item


def _login(client: TestClient, email: str):
    client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})


# A. Local PNG upload succeeds
def test_local_png_upload_succeeds(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "png_user@test.com")
    _login(client, user.email)

    files = {"file": ("dish.png", io.BytesIO(PNG_BYTES), "image/png")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["image_source"] == "MANUAL"
    assert data["manual_image_url"].startswith("/uploads/menu_images/")
    assert data["image_url"] == data["manual_image_url"]


# B. Local JPG upload succeeds
def test_local_jpg_upload_succeeds(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "jpg_user@test.com")
    _login(client, user.email)

    files = {"file": ("dish.jpg", io.BytesIO(JPG_BYTES), "image/jpeg")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["image_source"] == "MANUAL"
    assert data["manual_image_url"].startswith("/uploads/menu_images/")


# C. Local WEBP upload succeeds
def test_local_webp_upload_succeeds(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "webp_user@test.com")
    _login(client, user.email)

    files = {"file": ("dish.webp", io.BytesIO(WEBP_BYTES), "image/webp")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["image_source"] == "MANUAL"
    assert data["manual_image_url"].startswith("/uploads/menu_images/")


# D. >5MB file rejected
def test_large_file_rejected(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "large_user@test.com")
    _login(client, user.email)

    huge_payload = PNG_BYTES + (b"0" * (5 * 1024 * 1024 + 10))
    files = {"file": ("huge.png", io.BytesIO(huge_payload), "image/png")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp.status_code == 400
    assert "5 MB" in resp.json()["detail"]


# E. Non-image file rejected
def test_non_image_file_rejected(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "exe_user@test.com")
    _login(client, user.email)

    # Executable / text disguised as png
    fake_png = b"MZ\x90\x00\x03\x00\x00\x00"
    files = {"file": ("malicious.png", io.BytesIO(fake_png), "image/png")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp.status_code == 400
    assert "Invalid image format" in resp.json()["detail"]


# F. Image persists after refresh/restart
def test_image_persists_in_db_and_disk(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "persist_user@test.com")
    _login(client, user.email)

    files = {"file": ("dish.png", io.BytesIO(PNG_BYTES), "image/png")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    saved_url = resp.json()["manual_image_url"]

    # Verify directly from database session refresh
    db_session.expire_all()
    reloaded_item = db_session.query(MenuItem).filter(MenuItem.id == item.id).first()
    assert reloaded_item.manual_image_url == saved_url
    assert reloaded_item.image_source == "MANUAL"

    # Verify physical file exists on disk
    rel_path = saved_url.replace("/uploads/", "")
    full_path = os.path.join(os.getcwd(), "data", "uploads", rel_path)
    assert os.path.isfile(full_path)


# G. Valid remote image URL works
def test_valid_remote_image_url_works(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "remote_user@test.com")
    _login(client, user.email)

    # Mock external HTTP request
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "image/jpeg"}
    mock_resp.content = JPG_BYTES

    with patch("backend.app.services.image_service.validate_url_host", return_value="example.com"):
        with patch.object(httpx.Client, "get", return_value=mock_resp):
            resp = client.post(
                f"/api/v1/kitchen/menu/{item.id}/upload-image",
                json={"image_url": "https://example.com/photos/biryani.jpg"}
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["image_source"] == "MANUAL"
            assert data["manual_image_url"].startswith("/uploads/menu_images/")


# H. Invalid URL rejected
def test_invalid_url_rejected(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "inv_url@test.com")
    _login(client, user.email)

    resp = client.post(
        f"/api/v1/kitchen/menu/{item.id}/upload-image",
        json={"image_url": "not-a-valid-url"}
    )
    assert resp.status_code == 400


# I. Remote HTML URL rejected
def test_remote_html_url_rejected(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "html_url@test.com")
    _login(client, user.email)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.content = b"<html><body>Not an image</body></html>"

    with patch("backend.app.services.image_service.validate_url_host", return_value="example.com"):
        with patch.object(httpx.Client, "get", return_value=mock_resp):
            resp = client.post(
                f"/api/v1/kitchen/menu/{item.id}/upload-image",
                json={"image_url": "https://example.com/not-an-image"}
            )
            assert resp.status_code == 400
            assert "Content-Type is 'text/html'" in resp.json()["detail"]


# J. Remote URL timeout handled
def test_remote_url_timeout_handled(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "timeout_user@test.com")
    _login(client, user.email)

    with patch("backend.app.services.image_service.validate_url_host", return_value="slow.com"):
        with patch.object(httpx.Client, "get", side_effect=httpx.TimeoutException("Timeout")):
            resp = client.post(
                f"/api/v1/kitchen/menu/{item.id}/upload-image",
                json={"image_url": "https://slow.com/dish.jpg"}
            )
            assert resp.status_code == 400
            assert "timed out" in resp.json()["detail"]


# K. SSRF/private URL rejected
def test_ssrf_private_url_rejected(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "ssrf_user@test.com")
    _login(client, user.email)

    for bad_url in [
        "http://localhost:8000/secret",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://192.168.1.1/router",
        "http://10.0.0.1/internal",
    ]:
        resp = client.post(
            f"/api/v1/kitchen/menu/{item.id}/upload-image",
            json={"image_url": bad_url}
        )
        assert resp.status_code == 400
        assert "private or local network addresses are not permitted" in resp.json()["detail"]


# L. Empty image upload rejected
def test_empty_image_upload_rejected(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "empty_file_user@test.com")
    _login(client, user.email)

    files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
    resp = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# M. Remove image works and clears image completely
def test_remove_image_clears_image(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "remove_user@test.com")
    _login(client, user.email)

    # 1. Set manual image
    files = {"file": ("dish.png", io.BytesIO(PNG_BYTES), "image/png")}
    resp1 = client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)
    assert resp1.status_code == 200
    assert resp1.json()["manual_image_url"] is not None

    # 2. Remove image
    resp2 = client.delete(f"/api/v1/kitchen/menu/{item.id}/image")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["manual_image_url"] is None
    assert data2["image_url"] is None
    assert data2["image_source"] == "MANUAL"

    # 3. Verify in database
    db_session.expire_all()
    reloaded = db_session.query(MenuItem).filter(MenuItem.id == item.id).first()
    assert reloaded.manual_image_url is None
    assert reloaded.image_url is None



# N. Customer sees saved image
def test_customer_sees_saved_image(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "cust_view_owner@test.com")
    _login(client, user.email)

    files = {"file": ("dish.png", io.BytesIO(PNG_BYTES), "image/png")}
    client.post(f"/api/v1/kitchen/menu/{item.id}/upload-image", files=files)

    # Customer queries public menu
    resp = client.get("/api/v1/customer/menu")
    assert resp.status_code == 200
    dishes = resp.json()
    saved_dish = next((d for d in dishes if d["id"] == item.id), None)
    assert saved_dish is not None
    assert saved_dish["image_url"].startswith("/uploads/menu_images/")
    assert saved_dish["image_source"] == "MANUAL"


# O. Other kitchen cannot modify image
def test_other_kitchen_cannot_modify_image(client: TestClient, db_session: Session):
    user1, profile1, item1 = _setup_kitchen_and_item(db_session, "owner1@test.com")
    user2, profile2, item2 = _setup_kitchen_and_item(db_session, "owner2@test.com")

    # Log in as owner 2 and attempt to upload to owner 1's dish
    _login(client, user2.email)
    files = {"file": ("dish.png", io.BytesIO(PNG_BYTES), "image/png")}
    resp = client.post(f"/api/v1/kitchen/menu/{item1.id}/upload-image", files=files)
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()


# P. No fake image URL is stored
def test_no_fake_image_url_stored(client: TestClient, db_session: Session):
    user, profile, item = _setup_kitchen_and_item(db_session, "fake_url_user@test.com")
    _login(client, user.email)

    # Sending invalid data or unsupported URL does not store placeholder fake URLs
    resp = client.post(
        f"/api/v1/kitchen/menu/{item.id}/upload-image",
        json={"image_url": "ftp://malicious.com/fake.jpg"}
    )
    assert resp.status_code == 400

    db_session.expire_all()
    reloaded = db_session.query(MenuItem).filter(MenuItem.id == item.id).first()
    assert reloaded.manual_image_url is None
    assert reloaded.image_url is None
