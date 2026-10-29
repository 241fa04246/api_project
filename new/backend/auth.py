from .database import connection
from .models import validate_registration
from .security import (
    DUMMY_PASSWORD_HASH,
    TOKEN_LIFETIME_SECONDS,
    ApiError,
    create_token,
    hash_password,
    verify_password,
    verify_token,
)


def register(database_path, body):
    username, password = validate_registration(body)
    with connection(database_path) as db:
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'member')",
            (username, hash_password(password)),
        )
        return {"id": cursor.lastrowid, "username": username, "role": "member"}


def login(database_path, body, jwt_secret):
    username = body.get("username")
    password = body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        raise ApiError(400, "username and password are required")
    with connection(database_path) as db:
        user = db.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,)
        ).fetchone()
    stored_hash = user["password_hash"] if user else DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, stored_hash)
    if user is None or not password_matches:
        raise ApiError(401, "Invalid username or password")
    token = create_token(user["id"], user["username"], user["role"], jwt_secret)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": TOKEN_LIFETIME_SECONDS,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    }


def current_user(database_path, authorization, jwt_secret):
    if not authorization.startswith("Bearer "):
        raise ApiError(401, "A bearer token is required")
    claims = verify_token(authorization[7:].strip(), jwt_secret)
    with connection(database_path) as db:
        user = db.execute("SELECT username, role FROM users WHERE id = ?", (int(claims["sub"]),)).fetchone()
    if user is None:
        raise ApiError(401, "Invalid or expired bearer token")
    claims["username"] = user["username"]
    claims["role"] = user["role"]
    return claims
