import base64
import json
import os
import re
import urllib.parse
import urllib.request
from functools import wraps

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

import keyring
from extensions import bcrypt, get_db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
ROLES = ("intern", "supervisor", "admin")
COMMON_PASSWORDS = {
    "password1234", "password12345", "123456789012", "qwertyuiop12", "administrator",
    "welcome12345", "iloveyou1234", "letmein12345", "passw0rd1234", "p@ssw0rd1234",
}


class ValidationError(Exception):
    pass


# ---------- input validation (R-005) ----------

def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def get_str(data, key, *, required=True, max_len=128):
    value = data.get(key)
    if value is None:
        if required:
            raise ValidationError(f"'{key}' is required")
        return None
    # Only plain strings are accepted, so objects like {"$ne": null} cannot reach a query.
    if not isinstance(value, str):
        raise ValidationError(f"'{key}' must be a string")
    if len(value) > max_len:
        raise ValidationError(f"'{key}' is too long")
    return value


def get_password(data, key="password"):
    password = get_str(data, key, max_len=64)
    # bcrypt only accepts up to 72 bytes; reject instead of failing or truncating.
    if len(password.encode()) > 72:
        raise ValidationError(f"'{key}' is too long")
    return password


def get_username(data, key="username"):
    username = get_str(data, key, max_len=32)
    if not USERNAME_RE.match(username):
        raise ValidationError("Username must be 3-32 letters, digits, '.', '_' or '-'")
    return username


# ---------- password policy (R-001, NIST SP 800-63B) ----------

def password_problems(password, username):
    problems = []
    if len(password) < 12:
        problems.append("at least 12 characters")
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        problems.append("upper- and lower-case letters")
    if not re.search(r"\d", password):
        problems.append("a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("a symbol")
    if username and username.lower() in password.lower():
        problems.append("must not contain the username")
    if password.lower() in COMMON_PASSWORDS:
        problems.append("must not be a commonly used password")
    return problems


def hash_password(password):
    return bcrypt.generate_password_hash(password, rounds=12).decode()


# ---------- field-level encryption (R-002 + C2): AES-256-GCM, keys from Vault ----------

def encrypt_field(plaintext):
    if plaintext is None:
        return None
    version, key = keyring.current_key()
    nonce = os.urandom(12)
    return f"{version}:" + base64.b64encode(nonce + AESGCM(key).encrypt(nonce, plaintext.encode(), None)).decode()


def decrypt_field(token):
    if not token:
        return None
    version, _, payload = token.partition(":")
    raw = base64.b64decode(payload)
    return AESGCM(keyring.key_for(version)).decrypt(raw[:12], raw[12:], None).decode()


def key_version(token):
    return token.partition(":")[0] if token else None


# ---------- CAPTCHA (R-005): Cloudflare Turnstile ----------

def verify_captcha(token):
    if not isinstance(token, str) or not token or len(token) > 2048:
        return False
    body = urllib.parse.urlencode({
        "secret": current_app.config["TURNSTILE_SECRET"],
        "response": token,
        "remoteip": request.remote_addr or "",
    }).encode()
    try:
        with urllib.request.urlopen(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify", body, timeout=5
        ) as resp:
            return bool(json.load(resp).get("success"))
    except Exception:
        current_app.logger.exception("CAPTCHA verification failed")
        return False


# ---------- authorization (R-004) ----------

def current_user():
    return get_db().users.find_one({"username": get_jwt_identity()})


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from audit import audit

            verify_jwt_in_request()
            user = current_user()
            # The role is re-read from the database so a demoted user loses access immediately.
            if not user or user["role"] != get_jwt().get("role"):
                return jsonify(error="Session is no longer valid, please log in again"), 401
            if user["role"] not in roles:
                audit("ACCESS_DENIED", user=user["username"], role=user["role"],
                      target=request.path, success=False)
                return jsonify(error="You do not have permission for this action"), 403
            return fn(user, *args, **kwargs)
        return wrapper
    return decorator


def reauthenticate(user, data):
    """R-003: sensitive actions require the password again."""
    password = data.get("password")
    return isinstance(password, str) and len(password.encode()) <= 72 and bcrypt.check_password_hash(user["password_hash"], password)
