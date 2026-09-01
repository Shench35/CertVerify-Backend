from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    # Application Metadata
    PROJECT_NAME: str = "CertVerify API"
    PROJECT_DESCRIPTION: str = "AI-Powered Forensic Certificate Verification Platform"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    DATABASE_URL: str

    # Squad Payment Gateway
    SQUAD_SECRET_KEY: str
    SQUAD_BASE_URL: str = "https://sandbox-api-d.squadco.com"
    SQUAD_CALLBACK_URL: str = "https://junkman-thrash-omission.ngrok-free.dev/payment-success"

    # Google Gemini AI
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EXAMINER_MODEL: str = "gemini-2.5-flash"

    # Firebase Authentication
    FIREBASE_CREDENTIALS_PATH: str = "certverify-backend-firebase-adminsdk-fbsvc-b867004492.json"
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = None
    FIREBASE_WEB_API_KEY: str = ""

    # Celery & Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM_ADDRESS: str = "noreply@certverify.com"
    EMAIL_FROM_NAME: str = "CertVerify"

    # Admin
    ADMIN_EMAILS: list[str] = []
    ADMIN_SECRET_KEY: str = "change-me-in-production"

    # Frontend URL (for email links)
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
