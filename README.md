# 🎓 CertVerify API — Forensic Certificate Verification Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon%20DB-blue)](https://neon.tech/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**CertVerify** is an enterprise-grade, AI-powered forensic credential verification engine designed for African secondary school credentials—specifically **WAEC** (West African Examinations Council) and **NECO** (National Examinations Council) certificates.

It combines **hybrid verification strategies**, **asynchronous background processing**, and a **scalable B2B API** to provide accurate, fast, and reliable certificate authenticity verification at scale.

---

## 🎯 Features Overview

### 🔍 **Hybrid Verification Strategy**
1. **Multimodal Computer Vision Forensics (60% weight)**
   - Visual inspection of security seals, fonts, layout markers, photograph embossing, and QR codes
   - Google Gemini 2.5 Flash multimodal AI for deep forensic analysis
   - PyMuPDF for PDF/image preprocessing and OCR
   - Forensic template matching against reference documents

2. **Cognitive Dynamic Knowledge Testing (40% weight)**
   - Generates 5 dynamic, subject-specific reasoning questions based on the candidate's transcript
   - Gemini AI generates questions tailored to the candidate's subjects
   - Strict evaluation of answers to verify genuine subject comprehension
   - Real-time assessment scoring

3. **Composite Trust Score**
   - Combines forensic score + knowledge assessment score
   - Returns verdicts: `AUTHENTIC`, `SUSPICIOUS`, or `HIGH_RISK`
   - Detailed forensic reports with flagged issues and tampering signs

### 💳 **Payment Integration**
- Squad payment gateway for certificate verification
- Support for Nigerian Naira (₦) transactions
- Webhook-based payment confirmation with HMAC verification
- Email notifications on payment confirmation

### 🔐 **User Authentication**
- Firebase Authentication with email/password login
- JWT tokens for secure API access
- Refresh token mechanism for extended sessions
- Password reset via email
- Custom claims for admin role management

### 🏢 **B2B API with Credit System**
- API keys for third-party organizations
- Atomic credit consumption per verification
- Credit top-up and balance tracking
- No-login verification endpoint for enterprise integration
- Rate limiting and audit logging

### 👨‍💼 **Admin Panel**
- Complete dashboard with platform statistics
- User management (list, view, disable, grant admin roles)
- Transaction oversight and filtering
- API key management and credit allocation
- Bulk email capabilities
- Verification report filtering and oversight
- System health monitoring

### ⚡ **Async Task Processing**
- Celery + Redis for background job processing
- Non-blocking certificate verification (202 Accepted pattern)
- Task polling API for async verification status
- Email notifications queued asynchronously
- Scalable background workers for high throughput
- Automatic task retry with exponential backoff

---

## 🏗️ Architecture Overview

### System Diagram
```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│   FastAPI   │◄───────►│  PostgreSQL  │         │ Redis Cloud  │
│  (Primary)  │         │  (Neon DB)   │         │   (Broker)   │
└─────────────┘         └──────────────┘         └──────────────┘
      │                        ▲                         ▲
      │                        │                         │
      ├──────────────────►     │                         │
      │                        │    ┌──────────────┐     │
      │                        └───►│   Celery     │────►
      │                             │   Workers   │
      │                             └──────────────┘
      │                                    │
      ├─────► Firebase Auth                │
      │                                    │
      ├─────► Google Gemini API ◄──────────┘
      │
      ├─────► Squad Payment Gateway
      │
      └─────► Gmail SMTP

```

### Project Structure
```
CertVerify-Backend/
├── .env                                  # Environment configuration (secrets)
├── .env.example                          # Example environment template
├── .gitignore                            # Git exclusion rules
├── LICENSE                               # MIT License
├── README.md                             # This file
├── requirements.txt                      # Python dependencies
├── run_tests.py                          # Test runner script
├── certverify-backend-firebase-adminsdk-*.json  # Firebase credentials
│
├── app/                                  # Main application package
│   ├── __init__.py
│   ├── main.py                           # FastAPI entrypoint & lifespan management
│   │
│   ├── core/                             # Core infrastructure & configuration
│   │   ├── __init__.py
│   │   ├── config.py                     # Pydantic Settings & environment loader
│   │   ├── database.py                   # SQLModel engine & session management
│   │   ├── firebase.py                   # Firebase Admin SDK initialization
│   │   ├── security.py                   # JWT/Bearer token verification
│   │   └── celery_app.py                 # Celery task configuration & initialization
│   │
│   ├── models/                           # SQLModel ORM Models (PostgreSQL tables)
│   │   ├── __init__.py
│   │   ├── transaction.py                # Transaction records & AI verification results
│   │   ├── api_key.py                    # B2B API keys & credit balances
│   │   └── task_result.py                # Async task status & results tracking
│   │
│   ├── schemas/                          # Pydantic DTOs & Validation Schemas
│   │   ├── __init__.py
│   │   ├── auth.py                       # Registration, login, refresh token schemas
│   │   ├── payment.py                    # Payment request/response DTOs
│   │   ├── verification.py               # Forensic AI pipeline schemas
│   │   ├── admin.py                      # Admin panel request/response schemas
│   │   └── b2b.py                        # B2B API key & credit schemas
│   │
│   ├── services/                         # Business Logic & External Integrations
│   │   ├── __init__.py
│   │   ├── auth_service.py               # Firebase Auth & Identity Toolkit ops
│   │   ├── document_analyser.py          # Gemini Vision multimodal analysis
│   │   ├── template_service.py           # WAEC/NECO forensic rules & penalties
│   │   ├── validator_service.py          # Deterministic forensic checks
│   │   ├── assessment_service.py         # Dynamic Q&A generation & evaluation
│   │   ├── payment_service.py            # Squad payment gateway integration
│   │   ├── b2b_service.py                # Atomic credit management for B2B
│   │   ├── email_service.py              # SMTP email sending (Gmail)
│   │   └── admin_service.py              # Admin panel business logic
│   │
│   ├── api/                              # HTTP Routers & Endpoints
│   │   ├── __init__.py
│   │   ├── router.py                     # Primary API aggregator & router composition
│   │   └── v1/                           # Version 1 API Endpoints
│   │       ├── __init__.py
│   │       ├── auth.py                   # /auth/* endpoints
│   │       ├── payments.py               # /payment/* endpoints
│   │       ├── verification.py           # /AI_pipeline/verify/* endpoints (async)
│   │       ├── b2b.py                    # /third_party/api/v1/* endpoints
│   │       └── admin.py                  # /admin/* endpoints
│   │
│   ├── tasks/                            # Celery Background Tasks
│   │   ├── __init__.py
│   │   ├── verification_tasks.py         # Certificate verification processing
│   │   ├── email_tasks.py                # Email notification tasks
│   │   └── admin_tasks.py                # Scheduled admin operations
│   │
│   └── data/                             # Reference datasets
│       └── WAEC_RESULTS_STATISTICS_2016-2018.pdf
│
├── tests/                                # Unit & Integration Tests
│   ├── __init__.py
│   ├── conftest.py                       # Pytest fixtures & configuration
│   ├── test_health.py                    # Health check endpoints
│   ├── test_auth.py                      # Authentication endpoints
│   ├── test_payments.py                  # Payment gateway integration
│   ├── test_pipeline.py                  # Verification pipeline
│   ├── test_b2b.py                       # B2B API endpoints
│   └── test_templates.py                 # Forensic template rules
│
└── .vscode/                              # VSCode workspace settings
    └── settings.json
```

---

## 📊 Database Schema

### Tables

#### `transaction_records`
Stores payment transactions and verification results.
```sql
- transaction_id (UUID, PK)
- transaction_ref (VARCHAR, UNIQUE)
- user_id (VARCHAR, FK to Firebase)
- email (VARCHAR)
- amount_naira (FLOAT)
- amount_kobo (INT)
- status (VARCHAR) -- 'pending', 'success', 'failed'
- created_at, paid_at (TIMESTAMP)
- cert_type (VARCHAR) -- 'WAEC', 'NECO'
- verification_result (TEXT/JSON)
- questions (TEXT/JSON)
- document_score, knowledge_score, final_trust_score (FLOAT)
- final_verdict (VARCHAR) -- 'AUTHENTIC', 'SUSPICIOUS', 'HIGH_RISK'
```

#### `api_keys`
B2B API keys for third-party organizations.
```sql
- id (UUID, PK)
- api_key (VARCHAR, UNIQUE, INDEXED)
- user_id (VARCHAR, FK to Firebase)
- email (VARCHAR)
- name (VARCHAR)
- credits (INT)
- is_active (BOOLEAN)
- created_at (TIMESTAMP)
```

#### `task_results`
Tracks async Celery task status and results.
```sql
- id (UUID, PK)
- task_id (VARCHAR, UNIQUE, INDEXED)
- task_type (VARCHAR) -- 'verification', 'email', 'admin'
- status (VARCHAR) -- 'pending', 'started', 'success', 'failure'
- user_id (VARCHAR, INDEXED)
- transaction_ref (VARCHAR, INDEXED)
- result (TEXT/JSON)
- error (TEXT)
- created_at, updated_at, completed_at (TIMESTAMP)
```

---

## 🔌 API Endpoints Reference

### 1. Health & Status (`/`)
Check API health and connectivity.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/` | Root endpoint, returns project info | ❌ |
| `GET` | `/health` | Health check, confirms DB connection | ❌ |

**Example Response:**
```json
{
  "project": "CertVerify API",
  "version": "1.0.0",
  "status": "operational",
  "docs": "/docs"
}
```

---

### 2. Authentication (`/auth`)
User registration, login, and token management.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/auth/register` | Register new user with Firebase | ❌ |
| `POST` | `/auth/login` | Email/password login → ID & refresh tokens | ❌ |
| `POST` | `/auth/refresh` | Exchange refresh token for new ID token | ❌ |
| `POST` | `/auth/forgot-password` | Send password reset email | ❌ |
| `GET` | `/auth/me` | Get authenticated user profile & claims | 🔐 Bearer |

**Register Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "display_name": "John Doe"
}
```

**Login Response:**
```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMyJ9...",
  "refresh_token": "AHbXAT0tM3C-...",
  "user": {
    "uid": "user_123",
    "email": "user@example.com",
    "display_name": "John Doe",
    "email_verified": false
  }
}
```

---

### 3. Payments (`/payment`)
Initiate, verify, and track payments via Squad.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/payment/pay/initiate` | Create payment session & get checkout URL | 🔐 Bearer (optional) |
| `GET` | `/payment/pay/verify/{ref}` | Check payment status with Squad API | ❌ |
| `POST` | `/payment/webhook` | Squad webhook for payment confirmation | 🔒 HMAC |
| `GET` | `/payment/payment_success` | Redirect after inline payment | ❌ |
| `GET` | `/payment/history` | List all transactions for user | 🔐 Bearer |

**Initiate Payment Request:**
```json
{
  "amount_naira": 5000.00,
  "email": "user@example.com"
}
```

**Initiate Payment Response:**
```json
{
  "status": "success",
  "checkout_url": "https://sandbox-checkout.squadco.com/...",
  "transaction_ref": "TXN-abc123",
  "amount_naira": 5000.00
}
```

---

### 4. AI Certificate Verification (`/AI_pipeline/verify`)
Upload certificates for forensic analysis with async processing.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/AI_pipeline/verify/analyse` | Queue certificate for verification (202 Accepted) | 🔐 Bearer |
| `GET` | `/AI_pipeline/verify/status/{task_id}` | Poll async task status & results | 🔐 Bearer |
| `GET` | `/AI_pipeline/verify/history` | List user verification reports | 🔐 Bearer |
| `GET` | `/AI_pipeline/verify/report/{ref}` | Get detailed forensic report | 🔐 Bearer |

**Analyse Certificate Request:**
```bash
curl -X POST http://localhost:8000/AI_pipeline/verify/analyse \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@certificate.pdf" \
  -F "cert_type=WAEC" \
  -F "transaction_ref=TXN-abc123"
```

**Analyse Response (202 Accepted):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "transaction_ref": "TXN-abc123",
  "message": "Verification queued. Poll the status endpoint to check progress."
}
```

**Status Polling Response (processing):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "created_at": "2026-09-01T10:30:00Z",
  "updated_at": "2026-09-01T10:30:05Z"
}
```

**Status Polling Response (complete):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "completed_at": "2026-09-01T10:32:15Z",
  "result": {
    "transaction_ref": "TXN-abc123",
    "final_verdict": "AUTHENTIC",
    "final_trust_score": 82.5,
    "document_score": 85.0,
    "knowledge_score": 78.0,
    "extracted_info": {
      "candidate_name": "Jane Doe",
      "exam_year": "2023",
      "subjects": ["Mathematics", "English", "Physics"],
      "registration_number": "WAE123456789"
    },
    "flagged_issues": [],
    "triggered_flags": [],
    "tampering_signs": []
  }
}
```

**Verification Report Response:**
```json
{
  "transaction_ref": "TXN-abc123",
  "cert_type": "WAEC",
  "created_at": "2026-09-01T10:30:00Z",
  "document_score": 85.0,
  "final_trust_score": 82.5,
  "final_verdict": "AUTHENTIC",
  "extracted_info": {
    "candidate_name": "Jane Doe",
    "exam_year": "2023",
    "subjects": [
      {"subject": "Mathematics", "grade": "A1", "remark": "Excellent"},
      {"subject": "English", "grade": "A2", "remark": "Excellent"},
      {"subject": "Physics", "grade": "B2", "remark": "Good"}
    ]
  },
  "flagged_issues": [],
  "triggered_flags": [],
  "tampering_signs": []
}
```

---

### 5. B2B Third-Party API (`/third_party/api/v1`)
External verification and credit-based API for organizations.

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/third_party/api/v1/keys/generate` | Generate new B2B API key (secret key shown once) | 🔐 Bearer |
| `GET` | `/third_party/api/v1/keys` | List organization API keys (masked secrets) | 🔐 Bearer |
| `POST` | `/third_party/api/v1/keys/{id}/rotate` | Rotate secret key (invalidates old key) | 🔐 Bearer |
| `DELETE` | `/third_party/api/v1/keys/{id}` | Revoke (deactivate) API key | 🔐 Bearer |
| `POST` | `/third_party/api/v1/verify` | Direct verification (atomic credit deduction) | 🔑 X-API-Key |

**Generate API Key Request:**
```json
{
  "name": "Mobile App Integration"
}
```

**Generate API Key Response (Full Secret Shown Once):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key": "cvfy_a1b2c3d4e5f6...",
  "masked_key": "cvfy_a1b...e5f6",
  "name": "Mobile App Integration",
  "credits": 3,
  "is_active": true,
  "created_at": "2026-09-01T10:30:00Z",
  "message": "API key generated successfully. Save this secret key securely — it will not be displayed in full again."
}
```

**List API Keys Response (Masked Secrets):**
```json
{
  "count": 1,
  "api_keys": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "masked_key": "cvfy_a1b...e5f6",
      "name": "Mobile App Integration",
      "credits": 3,
      "is_active": true,
      "created_at": "2026-09-01T10:30:00Z"
    }
  ]
}
```

**B2B Verification Request:**
```bash
curl -X POST http://localhost:8000/third_party/api/v1/verify \
  -H "X-API-Key: sk_live_abc123def456..." \
  -F "file=@certificate.pdf" \
  -F "cert_type=WAEC"
```

**B2B Verification Response (synchronous):**
```json
{
  "success": true,
  "final_verdict": "AUTHENTIC",
  "document_score": 85.0,
  "credits_remaining": 99,
  "transaction_ref": "B2B-xyz789"
}
```

---

### 6. Admin Panel (`/admin`)
Platform management and oversight (requires admin Firebase custom claim).

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/admin/dashboard` | Platform statistics & KPIs | 🔐 Admin |
| `GET` | `/admin/users` | List all Firebase users (paginated) | 🔐 Admin |
| `GET` | `/admin/users/{uid}` | Get user details | 🔐 Admin |
| `POST` | `/admin/users/set-admin` | Grant/revoke admin privileges | 🔐 Admin |
| `POST` | `/admin/users/disable` | Disable/enable user account | 🔐 Admin |
| `GET` | `/admin/transactions` | List transactions (filterable) | 🔐 Admin |
| `GET` | `/admin/transactions/{ref}` | Get transaction detail | 🔐 Admin |
| `GET` | `/admin/api-keys` | List B2B API keys | 🔐 Admin |
| `PATCH` | `/admin/api-keys/{key}` | Update API key (credits, status) | 🔐 Admin |
| `GET` | `/admin/verifications` | List verifications (filterable) | 🔐 Admin |
| `POST` | `/admin/email/send-bulk` | Send bulk email to recipients | 🔐 Admin |

**Dashboard Response:**
```json
{
  "total_users": 1250,
  "total_transactions": 3480,
  "total_revenue_naira": 17400000.00,
  "total_verifications": 2890,
  "pending_transactions": 45,
  "successful_transactions": 3435,
  "verdicts_authentic": 2650,
  "verdicts_suspicious": 180,
  "verdicts_high_risk": 60,
  "total_api_keys": 87,
  "total_b2b_credits_issued": 50000
}
```

---

## 🚀 Setup & Installation

### Prerequisites
- **Python 3.11+** — Download from [python.org](https://www.python.org/)
- **PostgreSQL database** — Use [Neon DB](https://neon.tech/) (free tier available)
- **Redis Cloud** — Use [Upstash](https://upstash.com/) or [Redis Labs](https://redis.com/cloud/)
- **Firebase Project** — Set up at [firebase.google.com](https://firebase.google.com/)
- **Google Gemini API Key** — Get from [Google AI Studio](https://aistudio.google.com/apikey)
- **Squad Merchant Account** — Register at [squadco.com](https://squadco.com/)
- **Gmail App Password** — Enable 2FA & create app-specific password

### Step 1: Clone Repository & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/Shench35/CertVerify-Backend.git
cd CertVerify-Backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Create a `.env` file in the project root with all required credentials:

```ini
# ─── Database ────────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require

# ─── Google Gemini AI ────────────────────────────────────────
GEMINI_API_KEY=AIzaSy...

# ─── Firebase Authentication ─────────────────────────────────
FIREBASE_CREDENTIALS_PATH=certverify-backend-firebase-adminsdk-fbsvc-b867004492.json
FIREBASE_WEB_API_KEY=AIzaSy...

# ─── Squad Payment Gateway ───────────────────────────────────
SQUAD_SECRET_KEY=sandbox_sk_2769eb78936fc094ceecc3faa15892c27b989a7ed12f
SQUAD_BASE_URL=https://sandbox-api-d.squadco.com
SQUAD_CALLBACK_URL=https://yourdomain.com/payment/payment_success

# ─── Redis / Celery (Cloud) ──────────────────────────────────
CELERY_BROKER_URL=redis://default:password@your-redis-host:6379/0
CELERY_RESULT_BACKEND=redis://default:password@your-redis-host:6379/1

# ─── SMTP / Email (Gmail) ────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_USE_TLS=True
EMAIL_FROM_ADDRESS=your_email@gmail.com
EMAIL_FROM_NAME=CertVerify

# ─── Admin Panel ──────────────────────────────────────────────
ADMIN_SECRET_KEY=your_admin_secret_key_change_in_production
FRONTEND_URL=http://localhost:3000
```

### Step 3: Verify Configuration
Test all external connections:

```bash
# Test Redis connection
python -c "
import redis
r = redis.from_url('your_redis_url')
print('✅ Redis:', r.ping())
"

# Test email configuration
python -c "
from app.core.config import settings
import smtplib
server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
server.starttls()
server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
print('✅ Email:', 'Authenticated')
server.quit()
"
```

---

## 🏃 Running the Application

### Option 1: Development with All Services

Open **3 separate terminal windows:**

**Terminal 1: Start Celery Worker**
```bash
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

**Terminal 2: Start FastAPI Server**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3: (Optional) Start Celery Beat Scheduler**
```bash
celery -A app.core.celery_app beat --loglevel=info
```

### Option 2: Production Deployment
```bash
# Start Gunicorn + Uvicorn workers
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Start Celery worker (separate process)
celery -A app.core.celery_app worker --loglevel=info --concurrency=4

# Start Celery beat scheduler (separate process)
celery -A app.core.celery_app beat --loglevel=info
```

### 📖 Access Documentation
Once running, open in browser:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_auth.py -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/test_auth.py::test_register_user -v
```

Test structure:
- **test_health.py** — Health check endpoints
- **test_auth.py** — Authentication & user management
- **test_payments.py** — Payment gateway & Squad integration
- **test_pipeline.py** — Certificate verification workflow
- **test_b2b.py** — B2B API & credit system
- **test_templates.py** — Forensic validation rules

---

## 📈 Verification Workflow

### Traditional (Synchronous)
```
Client uploads certificate
    ↓
FastAPI processes immediately
    ↓
Gemini analyzes document (30-60s)
    ↓
Deterministic checks run
    ↓
Assessment questions generated
    ↓
User submitted answers
    ↓
Knowledge score calculated
    ↓
Final verdict returned
    ↓
Response sent to client ⏱️ (60-120s total)
```

### Asynchronous (Current - Non-blocking)
```
Client uploads certificate
    ↓
FastAPI returns 202 immediately with task_id
    ↓
Client can continue using app
    ↓
[Background] Celery worker processes certificate
    ↓
[Background] Gemini analyzes document
    ↓
[Background] Deterministic checks & assessment run
    ↓
[Background] Results saved to database
    ↓
[Background] Email notification sent
    ↓
Client polls /status/{task_id} for results
    ↓
Results available when ready ✅
```

### Verification Scoring
```
Document Forensic Score (Gemini + Rules):
  - Seal & logo verification
  - Font analysis
  - Layout consistency
  - Photograph embossing
  - QR code validation
  - Registration number format
  - Grade/remark combinations
  - Age & date consistency
  - Subject count validation
  
Result: 0-100 points, penalties applied for triggered flags

Knowledge Assessment Score (Dynamic Q&A):
  - 5 subject-specific reasoning questions
  - Real-time answer evaluation
  - Application understanding verification
  
Result: 0-100 points

Composite Trust Score:
  - 60% Document Score
  - 40% Knowledge Score
  - Final: 0-100
  
Verdict:
  - 75-100: AUTHENTIC ✅
  - 40-74: SUSPICIOUS ⚠️
  - 0-39: HIGH_RISK ❌
```

---

## 🔒 Security Features

- **Firebase Authentication** — Secured with Google Identity Platform
- **Bearer Token Validation** — JWT tokens with signature verification
- **HMAC Webhook Verification** — Squad webhook authenticity validation
- **Admin Role-Based Access** — Firebase custom claims for authorization
- **API Key Management** — Secure B2B API key generation & rotation
- **CORS Protection** — Configurable allowed origins
- **Environment Secrets** — All credentials in `.env` (never committed)
- **Password Encryption** — Firebase handles bcrypt hashing
- **Database Pooling** — Secure connection management via SQLAlchemy

---

## 🔄 Async Task Types

### Verification Tasks
- **run_verification** — Full certificate forensic analysis
- **run_b2b_verification** — B2B sync verification

### Email Tasks
- **send_payment_confirmation_task** — Payment confirmation email
- **send_verification_report_task** — Verification result email
- **send_b2b_credit_alert_task** — Low credit warning email
- **send_api_key_generated_task** — API key creation notification
- **send_bulk_email_task** — Admin bulk messaging

### Admin Tasks
- **generate_platform_report** — Daily statistics report
- **cleanup_expired_transactions** — Maintenance task

---

## 🐳 Docker Deployment (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY .env .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build & run:
```bash
docker build -t certverify-api .
docker run -p 8000:8000 --env-file .env certverify-api
```

---

## 📊 Performance Metrics

**Expected Performance:**
- Health check: **< 100ms**
- Authentication: **200-300ms** (Firebase round trip)
- Async verification: **30-60s** (Certificate + AI analysis)
- B2B verification: **30-60s** (Same as async)
- Email sending: **1-2s** (Queued asynchronously)
- Admin dashboard: **200-500ms** (Aggregation query)

**Scalability:**
- FastAPI workers: Horizontal scaling via Gunicorn
- Celery workers: Independent scaling based on queue depth
- Redis: Cloud-managed auto-scaling
- PostgreSQL: Connection pooling with SQLAlchemy

---

## 🐛 Troubleshooting

### Redis Connection Failed
```bash
# Check Redis URL format
# Should be: redis://default:PASSWORD@HOST:PORT/DB
# Verify host is accessible (no firewall blocking)
python -c "import redis; r = redis.from_url('your_url'); print(r.ping())"
```

### Celery Worker Not Processing Tasks
```bash
# Ensure broker URL is correct in .env
# Check Redis connectivity
# Restart worker: celery -A app.core.celery_app worker --loglevel=debug
```

### Gmail SMTP Authentication Error
```bash
# Verify 2FA is enabled on Gmail account
# Generate app-specific password (not regular password)
# Use app-specific password in SMTP_PASSWORD
```

### FastAPI Not Finding .env Variables
```bash
# Ensure .env is in project root (same level as requirements.txt)
# Run from project root: uvicorn app.main:app --reload
# Check .env file has no spaces around = signs
```

---

## 📝 API Examples

### Complete Verification Flow

**1. Register User**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "password": "SecurePass123!",
    "display_name": "Jane Doe"
  }'
```

**2. Login**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "password": "SecurePass123!"
  }'
# Response includes: id_token, refresh_token
```

**3. Initiate Payment**
```bash
curl -X POST http://localhost:8000/payment/pay/initiate \
  -H "Authorization: Bearer ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_naira": 5000.00,
    "email": "jane@example.com"
  }'
# Response includes: checkout_url, transaction_ref
```

**4. Complete Payment** (via Squad checkout)

**5. Upload Certificate (Async)**
```bash
curl -X POST http://localhost:8000/AI_pipeline/verify/analyse \
  -H "Authorization: Bearer ID_TOKEN" \
  -F "file=@certificate.pdf" \
  -F "cert_type=WAEC" \
  -F "transaction_ref=TXN-abc123"
# Response: {"task_id": "xyz", "status": "pending"}
```

**6. Poll Task Status**
```bash
curl -X GET http://localhost:8000/AI_pipeline/verify/status/xyz \
  -H "Authorization: Bearer ID_TOKEN"
# Response evolves: pending → started → success
```

**7. Get Final Report**
```bash
curl -X GET http://localhost:8000/AI_pipeline/verify/report/TXN-abc123 \
  -H "Authorization: Bearer ID_TOKEN"
# Response: Full forensic report with verdict
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure:
- Code follows PEP 8 style guide
- All tests pass (`pytest tests/ -v`)
- New features include test coverage
- Documentation is updated

---

## 📧 Support

For issues, questions, or suggestions:
- **GitHub Issues:** [Create an issue](https://github.com/Shench35/CertVerify-Backend/issues)
- **Email:** support@certverify.com

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Firebase** for authentication infrastructure
- **Google Gemini** for multimodal AI capabilities
- **Squad** for payment processing
- **FastAPI** community for excellent framework
- **Celery** for distributed task processing
- **PostgreSQL** for reliable data storage

---

## 📈 Roadmap

- [ ] Multi-language support (French, Spanish, Swahili)
- [ ] Mobile app for direct camera verification
- [ ] Blockchain certificate storage & verification
- [ ] Advanced ML model for forensic scoring
- [ ] Real-time video KYC integration
- [ ] Batch verification API for enterprises
- [ ] Analytics dashboard with advanced filtering
- [ ] Subscription-based pricing tiers
- [ ] ISO 27001 compliance certification
- [ ] Multi-region deployment

---

**Built with ❤️ for African education & credibility verification**

*Last Updated: September 2026*