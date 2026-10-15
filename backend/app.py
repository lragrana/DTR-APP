import logging
from datetime import datetime, timezone

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import bcrypt, get_db, init_db, jwt, limiter
from routes.admin import admin_bp
from routes.attendance import attendance_bp
from routes.auth import auth_bp
from security import ValidationError, hash_password, password_problems


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # nginx is the only proxy in front of the app; trust exactly one hop.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    init_db(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)

    @jwt.token_in_blocklist_loader
    def token_revoked(_header, payload):
        return get_db().revoked_tokens.find_one({"jti": payload["jti"]}) is not None

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return jsonify(error="Authentication required"), 401

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return jsonify(error="Invalid token"), 401

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return jsonify(error="Session expired, please log in again"), 401

    @jwt.revoked_token_loader
    def revoked_token(_header, _payload):
        return jsonify(error="Session has been logged out"), 401

    @app.get("/api/health")
    @limiter.exempt
    def health():
        return jsonify(status="ok"), 200

    @app.errorhandler(ValidationError)
    def validation_error(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.name), e.code

    @app.errorhandler(Exception)
    def unexpected_error(e):
        # Details go to the server log only; clients get a generic message.
        app.logger.exception("Unhandled error")
        return jsonify(error="Internal server error"), 500

    @app.after_request
    def api_headers(resp):
        # Browser security headers are added by nginx; API data must never be cached.
        resp.headers["Cache-Control"] = "no-store"
        return resp

    with app.app_context():
        _seed_admin(app)
    return app


def _seed_admin(app):
    username, password = app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"]
    if not username or not password:
        return
    if password_problems(password, username):
        raise RuntimeError("ADMIN_PASSWORD does not meet the password policy")
    get_db().users.update_one(
        {"username": username},
        {"$setOnInsert": {"username": username, "password_hash": hash_password(password),
                          "full_name_enc": None, "role": "admin", "failed_attempts": 0,
                          "locked_until": None, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
