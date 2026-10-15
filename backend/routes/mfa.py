"""C1 – Multi-factor authentication (TOTP, RFC 6238) for admin and supervisor accounts.

Flow: password login -> 5-minute "MFA pending" token -> setup/confirm (first time) or verify -> 15-minute JWT.
The pending token is accepted only by the endpoints in this blueprint (see app.py token_verification_loader).
"""
import base64
import io
import secrets
import time
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
import qrcode.image.svg
from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import create_access_token, get_jwt, jwt_required

from audit import audit
from extensions import bcrypt, get_db, limiter
from security import ValidationError, current_user, decrypt_field, encrypt_field, get_str, json_body

mfa_bp = Blueprint("mfa", __name__, url_prefix="/api/auth/mfa")

MFA_ROLES = ("admin", "supervisor")
ISSUER = "DTR Timetrack"
BACKUP_CODE_COUNT = 8
PENDING_MINUTES = 5


def mfa_required_for(user):
    return user["role"] in MFA_ROLES


def pending_token(user):
    """Short-lived token that proves only the password step; it cannot call any normal API."""
    return create_access_token(
        identity=user["username"],
        additional_claims={"role": user["role"], "mfa_pending": True},
        expires_delta=timedelta(minutes=PENDING_MINUTES),
    )


def _pending_user():
    claims = get_jwt()
    if not claims.get("mfa_pending"):
        raise ValidationError("This step needs the token from the password login")
    user = current_user()
    if not user or user["role"] != claims.get("role"):
        return None
    return user


def _finish_login(user, detail):
    """Revoke the pending token (single use) and issue the normal 15-minute session token."""
    claims = get_jwt()
    db = get_db()
    db.revoked_tokens.insert_one({"jti": claims["jti"],
                                  "exp": datetime.fromtimestamp(claims["exp"], timezone.utc)})
    db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_attempts": 0, "mfa_failed": 0, "locked_until": None}})
    token = create_access_token(identity=user["username"], additional_claims={"role": user["role"], "mfa": True})
    audit("LOGIN_SUCCESS", user=user["username"], role=user["role"], detail=detail)
    return jsonify(access_token=token, role=user["role"], expires_in=900), 200


def _code(data):
    code = get_str(data, "code", max_len=20).replace(" ", "").replace("-", "").upper()
    if not code.isalnum():
        raise ValidationError("Code must be 6 digits or a backup code")
    return code


def _totp_step(secret, code):
    """Return the time step a valid code belongs to (±1 step for clock drift), else None."""
    if not (len(code) == 6 and code.isdigit()):
        return None
    totp = pyotp.TOTP(secret)
    now = time.time()
    for drift in (0, -1, 1):
        at = now + drift * totp.interval
        if secrets.compare_digest(totp.at(at), code):
            return totp.timecode(datetime.fromtimestamp(at, timezone.utc))
    return None


def _register_failure(user, action):
    db = get_db()
    failures = user.get("mfa_failed", 0) + 1
    update = {"mfa_failed": failures}
    if failures >= current_app.config["LOCKOUT_THRESHOLD"]:
        update = {"mfa_failed": 0,
                  "locked_until": datetime.now(timezone.utc) + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])}
        audit("MFA_LOCKED", user=user["username"], role=user["role"], success=False,
              detail=f"{failures} wrong codes")
    db.users.update_one({"_id": user["_id"]}, {"$set": update})
    audit(action, user=user["username"], role=user["role"], success=False, detail=f"wrong code {failures}")
    if "locked_until" in update:
        return jsonify(error="Too many wrong codes. The account is locked for 15 minutes."), 423
    return jsonify(error="Invalid code"), 401


def _locked(user):
    locked_until = user.get("locked_until")
    return locked_until and locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


@mfa_bp.post("/setup")
@jwt_required()
@limiter.limit("10 per minute")
def setup():
    user = _pending_user()
    if not user:
        return jsonify(error="Session is no longer valid, please log in again"), 401
    if user.get("mfa_enabled"):
        return jsonify(error="MFA is already set up for this account"), 409
    secret = pyotp.random_base32()
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"mfa_pending_secret_enc": encrypt_field(secret)}})
    uri = pyotp.TOTP(secret).provisioning_uri(name=user["username"], issuer_name=ISSUER)
    svg = io.BytesIO()
    qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8).save(svg)
    audit("MFA_SETUP_STARTED", user=user["username"], role=user["role"])
    return jsonify(qr_svg="data:image/svg+xml;base64," + base64.b64encode(svg.getvalue()).decode(),
                   secret=secret, issuer=ISSUER), 200


@mfa_bp.post("/confirm")
@jwt_required()
@limiter.limit("10 per minute")
def confirm():
    user = _pending_user()
    if not user:
        return jsonify(error="Session is no longer valid, please log in again"), 401
    if user.get("mfa_enabled"):
        return jsonify(error="MFA is already set up for this account"), 409
    if _locked(user):
        return jsonify(error="Account is locked after too many failed attempts. Try again later."), 423
    secret = decrypt_field(user.get("mfa_pending_secret_enc"))
    if not secret:
        return jsonify(error="Start the MFA setup first"), 400
    step = _totp_step(secret, _code(json_body()))
    if step is None:
        return _register_failure(user, "MFA_SETUP_FAILED")

    codes = [secrets.token_hex(5).upper() for _ in range(BACKUP_CODE_COUNT)]
    get_db().users.update_one({"_id": user["_id"]}, {
        "$set": {"mfa_enabled": True, "mfa_secret_enc": encrypt_field(secret), "mfa_last_step": step,
                 "mfa_backup_hashes": [bcrypt.generate_password_hash(c, rounds=10).decode() for c in codes],
                 "mfa_enrolled_at": datetime.now(timezone.utc)},
        "$unset": {"mfa_pending_secret_enc": ""},
    })
    audit("MFA_ENABLED", user=user["username"], role=user["role"])
    resp, status = _finish_login(user, "password + TOTP (enrolment)")
    body = resp.get_json()
    body["backup_codes"] = codes
    return jsonify(body), status


@mfa_bp.post("/verify")
@jwt_required()
@limiter.limit("10 per minute")
def verify():
    user = _pending_user()
    if not user:
        return jsonify(error="Session is no longer valid, please log in again"), 401
    if not user.get("mfa_enabled"):
        return jsonify(error="MFA is not set up yet"), 400
    if _locked(user):
        audit("LOGIN_BLOCKED_LOCKED", user=user["username"], role=user["role"], success=False, detail="mfa step")
        return jsonify(error="Account is locked after too many failed attempts. Try again later."), 423
    code = _code(json_body())
    db = get_db()

    step = _totp_step(decrypt_field(user["mfa_secret_enc"]), code)
    if step is not None:
        # Replay protection: a code that was already used (same or older time step) is rejected.
        if step <= user.get("mfa_last_step", -1):
            return _register_failure(user, "MFA_REPLAY_BLOCKED")
        db.users.update_one({"_id": user["_id"]}, {"$set": {"mfa_last_step": step}})
        audit("MFA_VERIFY_SUCCESS", user=user["username"], role=user["role"])
        return _finish_login(user, "password + TOTP")

    # Backup codes: 10 hex characters, each usable once.
    for i, hashed in enumerate(user.get("mfa_backup_hashes", [])):
        if len(code) == 10 and bcrypt.check_password_hash(hashed, code):
            remaining = user["mfa_backup_hashes"][:i] + user["mfa_backup_hashes"][i + 1:]
            db.users.update_one({"_id": user["_id"]}, {"$set": {"mfa_backup_hashes": remaining}})
            audit("MFA_BACKUP_CODE_USED", user=user["username"], role=user["role"],
                  detail=f"{len(remaining)} backup codes left")
            return _finish_login(user, "password + backup code")

    return _register_failure(user, "MFA_VERIFY_FAILED")

