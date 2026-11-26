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


# ---------------------------------------------------------------------------
# DELETE /books/{id}
# ---------------------------------------------------------------------------


def test_delete_book_returns_204_and_removes_it(client: TestClient):
    book = _create_book(client)

    response = client.delete(f"/books/{book['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/books/{book['id']}").status_code == 404
    assert client.get("/books/").json() == []


def test_delete_unknown_book_returns_404(client: TestClient):
    assert client.delete("/books/9999").status_code == 404


def test_delete_book_twice_returns_404_the_second_time(client: TestClient):
    book = _create_book(client)
    client.delete(f"/books/{book['id']}")

    assert client.delete(f"/books/{book['id']}").status_code == 404


def test_delete_book_with_a_copy_on_loan_returns_409_and_keeps_everything(client: TestClient):
    book = _create_book(client, copies=2)
    borrower = _create_borrower(client)
    _borrow(client, book["id"], borrower["id"])
    before = _get_book(client, book["id"])

    response = client.delete(f"/books/{book['id']}")

    assert response.status_code == 409
    assert _get_book(client, book["id"]) == before
    assert [b["id"] for b in client.get(f"/borrowers/{borrower['id']}/books").json()] == [
        book["id"]
    ]


def test_delete_book_after_every_copy_is_returned_succeeds(client: TestClient):
    # Foreign keys are enforced, so a 204 also proves the loan history was removed with the book.
    book = _create_book(client)
    borrower = _create_borrower(client)
    _borrow(client, book["id"], borrower["id"])
    client.post(f"/books/{book['id']}/return", json={"borrower_id": borrower["id"]})

    assert client.delete(f"/books/{book['id']}").status_code == 204
    assert client.get(f"/borrowers/{borrower['id']}").status_code == 200
    assert client.get(f"/borrowers/{borrower['id']}/books").json() == []


def test_delete_book_leaves_other_loans_untouched(client: TestClient):
    deleted, kept = _create_book(client, 1), _create_book(client, 2)
    borrower = _create_borrower(client)
    _borrow(client, kept["id"], borrower["id"])

    assert client.delete(f"/books/{deleted['id']}").status_code == 204
    assert [b["id"] for b in client.get(f"/borrowers/{borrower['id']}/books").json()] == [
        kept["id"]
    ]


# ---------------------------------------------------------------------------
# PATCH /borrowers/{id}
# ---------------------------------------------------------------------------


def test_patch_borrower_changes_only_the_sent_fields(client: TestClient):
    borrower = _create_borrower(client)

    response = client.patch(f"/borrowers/{borrower['id']}", json={"name": "New name"})

    assert response.status_code == 200
    assert response.json() == {**borrower, "name": "New name"}


def test_patch_borrower_email_of_another_borrower_returns_409(client: TestClient):
    first, second = _create_borrower(client, 1), _create_borrower(client, 2)

    response = client.patch(f"/borrowers/{second['id']}", json={"email": first["email"]})

    assert response.status_code == 409
    assert client.get(f"/borrowers/{second['id']}").json()["email"] == second["email"]


def test_patch_borrower_with_its_own_email_is_not_a_conflict(client: TestClient):
    borrower = _create_borrower(client)

    response = client.patch(
        f"/borrowers/{borrower['id']}", json={"email": borrower["email"], "name": "Same email"}
    )

    assert response.status_code == 200


def test_patch_borrower_to_a_new_email(client: TestClient):
    borrower = _create_borrower(client)

    response = client.patch(f"/borrowers/{borrower['id']}", json={"email": "new@example.com"})

    assert response.json()["email"] == "new@example.com"


@pytest.mark.parametrize(
    "body", [{}, {"name": None}, {"email": None}, {"name": ""}, {"email": "not-an-email"}]
)
def test_patch_borrower_with_an_invalid_body_returns_422(client: TestClient, body: dict):
    borrower = _create_borrower(client)

    assert client.patch(f"/borrowers/{borrower['id']}", json=body).status_code == 422


def test_patch_unknown_borrower_returns_404(client: TestClient):
    assert client.patch("/borrowers/9999", json={"name": "x"}).status_code == 404


# ---------------------------------------------------------------------------
# DELETE /borrowers/{id}
# ---------------------------------------------------------------------------


def test_delete_borrower_returns_204_and_removes_them(client: TestClient):
    borrower = _create_borrower(client)

    response = client.delete(f"/borrowers/{borrower['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/borrowers/{borrower['id']}").status_code == 404
    assert client.get("/borrowers/").json() == []


def test_delete_unknown_borrower_returns_404(client: TestClient):
    assert client.delete("/borrowers/9999").status_code == 404


def test_delete_borrower_holding_a_book_returns_409_and_keeps_the_loan(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client)
    _borrow(client, book["id"], borrower["id"])

    response = client.delete(f"/borrowers/{borrower['id']}")

    assert response.status_code == 409
    assert client.get(f"/borrowers/{borrower['id']}").status_code == 200
    assert _get_book(client, book["id"])["available_copies"] == 0


def test_delete_borrower_after_returning_everything_succeeds(client: TestClient):
    # Foreign keys are enforced, so a 204 also proves the loan history was removed with them.
    book = _create_book(client)
    borrower = _create_borrower(client)
    _borrow(client, book["id"], borrower["id"])
    client.post(f"/books/{book['id']}/return", json={"borrower_id": borrower["id"]})

    assert client.delete(f"/borrowers/{borrower['id']}").status_code == 204
    assert _get_book(client, book["id"])["available_copies"] == 1


def test_delete_borrower_leaves_other_borrowers_loans_untouched(client: TestClient):
    book = _create_book(client, copies=2)
    leaving, staying = _create_borrower(client, 1), _create_borrower(client, 2)
    _borrow(client, book["id"], staying["id"])

    assert client.delete(f"/borrowers/{leaving['id']}").status_code == 204
    assert [b["id"] for b in client.get(f"/borrowers/{staying['id']}/books").json()] == [book["id"]]
