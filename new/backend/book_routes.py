import re
from urllib.parse import parse_qs

from .database import connection
from .models import validate_book
from .security import ApiError


def list_books(database_path, query):
    search = parse_qs(query).get("q", [""])[0].strip()
    with connection(database_path) as db:
        if search:
            books = db.execute(
                "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title",
                (f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    return {"books": [dict(book) for book in books]}


def handle_book(database_path, method, path, body, user):
    match = re.fullmatch(r"/api/books/(\d+)", path)
    if not match:
        raise ApiError(404, "Endpoint not found")
    book_id = int(match.group(1))
    if method == "GET":
        with connection(database_path) as db:
            book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if book is None:
            raise ApiError(404, "Book not found")
        return 200, {"book": dict(book)}
    if method in ("PUT", "PATCH"):
        require_admin(user)
        with connection(database_path) as db:
            existing = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            if existing is None:
                raise ApiError(404, "Book not found")
            book = validate_book(body, partial=method == "PATCH", existing=dict(existing))
            db.execute(
                "UPDATE books SET title = ?, author = ?, isbn = ?, year = ?, copies = ? WHERE id = ?",
                tuple(book[field] for field in ("title", "author", "isbn", "year", "copies")) + (book_id,),
            )
        book["id"] = book_id
        return 200, {"book": book}
    if method == "DELETE":
        require_admin(user)
        with connection(database_path) as db:
            cursor = db.execute("DELETE FROM books WHERE id = ?", (book_id,))
            if cursor.rowcount == 0:
                raise ApiError(404, "Book not found")
        return 200, {"message": "Book deleted"}
    raise ApiError(404, "Endpoint not found")


def create_book(database_path, body, user):
    require_admin(user)
    book = validate_book(body)
    with connection(database_path) as db:
        cursor = db.execute(
            "INSERT INTO books (title, author, isbn, year, copies) VALUES (?, ?, ?, ?, ?)",
            tuple(book[field] for field in ("title", "author", "isbn", "year", "copies")),
        )
        book["id"] = cursor.lastrowid
    return 201, {"book": book}


def require_admin(user):
    if user is None:
        raise ApiError(401, "A bearer token is required")
    if user["role"] != "admin":
        raise ApiError(403, "Insufficient permissions")
