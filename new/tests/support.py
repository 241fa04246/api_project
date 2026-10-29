import json
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from http.client import HTTPConnection

from backend.database import initialize
from backend.main import AppConfig, make_handler
from http.server import ThreadingHTTPServer


class LibraryTestCase(unittest.TestCase):
    api_key = "test-api-key-123456"
    jwt_secret = "test-jwt-secret-that-is-at-least-32-chars"

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.temp_dir.name, "test.db")
        initialize(cls.db_path)
        config = AppConfig(cls.db_path, cls.api_key, cls.jwt_secret)
        base_handler = make_handler(config)

        class QuietHandler(base_handler):
            def log_message(self, format_string, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port
        cls.admin_id = cls.register("administrator", "admin-password-123")["id"]
        with closing(sqlite3.connect(cls.db_path)) as db, db:
            db.execute("UPDATE users SET role = 'admin' WHERE id = ?", (cls.admin_id,))
        cls.admin_token = cls.login("administrator", "admin-password-123")
        cls.member_id = cls.register("bookreader", "member-password-123")["id"]
        cls.member_token = cls.login("bookreader", "member-password-123")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp_dir.cleanup()

    @classmethod
    def request(cls, method, path, body=None, token=None, api_key=None):
        connection = HTTPConnection("127.0.0.1", cls.port)
        headers = {"X-API-Key": cls.api_key if api_key is None else api_key}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        data = response.read()
        status = response.status
        connection.close()
        return status, json.loads(data) if data else None

    @classmethod
    def register(cls, username, password):
        status, response = cls.request(
            "POST", "/api/auth/register", {"username": username, "password": password}
        )
        if status != 201:
            raise AssertionError(response)
        return response

    @classmethod
    def login(cls, username, password):
        status, response = cls.request(
            "POST", "/api/auth/login", {"username": username, "password": password}
        )
        if status != 200:
            raise AssertionError(response)
        return response["access_token"]
