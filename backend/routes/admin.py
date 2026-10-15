from flask import Blueprint, jsonify, request

import keyring

from audit import audit
from extensions import get_db
from security import (ROLES, USERNAME_RE, ValidationError, decrypt_field, encrypt_field, get_str, json_body,
                      key_version, reauthenticate, roles_required)

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/users")
@roles_required("admin")
def list_users(user):
    users = get_db().users.find({}, {"_id": 0, "username": 1, "role": 1, "locked_until": 1, "mfa_enabled": 1})
    return jsonify([{"username": u["username"], "role": u["role"], "locked": bool(u.get("locked_until")),
                     "mfa": bool(u.get("mfa_enabled"))} for u in users]), 200


@admin_bp.patch("/users/<username>/role")
@roles_required("admin")
def change_role(user, username):
    if not USERNAME_RE.match(username):
        raise ValidationError("Invalid username")
    data = json_body()
    new_role = get_str(data, "role", max_len=20)
    if new_role not in ROLES:
        raise ValidationError(f"Role must be one of: {', '.join(ROLES)}")
    if not reauthenticate(user, data):
        audit("REAUTH_FAILED", user=user["username"], role=user["role"], target=username, success=False)
        return jsonify(error="Re-authentication required: enter your password"), 401
    if username == user["username"]:
        return jsonify(error="You cannot change your own role"), 400
    db = get_db()
    target = db.users.find_one({"username": username})
    if not target:
        return jsonify(error="User not found"), 404
    db.users.update_one({"_id": target["_id"]}, {"$set": {"role": new_role}})
    # R-004: every privilege change is logged with old and new role.
    audit("ROLE_CHANGE", user=user["username"], role=user["role"], target=username,
          detail=f"{target['role']} -> {new_role}")
    return jsonify(message=f"{username} is now {new_role}"), 200


@admin_bp.get("/audit-logs")
@roles_required("admin")
def audit_logs(user):
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 500)
    except ValueError:
        raise ValidationError("limit must be a number")
    logs = get_db().audit_logs.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
    return jsonify([{**l, "ts": l["ts"].isoformat()} for l in logs]), 200


@admin_bp.get("/alerts")
@roles_required("admin")
def alerts(user):
    items = get_db().alerts.find({}, {"_id": 0}).sort("ts", -1).limit(100)
    return jsonify([{**a, "ts": a["ts"].isoformat()} for a in items]), 200


# ---------- C2: encryption key status and rotation ----------

ENCRYPTED_FIELDS = {"users": ["full_name_enc", "mfa_secret_enc", "mfa_pending_secret_enc"],
                    "attendance": ["notes_enc"]}


def _key_usage():
    db = get_db()
    usage = {}
    for coll, fields in ENCRYPTED_FIELDS.items():
        for doc in db[coll].find({}, {f: 1 for f in fields}):
            for f in fields:
                v = key_version(doc.get(f))
                if v:
                    usage[v] = usage.get(v, 0) + 1
    return usage


@admin_bp.get("/keys")
@roles_required("admin")
def key_status(user):
    return jsonify(**keyring.status(), encrypted_values_by_version=_key_usage()), 200


@admin_bp.post("/keys/rotate")
@roles_required("admin")
def rotate_keys(user):
    data = json_body()
    if not reauthenticate(user, data):
        audit("REAUTH_FAILED", user=user["username"], role=user["role"], target="field-keys", success=False)
        return jsonify(error="Re-authentication required: enter your password"), 401
    old = keyring.status()["current"]
    # 1) new key version in Vault becomes current, 2) re-encrypt every field, 3) retire old versions.
    new = keyring.add_new_version()
    db = get_db()
    count = 0
    for coll, fields in ENCRYPTED_FIELDS.items():
        for doc in db[coll].find({}, {f: 1 for f in fields}):
            update = {f: encrypt_field(decrypt_field(doc[f])) for f in fields
                      if doc.get(f) and key_version(doc[f]) != new}
            if update:
                db[coll].update_one({"_id": doc["_id"]}, {"$set": update})
                count += len(update)
    retired = keyring.retire_versions(keep=new)
    audit("KEY_ROTATED", user=user["username"], role=user["role"], target="field-keys",
          detail=f"{old} -> {new}; {count} values re-encrypted; retired {','.join(retired)}")
    return jsonify(message=f"Encryption key rotated to {new}", re_encrypted=count, retired=retired), 200
