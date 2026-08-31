# CertVerify API — Forensic Certificate Verification Platform

**CertVerify** is an enterprise-grade, AI-powered forensic credential verification engine designed for African secondary school credentials—specifically **WAEC** (West African Examinations Council) and **NECO** (National Examinations Council).

It leverages a **Hybrid Verification Strategy**:
1. **Multimodal Computer Vision Forensics (60% weight):** Visual inspection of seals, fonts, layout markers, photograph embossing, and QR codes via Google Gemini Flash + PyMuPDF against forensic reference templates.
2. **Cognitive Dynamic Knowledge Testing (40% weight):** Generates 5 dynamic, subject-specific reasoning questions based on the candidate's transcript and strictly evaluates their answers to verify genuine subject comprehension.
3. **B2B API Integration:** External organizations can verify credentials with API keys and atomic credit consumption.

---

## Architecture Overview

```
CertVerify-Backend/
├── .env                              # Environment configuration
├── .gitignore                        # Git exclusion rules (keys, secrets, caches)
├── LICENSE                           # MIT License
├── README.md                         # Project documentation
├── requirements.txt                  # Python dependencies
├── certverify-backend-*.json         # Firebase Service Account credentials
└── app/
    ├── __init__.py
    ├── main.py                       # FastAPI entrypoint & lifespan management
    │
    ├── core/                         # Core configuration & infrastructure
    │   ├── config.py                 # Pydantic Settings & environment loader
    │   ├── database.py               # SQLModel / SQLAlchemy engine & session dependency
    │   ├── firebase.py               # Firebase Admin SDK initialization
    │   └── security.py               # Bearer token verification dependencies
    │
    ├── models/                       # Database Models (PostgreSQL / Neon DB)
    │   ├── transaction.py            # Transaction records & AI verification results
    │   └── api_key.py                # B2B API keys & credit balances
    │
    ├── schemas/                      # Pydantic DTOs & Validation Schemas
    │   ├── auth.py                   # Authentication schemas
    │   ├── payment.py                # Payment request/response schemas
    │   ├── verification.py           # Forensic AI pipeline schemas
    │   └── b2b.py                    # B2B API key schemas
    │
    ├── services/                     # Business Logic & Integrations
    │   ├── auth_service.py           # Firebase Auth & Identity Toolkit operations
    │   ├── document_analyser.py      # Gemini Vision OCR & prompt engineering
    │   ├── template_service.py       # WAEC/NECO forensic rules & penalty matrices
    │   ├── validator_service.py      # Deterministic checks (age, regex, grades)
    │   ├── assessment_service.py     # Dynamic Q&A generation & examiner scoring
    │   ├── payment_service.py        # Squad payment gateway integration
    │   └── b2b_service.py            # Atomic Postgres credit management
    │
    ├── api/                          # HTTP Routers & Endpoints
    │   ├── router.py                 # Primary API aggregator
    │   └── v1/                       # Version 1 Endpoints
    │       ├── auth.py               # /auth/*
    │       ├── payments.py           # /payment/*
    │       ├── verification.py       # /AI_pipeline/verify/*
    │       └── b2b.py                # /third_party/api/v1/*
    │
    └── data/                         # Datasets & reference documents
        └── WAEC_RESULTS_STATISTICS_2016-2018.pdf
```

---

## API Endpoints Reference

### 1. Authentication (`/auth`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Register new user account | None |
| `POST` | `/auth/login` | Email/password login $\to$ returns access & refresh tokens | None |
| `POST` | `/auth/refresh` | Exchange refresh token for fresh ID token | None |
| `POST` | `/auth/forgot-password` | Send password reset email | None |
| `GET` | `/auth/me` | Fetch authenticated user profile & claims | **Bearer Token** |

### 2. Payments (`/payment`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/payment/pay/initiate` | Initiate payment checkout session | Optional Bearer |
| `GET` | `/payment/pay/verify/{ref}` | Verify payment status with Squad | None |
| `POST` | `/payment/webhook` | Squad payment confirmation webhook | HMAC Header |
| `GET` | `/payment/pay/callback` | Redirect landing after inline payment | None |
| `GET` | `/payment/history` | List all user transactions | **Bearer Token** |

### 3. AI Certificate Verification (`/AI_pipeline/verify`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/AI_pipeline/verify/analyse` | Upload certificate $\to$ Forensic check + 5 Questions | **Bearer Token** |
| `POST` | `/AI_pipeline/verify/score` | Submit answers $\to$ Composite Trust Score & Verdict | **Bearer Token** |
| `GET` | `/AI_pipeline/verify/history` | List user verification reports | **Bearer Token** |
| `GET` | `/AI_pipeline/verify/report/{ref}` | Get detailed single forensic report | **Bearer Token** |

### 4. B2B Third-Party API (`/third_party/api/v1`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/third_party/api/v1/keys/generate` | Generate external API key | Optional Bearer |
| `GET` | `/third_party/api/v1/keys` | List organization API keys & balances | **Bearer Token** |
| `POST` | `/third_party/api/v1/credits/add` | Top-up credits for an API key | None / Admin |
| `POST` | `/third_party/api/v1/verify` | Direct verification (Atomic credit deduction) | **X-API-Key Header** |

---

## Setup & Installation

### 1. Prerequisites
- Python 3.11+
- PostgreSQL database (e.g. Neon DB)
- Firebase Project (with Authentication enabled)
- Google Gemini API Key
- Squad Merchant Account

### 2. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables (`.env`)
Create or edit your `.env` file in the project root:
```ini
# PostgreSQL Database
DATABASE_URL=postgresql://user:password@host/neondb?sslmode=require

# Google Gemini AI
GEMINI_API_KEY=AIzaSy...

# Firebase Authentication
FIREBASE_CREDENTIALS_PATH=certverify-backend-firebase-adminsdk-....json
FIREBASE_WEB_API_KEY=AIzaSy...

# Squad Payment Gateway
SQUAD_SECRET_KEY=sandbox_sk_...
SQUAD_BASE_URL=https://sandbox-api-d.squadco.com
```

### 4. Run the Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Interactive Documentation
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.