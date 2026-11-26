"""
Integration tests for changing and removing records: PATCH and DELETE on
/books/{id} and /borrowers/{id}.
"""

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _isbn(n: int) -> str:
    return f"978000000{n:04d}"


def _create_book(client: TestClient, n: int = 1, copies: int = 1) -> dict:
    payload = {"title": f"Book {n}", "author": f"Author {n}", "isbn": _isbn(n)}
    response = client.post("/books/", json={**payload, "total_copies": copies})
    assert response.status_code == 201
    return response.json()


def _create_borrower(client: TestClient, n: int = 1) -> dict:
    payload = {"name": f"User {n}", "email": f"user{n}@example.com"}
    response = client.post("/borrowers/", json=payload)
    assert response.status_code == 201
    return response.json()


def _borrow(client: TestClient, book_id: int, borrower_id: int) -> None:
    response = client.post(f"/books/{book_id}/borrow", json={"borrower_id": borrower_id})
    assert response.status_code == 200


def _get_book(client: TestClient, book_id: int) -> dict:
    return client.get(f"/books/{book_id}").json()


# ---------------------------------------------------------------------------
# PATCH /books/{id}
# ---------------------------------------------------------------------------


def test_patch_book_changes_only_the_sent_fields(client: TestClient):
    book = _create_book(client)

    response = client.patch(f"/books/{book['id']}", json={"title": "New title"})

    assert response.status_code == 200
    assert response.json() == {**book, "title": "New title"}


def test_patch_book_isbn_of_another_book_returns_409(client: TestClient):
    first, second = _create_book(client, 1), _create_book(client, 2)

    response = client.patch(f"/books/{second['id']}", json={"isbn": first["isbn"]})

    assert response.status_code == 409
    assert _get_book(client, second["id"])["isbn"] == second["isbn"]


def test_patch_book_with_its_own_isbn_is_not_a_conflict(client: TestClient):
    book = _create_book(client)

    response = client.patch(f"/books/{book['id']}", json={"isbn": book["isbn"], "title": "T"})

    assert response.status_code == 200


def test_patch_book_to_a_new_isbn(client: TestClient):
    book = _create_book(client)

    response = client.patch(f"/books/{book['id']}", json={"isbn": "0-306-40615-2"})

    assert response.json()["isbn"] == "0-306-40615-2"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": None},
        {"title": ""},
        {"isbn": "notanisbn"},
        {"total_copies": 0},
        {"total_copies": 1001},
        {"total_copies": "many"},
    ],
)
def test_patch_book_with_an_invalid_body_returns_422(client: TestClient, body: dict):
    book = _create_book(client)

    assert client.patch(f"/books/{book['id']}", json=body).status_code == 422


def test_patch_unknown_book_returns_404(client: TestClient):
    assert client.patch("/books/9999", json={"title": "x"}).status_code == 404


def test_patch_total_copies_up_makes_the_new_copies_available(client: TestClient):
    book = _create_book(client, copies=1)

    body = client.patch(f"/books/{book['id']}", json={"total_copies": 4}).json()

    assert (body["total_copies"], body["available_copies"]) == (4, 4)


def test_patch_total_copies_keeps_the_copies_on_loan_out_of_stock(client: TestClient):
    book = _create_book(client, copies=3)
    for n in (1, 2):
        _borrow(client, book["id"], _create_borrower(client, n)["id"])  # 2 on loan, 1 free

    grown = client.patch(f"/books/{book['id']}", json={"total_copies": 5}).json()
    shrunk = client.patch(f"/books/{book['id']}", json={"total_copies": 2}).json()

    assert (grown["total_copies"], grown["available_copies"]) == (5, 3)
    assert (shrunk["total_copies"], shrunk["available_copies"]) == (2, 0)  # exactly the loans


def test_patch_total_copies_below_the_loans_returns_409_and_changes_nothing(client: TestClient):
    book = _create_book(client, copies=3)
    for n in (1, 2):
        _borrow(client, book["id"], _create_borrower(client, n)["id"])
    before = _get_book(client, book["id"])

    response = client.patch(f"/books/{book['id']}", json={"title": "New title", "total_copies": 1})

    assert response.status_code == 409
    assert _get_book(client, book["id"]) == before  # the title change was rolled back too
