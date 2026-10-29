import sqlite3
from contextlib import contextmanager


@contextmanager
def connection(database_path):
    db = sqlite3.connect(database_path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(database_path):
    with connection(database_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'member'))
            );
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                copies INTEGER NOT NULL CHECK (copies >= 0)
            );
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                book_id INTEGER NOT NULL REFERENCES books(id),
                borrowed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                returned_at TEXT
            );
            """
        )


def set_user_role(database_path, username, role):
    if role not in ("admin", "member"):
        raise ValueError("role must be admin or member")
    with connection(database_path) as db:
        cursor = db.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        return cursor.rowcount
