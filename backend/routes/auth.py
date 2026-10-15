from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import create_access_token, get_jwt, jwt_required

from audit import audit
from extensions import bcrypt, get_db, limiter
from routes.mfa import mfa_required_for, pending_token
from security import (current_user, decrypt_field, encrypt_field, get_password, get_str, get_username,
                      hash_password, json_body, password_problems, verify_captcha)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_dummy_hash = None


def _timing_hash():
    """A real bcrypt hash, so a login for an unknown user takes as long as one for a real user."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("timing-equalizer-not-a-real-password")
    return _dummy_hash


@auth_bp.post("/register")
@limiter.limit("10 per minute")
def register():
    data = json_body()
    username = get_username(data)
    password = get_password(data)
    full_name = get_str(data, "full_name", required=False, max_len=100)
    if not verify_captcha(data.get("captcha_token")):
        audit("REGISTER", user=username, success=False, detail="captcha failed")
        return jsonify(error="CAPTCHA verification failed"), 400

    problems = password_problems(password, username)
    if problems:
        return jsonify(error="Password does not meet the policy", requirements=problems), 400

    db = get_db()
    if db.users.find_one({"username": username}):
        return jsonify(error="Username is not available"), 409
    db.users.insert_one({
        "username": username,
        "password_hash": hash_password(password),
        "full_name_enc": encrypt_field(full_name),
        "role": "intern",
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
    })
    audit("REGISTER", user=username, role="intern")
    return jsonify(message="Account created"), 201


@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():
    data = json_body()
    username = get_username(data)
    password = get_password(data)
    if not verify_captcha(data.get("captcha_token")):
        audit("LOGIN_FAILED", user=username, success=False, detail="captcha failed")
        return jsonify(error="CAPTCHA verification failed"), 400

    db = get_db()
    user = db.users.find_one({"username": username})
    now = datetime.now(timezone.utc)

    locked_until = user.get("locked_until") if user else None
    if locked_until and locked_until.replace(tzinfo=timezone.utc) > now:
        audit("LOGIN_BLOCKED_LOCKED", user=username, success=False)
        return jsonify(error="Account is locked after too many failed attempts. Try again later."), 423

    if not bcrypt.check_password_hash(user["password_hash"] if user else _timing_hash(), password) or not user:
        detail = None
        if user:
            attempts = user.get("failed_attempts", 0) + 1
            update = {"failed_attempts": attempts}
            if attempts >= current_app.config["LOCKOUT_THRESHOLD"]:
                update = {"failed_attempts": 0,
                          "locked_until": now + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])}
                detail = "account locked"
                audit("ACCOUNT_LOCKED", user=username, success=False)
            db.users.update_one({"_id": user["_id"]}, {"$set": update})
        audit("LOGIN_FAILED", user=username, success=False, detail=detail)
        return jsonify(error="Invalid username or password"), 401

    # C1: admins and supervisors must pass a second factor before they get a session token.
    if mfa_required_for(user):
        audit("LOGIN_PASSWORD_OK_MFA_PENDING", user=username, role=user["role"])
        return jsonify(mfa_required=True, mfa_enrolled=bool(user.get("mfa_enabled")),
                       mfa_token=pending_token(user), expires_in=300), 200

    db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_attempts": 0, "locked_until": None}})
    token = create_access_token(identity=username, additional_claims={"role": user["role"]})
    audit("LOGIN_SUCCESS", user=username, role=user["role"])
    return jsonify(access_token=token, role=user["role"], expires_in=900), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    claims = get_jwt()
    get_db().revoked_tokens.insert_one({
        "jti": claims["jti"],
        "exp": datetime.fromtimestamp(claims["exp"], timezone.utc),
    })
    audit("LOGOUT", user=claims["sub"], role=claims.get("role"))
    return jsonify(message="Logged out"), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user = current_user()
    if not user:
        return jsonify(error="Session is no longer valid, please log in again"), 401
    return jsonify(username=user["username"], role=user["role"],
                   full_name=decrypt_field(user.get("full_name_enc"))), 200
