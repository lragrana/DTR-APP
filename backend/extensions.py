from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

bcrypt = Bcrypt()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)

_db = None


def init_db(app):
    global _db
    client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000)
    _db = client[app.config["MONGO_DB"]]


def get_db():
    return _db
