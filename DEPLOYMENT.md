# Local Deployment Guide - KitchenVerse

This guide provides exact steps to deploy and run the platform locally.

---

## PREREQUISITES

### Required Software

1. **Python 3.11 or higher**
   - Download: https://www.python.org/downloads/
   - Verify: `python --version` (should show 3.11.x or higher)

2. **PostgreSQL 15 or higher**
   - Download: https://www.postgresql.org/download/
   - Verify: `psql --version` (should show 15.x or higher)

3. **Node.js 18 or higher**
   - Download: https://nodejs.org/
   - Verify: `node --version` (should show v18.x or higher)
   - Verify: `npm --version` (should show 9.x or higher)

4. **Git** (optional, for version control)
   - Download: https://git-scm.com/downloads

---

## STEP 1: DATABASE SETUP

### 1.1 Install and Start PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql-15
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
- Run the installer from postgresql.org
- Follow the wizard, set a password for the `postgres` user

### 1.2 Create Database and User

```bash
# Connect to PostgreSQL as superuser
psql -U postgres

# In the PostgreSQL prompt:
CREATE USER cloud_kitchen_user WITH PASSWORD 'your_secure_password_here';
CREATE DATABASE cloud_kitchen OWNER cloud_kitchen_user;
GRANT ALL PRIVILEGES ON DATABASE cloud_kitchen TO cloud_kitchen_user;
\q
```

**Verify:**
```bash
psql -U cloud_kitchen_user -d cloud_kitchen -h localhost
# Should connect successfully
\q
```

---

## STEP 2: BACKEND SETUP

### 2.1 Navigate to Backend Directory

```bash
cd backend
```

### 2.2 Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# You should see (venv) in your terminal prompt
```

### 2.3 Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- SQLAlchemy (ORM)
- Alembic (database migrations)
- Pydantic (validation)
- python-jose (JWT tokens)
- passlib + bcrypt (password hashing)
- pytest (testing)
- And other dependencies

### 2.4 Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual values
nano .env  # or use any text editor
```

**Required changes in `.env`:**

```env
# Database - UPDATE THESE VALUES
DATABASE_URL=postgresql+asyncpg://cloud_kitchen_user:your_secure_password_here@localhost:5432/cloud_kitchen
DATABASE_URL_SYNC=postgresql://cloud_kitchen_user:your_secure_password_here@localhost:5432/cloud_kitchen

# JWT Secret - GENERATE A NEW ONE
# Run: python -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_SECRET=paste_your_generated_secret_here

# Keep these as-is for development:
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
EMAIL_PROVIDER=console
EMAIL_FROM=noreply@cloudkitchen.example.com
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
APP_NAME=KitchenVerse
APP_ENV=development
DEBUG=true
```

**Generate JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Copy the output and paste it as JWT_SECRET in .env
```

### 2.5 Run Database Migrations

```bash
# Make sure you're in the backend directory with venv activated
alembic upgrade head
```

**Verify tables were created:**
```bash
psql -U cloud_kitchen_user -d cloud_kitchen -h localhost

# In PostgreSQL prompt:
\dt
# Should show: users, customer_profiles, kitchen_profiles, addresses, etc.

\d users
# Should show all columns

\q
```

### 2.6 Start Backend Server

```bash
# In backend directory with venv activated
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Verify backend is running:**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","app":"KitchenVerse","environment":"development"}
```

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## STEP 3: FRONTEND SETUP

### 3.1 Open New Terminal

Keep the backend running in the first terminal. Open a new terminal window.

### 3.2 Navigate to Project Root

```bash
cd /path/to/your/project
# (the directory containing this README)
```

### 3.3 Install Node Dependencies

```bash
npm install
```

This installs:
- React 18
- React Router
- TypeScript
- Tailwind CSS
- Vite (build tool)
- And other dependencies

### 3.4 Configure Frontend Environment

```bash
# Create .env file for frontend
cat > .env << 'EOF'
VITE_API_URL=http://localhost:8000
EOF
```

### 3.5 Start Frontend Development Server

```bash
npm run dev
```

**Expected output:**
```
  VITE v6.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

**Open in browser:** http://localhost:3000

---

## STEP 4: VERIFICATION

### 4.1 Test User Registration

1. Open http://localhost:3000 in your browser
2. Click "Create Account" or navigate to http://localhost:3000/register
3. Fill in the registration form:
   - First Name: Test
   - Last Name: User
   - Email: test@example.com
   - Password: TestPass123! (must include uppercase, lowercase, digit, special char)
   - Role: Customer
4. Click "Create Account"
5. You should see: "Registration successful. Email service not configured..."

**Verify in database:**
```bash
psql -U cloud_kitchen_user -d cloud_kitchen -h localhost

SELECT id, email, first_name, last_name, role, status, is_email_verified 
FROM users WHERE email = 'test@example.com';

# Should show the user with status = 'PENDING_VERIFICATION'

\q
```

### 4.2 Test Login

1. Navigate to http://localhost:3000/login
2. Enter:
   - Email: test@example.com
   - Password: TestPass123!
3. Click "Sign In"
4. You should be redirected to /profile page
5. You should see your user information

**Verify token was created:**
- Open browser DevTools (F12)
- Go to Application tab (Chrome) or Storage tab (Firefox)
- Check Local Storage for `auth_tokens`
- Should contain `access_token` and `refresh_token`

### 4.3 Test Protected Routes

1. While logged in, navigate to http://localhost:3000/profile
2. Should show your profile information
3. **Note:** Since email is not verified, you'll see a yellow warning banner at the top
4. Log out
5. Try to access http://localhost:3000/profile again
6. Should redirect to /login

**Authentication Flow Notes:**
- Unverified users CAN log in and view their profile
- The profile page shows a yellow warning banner for unverified users
- In Phase 2, certain actions (placing orders, etc.) will require email verification
- The backend `get_current_active_user` dependency enforces verification for protected actions

### 4.4 Test Password Validation

Try registering with weak passwords:
- `short` → Should fail (too short)
- `alllowercase1!` → Should fail (no uppercase)
- `ALLUPPERCASE1!` → Should fail (no lowercase)
- `NoDigitsHere!` → Should fail (no digit)
- `NoSpecial123` → Should fail (no special character)
- `ValidPass123!` → Should succeed

---

## STEP 5: RUNNING TESTS

### 5.1 Backend Tests

```bash
# In backend directory with venv activated
pytest tests/ -v
```

**Expected output:**
```
tests/test_auth.py::TestRegistration::test_register_customer_success PASSED
tests/test_auth.py::TestRegistration::test_register_duplicate_email PASSED
...
======================== 30 passed in x.xx s =========================
```

### 5.2 Frontend Type Check

```bash
# In project root
npm run typecheck
```

**Expected output:**
```
> tsc --noEmit
(no errors)
```

### 5.3 Frontend Production Build

```bash
npm run build
```

**Expected output:**
```
vite v6.x.x building for production...
✓ 43 modules transformed.
dist/index.html                   x.xx kB
dist/assets/index-xxxxx.css      xx.xx kB
dist/assets/index-xxxxx.js     xxx.xx kB
✓ built in x.xx s
```

---

## STEP 6: EMAIL CONFIGURATION (OPTIONAL)

For development, email is logged to console. For production, configure SMTP or SendGrid.

### Option A: SMTP (Gmail example)

Edit `.env`:
```env
EMAIL_PROVIDER=smtp
EMAIL_FROM=your-email@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

**Note:** For Gmail, you need to:
1. Enable 2-factor authentication
2. Generate an App Password: https://myaccount.google.com/apppasswords

### Option B: SendGrid

1. Sign up at https://sendgrid.com
2. Get API key
3. Edit `.env`:
```env
EMAIL_PROVIDER=sendgrid
EMAIL_FROM=verified-sender@yourdomain.com
SENDGRID_API_KEY=SG.xxxxx
```

---

## TROUBLESHOOTING

### Backend won't start

**Error: "could not connect to server"**
- PostgreSQL not running: `brew services start postgresql@15` (macOS) or `sudo systemctl start postgresql` (Linux)
- Wrong credentials: Check `.env` DATABASE_URL

**Error: "relation 'users' does not exist"**
- Run migrations: `alembic upgrade head`

**Error: "No module named 'fastapi'"**
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

### Frontend won't start

**Error: "Cannot find module"**
- Delete node_modules and reinstall:
  ```bash
  rm -rf node_modules package-lock.json
  npm install
  ```

**Error: "EADDRINUSE: address already in use"**
- Port 3000 is in use. Kill the process or change port in `vite.config.js`

**API calls fail with CORS error**
- Backend not running: Start backend on port 8000
- Check CORS_ORIGINS in backend `.env` includes `http://localhost:3000`

### Database issues

**Cannot connect to PostgreSQL**
- Check PostgreSQL is running
- Verify credentials in `.env`
- Check database exists: `psql -U postgres -c "\l"`

**Migration fails**
- Drop and recreate database:
  ```bash
  psql -U postgres
  DROP DATABASE cloud_kitchen;
  CREATE DATABASE cloud_kitchen OWNER cloud_kitchen_user;
  \q
  alembic upgrade head
  ```

---

## DEFAULT URLS

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

---

## STOPPING SERVICES

**Backend:** Press `Ctrl+C` in the backend terminal

**Frontend:** Press `Ctrl+C` in the frontend terminal

**PostgreSQL:**
- macOS: `brew services stop postgresql@15`
- Linux: `sudo systemctl stop postgresql`

---

## NEXT STEPS

Once everything is running:

1. **Create admin user** (manually in database for now):
   ```bash
   psql -U cloud_kitchen_user -d cloud_kitchen -h localhost
   ```
   ```sql
   -- Generate password hash in Python first:
   -- python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('AdminPass123!'))"
   
   INSERT INTO users (id, email, hashed_password, first_name, last_name, role, status, is_email_verified)
   VALUES (
     gen_random_uuid(),
     'admin@example.com',
     '$2b$12$...', -- paste hash from Python
     'Admin',
     'User',
     'ADMIN',
     'ACTIVE',
     true
   );
   ```

2. **Configure email provider** for production use

3. **Proceed to Phase 2** when ready (menu management, orders, etc.)

---

## SUPPORT

If you encounter issues not covered here:

1. Check the logs (terminal output)
2. Verify all prerequisites are installed and correct versions
3. Ensure `.env` files are configured correctly
4. Check database connectivity
5. Review the error messages carefully

---

## QUICK START CHECKLIST

- [ ] Python 3.11+ installed
- [ ] PostgreSQL 15+ installed and running
- [ ] Node.js 18+ installed
- [ ] Database `cloud_kitchen` created
- [ ] Backend `.env` configured with database credentials
- [ ] JWT secret generated and added to `.env`
- [ ] Backend dependencies installed (`pip install -r requirements.txt`)
- [ ] Database migrations run (`alembic upgrade head`)
- [ ] Backend server started (`uvicorn app.main:app --reload`)
- [ ] Frontend dependencies installed (`npm install`)
- [ ] Frontend `.env` configured
- [ ] Frontend dev server started (`npm run dev`)
- [ ] Can register a user
- [ ] Can login
- [ ] Can access protected routes
- [ ] Backend tests pass (`pytest tests/ -v`)
- [ ] Frontend builds successfully (`npm run build`)

---

**Last Updated:** Phase 1 Complete
**Status:** Ready for local deployment
