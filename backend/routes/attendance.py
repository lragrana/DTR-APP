from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request

from audit import audit
from extensions import get_db
from security import (USERNAME_RE, ValidationError, decrypt_field, encrypt_field, get_str,
                      json_body, reauthenticate, roles_required)

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


def _out(rec):
    return {
        "id": str(rec["_id"]),
        "username": rec["username"],
        "check_in": rec["check_in"].isoformat(),
        "check_out": rec["check_out"].isoformat() if rec.get("check_out") else None,
        "notes": decrypt_field(rec.get("notes_enc")),
    }


@attendance_bp.post("/check-in")
@roles_required("intern", "supervisor", "admin")
def check_in(user):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    notes = get_str(data, "notes", required=False, max_len=200)
    db = get_db()
    # The user is always taken from the token, never from the request body.
    if db.attendance.find_one({"username": user["username"], "check_out": None}):
        return jsonify(error="You are already checked in"), 409
    rec = {"username": user["username"], "check_in": datetime.now(timezone.utc),
           "check_out": None, "notes_enc": encrypt_field(notes)}
    rec_id = db.attendance.insert_one(rec).inserted_id
    audit("CHECK_IN", user=user["username"], role=user["role"], target=str(rec_id))
    return jsonify(message="Checked in", id=str(rec_id)), 201


@attendance_bp.post("/check-out")
@roles_required("intern", "supervisor", "admin")
def check_out(user):
    db = get_db()
    rec = db.attendance.find_one({"username": user["username"], "check_out": None})
    if not rec:
        return jsonify(error="You are not checked in"), 409
    db.attendance.update_one({"_id": rec["_id"]}, {"$set": {"check_out": datetime.now(timezone.utc)}})
    audit("CHECK_OUT", user=user["username"], role=user["role"], target=str(rec["_id"]))
    return jsonify(message="Checked out"), 200


@attendance_bp.get("/me")
@roles_required("intern", "supervisor", "admin")
def my_records(user):
    recs = get_db().attendance.find({"username": user["username"]}).sort("check_in", -1).limit(100)
    return jsonify([_out(r) for r in recs]), 200


@attendance_bp.get("")
@roles_required("supervisor", "admin")
def all_records(user):
    query = {}
    username = request.args.get("username")
    if username:
        if not USERNAME_RE.match(username):
            raise ValidationError("Invalid username filter")
        query["username"] = username
    recs = get_db().attendance.find(query).sort("check_in", -1).limit(500)
    audit("VIEW_ALL_ATTENDANCE", user=user["username"], role=user["role"], target=username)
    return jsonify([_out(r) for r in recs]), 200


@attendance_bp.delete("/<record_id>")
@roles_required("admin")
def delete_record(user, record_id):
    data = json_body()
    if not reauthenticate(user, data):
        audit("REAUTH_FAILED", user=user["username"], role=user["role"], target=record_id, success=False)
        return jsonify(error="Re-authentication required: enter your password"), 401
    if not ObjectId.is_valid(record_id):
        raise ValidationError("Invalid record id")
    result = get_db().attendance.delete_one({"_id": ObjectId(record_id)})
    if not result.deleted_count:
        return jsonify(error="Record not found"), 404
    audit("ATTENDANCE_DELETE", user=user["username"], role=user["role"], target=record_id)
    return jsonify(message="Record deleted"), 200
