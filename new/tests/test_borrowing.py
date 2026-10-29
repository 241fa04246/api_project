from .support import LibraryTestCase


class BorrowingTests(LibraryTestCase):
    def test_member_borrow_return_and_loan_visibility(self):
        payload = {"title": "Dune", "author": "Frank Herbert", "isbn": "9780441172719", "year": 1965, "copies": 1}
        status, response = self.request("POST", "/api/books", payload, self.admin_token)
        self.assertEqual(status, 201)
        book_id = response["book"]["id"]

        status, borrowed = self.request(
            "POST", f"/api/books/{book_id}/borrow", token=self.member_token
        )
        self.assertEqual(status, 201)
        status, response = self.request("POST", f"/api/books/{book_id}/borrow", token=self.member_token)
        self.assertEqual(status, 409)

        status, loans = self.request("GET", "/api/loans", token=self.member_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(loans["loans"]), 1)
        self.assertEqual(loans["loans"][0]["id"], borrowed["loan_id"])

        status, returned = self.request(
            "POST", f"/api/books/{book_id}/return", token=self.member_token
        )
        self.assertEqual(status, 200)
        self.assertEqual(returned["status"], "returned")
        status, _ = self.request("POST", f"/api/books/{book_id}/return", token=self.member_token)
        self.assertEqual(status, 404)

    def test_other_member_cannot_return_a_loan(self):
        payload = {"title": "Solaris", "author": "Stanislaw Lem", "isbn": "9780156027601", "year": 1961, "copies": 1}
        status, response = self.request("POST", "/api/books", payload, self.admin_token)
        self.assertEqual(status, 201)
        book_id = response["book"]["id"]
        self.request("POST", f"/api/books/{book_id}/borrow", token=self.member_token)
        self.register("anotherreader", "another-long-password")
        other_token = self.login("anotherreader", "another-long-password")
        status, _ = self.request("POST", f"/api/books/{book_id}/return", token=other_token)
        self.assertEqual(status, 404)
