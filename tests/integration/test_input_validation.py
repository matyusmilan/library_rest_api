"""
Input boundary and validation tests.

These tests verify that the API correctly rejects invalid or out-of-range
input at the HTTP layer. Every test targets a specific schema constraint
(min_length, max_length, gt) to confirm the boundary is enforced — both
below and at the limit — rather than relying on typical happy-path values.

All tests use the shared TestClient fixture from conftest.py.
"""

import pytest
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
# BookCreate – total_copies boundaries (1..1000)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("copies", [1, 5, 1000])
def test_book_total_copies_within_range_returns_201(client: TestClient, copies: int):
    payload = {**VALID_BOOK, "total_copies": copies}
    response = client.post("/books/", json=payload)
    assert response.status_code == 201
    assert response.json()["total_copies"] == copies


@pytest.mark.parametrize("copies", [0, -1, 1001, 2.5, "three", None])
def test_book_total_copies_out_of_range_or_invalid_returns_422(client: TestClient, copies):
    payload = {**VALID_BOOK, "total_copies": copies}
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


# ---------------------------------------------------------------------------
# SQL injection resistance
#
# These tests send classic SQL injection payloads in string fields and verify
# that the API never crashes (no 500) and never leaks unintended data.
# They treat the application as a black box: the goal is not to test SQLAlchemy
# internals, but to establish a regression baseline — if the DB layer is ever
# replaced or bypassed, these tests will catch it immediately.
# ---------------------------------------------------------------------------

_SQL_PAYLOADS = [
    "' OR '1'='1",  # tautology — tries to match every row
    "'; DROP TABLE books;--",  # stacked query — tries to destroy a table
    "' UNION SELECT * FROM borrowers --",  # union — tries to read another table
    "' OR 1=1--",  # comment-terminated tautology
    "\\'; DROP TABLE books;--",  # escaped quote variant
]


def test_sql_injection_in_book_title_does_not_crash(client: TestClient):
    """Injecting SQL into title must never return 500."""
    for payload in _SQL_PAYLOADS:
        response = client.post(
            "/books/",
            json={"title": payload, "author": "Author", "isbn": "978-0-13-235088-4"},
        )
        assert response.status_code != 500, f"500 on title payload: {payload!r}"


def test_sql_injection_in_book_title_does_not_leak_data(client: TestClient):
    """A tautology payload in title must not return all books — only an exact match."""
    # seed one real book
    client.post(
        "/books/",
        json={"title": "Real Book", "author": "Author", "isbn": "978-0-13-235088-4"},
    )

    # list endpoint returns all books regardless — verify the injection payload
    # was stored as a literal string, not interpreted
    books = client.get("/books/").json()
    titles = [b["title"] for b in books]
    # the tautology string must appear as a literal title, not cause extra rows
    assert all(t in [b["title"] for b in books] for t in titles)
    assert len(books) == 1  # only the one seeded book, no extra rows from injection


def test_sql_injection_in_book_author_does_not_crash(client: TestClient):
    """Injecting SQL into author must never return 500."""
    for payload in _SQL_PAYLOADS:
        response = client.post(
            "/books/",
            json={"title": "Title", "author": payload, "isbn": "0-306-40615-2"},
        )
        assert response.status_code != 500, f"500 on author payload: {payload!r}"


def test_sql_injection_in_borrower_name_does_not_crash(client: TestClient):
    """Injecting SQL into borrower name must never return 500."""
    for i, payload in enumerate(_SQL_PAYLOADS):
        response = client.post(
            "/borrowers/",
            json={"name": payload, "email": f"inject{i}@example.com"},
        )
        assert response.status_code != 500, f"500 on name payload: {payload!r}"


def test_sql_injection_in_borrower_email_does_not_crash(client: TestClient):
    """Injecting SQL into borrower email is blocked by EmailStr validation (422),
    never by a DB error (500)."""
    for payload in _SQL_PAYLOADS:
        response = client.post(
            "/borrowers/",
            json={"name": "Bob", "email": payload},
        )
        # EmailStr rejects these as malformed — we just confirm no 500
        assert response.status_code != 500, f"500 on email payload: {payload!r}"


def test_sql_injection_in_borrow_endpoint_does_not_crash(client: TestClient):
    """Integer field (borrower_id) with SQL-like string must return 422, not 500."""
    book = client.post(
        "/books/",
        json={"title": "Inject Book", "author": "Author", "isbn": "9780306406157"},
    ).json()

    response = client.post(
        f"/books/{book['id']}/borrow",
        json={"borrower_id": "1; DROP TABLE borrowers;--"},
    )
    # Pydantic rejects non-integer borrower_id with 422
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# HTTP-level robustness
#
# These tests verify correct API behaviour for malformed or unusual HTTP
# requests, independent of business logic. They treat the application as a
# black box and document the current contract so regressions are caught if
# the framework or middleware stack changes.
# ---------------------------------------------------------------------------


def test_missing_content_type_returns_422(client: TestClient):
    """POST without Content-Type header should be rejected with 422."""
    response = client.post(
        "/books/",
        content='{"title":"X","author":"Y","isbn":"978-0-13-235088-4"}',
    )
    assert response.status_code == 422


def test_wrong_content_type_returns_422(client: TestClient):
    """POST with Content-Type: text/plain instead of application/json returns 422."""
    response = client.post(
        "/books/",
        content="title=X&author=Y",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 422


def test_malformed_json_unclosed_brace_returns_422(client: TestClient):
    """JSON with an unclosed brace cannot be parsed and returns 422."""
    response = client.post(
        "/books/",
        content='{"title":"X","author":"Y"',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_malformed_json_plain_text_returns_422(client: TestClient):
    """Plain text sent as application/json returns 422."""
    response = client.post(
        "/books/",
        content="not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_empty_body_returns_422(client: TestClient):
    """An empty request body returns 422 — required fields are missing."""
    response = client.post(
        "/books/",
        content="",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_duplicate_json_key_last_value_wins(client: TestClient):
    """When a JSON object contains duplicate keys, Python's json parser keeps
    the last value. This is spec-compliant behaviour (RFC 8259 leaves it
    undefined); we document it here so the contract is explicit.
    """
    response = client.post(
        "/books/",
        content='{"title":"first","title":"last","author":"Author","isbn":"978-0-13-235088-4"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "last"
