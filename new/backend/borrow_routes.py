from .database import connection
from .security import ApiError


def borrow(database_path, book_id, user):
    if user is None:
        raise ApiError(401, "A bearer token is required")
    if user["role"] != "member":
        raise ApiError(403, "Only members can borrow books")
    with connection(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if book is None:
            raise ApiError(404, "Book not found")
        if book["copies"] < 1:
            raise ApiError(409, "No copies are currently available")
        db.execute("UPDATE books SET copies = copies - 1 WHERE id = ?", (book_id,))
        cursor = db.execute(
            "INSERT INTO loans (user_id, book_id) VALUES (?, ?)", (int(user["sub"]), book_id)
        )
        return 201, {"loan_id": cursor.lastrowid, "book_id": book_id, "status": "borrowed"}


def return_book(database_path, book_id, user):
    if user is None:
        raise ApiError(401, "A bearer token is required")
    with connection(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        loan = db.execute(
            "SELECT id FROM loans WHERE book_id = ? AND user_id = ? AND returned_at IS NULL "
            "ORDER BY id LIMIT 1",
            (book_id, int(user["sub"])),
        ).fetchone()
        if loan is None:
            raise ApiError(404, "No active loan found for this book")
        db.execute("UPDATE loans SET returned_at = CURRENT_TIMESTAMP WHERE id = ?", (loan["id"],))
        db.execute("UPDATE books SET copies = copies + 1 WHERE id = ?", (book_id,))
    return 200, {"loan_id": loan["id"], "book_id": book_id, "status": "returned"}


def list_loans(database_path, user):
    if user is None:
        raise ApiError(401, "A bearer token is required")
    with connection(database_path) as db:
        if user["role"] == "admin":
            loans = db.execute(
                "SELECT loans.*, users.username, books.title FROM loans "
                "JOIN users ON users.id = loans.user_id JOIN books ON books.id = loans.book_id "
                "ORDER BY loans.id DESC"
            ).fetchall()
        else:
            loans = db.execute(
                "SELECT loans.*, books.title FROM loans JOIN books ON books.id = loans.book_id "
                "WHERE loans.user_id = ? ORDER BY loans.id DESC",
                (int(user["sub"]),),
            ).fetchall()
    return {"loans": [dict(loan) for loan in loans]}
