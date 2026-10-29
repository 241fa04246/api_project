import re
import time

from .security import ApiError


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
BOOK_FIELDS = ("title", "author", "isbn", "year", "copies")


def validate_registration(body):
    username = body.get("username")
    password = body.get("password")
    if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
        raise ApiError(400, "username must be 3-32 letters, numbers, dots, underscores, or hyphens")
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise ApiError(400, "password must be between 10 and 128 characters")
    return username, password


def validate_book(body, partial=False, existing=None):
    if not isinstance(body, dict):
        raise ApiError(400, "JSON body must be an object")
    if not partial and any(field not in body for field in BOOK_FIELDS):
        raise ApiError(400, "title, author, isbn, year, and copies are required")
    result = dict(existing or {})
    for field in BOOK_FIELDS:
        if field in body:
            result[field] = body[field]
    for field in ("title", "author", "isbn"):
        value = result.get(field)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
            raise ApiError(400, f"{field} must be a non-empty string of at most 200 characters")
        result[field] = value.strip()
    for field, minimum, maximum in (
        ("year", 0, time.gmtime().tm_year + 1),
        ("copies", 0, 100_000),
    ):
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ApiError(400, f"{field} must be an integer between {minimum} and {maximum}")
    return result
