import argparse
import json
import mimetypes
import os
import re
import sqlite3
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import auth, book_routes, borrow_routes
from .database import initialize, set_user_role
from .security import ApiError, validate_api_key


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
MAX_BODY_SIZE = 1_048_576
DEFAULT_DB = ROOT / "library.db"


class AppConfig:
    def __init__(self, database_path, api_key, jwt_secret):
        self.database_path = str(database_path)
        self.api_key = api_key
        self.jwt_secret = jwt_secret


def make_handler(config):
    class LibraryHandler(BaseHTTPRequestHandler):
        server_version = "LibraryManagementSystem/1.0"

        def _send_json(self, status, payload):
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _send_page(self, filename):
            path = FRONTEND / filename
            try:
                content = path.read_bytes()
            except OSError:
                self._send_json(500, {"error": "Frontend file is unavailable"})
                return
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in ("application/javascript",):
                content_type += "; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(content)

        def _body(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ApiError(400, "Invalid Content-Length") from error
            if length < 0 or length > MAX_BODY_SIZE:
                raise ApiError(413, "Request body is too large")
            if length == 0:
                raise ApiError(400, "A JSON request body is required")
            if "application/json" not in self.headers.get("Content-Type", "").lower():
                raise ApiError(415, "Content-Type must be application/json")
            try:
                body = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ApiError(400, "Request body must be valid JSON") from error
            if not isinstance(body, dict):
                raise ApiError(400, "JSON body must be an object")
            return body

        def _handle_api(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path == "/health" and self.command == "GET":
                self._send_json(200, {"status": "ok"})
                return
            validate_api_key(self.headers.get("X-API-Key", ""), config.api_key)
            if path == "/api/auth/register" and self.command == "POST":
                self._send_json(201, auth.register(config.database_path, self._body()))
                return
            if path == "/api/auth/login" and self.command == "POST":
                self._send_json(200, auth.login(config.database_path, self._body(), config.jwt_secret))
                return

            user = None
            if self.headers.get("Authorization", "").startswith("Bearer "):
                user = auth.current_user(
                    config.database_path, self.headers.get("Authorization", ""), config.jwt_secret
                )
            if path == "/api/auth/me" and self.command == "GET":
                if user is None:
                    raise ApiError(401, "A bearer token is required")
                self._send_json(
                    200,
                    {"user": {"id": int(user["sub"]), "username": user["username"], "role": user["role"]}},
                )
            elif path == "/api/books" and self.command == "GET":
                self._send_json(200, book_routes.list_books(config.database_path, parsed.query))
            elif path == "/api/books" and self.command == "POST":
                status, result = book_routes.create_book(config.database_path, self._body(), user)
                self._send_json(status, result)
            elif path.startswith("/api/books/"):
                book_action = re.fullmatch(r"/api/books/(\d+)/(borrow|return)", path)
                if book_action and self.command == "POST":
                    book_id = int(book_action.group(1))
                    action = book_action.group(2)
                    operation = borrow_routes.borrow if action == "borrow" else borrow_routes.return_book
                    status, result = operation(config.database_path, book_id, user)
                    self._send_json(status, result)
                else:
                    status, result = book_routes.handle_book(
                        config.database_path, self.command, path, self._body_if_needed(), user
                    )
                    self._send_json(status, result)
            elif path == "/api/loans" and self.command == "GET":
                self._send_json(200, borrow_routes.list_loans(config.database_path, user))
            else:
                raise ApiError(404, "Endpoint not found")

        def _body_if_needed(self):
            if self.command in ("PUT", "PATCH"):
                return self._body()
            return {}

        def _handle(self):
            try:
                path = urlparse(self.path).path
                if self.command == "GET" and path in ("/", "/index.html"):
                    self._send_page("index.html")
                elif self.command == "GET" and path in (
                    "/login.html",
                    "/register.html",
                    "/dashboard.html",
                    "/books.html",
                    "/style.css",
                    "/script.js",
                ):
                    self._send_page(path.lstrip("/"))
                elif path == "/favicon.ico":
                    self.send_error(404)
                elif path.startswith("/api/") or path == "/health":
                    self._handle_api()
                else:
                    raise ApiError(404, "Endpoint not found")
            except ApiError as error:
                self._send_json(error.status, {"error": error.message})
            except sqlite3.IntegrityError:
                self._send_json(409, {"error": "A record with that unique value already exists"})
            except Exception:
                self.log_error("Unhandled request error", exc_info=True)
                self._send_json(500, {"error": "Internal server error"})

        def do_GET(self):
            self._handle()

        def do_POST(self):
            self._handle()

        def do_PUT(self):
            self._handle()

        def do_PATCH(self):
            self._handle()

        def do_DELETE(self):
            self._handle()

        def log_message(self, format_string, *args):
            super().log_message(format_string, *args)

    return LibraryHandler


def run_server():
    api_key = os.environ.get("LIBRARY_API_KEY")
    jwt_secret = os.environ.get("JWT_SECRET")
    if not api_key or len(api_key) < 16:
        raise SystemExit("Set LIBRARY_API_KEY to a secret of at least 16 characters.")
    if not jwt_secret or len(jwt_secret) < 32:
        raise SystemExit("Set JWT_SECRET to a secret of at least 32 characters.")
    database_path = os.environ.get("LIBRARY_DB", str(DEFAULT_DB))
    initialize(database_path)
    config = AppConfig(database_path, api_key, jwt_secret)
    host = os.environ.get("LIBRARY_HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, int(os.environ.get("PORT", "8000"))), make_handler(config))
    certificate = os.environ.get("TLS_CERT_FILE")
    private_key = os.environ.get("TLS_KEY_FILE")
    if bool(certificate) != bool(private_key):
        server.server_close()
        raise SystemExit("Set both TLS_CERT_FILE and TLS_KEY_FILE to enable HTTPS.")
    if certificate and private_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=certificate, keyfile=private_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    else:
        scheme = "http (development only)"
    print(f"Library Management System listening on {scheme}://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Library Management System")
    parser.add_argument("--promote", metavar="USERNAME", help="grant an existing user admin access and exit")
    parser.add_argument("--demote", metavar="USERNAME", help="change an admin account back to member and exit")
    args = parser.parse_args()
    if args.promote or args.demote:
        database_path = os.environ.get("LIBRARY_DB", str(DEFAULT_DB))
        role = "admin" if args.promote else "member"
        username = args.promote or args.demote
        changed = set_user_role(database_path, username, role)
        if not changed:
            raise SystemExit(f"No user found with username {username!r}.")
        print(f"Updated {username!r} role to {role}.")
        return
    run_server()


if __name__ == "__main__":
    main()
