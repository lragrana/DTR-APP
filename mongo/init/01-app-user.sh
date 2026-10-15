#!/bin/bash
# Runs once, when the database volume is first created.
# Creates collections/indexes and a least-privilege application user:
# the app may only INSERT and READ audit logs and alerts (no update/delete = append-only).
set -e
mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin <<JS
const d = db.getSiblingDB("dtr_database");
["users", "attendance", "audit_logs", "alerts", "revoked_tokens"].forEach(c => d.createCollection(c));
d.users.createIndex({ username: 1 }, { unique: true });
d.attendance.createIndex({ username: 1, check_in: -1 });
d.audit_logs.createIndex({ ts: -1 });
d.audit_logs.createIndex({ user: 1, action: 1, ts: -1 });
d.audit_logs.createIndex({ ip: 1, action: 1, ts: -1 });
d.alerts.createIndex({ type: 1, key: 1, ts: -1 });
d.revoked_tokens.createIndex({ jti: 1 }, { unique: true });
d.revoked_tokens.createIndex({ exp: 1 }, { expireAfterSeconds: 0 });
d.createRole({
  role: "dtrAppRole",
  privileges: [
    { resource: { db: "dtr_database", collection: "users" },          actions: ["find", "insert", "update"] },
    { resource: { db: "dtr_database", collection: "attendance" },     actions: ["find", "insert", "update", "remove"] },
    { resource: { db: "dtr_database", collection: "revoked_tokens" }, actions: ["find", "insert"] },
    { resource: { db: "dtr_database", collection: "audit_logs" },     actions: ["find", "insert"] },
    { resource: { db: "dtr_database", collection: "alerts" },         actions: ["find", "insert"] }
  ],
  roles: []
});
d.createUser({ user: "$APP_DB_USER", pwd: "$APP_DB_PASSWORD", roles: [{ role: "dtrAppRole", db: "dtr_database" }] });
JS
