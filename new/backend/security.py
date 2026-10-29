import base64
import hashlib
import hmac
import json
import secrets
import time


TOKEN_LIFETIME_SECONDS = 3600
DUMMY_PASSWORD_HASH = None


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"{_b64url(salt)}${_b64url(digest)}"


def verify_password(password, stored_hash):
    try:
        salt_text, digest_text = stored_hash.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return hmac.compare_digest(actual, expected)


def create_token(user_id, username, role, secret):
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": str(user_id),
                "username": username,
                "role": role,
                "iat": now,
                "exp": now + TOKEN_LIFETIME_SECONDS,
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(signature)}"


def verify_token(token, secret):
    try:
        header, payload, signature = token.split(".")
        header_claims = json.loads(base64.urlsafe_b64decode(header + "=" * (-len(header) % 4)))
        if header_claims.get("alg") != "HS256" or header_claims.get("typ") != "JWT":
            raise ValueError("Unsupported token header")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _b64url(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid token signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if claims.get("exp", 0) <= int(time.time()):
            raise ValueError("Expired token")
        if (
            not isinstance(claims.get("sub"), str)
            or not claims["sub"].isdecimal()
            or claims.get("role") not in ("admin", "member")
        ):
            raise ValueError("Invalid token claims")
        return claims
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, AttributeError) as error:
        raise ApiError(401, "Invalid or expired bearer token") from error


def validate_api_key(provided, expected):
    if not hmac.compare_digest(provided or "", expected):
        raise ApiError(401, "A valid X-API-Key header is required")


DUMMY_PASSWORD_HASH = hash_password("constant-time-login-check-password")
