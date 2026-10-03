# Admin Account Setup Guide

This guide explains how to create the initial administrator account for the Cloud Kitchen Platform.

## Overview

The platform uses a role-based access control system with three roles:
- **CUSTOMER**: Regular users who can browse and order food
- **KITCHEN_OWNER**: Restaurant owners who manage their kitchens and menus
- **ADMIN**: Platform administrators with full system access

For security reasons, **ADMIN accounts cannot be created through the public registration form**. They must be created using the bootstrap script or manually in the database.

## Prerequisites

Before creating an admin account, ensure:

1. ✅ Backend is configured and database is running
2. ✅ Database migrations have been applied (`alembic upgrade head`)
3. ✅ Backend server is running (`uvicorn app.main:app --reload`)
4. ✅ You have access to the backend server terminal

## Method 1: Using the Bootstrap Script (Recommended)

### Step 1: Navigate to Backend Directory

```bash
cd backend
```

### Step 2: Activate Virtual Environment

```bash
# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

### Step 3: Run the Bootstrap Script

**Option A: Interactive Mode**
```bash
python scripts/bootstrap_admin.py
```

The script will prompt you for:
- Admin email address
- First name
- Last name
- Password (hidden input)
- Password confirmation

**Option B: Environment Variable Mode**
```bash
export ADMIN_PASSWORD='YourSecurePassword123!'
python scripts/bootstrap_admin.py
```

Then enter the other details when prompted.

### Step 4: Verify Admin Account

After the script completes successfully:

1. Open your browser to `http://localhost:3000/login`
2. Log in with the admin credentials you just created
3. You should be redirected to the admin dashboard (once implemented)

### Step 5: Security Cleanup

**IMPORTANT**: After creating the admin account:

```bash
# Delete the bootstrap script
rm scripts/bootstrap_admin.py

# Or move it to a secure location
mv scripts/bootstrap_admin.py ~/secure-scripts/

# Unset the environment variable if you used it
unset ADMIN_PASSWORD
```

## Method 2: Manual Database Creation

If you prefer to create the admin account directly in the database:

### Step 1: Generate Password Hash

```bash
cd backend
python -c "
from app.core.security import hash_password
password = input('Enter password: ')
print('Hash:', hash_password(password))
"
```

Copy the generated hash.

### Step 2: Insert Admin User

Connect to your PostgreSQL database:

```bash
psql -U cloud_kitchen -d cloud_kitchen
```

Execute the SQL (replace placeholders):

```sql
INSERT INTO users (
    id,
    email,
    hashed_password,
    first_name,
    last_name,
    role,
    status,
    is_email_verified,
    email_verified_at,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'admin@example.com',  -- Replace with actual email
    'YOUR_HASHED_PASSWORD',  -- Replace with hash from Step 1
    'Admin',  -- Replace with first name
    'User',  -- Replace with last name
    'ADMIN',
    'ACTIVE',
    true,
    NOW(),
    NOW(),
    NOW()
);
```

### Step 3: Verify

```sql
SELECT id, email, role, status FROM users WHERE role = 'ADMIN';
```

Exit psql:
```sql
\q
```

## Password Requirements

Admin passwords must meet the following security requirements:

- ✅ Minimum 8 characters
- ✅ At least one uppercase letter (A-Z)
- ✅ At least one lowercase letter (a-z)
- ✅ At least one digit (0-9)
- ✅ At least one special character (!@#$%^&*()_+-=[]{}|;:'",./<>?\\|`~)

**Example strong password**: `Admin@2024!Secure`

## Security Best Practices

### For Admin Accounts

1. **Use Strong Passwords**: Follow the password requirements above
2. **Unique Passwords**: Never reuse passwords from other services
3. **Limit Access**: Only create admin accounts for trusted personnel
4. **Regular Audits**: Periodically review admin accounts
5. **Secure Storage**: Never store admin credentials in plain text or commit to git

### For the Bootstrap Script

1. **Delete After Use**: Remove the script after creating the initial admin
2. **Never Commit**: Ensure the script is in `.gitignore`
3. **Secure Location**: If keeping the script, store it securely
4. **Environment Variables**: Use env vars for passwords, not command-line arguments

### For Production

1. **Enable 2FA**: Implement two-factor authentication (future feature)
2. **Audit Logging**: Track all admin actions
3. **IP Restrictions**: Consider restricting admin access by IP (future feature)
4. **Session Management**: Implement secure session handling
5. **Regular Rotation**: Rotate admin credentials periodically

## Troubleshooting

### Error: "Database initialization failed"

**Cause**: Database connection issue

**Solution**:
```bash
# Check if PostgreSQL is running
pg_isready

# Verify .env configuration
cat backend/.env | grep DATABASE_URL

# Test database connection
psql -U cloud_kitchen -d cloud_kitchen -c "SELECT 1;"
```

### Error: "User with email already exists"

**Cause**: An account with that email already exists

**Solution**:
- Use a different email address, OR
- The script will offer to promote the existing user to ADMIN

### Error: "Password validation failed"

**Cause**: Password doesn't meet security requirements

**Solution**:
- Ensure password meets all requirements listed above
- Use a password manager to generate a strong password

### Error: "ModuleNotFoundError"

**Cause**: Virtual environment not activated or dependencies not installed

**Solution**:
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Verification Checklist

After creating the admin account, verify:

- [ ] Admin can log in at `/login`
- [ ] Admin is redirected to admin dashboard (or `/profile` if dashboard not implemented)
- [ ] Admin role is correctly set in database
- [ ] Bootstrap script has been deleted or secured
- [ ] Admin credentials are stored securely (password manager)
- [ ] `.env` file is in `.gitignore`

## Adding More Admins

Once the first admin is created, additional admins can be created:

1. **Using the bootstrap script** (if not deleted)
2. **By the existing admin** (future feature: admin panel)
3. **Manually in the database** (using Method 2 above)

## Role Hierarchy

```
ADMIN
  ├─ Can manage all users
  ├─ Can manage all kitchens
  ├─ Can view all orders
  ├─ Can access system settings
  └─ Can promote/demote roles

KITCHEN_OWNER
  ├─ Can manage their own kitchen(s)
  ├─ Can manage their own menu items
  ├─ Can view their own orders
  └─ Cannot access admin features

CUSTOMER
  ├─ Can browse kitchens and menus
  ├─ Can place orders
  ├─ Can view their order history
  └─ Cannot manage kitchens
```

## Next Steps

After creating the admin account:

1. ✅ Log in as admin to verify access
2. ✅ Review the admin dashboard (Phase 2 feature)
3. ✅ Create kitchen owner accounts (if needed)
4. ✅ Configure platform settings (future feature)
5. ✅ Set up monitoring and logging (future feature)

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review backend logs: `tail -f backend/logs/app.log`
3. Verify database connection and migrations
4. Ensure all environment variables are set correctly

---

**Last Updated**: 2024
**Version**: 1.0
**Status**: Production Ready
