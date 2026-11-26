"""
Integration tests for the list endpoints: /books/all, /books/available, /books/
and their shared `limit` / `offset` pagination.

  * /books/all        every book in the library, borrowed out or not
  * /books/available  only books with at least one copy left to borrow
  * /books/           alias of /books/all
"""

import pytest
from fastapi.testclient import TestClient

BOOK_LISTS = ["/books/", "/books/all", "/books/available"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _isbn(n: int) -> str:
    return f"978000000{n:04d}"  # 13 digits, accepted by the ISBN validator


def _create_book(client: TestClient, n: int = 1, copies: int = 1) -> dict:
    payload = {"title": f"Book {n}", "author": "Author", "isbn": _isbn(n), "total_copies": copies}
    response = client.post("/books/", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_borrower(client: TestClient, n: int = 1) -> dict:
    payload = {"name": f"User {n}", "email": f"user{n}@example.com"}
    response = client.post("/borrowers/", json=payload)
    assert response.status_code == 201
    return response.json()


def _ids(client: TestClient, url: str) -> list[int]:
    response = client.get(url)
    assert response.status_code == 200
    return [item["id"] for item in response.json()]


# ---------------------------------------------------------------------------
# /books/all and /books/available
# ---------------------------------------------------------------------------


def test_all_lists_every_book_including_fully_borrowed_ones(client: TestClient):
    borrowed_out = _create_book(client, 1)
    in_stock = _create_book(client, 2)
    borrower = _create_borrower(client)
    client.post(f"/books/{borrowed_out['id']}/borrow", json={"borrower_id": borrower["id"]})

    assert _ids(client, "/books/all") == [borrowed_out["id"], in_stock["id"]]


def test_available_excludes_books_with_no_copy_left(client: TestClient):
    borrowed_out = _create_book(client, 1)
    in_stock = _create_book(client, 2)
    borrower = _create_borrower(client)
    client.post(f"/books/{borrowed_out['id']}/borrow", json={"borrower_id": borrower["id"]})

    assert _ids(client, "/books/available") == [in_stock["id"]]


def test_available_includes_a_book_with_some_copies_still_free(client: TestClient):
    book = _create_book(client, copies=2)
    borrower = _create_borrower(client)
    client.post(f"/books/{book['id']}/borrow", json={"borrower_id": borrower["id"]})

    assert _ids(client, "/books/available") == [book["id"]]


def test_returned_book_is_available_again(client: TestClient):
    book = _create_book(client)
    borrower = _create_borrower(client)
    client.post(f"/books/{book['id']}/borrow", json={"borrower_id": borrower["id"]})
    assert _ids(client, "/books/available") == []

    client.post(f"/books/{book['id']}/return", json={"borrower_id": borrower["id"]})

    assert _ids(client, "/books/available") == [book["id"]]


def test_available_is_empty_on_a_fresh_library(client: TestClient):
    assert client.get("/books/available").json() == []


def test_books_root_is_an_alias_of_all(client: TestClient):
    _create_book(client, 1)
    _create_book(client, 2)

    assert client.get("/books/").json() == client.get("/books/all").json()


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", BOOK_LISTS)
def test_limit_and_offset_select_a_page_in_id_order(client: TestClient, url: str):
    created = [_create_book(client, n)["id"] for n in range(1, 6)]

    assert _ids(client, f"{url}?limit=2") == created[:2]
    assert _ids(client, f"{url}?limit=2&offset=2") == created[2:4]
    assert _ids(client, f"{url}?limit=2&offset=4") == created[4:]


@pytest.mark.parametrize("url", BOOK_LISTS)
def test_offset_past_the_end_returns_an_empty_page(client: TestClient, url: str):
    _create_book(client)

    assert _ids(client, f"{url}?offset=10") == []


def test_default_page_size_is_50(client: TestClient):
    for n in range(1, 52):
        _create_book(client, n)

    assert len(_ids(client, "/books/all")) == 50


def test_limit_of_100_is_accepted(client: TestClient):
    assert client.get("/books/all?limit=100").status_code == 200


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=abc", "offset=-1", "offset=x"])
@pytest.mark.parametrize("url", BOOK_LISTS)
def test_invalid_pagination_returns_422(client: TestClient, url: str, query: str):
    assert client.get(f"{url}?{query}").status_code == 422
