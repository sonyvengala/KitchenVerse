"""
Security & Test Isolation Regression Suite.
Guarantees that:
1. Automated tests and scripts CANNOT mutate existing real users' passwords, roles, verification, or credentials.
2. Real user accounts cannot be deleted by tests or scripts.
3. Isolated test users (e.g. test_*@example.com) can be freely created, modified, and cleaned up.
4. scripts/live_test_images.py contains zero references to real accounts.
"""
import pytest
from sqlalchemy.orm import Session
from backend.app.core.security import get_password_hash
from backend.app.models.enums import UserRole
from backend.app.models.user import User


def test_safety_guard_blocks_real_user_password_mutation(db_session: Session):
    """Attempting to mutate a protected real user's password in tests must raise PermissionError."""
    # Seed a simulated protected real user record in the isolated in-memory test DB
    protected_user = User(
        email="sonyvengala7@gmail.com",
        hashed_password=get_password_hash("OriginalPassword123!"),
        full_name="Vengala Sony",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    # Adding a new record is allowed (seeding), but modifying an existing record is guarded
    db_session.add(protected_user)
    db_session.commit()

    # Attempt to tamper with password
    protected_user.hashed_password = get_password_hash("KitchenPass123!")
    
    with pytest.raises(PermissionError) as exc_info:
        db_session.commit()

    assert "TEST ISOLATION VIOLATION" in str(exc_info.value)
    assert "sonyvengala7@gmail.com" in str(exc_info.value)
    db_session.rollback()


def test_safety_guard_blocks_real_user_role_tampering(db_session: Session):
    """Attempting to mutate a protected real user's role in tests must raise PermissionError."""
    protected_user = User(
        email="sonyvengala04@gmail.com",
        hashed_password=get_password_hash("CustomerPass123!"),
        full_name="Vengala Sony Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(protected_user)
    db_session.commit()

    # Attempt to tamper with role or verification
    protected_user.role = UserRole.ADMIN
    with pytest.raises(PermissionError) as exc_info:
        db_session.commit()

    assert "TEST ISOLATION VIOLATION" in str(exc_info.value)
    db_session.rollback()


def test_safety_guard_blocks_real_user_deletion(db_session: Session):
    """Attempting to delete a protected real user in tests must raise PermissionError."""
    protected_user = User(
        email="sonyvengala7@gmail.com",
        hashed_password=get_password_hash("SecretPass123!"),
        full_name="Vengala Sony",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(protected_user)
    db_session.commit()

    # Attempt to delete
    db_session.delete(protected_user)
    with pytest.raises(PermissionError) as exc_info:
        db_session.commit()

    assert "TEST ISOLATION VIOLATION" in str(exc_info.value)
    assert "delete" in str(exc_info.value).lower()
    db_session.rollback()


def test_isolated_test_users_operate_normally(db_session: Session):
    """Isolated test accounts (*@example.com, test_*) can be created and updated normally."""
    test_user = User(
        email="test_synthetic_chef@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Synthetic Test Chef",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=False,
    )
    db_session.add(test_user)
    db_session.commit()

    # Test user verification update succeeds without isolation violation
    test_user.is_verified = True
    db_session.commit()
    db_session.refresh(test_user)
    assert test_user.is_verified is True


def test_no_real_accounts_in_live_scripts():
    """Ensure scripts/live_test_images.py contains zero references to real account emails or names."""
    with open("scripts/live_test_images.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "sonyvengala" not in content.lower(), "Found real account email/username in scripts/live_test_images.py"
    assert "kitchenpass123!" not in content.lower(), "Found real account password in scripts/live_test_images.py"


def test_password_reset_flow_on_isolated_synthetic_account(db_session: Session):
    """
    Verifies that the legitimate password-reset flow operates properly on an isolated test account:
    - Reset request generates valid token
    - Token allows setting new password
    - Old password stops working
    - New password succeeds
    - Token cannot be reused
    """
    import uuid
    from fastapi import HTTPException
    from backend.app.services.auth_service import AuthService

    suffix = uuid.uuid4().hex[:6]
    email = f"test_pwd_reset_{suffix}@example.com"
    old_pwd = "OldPassword123!"
    new_pwd = "NewSecurePassword456!"

    user = User(
        email=email,
        hashed_password=get_password_hash(old_pwd),
        full_name="Password Test User",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    # 1. Old password works initially
    auth_user = AuthService.authenticate_user(db_session, email, old_pwd)
    assert auth_user.id == user.id

    # 2. Request password reset
    reset_token = AuthService.request_password_reset(db_session, email)
    assert reset_token is not None

    # 3. Perform password reset with token
    updated_user = AuthService.reset_password(db_session, reset_token, new_pwd)
    assert updated_user.id == user.id

    # 4. Old password stops working (401 Unauthorized)
    with pytest.raises(HTTPException) as exc_old:
        AuthService.authenticate_user(db_session, email, old_pwd)
    assert exc_old.value.status_code == 401

    # 5. New password works
    reauthed_user = AuthService.authenticate_user(db_session, email, new_pwd)
    assert reauthed_user.id == user.id

    # 6. Reset token cannot be reused
    with pytest.raises(HTTPException) as exc_reuse:
        AuthService.reset_password(db_session, reset_token, "AnotherPass789!")
    assert exc_reuse.value.status_code == 400
    assert "invalid" in exc_reuse.value.detail.lower()


def test_email_verification_flow_on_isolated_synthetic_account(db_session: Session):
    """Verifies that email verification flow operates properly on an isolated test account."""
    import uuid
    from backend.app.services.auth_service import AuthService
    from backend.app.core.security import generate_verification_token

    suffix = uuid.uuid4().hex[:6]
    email = f"test_verify_{suffix}@example.com"

    user = User(
        email=email,
        hashed_password=get_password_hash("SecretPass123!"),
        full_name="Verify Test User",
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    db_session.commit()

    token = generate_verification_token(user_id=user.id, email=email)
    user.verification_token = token
    db_session.commit()

    # Verify email
    verified_user = AuthService.verify_email(db_session, token)
    assert verified_user.is_verified is True
    assert verified_user.verification_token is None
