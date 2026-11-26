"""
Integration tests for lending: multiple copies, borrow and return.

Business rules covered here:
  * A title can have several interchangeable copies; each borrow takes one.
  * A borrower may hold at most ONE copy of a title at a time.
  * Returning a copy makes it available again; a repeated return is rejected.
  * available_copies == total_copies - (number of active loans) at all times.
"""

from fastapi.testclient import TestClient

ISBN_A = "978-0-13-235088-4"
ISBN_B = "978-0-13-595705-9"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_book(client: TestClient, copies: int = 1, isbn: str = ISBN_A) -> dict:
    payload = {"title": f"Book {isbn}", "author": "Author", "isbn": isbn, "total_copies": copies}
    response = client.post("/books/", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_borrower(client: TestClient, n: int) -> dict:
    response = client.post(
        "/borrowers/", json={"name": f"User {n}", "email": f"user{n}@example.com"}
    )
    assert response.status_code == 201
    return response.json()


def _borrow(client: TestClient, book_id: int, borrower_id: int):
    return client.post(f"/books/{book_id}/borrow", json={"borrower_id": borrower_id})


def _return(client: TestClient, book_id: int, borrower_id: int):
    return client.post(f"/books/{book_id}/return", json={"borrower_id": borrower_id})


def _available(client: TestClient, book_id: int) -> int:
    books = client.get("/books/").json()
    return next(b["available_copies"] for b in books if b["id"] == book_id)


def _borrowed_book_ids(client: TestClient, borrower_id: int) -> list[int]:
    return [b["id"] for b in client.get(f"/borrowers/{borrower_id}/books").json()]


# ---------------------------------------------------------------------------
# Multiple copies
# ---------------------------------------------------------------------------


def test_each_borrow_takes_one_copy(client: TestClient):
    book = _create_book(client, copies=3)
    first, second = _create_borrower(client, 1), _create_borrower(client, 2)

    assert _borrow(client, book["id"], first["id"]).json()["available_copies"] == 2
    assert _borrow(client, book["id"], second["id"]).json()["available_copies"] == 1


def test_borrow_returns_409_when_all_copies_are_out(client: TestClient):
    book = _create_book(client, copies=2)
    borrowers = [_create_borrower(client, n) for n in range(1, 4)]
    assert _borrow(client, book["id"], borrowers[0]["id"]).status_code == 200
    assert _borrow(client, book["id"], borrowers[1]["id"]).status_code == 200

    response = _borrow(client, book["id"], borrowers[2]["id"])

    assert response.status_code == 409
    assert _available(client, book["id"]) == 0
    assert _borrowed_book_ids(client, borrowers[2]["id"]) == []  # no loan was left behind


# ---------------------------------------------------------------------------
# Rule: one copy per title per borrower
# ---------------------------------------------------------------------------


def test_borrower_cannot_hold_two_copies_of_the_same_title(client: TestClient):
    book = _create_book(client, copies=3)
    borrower = _create_borrower(client, 1)
    assert _borrow(client, book["id"], borrower["id"]).status_code == 200

    response = _borrow(client, book["id"], borrower["id"])

    assert response.status_code == 409
    assert _available(client, book["id"]) == 2  # the rejected borrow took no copy


def test_borrower_can_hold_different_titles_at_once(client: TestClient):
    first = _create_book(client, isbn=ISBN_A)
    second = _create_book(client, isbn=ISBN_B)
    borrower = _create_borrower(client, 1)

    assert _borrow(client, first["id"], borrower["id"]).status_code == 200
    assert _borrow(client, second["id"], borrower["id"]).status_code == 200
    assert sorted(_borrowed_book_ids(client, borrower["id"])) == sorted([first["id"], second["id"]])


# ---------------------------------------------------------------------------
# Return
# ---------------------------------------------------------------------------


def test_return_makes_the_copy_available_again(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client, 1)
    _borrow(client, book["id"], borrower["id"])

    response = _return(client, book["id"], borrower["id"])

    assert response.status_code == 200
    assert response.json()["available_copies"] == 1
    assert _borrowed_book_ids(client, borrower["id"]) == []


def test_borrower_can_borrow_again_after_returning(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client, 1)
    _borrow(client, book["id"], borrower["id"])
    _return(client, book["id"], borrower["id"])

    assert _borrow(client, book["id"], borrower["id"]).status_code == 200


def test_returned_copy_can_be_borrowed_by_someone_else(client: TestClient):
    book = _create_book(client)  # a single copy
    first, second = _create_borrower(client, 1), _create_borrower(client, 2)
    _borrow(client, book["id"], first["id"])
    assert _borrow(client, book["id"], second["id"]).status_code == 409

    _return(client, book["id"], first["id"])

    assert _borrow(client, book["id"], second["id"]).status_code == 200


def test_return_without_an_active_loan_returns_404(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client, 1)

    response = _return(client, book["id"], borrower["id"])

    assert response.status_code == 404
    assert _available(client, book["id"]) == 1  # nothing was added


def test_repeated_return_returns_404_and_does_not_inflate_copies(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client, 1)
    _borrow(client, book["id"], borrower["id"])
    assert _return(client, book["id"], borrower["id"]).status_code == 200

    response = _return(client, book["id"], borrower["id"])

    assert response.status_code == 404
    assert _available(client, book["id"]) == 1  # not 2


def test_return_of_unknown_book_returns_404(client: TestClient):
    borrower = _create_borrower(client, 1)

    assert _return(client, 9999, borrower["id"]).status_code == 404


def test_return_by_unknown_borrower_returns_404(client: TestClient):
    book = _create_book(client)

    assert _return(client, book["id"], 9999).status_code == 404


# ---------------------------------------------------------------------------
# Invariant
# ---------------------------------------------------------------------------


def test_available_copies_equals_total_minus_active_loans(client: TestClient):
    book = _create_book(client, copies=3)
    borrowers = [_create_borrower(client, n) for n in range(1, 4)]
    for borrower in borrowers:
        _borrow(client, book["id"], borrower["id"])
    _return(client, book["id"], borrowers[1]["id"])

    holders = [b for b in borrowers if book["id"] in _borrowed_book_ids(client, b["id"])]

    assert len(holders) == 2  # only the borrower who returned lost the book
    assert _available(client, book["id"]) == book["total_copies"] - len(holders)
