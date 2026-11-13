import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BCRYPT_BYTES = 72


def _user_json(user):
    return {"id": user.id, "full_name": user.full_name, "email": user.email}


def _create_access_token(user):
    secret = current_app.config["JWT_SECRET_KEY"]
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured before issuing tokens.")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(
        minutes=current_app.config["JWT_ACCESS_TOKEN_MINUTES"]
    )
    return jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": expires},
        secret,
        algorithm="HS256",
    )


def _json_body():
    if not request.is_json:
        return None
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _required_string(body, field):
    value = body.get(field)
    return value.strip() if isinstance(value, str) else ""


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return jsonify({"message": "Authentication required."}), 401

        secret = current_app.config["JWT_SECRET_KEY"]
        if not secret:
            current_app.logger.error("JWT_SECRET_KEY is not configured.")
            return jsonify({"message": "Authentication service is unavailable."}), 503

        try:
            payload = jwt.decode(token.strip(), secret, algorithms=["HS256"])
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return jsonify({"message": "Invalid or expired authentication token."}), 401

        user = db.session.get(User, user_id)
        if user is None:
            return jsonify({"message": "Invalid or expired authentication token."}), 401

        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


@auth_bp.post("/register")
def register():
    body = _json_body()
    if body is None:
        return jsonify({"message": "A JSON request body is required."}), 400

    full_name = _required_string(body, "full_name")
    email = _required_string(body, "email").lower()
    password = body.get("password")

    if not full_name or len(full_name) > 120:
        return jsonify({"message": "Name is required and must be at most 120 characters."}), 400
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return jsonify({"message": "Enter a valid email address."}), 400
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"message": "Password must be at least 8 characters."}), 400
    if len(password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        return jsonify({"message": "Password must be at most 72 UTF-8 bytes."}), 400
    if not current_app.config["JWT_SECRET_KEY"]:
        current_app.logger.error("JWT_SECRET_KEY is not configured.")
        return jsonify({"message": "Authentication service is unavailable."}), 503

    if db.session.query(User.id).filter_by(email=email).first():
        return jsonify({"message": "An account with this email already exists."}), 409

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(full_name=full_name, email=email, password_hash=password_hash)
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "An account with this email already exists."}), 409

    return jsonify({"user": _user_json(user), "token": _create_access_token(user)}), 201


@auth_bp.post("/login")
def login():
    body = _json_body()
    if body is None:
        return jsonify({"message": "A JSON request body is required."}), 400

    email = _required_string(body, "email").lower()
    password = body.get("password")
    if not EMAIL_PATTERN.fullmatch(email) or not isinstance(password, str):
        return jsonify({"message": "Email or password is incorrect."}), 401
    if len(password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        return jsonify({"message": "Email or password is incorrect."}), 401
    if not current_app.config["JWT_SECRET_KEY"]:
        current_app.logger.error("JWT_SECRET_KEY is not configured.")
        return jsonify({"message": "Authentication service is unavailable."}), 503

    user = db.session.query(User).filter_by(email=email).first()
    if user is None or not bcrypt.checkpw(
        password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        return jsonify({"message": "Email or password is incorrect."}), 401

    return jsonify({"user": _user_json(user), "token": _create_access_token(user)}), 200


@auth_bp.get("/me")
@token_required
def current_user():
    return jsonify({"user": _user_json(g.current_user)})
