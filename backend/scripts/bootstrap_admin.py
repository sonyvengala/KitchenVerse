#!/usr/bin/env python3
"""
Admin Bootstrap Script - Creates the first ADMIN account.

SECURITY NOTES:
- This script should ONLY be run once to create the initial admin
- After creating the first admin, delete or secure this script
- The admin password is passed via environment variable (never hardcode)
- This script requires direct database access (not exposed via API)

USAGE:
    # Set the admin password as environment variable
    export ADMIN_PASSWORD='YourSecurePassword123!'
    
    # Run the script
    python scripts/bootstrap_admin.py

    # Or inline:
    ADMIN_PASSWORD='YourSecurePassword123!' python scripts/bootstrap_admin.py

PASSWORD REQUIREMENTS:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&* etc.)

AFTER RUNNING:
    1. Verify the admin can log in at /login
    2. Delete this script or move it to a secure location
    3. Never commit admin credentials to version control
"""

import asyncio
import os
import sys
import re
from getpass import getpass

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database.session import async_session_factory, init_db
from app.models.user import User, UserRole, UserStatus, CustomerProfile
from app.core.security import hash_password


def validate_password(password: str) -> list:
    """Validate password meets security requirements."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?\\|`~]', password):
        errors.append("Password must contain at least one special character")
    return errors


async def create_admin_user(email: str, password: str, first_name: str, last_name: str):
    """Create an admin user in the database."""
    
    # Validate password
    password_errors = validate_password(password)
    if password_errors:
        print("\n❌ Password validation failed:")
        for error in password_errors:
            print(f"   - {error}")
        return False
    
    # Initialize database
    try:
        await init_db()
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running")
        print("  2. DATABASE_URL is set in .env")
        print("  3. Database 'cloud_kitchen' exists")
        return False
    
    async with async_session_factory() as session:
        # Check if email already exists
        result = await session.execute(select(User).where(User.email == email.lower()))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"\n❌ User with email '{email}' already exists")
            print(f"   User ID: {existing_user.id}")
            print(f"   Current role: {existing_user.role.value}")
            
            if existing_user.role != UserRole.ADMIN:
                response = input("\n⚠️  Do you want to promote this user to ADMIN? (yes/no): ")
                if response.lower() == 'yes':
                    existing_user.role = UserRole.ADMIN
                    existing_user.status = UserStatus.ACTIVE
                    existing_user.is_email_verified = True
                    await session.commit()
                    print(f"\n✅ User promoted to ADMIN successfully")
                    print(f"   Email: {email}")
                    return True
                else:
                    print("\n❌ Operation cancelled")
                    return False
            else:
                print("\n⚠️  User is already an ADMIN")
                return False
        
        # Create new admin user
        admin_user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            is_email_verified=True,
        )
        session.add(admin_user)
        
        # Create customer profile (required by schema)
        profile = CustomerProfile(user_id=admin_user.id)
        session.add(profile)
        
        await session.commit()
        
        print("\n" + "="*60)
        print("✅ ADMIN USER CREATED SUCCESSFULLY")
        print("="*60)
        print(f"\n📧 Email:    {email}")
        print(f"👤 Name:     {first_name} {last_name}")
        print(f"🔑 Role:     ADMIN")
        print(f"🆔 User ID:  {admin_user.id}")
        print(f"\n🔐 The admin can now log in at: http://localhost:3000/login")
        print("\n⚠️  IMPORTANT SECURITY REMINDERS:")
        print("   1. Delete this script or move it to a secure location")
        print("   2. Never commit admin credentials to version control")
        print("   3. Use a strong, unique password")
        print("   4. Consider enabling 2FA in a future phase")
        print("="*60 + "\n")
        
        return True


async def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("🔐 ADMIN BOOTSTRAP SCRIPT")
    print("="*60)
    print("\nThis script creates the first ADMIN account for the platform.")
    print("It should only be run once during initial setup.\n")
    
    # Get admin credentials
    email = input("Admin email: ").strip()
    if not email:
        print("\n❌ Email is required")
        return
    
    # Validate email format
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        print("\n❌ Invalid email format")
        return
    
    first_name = input("First name: ").strip()
    if not first_name:
        print("\n❌ First name is required")
        return
    
    last_name = input("Last name: ").strip()
    if not last_name:
        print("\n❌ Last name is required")
        return
    
    # Get password from environment or interactive input
    password = os.environ.get('ADMIN_PASSWORD')
    if password:
        print("\n✓ Using password from ADMIN_PASSWORD environment variable")
    else:
        print("\n💡 Tip: You can set ADMIN_PASSWORD env var to avoid typing")
        password = getpass("Admin password: ")
        if not password:
            print("\n❌ Password is required")
            return
        
        # Confirm password
        password_confirm = getpass("Confirm password: ")
        if password != password_confirm:
            print("\n❌ Passwords do not match")
            return
    
    # Create the admin user
    success = await create_admin_user(email, password, first_name, last_name)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
