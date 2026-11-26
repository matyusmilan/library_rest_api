"""
Integration tests for the /books endpoints.

These tests exercise the full HTTP stack (routing → service → SQLAlchemy → SQLite)
using a real in-memory database, so they verify that all layers work together
correctly end-to-end.
"""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOOK_PAYLOAD = {"title": "Clean Code", "author": "Robert C. Martin", "isbn": "978-0-13-235088-4"}
BOOK_PAYLOAD_2 = {
    "title": "The Pragmatic Programmer",
    "author": "David Thomas",
    "isbn": "978-0-13-595705-9",
}


def _create_book(client: TestClient, payload: dict | None = None) -> dict:
    response = client.post("/books/", json=payload or BOOK_PAYLOAD)
    assert response.status_code == 201
    return response.json()


def _create_borrower(client: TestClient) -> dict:
    response = client.post("/borrowers/", json={"name": "Alice", "email": "alice@example.com"})
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# GET /books/
# ---------------------------------------------------------------------------


def test_list_books_empty(client: TestClient):
    response = client.get("/books/")

    assert response.status_code == 200
    assert response.json() == []


def test_list_books_returns_added_books(client: TestClient):
    _create_book(client, BOOK_PAYLOAD)
    _create_book(client, BOOK_PAYLOAD_2)

    response = client.get("/books/")

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# POST /books/
# ---------------------------------------------------------------------------


def test_create_book_returns_201_with_book(client: TestClient):
    response = client.post("/books/", json=BOOK_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == BOOK_PAYLOAD["title"]
    assert body["isbn"] == BOOK_PAYLOAD["isbn"]


def test_create_book_defaults_to_single_available_copy(client: TestClient):
    body = client.post("/books/", json=BOOK_PAYLOAD).json()

    assert body["total_copies"] == 1
    assert body["available_copies"] == 1


def test_create_book_with_multiple_copies_makes_all_available(client: TestClient):
    body = client.post("/books/", json={**BOOK_PAYLOAD, "total_copies": 5}).json()

    assert body["total_copies"] == 5
    assert body["available_copies"] == 5


def test_create_book_duplicate_isbn_returns_409(client: TestClient):
    _create_book(client)

    response = client.post("/books/", json=BOOK_PAYLOAD)

    assert response.status_code == 409


def test_create_book_missing_field_returns_422(client: TestClient):
    response = client.post("/books/", json={"title": "Incomplete"})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /books/{book_id}/borrow
# ---------------------------------------------------------------------------


def test_borrow_book_success(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client)

    response = client.post(f"/books/{book['id']}/borrow", json={"borrower_id": borrower["id"]})

    assert response.status_code == 200
    body = response.json()
    assert body["total_copies"] == 1
    assert body["available_copies"] == 0


def test_borrow_book_not_found_returns_404(client: TestClient):
    _create_borrower(client)

    response = client.post("/books/9999/borrow", json={"borrower_id": 1})

    assert response.status_code == 404


def test_borrow_book_twice_by_same_borrower_returns_409(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client)
    client.post(f"/books/{book['id']}/borrow", json={"borrower_id": borrower["id"]})

    response = client.post(f"/books/{book['id']}/borrow", json={"borrower_id": borrower["id"]})

    assert response.status_code == 409


def test_borrow_book_borrower_not_found_returns_404(client: TestClient):
    book = _create_book(client)

    response = client.post(f"/books/{book['id']}/borrow", json={"borrower_id": 9999})

    assert response.status_code == 404
