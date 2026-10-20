"""One-way API-key storage helpers."""

import hashlib


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def mask_api_key(api_key: str) -> str:
    if not api_key or len(api_key) < 12:
        return "****"
    return f"{api_key[:8]}...{api_key[-4:]}"
