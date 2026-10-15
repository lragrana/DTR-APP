import os
from datetime import timedelta


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Config:
    # Secrets come from the environment (.env / Docker), never from source code.
    MONGO_URI = _required("MONGO_URI")
    MONGO_DB = os.environ.get("MONGO_DB", "dtr_database")
    # C2: the JWT signing key and the field encryption keys are loaded from Vault at startup (keyring.py).
    VAULT_ADDR = _required("VAULT_ADDR")
    TURNSTILE_SECRET = _required("TURNSTILE_SECRET")

    # R-003: short-lived tokens, sent only in the Authorization header.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ALGORITHM = "HS256"

    # R-005: CORS allow-list, request size limit, rate limiting.
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "https://localhost").split(",") if o.strip()]
    MAX_CONTENT_LENGTH = 16 * 1024
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_HEADERS_ENABLED = True

    # R-001: account lockout.
    LOCKOUT_THRESHOLD = 5
    LOCKOUT_MINUTES = 15

    # Optional first admin account, created once on startup.
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
