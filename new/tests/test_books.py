from .support import LibraryTestCase


class BookTests(LibraryTestCase):
    def test_admin_can_create_and_search_books(self):
        payload = {
            "title": "The Hobbit",
            "author": "J. R. R. Tolkien",
            "isbn": "9780007525492",
            "year": 1937,
            "copies": 2,
        }
        status, response = self.request("POST", "/api/books", payload, self.admin_token)
        self.assertEqual(status, 201)
        book_id = response["book"]["id"]
        status, response = self.request("GET", "/api/books?q=Hobbit")
        self.assertEqual(status, 200)
        self.assertEqual([book["id"] for book in response["books"]], [book_id])
        status, response = self.request("GET", f"/api/books/{book_id}")
        self.assertEqual(status, 200)
        self.assertEqual(response["book"]["author"], "J. R. R. Tolkien")

    def test_member_cannot_manage_catalog_and_bad_input_is_rejected(self):
        payload = {"title": "Bad", "author": "Author", "isbn": "bad-isbn", "year": True, "copies": -1}
        status, response = self.request("POST", "/api/books", payload, self.member_token)
        self.assertEqual(status, 403)
        status, response = self.request("POST", "/api/books", payload, self.admin_token)
        self.assertEqual(status, 400)
        self.assertIn("year", response["error"])

    def test_admin_can_update_and_delete_books(self):
        payload = {"title": "Dune", "author": "Frank Herbert", "isbn": "9780441172719", "year": 1965, "copies": 1}
        status, response = self.request("POST", "/api/books", payload, self.admin_token)
        self.assertEqual(status, 201)
        book_id = response["book"]["id"]
        status, response = self.request("PATCH", f"/api/books/{book_id}", {"copies": 3}, self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(response["book"]["copies"], 3)
        status, _ = self.request("DELETE", f"/api/books/{book_id}", token=self.admin_token)
        self.assertEqual(status, 200)
        status, _ = self.request("GET", f"/api/books/{book_id}")
        self.assertEqual(status, 404)
