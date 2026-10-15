from flask import Blueprint, jsonify, request

from audit import audit
from extensions import get_db
from security import ROLES, ValidationError, get_str, json_body, reauthenticate, roles_required, USERNAME_RE

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/users")
@roles_required("admin")
def list_users(user):
    users = get_db().users.find({}, {"_id": 0, "username": 1, "role": 1, "locked_until": 1})
    return jsonify([{"username": u["username"], "role": u["role"],
                     "locked": bool(u.get("locked_until"))} for u in users]), 200


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
