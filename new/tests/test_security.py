from backend.database import connection
from backend.security import hash_password, verify_password
from http.client import HTTPConnection
from .support import LibraryTestCase


class SecurityTests(LibraryTestCase):
    def test_api_key_is_required_for_api_but_not_health(self):
        status, response = self.request("GET", "/api/books", api_key="wrong-api-key")
        self.assertEqual(status, 401)
        self.assertIn("X-API-Key", response["error"])
        status, response = self.request("GET", "/health", api_key="")
        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "ok")

    def test_token_is_required_for_private_routes_and_admin_role_is_enforced(self):
        status, _ = self.request("GET", "/api/loans")
        self.assertEqual(status, 401)
        payload = {"title": "Test", "author": "Author", "isbn": "test-security-isbn", "year": 2020, "copies": 1}
        status, _ = self.request("POST", "/api/books", payload)
        self.assertEqual(status, 401)
        status, _ = self.request("POST", "/api/books", payload, self.member_token)
        self.assertEqual(status, 403)
        status, profile = self.request("GET", "/api/auth/me", token="not.a.valid.token")
        self.assertEqual(status, 401)

    def test_password_hash_is_salted_and_verified(self):
        first = hash_password("a-long-password")
        second = hash_password("a-long-password")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("a-long-password", first))
        self.assertFalse(verify_password("not-the-password", first))
        with connection(self.db_path) as db:
            stored = db.execute("SELECT password_hash FROM users WHERE username = 'bookreader'").fetchone()[0]
        self.assertNotEqual(stored, "member-password-123")

    def test_browser_pages_are_served_with_security_headers(self):
        connection = HTTPConnection("127.0.0.1", self.port)
        connection.request("GET", "/")
        response = connection.getresponse()
        html = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("Reading Room", html)
        self.assertIn("frame-ancestors 'none'", response.getheader("Content-Security-Policy"))
        connection.close()

        connection = HTTPConnection("127.0.0.1", self.port)
        connection.request("GET", "/script.js")
        response = connection.getresponse()
        script = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn('request("/auth/me")', script)
        connection.close()
