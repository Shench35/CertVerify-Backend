import json
import logging
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings, BASE_DIR

logger = logging.getLogger(__name__)


def initialize_firebase():
    """
    Initialize Firebase Admin SDK with service account credentials.
    Supports file path or raw JSON environment variable.
    """
    if firebase_admin._apps:
        return firebase_admin.get_app()

    cred_path = settings.FIREBASE_CREDENTIALS_PATH
    json_str = settings.FIREBASE_SERVICE_ACCOUNT_JSON

    # 1. From raw JSON string
    if json_str:
        try:
            cred_dict = json.loads(json_str)
            cred = credentials.Certificate(cred_dict)
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            logger.error(f"Failed to initialize Firebase from raw JSON: {e}")

    # 2. From file path
    resolved_path = Path(cred_path)
    if not resolved_path.is_absolute():
        resolved_path = BASE_DIR / cred_path

    if resolved_path.exists():
        try:
            cred = credentials.Certificate(str(resolved_path))
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            logger.error(f"Failed to initialize Firebase with file {resolved_path}: {e}")
            raise e
    else:
        logger.warning(
            f"Firebase credentials file not found at '{resolved_path}'. "
            f"Please ensure your Service Account JSON exists."
        )
        return None


firebase_app = initialize_firebase()
