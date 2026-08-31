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

    # Database
    DATABASE_URL: str

    # Squad Payment Gateway
    SQUAD_SECRET_KEY: str
    SQUAD_BASE_URL: str = "https://sandbox-api-d.squadco.com"
    SQUAD_CALLBACK_URL: str = "https://kinship-tropical-junkie.ngrok-free.dev/payment-success"

    # Google Gemini AI
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EXAMINER_MODEL: str = "gemini-2.5-flash"

    # Firebase Authentication
    FIREBASE_CREDENTIALS_PATH: str = "certverify-backend-firebase-adminsdk-fbsvc-b867004492.json"
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = None
    FIREBASE_WEB_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
