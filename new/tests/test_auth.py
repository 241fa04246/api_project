from .support import LibraryTestCase


class AuthenticationTests(LibraryTestCase):
    def test_registration_login_and_profile(self):
        created = self.register("newreader", "a-long-member-password")
        self.assertEqual(created["role"], "member")
        token = self.login("newreader", "a-long-member-password")
        status, profile = self.request("GET", "/api/auth/me", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(profile["user"]["username"], "newreader")
        self.assertEqual(profile["user"]["role"], "member")

    def test_registration_and_login_validation(self):
        status, response = self.request(
            "POST", "/api/auth/register", {"username": "x", "password": "short"}
        )
        self.assertEqual(status, 400)
        self.assertIn("username", response["error"])
        status, response = self.request(
            "POST", "/api/auth/login", {"username": "bookreader", "password": "wrong-password"}
        )
        self.assertEqual(status, 401)
        self.assertIn("Invalid username or password", response["error"])

    def test_public_registration_cannot_assign_admin_role(self):
        status, user = self.request(
            "POST",
            "/api/auth/register",
            {"username": "ordinaryuser", "password": "another-long-password", "role": "admin"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(user["role"], "member")
