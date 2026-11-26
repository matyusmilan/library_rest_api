"""
Integration tests for the /borrowers endpoints.

These tests exercise the full HTTP stack (routing → service → SQLAlchemy → SQLite)
using a real in-memory database, verifying all layers work together end-to-end.
"""

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BORROWER_PAYLOAD = {"name": "Alice Smith", "email": "alice@example.com"}
BOOK_PAYLOAD = {"title": "Clean Code", "author": "Robert C. Martin", "isbn": "978-0-13-235088-4"}


def _create_borrower(client: TestClient, payload: dict | None = None) -> dict:
    response = client.post("/borrowers/", json=payload or BORROWER_PAYLOAD)
    assert response.status_code == 201
    return response.json()


def _create_book(client: TestClient) -> dict:
    response = client.post("/books/", json=BOOK_PAYLOAD)
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# POST /borrowers/
# ---------------------------------------------------------------------------


def test_create_borrower_returns_201_with_borrower(client: TestClient):
    response = client.post("/borrowers/", json=BORROWER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == BORROWER_PAYLOAD["name"]
    assert body["email"] == BORROWER_PAYLOAD["email"]
    assert "id" in body


def test_create_borrower_duplicate_email_returns_409(client: TestClient):
    _create_borrower(client)

    response = client.post("/borrowers/", json=BORROWER_PAYLOAD)

    assert response.status_code == 409


def test_create_borrower_invalid_email_returns_422(client: TestClient):
    response = client.post("/borrowers/", json={"name": "Bob", "email": "not-an-email"})

    assert response.status_code == 422


def test_create_borrower_missing_name_returns_422(client: TestClient):
    response = client.post("/borrowers/", json={"email": "bob@example.com"})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /borrowers/{borrower_id}
# ---------------------------------------------------------------------------


def test_get_borrower_success(client: TestClient):
    borrower = _create_borrower(client)

    response = client.get(f"/borrowers/{borrower['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == borrower["id"]
    assert response.json()["email"] == borrower["email"]


def test_get_borrower_not_found_returns_404(client: TestClient):
    response = client.get("/borrowers/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /borrowers/{borrower_id}/books
# ---------------------------------------------------------------------------


def test_get_borrowed_books_empty(client: TestClient):
    borrower = _create_borrower(client)

    response = client.get(f"/borrowers/{borrower['id']}/books")

    assert response.status_code == 200
    assert response.json() == []


def test_get_borrowed_books_returns_borrowed_book(client: TestClient):
    borrower = _create_borrower(client)
    book = _create_book(client)
    client.post(f"/books/{book['id']}/borrow", json={"borrower_id": borrower["id"]})

    response = client.get(f"/borrowers/{borrower['id']}/books")

    assert response.status_code == 200
    books = response.json()
    assert len(books) == 1
    assert books[0]["id"] == book["id"]
    assert books[0]["available_copies"] == 0


def test_get_borrowed_books_borrower_not_found_returns_404(client: TestClient):
    response = client.get("/borrowers/9999/books")

    assert response.status_code == 404
