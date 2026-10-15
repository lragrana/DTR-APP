from datetime import datetime, timedelta, timezone

from flask import current_app, request

from extensions import get_db

EDIT_ACTIONS = ["CHECK_IN", "CHECK_OUT", "ATTENDANCE_DELETE", "ROLE_CHANGE"]
EDIT_ALERT_THRESHOLD = 20      # edits per user per minute
FAILED_LOGIN_ALERT_THRESHOLD = 5  # failed logins per source IP in 5 minutes


def audit(action, *, user=None, role=None, target=None, success=True, detail=None):
    """R-006: append-only audit trail (the app's DB role can insert and read, never update or delete)."""
    entry = {
        "ts": datetime.now(timezone.utc),
        "user": user,
        "role": role,
        "action": action,
        "target": target,
        "success": success,
        "detail": detail,
        "ip": request.remote_addr,
    }
    get_db().audit_logs.insert_one(entry)
    current_app.logger.info("AUDIT action=%s user=%s target=%s success=%s ip=%s",
                            action, user, target, success, entry["ip"])
    _check_anomalies(entry)


def _raise_alert(kind, key, count):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(minutes=5)
    if db.alerts.find_one({"type": kind, "key": key, "ts": {"$gte": since}}):
        return
    db.alerts.insert_one({"ts": datetime.now(timezone.utc), "type": kind, "key": key, "count": count})
    current_app.logger.warning("SECURITY ALERT type=%s key=%s count=%s", kind, key, count)


def _check_anomalies(entry):
    db = get_db()
    now = datetime.now(timezone.utc)
    if entry["action"] in EDIT_ACTIONS and entry["user"]:
        edits = db.audit_logs.count_documents(
            {"user": entry["user"], "action": {"$in": EDIT_ACTIONS}, "ts": {"$gte": now - timedelta(minutes=1)}})
        if edits > EDIT_ALERT_THRESHOLD:
            _raise_alert("HIGH_FREQUENCY_EDITS", entry["user"], edits)
    if entry["action"] == "LOGIN_FAILED":
        failures = db.audit_logs.count_documents(
            {"ip": entry["ip"], "action": "LOGIN_FAILED", "ts": {"$gte": now - timedelta(minutes=5)}})
        if failures >= FAILED_LOGIN_ALERT_THRESHOLD:
            _raise_alert("REPEATED_FAILED_LOGINS", entry["ip"], failures)
