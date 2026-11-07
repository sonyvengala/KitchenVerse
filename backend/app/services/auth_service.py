"""
Authentication and User Service.
Enforces business rules: password hashing, email uniqueness, verification,
and real session invalidation on logout and password reset.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.security import (
    get_password_hash,
    verify_password,
    generate_verification_token,
    verify_verification_token,
)
from backend.app.core.session import (
    create_user_session,
    revoke_session,
    revoke_all_user_sessions,
)
from backend.app.models.enums import UserRole
from backend.app.models.user import User, CustomerProfile, KitchenProfile, UserSession
from backend.app.models.platform import Notification
from backend.app.schemas.auth import (
    CustomerRegisterRequest,
    KitchenRegisterRequest,
)
import os
import hashlib
import time
from backend.app.core.config import settings
from backend.app.core.email import email_service

_resend_cooldowns = {}


class AuthService:
    @staticmethod
    def _validate_kitchen_license_input(req) -> None:
        lic_num = getattr(req, "fssai_license_number", None) or getattr(req, "business_license", None)
        if not lic_num:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FSSAI Food License document and registration number are required for new kitchen-owner applications."
            )
        file_token = getattr(req, "fssai_file_token", None)
        doc_b64 = getattr(req, "fssai_document_data", None)
        if not file_token and not doc_b64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FSSAI Food License certificate document is required for kitchen-owner registration."
            )

    @staticmethod
    def _setup_kitchen_license_on_registration(db: Session, kitchen_profile: KitchenProfile, req) -> None:
        from datetime import timedelta
        from backend.app.services.fssai_service import (
            FssaiService,
            SECURE_LICENSES_DIR,
            utc_now,
        )

        AuthService._validate_kitchen_license_input(req)
        lic_num = getattr(req, "fssai_license_number", None) or getattr(req, "business_license", None)

        b_name = getattr(req, "fssai_business_name", None) or kitchen_profile.kitchen_name
        exp_date_str = getattr(req, "fssai_expiry_date", None)
        if exp_date_str:
            exp_dt = FssaiService.parse_date(exp_date_str)
            if not exp_dt:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid FSSAI expiry date format.")
        else:
            exp_dt = utc_now() + timedelta(days=365)

        file_token = getattr(req, "fssai_file_token", None)
        doc_b64 = getattr(req, "fssai_document_data", None)
        file_meta = None

        if doc_b64:
            import base64
            doc_mime = "application/pdf"
            clean_b64 = doc_b64
            if "," in doc_b64:
                header, clean_b64 = doc_b64.split(",", 1)
                if "pdf" in header.lower():
                    doc_mime = "application/pdf"
                elif "png" in header.lower():
                    doc_mime = "image/png"
                else:
                    doc_mime = "image/jpeg"
            raw_bytes = base64.b64decode(clean_b64)
            orig_fn = getattr(req, "fssai_filename", None) or "fssai_license.pdf"
            file_meta = FssaiService.save_secure_license_file(raw_bytes, orig_fn, doc_mime)
        elif file_token:
            target_path = os.path.join(SECURE_LICENSES_DIR, os.path.basename(file_token))
            if os.path.exists(target_path):
                ext = os.path.splitext(target_path)[1].lower()
                mime = "application/pdf" if ext == ".pdf" else ("image/png" if ext == ".png" else "image/jpeg")
                fsize = os.path.getsize(target_path)
                with open(target_path, "rb") as f:
                    fcontent = f.read()
                file_hash = hashlib.sha256(fcontent).hexdigest()
                file_meta = {
                    "file_path": target_path,
                    "filename": os.path.basename(target_path),
                    "original_filename": getattr(req, "fssai_filename", None) or os.path.basename(target_path),
                    "file_size": fsize,
                    "mime_type": mime,
                    "file_hash": file_hash,
                }

        if not file_meta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FSSAI Food License certificate document is required for kitchen-owner registration."
            )

        FssaiService.create_or_update_license(
            db=db,
            kitchen_id=kitchen_profile.id,
            license_number=lic_num,
            business_name=b_name,
            expiry_date=exp_dt,
            issue_date=utc_now() - timedelta(days=30),
            file_meta=file_meta,
            document_type="INITIAL",
            allow_test_identifiers=True,
        )

    @staticmethod
    def register_customer(db: Session, req: CustomerRegisterRequest) -> Tuple[User, str]:
        """
        Register a new customer.
        Strictly sets role=UserRole.CUSTOMER server-side.
        """
        # Check if email is already taken
        existing_user = db.query(User).filter(User.email == req.email.lower()).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists.",
            )

        verification_token = generate_verification_token(email=req.email.lower())
        hashed_pwd = get_password_hash(req.password)

        # Allow KITCHEN_OWNER selection, but strictly forbid ADMIN elevation
        role = UserRole.CUSTOMER
        if req.role == "KITCHEN_OWNER" or req.role == UserRole.KITCHEN_OWNER:
            role = UserRole.KITCHEN_OWNER
            AuthService._validate_kitchen_license_input(req)

        full_name = req.full_name
        if not full_name and (getattr(req, "first_name", None) or getattr(req, "last_name", None)):
            full_name = f"{getattr(req, 'first_name', '') or ''} {getattr(req, 'last_name', '') or ''}".strip()
        if not full_name:
            full_name = req.email.split("@")[0].capitalize()

        phone_num = getattr(req, "phone_number", None) or getattr(req, "phone", None)

        new_user = User(
            email=req.email.lower(),
            hashed_password=hashed_pwd,
            full_name=full_name,
            phone_number=phone_num,
            role=role,
            is_active=True,
            is_verified=False,
            verification_token=verification_token,
        )
        db.add(new_user)
        db.flush()

        if role == UserRole.KITCHEN_OWNER:
            k_name = getattr(req, "kitchen_name", None) or f"{full_name}'s Kitchen"
            k_addr = getattr(req, "address", None) or "Central Cloud Kitchen Facility"
            k_city = getattr(req, "city", None) or "Bangalore"
            k_desc = getattr(req, "description", None) or f"Cloud Kitchen managed by {full_name}"

            kitchen_profile = KitchenProfile(
                user_id=new_user.id,
                kitchen_name=k_name,
                center_id=1,
                address=k_addr,
                city=k_city,
                description=k_desc,
                phone=phone_num,
                is_open=False,
                is_approved=False,
                approval_status="EMAIL_UNVERIFIED",
                rating=5.0,
                rating_count=0,
            )
            db.add(kitchen_profile)
            db.flush()
            AuthService._setup_kitchen_license_on_registration(db, kitchen_profile, req)

            # Create Welcome Notification
            notification = Notification(
                user_id=new_user.id,
                title="Kitchen Account Created",
                message=f"Your kitchen '{k_name}' registration is pending admin approval. You will receive an update once reviewed.",
                event_type="NOTIFICATION_CREATED",
            )
            db.add(notification)

            # Notify platform administrators about new onboarding request
            from backend.app.services.notification_service import NotificationService
            NotificationService.notify_admins(
                db=db,
                event_type="KITCHEN_REGISTRATION_REQUEST",
                title="New Kitchen Registration Request",
                message=f"Kitchen '{k_name}' was registered by {new_user.full_name} and is awaiting verification & approval.",
                metadata={"entity_type": "kitchen", "entity_id": kitchen_profile.id, "link": "/admin/kitchen-owners"}
            )
        else:
            customer_profile = CustomerProfile(
                user_id=new_user.id,
                dietary_preferences=getattr(req, "dietary_preferences", None),
            )
            db.add(customer_profile)

            # Create Welcome Notification
            notification = Notification(
                user_id=new_user.id,
                title="Welcome to KitchenVerse!",
                message="Your customer account has been created. Please verify your email to unlock all features.",
                event_type="NOTIFICATION_CREATED",
            )
            db.add(notification)

        db.commit()
        db.refresh(new_user)
        return new_user, verification_token

    @staticmethod
    def register_kitchen(db: Session, req: KitchenRegisterRequest) -> Tuple[User, str]:
        """
        Register a new kitchen owner and kitchen profile.
        Strictly sets role=UserRole.KITCHEN_OWNER server-side.
        """
        existing_user = db.query(User).filter(User.email == req.email.lower()).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists.",
            )

        AuthService._validate_kitchen_license_input(req)

        verification_token = generate_verification_token(email=req.email.lower())
        hashed_pwd = get_password_hash(req.password)

        new_user = User(
            email=req.email.lower(),
            hashed_password=hashed_pwd,
            full_name=req.full_name,
            phone_number=req.phone_number,
            role=UserRole.KITCHEN_OWNER,  # Guaranteed server-side
            is_active=True,
            is_verified=False,
            verification_token=verification_token,
        )
        db.add(new_user)
        db.flush()

        kitchen_profile = KitchenProfile(
            user_id=new_user.id,
            kitchen_name=req.kitchen_name,
            center_id=req.center_id or 1,
            description=req.description,
            address=req.address,
            city=req.city,
            phone=req.phone or req.phone_number,
            is_open=False,
            is_approved=False,
            approval_status="EMAIL_UNVERIFIED",
            rating=5.0,
            rating_count=1,
        )
        db.add(kitchen_profile)
        db.flush()
        AuthService._setup_kitchen_license_on_registration(db, kitchen_profile, req)

        notification = Notification(
            user_id=new_user.id,
            title="Kitchen Registered",
            message=f"Your kitchen '{req.kitchen_name}' is registered. Configure your ingredients and menu to begin accepting orders.",
            event_type="NOTIFICATION_CREATED",
        )
        db.add(notification)

        # Notify platform administrators about new onboarding request
        from backend.app.services.notification_service import NotificationService
        NotificationService.notify_admins(
            db=db,
            event_type="KITCHEN_REGISTRATION_REQUEST",
            title="New Kitchen Registration Request",
            message=f"Kitchen '{req.kitchen_name}' was registered by {new_user.full_name} and is awaiting verification & approval.",
            metadata={"entity_type": "kitchen", "entity_id": kitchen_profile.id, "link": "/admin/kitchen-owners"}
        )

        db.commit()
        db.refresh(new_user)
        return new_user, verification_token

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        """Authenticate user by email and password."""
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact support.",
            )
        return user

    @staticmethod
    def verify_email(db: Session, token: str) -> User:
        """Verify user email via verification token."""
        if not token or not str(token).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification link is invalid. No token provided.",
            )

        token = str(token).strip()
        data, err_type = verify_verification_token(token, max_age=86400)

        if err_type == "expired":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification link expired. Please request a new verification email.",
            )

        user = None
        if data and data.get("user_id"):
            user = db.query(User).filter(User.id == data["user_id"]).first()
        if not user and data and data.get("email"):
            user = db.query(User).filter(User.email == data["email"].lower()).first()

        # Fallback for opaque tokens or if signed token had no user found by ID/email
        if not user:
            user = db.query(User).filter(User.verification_token == token).first()

        if not user:
            # Check if this signed token belongs to an already-verified user
            if data and data.get("email"):
                u_by_email = db.query(User).filter(User.email == data["email"].lower()).first()
                if u_by_email and u_by_email.is_verified:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This verification link has already been used. Your email is already verified.",
                    )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification link is invalid. This link is broken or has already been used.",
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification link has already been used. Your email is already verified.",
            )

        if user.verification_token != token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification link has already been used or replaced. Please request a new verification email.",
            )

        db._allow_auth_service_update = True
        user.is_verified = True
        user.verification_token = None
        if user.kitchen_profile and user.kitchen_profile.approval_status == "EMAIL_UNVERIFIED":
            user.kitchen_profile.approval_status = "PENDING_APPROVAL"
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def resend_verification_email(
        db: Session,
        target_email: Optional[str] = None,
        authenticated_user: Optional[User] = None,
    ) -> dict:
        """
        Resend verification email to user.
        Enforces 60-second rate limit, generates fresh token, and returns provider delivery status.
        """
        email = None
        if authenticated_user and authenticated_user.email:
            email = authenticated_user.email.lower()
        elif target_email and target_email.strip():
            email = target_email.strip().lower()

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is required.",
            )

        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account registered with this email address.",
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already verified.",
            )

        # Rate limit check (60 seconds)
        now = time.time()
        last_sent = _resend_cooldowns.get(email, 0)
        cooldown_period = 60
        if now - last_sent < cooldown_period:
            remaining = int(cooldown_period - (now - last_sent))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting another verification email.",
            )

        fresh_token = generate_verification_token(user_id=user.id, email=user.email)
        db._allow_auth_service_update = True
        user.verification_token = fresh_token
        db.commit()
        db.refresh(user)

        _resend_cooldowns[email] = now

        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={fresh_token}"
        try:
            send_res = email_service.send_verification_email_sync(user.email, verification_url)
            provider = send_res.get("provider", settings.EMAIL_PROVIDER)
            if provider == "console":
                msg = f"Verification email logged to development console for {user.email}."
            else:
                msg = f"Verification email sent to {user.email}."
        except Exception as e:
            msg = f"Verification email queued (provider notice: {str(e)})"
            provider = settings.EMAIL_PROVIDER

        return {
            "status": "success",
            "message": msg,
            "provider": provider,
            "email": user.email,
            "cooldown_seconds": 60,
            "verification_token": fresh_token,
        }

    @staticmethod
    def request_password_reset(db: Session, email: str) -> Optional[str]:
        """Generate a password reset token with 1-hour expiration."""
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            # Silent return to prevent account enumeration
            return None

        reset_token = generate_verification_token()
        db._allow_auth_service_update = True
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()
        return reset_token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> User:
        """Reset password, clear tokens, and invalidate all existing active sessions."""
        now = datetime.now(timezone.utc)
        user = db.query(User).filter(User.password_reset_token == token).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token",
            )

        expiry = user.password_reset_expires
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if expiry < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token has expired",
            )

        db._allow_auth_service_update = True
        user.hashed_password = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.commit()

        # Invalidate all prior sessions for security
        revoke_all_user_sessions(db, user.id)
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
        """Change password with verification of current password."""
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        db._allow_auth_service_update = True
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        return True
