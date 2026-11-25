"""
Input boundary and validation tests.

These tests verify that the API correctly rejects invalid or out-of-range
input at the HTTP layer. Every test targets a specific schema constraint
(min_length, max_length, gt) to confirm the boundary is enforced — both
below and at the limit — rather than relying on typical happy-path values.

All tests use the shared TestClient fixture from conftest.py.
"""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_BOOK = {
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "isbn": "978-0-13-235088-4",  # valid ISBN-13
}

VALID_BORROWER = {"name": "Alice", "email": "alice@example.com"}


def _create_borrower(client: TestClient) -> dict:
    r = client.post("/borrowers/", json=VALID_BORROWER)
    assert r.status_code == 201
    return r.json()


def _create_book(client: TestClient, payload: dict | None = None) -> dict:
    r = client.post("/books/", json=payload or VALID_BOOK)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# BookCreate – title boundaries
# ---------------------------------------------------------------------------


def test_book_title_empty_string_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "title": ""}
    assert client.post("/books/", json=payload).status_code == 422


def test_book_title_at_max_length_returns_201(client: TestClient):
    payload = {**VALID_BOOK, "title": "A" * 255}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_title_exceeds_max_length_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "title": "A" * 256}
    assert client.post("/books/", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# BookCreate – author boundaries
# ---------------------------------------------------------------------------


def test_book_author_empty_string_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "author": ""}
    assert client.post("/books/", json=payload).status_code == 422


def test_book_author_at_max_length_returns_201(client: TestClient):
    payload = {**VALID_BOOK, "author": "B" * 255, "isbn": "0306406152"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_author_exceeds_max_length_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "author": "B" * 256}
    assert client.post("/books/", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# BookCreate – isbn format validation
# ---------------------------------------------------------------------------


def test_book_isbn10_compact_valid(client: TestClient):
    # compact ISBN-10 without hyphens
    payload = {**VALID_BOOK, "isbn": "0306406152", "title": "ISBN-10 compact"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_isbn10_hyphenated_valid(client: TestClient):
    payload = {**VALID_BOOK, "isbn": "0-306-40615-2", "title": "ISBN-10 hyphenated"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_isbn10_with_x_check_digit_valid(client: TestClient):
    # X is a valid check digit for ISBN-10
    payload = {**VALID_BOOK, "isbn": "0-306-40615-X", "title": "ISBN-10 X check"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_isbn13_compact_valid(client: TestClient):
    payload = {**VALID_BOOK, "isbn": "9780306406157", "title": "ISBN-13 compact"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_isbn13_hyphenated_valid(client: TestClient):
    payload = {**VALID_BOOK, "isbn": "978-0-306-40615-7", "title": "ISBN-13 hyphenated"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_isbn13_979_prefix_valid(client: TestClient):
    # ISBN-13 can start with 979 as well as 978
    payload = {**VALID_BOOK, "isbn": "9790306406157", "title": "ISBN-13 979 prefix"}
    assert client.post("/books/", json=payload).status_code == 201


def test_book_isbn_random_string_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "isbn": "notanisbn"}
    assert client.post("/books/", json=payload).status_code == 422


def test_book_isbn_all_letters_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "isbn": "ABCDEFGHIJ"}
    assert client.post("/books/", json=payload).status_code == 422


def test_book_isbn_wrong_length_digits_returns_422(client: TestClient):
    # 11 digits — not a valid ISBN-10 or ISBN-13 length
    payload = {**VALID_BOOK, "isbn": "12345678901"}
    assert client.post("/books/", json=payload).status_code == 422


def test_book_isbn13_wrong_prefix_returns_422(client: TestClient):
    # ISBN-13 must start with 978 or 979; 977 is invalid
    payload = {**VALID_BOOK, "isbn": "9770306406157"}
    assert client.post("/books/", json=payload).status_code == 422


def test_book_isbn_special_characters_returns_422(client: TestClient):
    payload = {**VALID_BOOK, "isbn": "!@#$%^&*()"}
    assert client.post("/books/", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# BorrowRequest – borrower_id boundaries
# ---------------------------------------------------------------------------


def test_borrow_borrower_id_zero_returns_422(client: TestClient):
    book = _create_book(client)
    assert client.post(f"/books/{book['id']}/borrow", json={"borrower_id": 0}).status_code == 422


def test_borrow_borrower_id_negative_returns_422(client: TestClient):
    book = _create_book(client, {**VALID_BOOK, "isbn": "0-306-40615-2", "title": "Borrow neg test"})
    assert client.post(f"/books/{book['id']}/borrow", json={"borrower_id": -1}).status_code == 422


def test_borrow_borrower_id_one_is_valid_gt_constraint(client: TestClient):
    # borrower_id=1 satisfies gt=0; borrower doesn't exist → 404, not 422
    book = _create_book(client, {**VALID_BOOK, "isbn": "9780306406157", "title": "Borrow gt test"})
    assert client.post(f"/books/{book['id']}/borrow", json={"borrower_id": 1}).status_code == 404


# ---------------------------------------------------------------------------
# BorrowerCreate – name boundaries
# ---------------------------------------------------------------------------


def test_borrower_name_empty_string_returns_422(client: TestClient):
    payload = {**VALID_BORROWER, "name": "", "email": "empty@example.com"}
    assert client.post("/borrowers/", json=payload).status_code == 422


def test_borrower_name_at_max_length_returns_201(client: TestClient):
    payload = {"name": "C" * 255, "email": "maxname@example.com"}
    assert client.post("/borrowers/", json=payload).status_code == 201


def test_borrower_name_exceeds_max_length_returns_422(client: TestClient):
    payload = {"name": "C" * 256, "email": "toolong@example.com"}
    assert client.post("/borrowers/", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# BorrowerCreate – email boundaries
# ---------------------------------------------------------------------------


def test_borrower_email_no_at_sign_returns_422(client: TestClient):
    payload = {"name": "Bob", "email": "notanemail"}
    assert client.post("/borrowers/", json=payload).status_code == 422


def test_borrower_email_missing_domain_returns_422(client: TestClient):
    payload = {"name": "Bob", "email": "bob@"}
    assert client.post("/borrowers/", json=payload).status_code == 422


def test_borrower_email_whitespace_only_returns_422(client: TestClient):
    payload = {"name": "Bob", "email": "   "}
    assert client.post("/borrowers/", json=payload).status_code == 422
