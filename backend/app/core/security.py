"""
Security utilities: password hashing with bcrypt, session token generation,
and cryptographically secure verification tokens.
"""
import secrets
import bcrypt


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# Alias to maintain backwards and cross-module compatibility
hash_password = get_password_hash


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def generate_session_id() -> str:
    """Generate a cryptographically secure 256-bit session token."""
    return secrets.token_hex(32)


def generate_verification_token(user_id: str = None, email: str = None) -> str:
    """Generate a URL-safe, cryptographically signed, timestamped token for email verification."""
    from itsdangerous import URLSafeTimedSerializer
    from backend.app.core.config import settings

    serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="email-verification")
    payload = {
        "user_id": str(user_id) if user_id else "",
        "email": str(email).lower() if email else "",
        "nonce": secrets.token_hex(16),
    }
    return serializer.dumps(payload)


def verify_verification_token(token: str, max_age: int = 86400) -> tuple:
    """
    Validates a timed signed verification token.
    Returns (payload_dict, error_string_or_None).
    error_string can be 'expired', 'invalid', or None.
    """
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
    from backend.app.core.config import settings

    serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="email-verification")
    try:
        data = serializer.loads(token, max_age=max_age)
        return data, None
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    except Exception:
        return None, "invalid"
