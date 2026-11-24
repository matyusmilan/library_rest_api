"""
Unit tests for the borrower service layer.

The database session is mocked so these tests run in isolation
without any real database or network calls.
"""

import pytest
from fastapi import HTTPException

from app.models.book import Book
from app.models.borrower import Borrower
from app.schemas.borrower import BorrowerCreate
from app.services.borrower_service import create_borrower, get_borrowed_books, get_borrower


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_borrower(**kwargs) -> Borrower:
    defaults = dict(id=1, name="Alice", email="alice@example.com", borrowed_books=[])
    return Borrower(**{**defaults, **kwargs})


def _make_book(**kwargs) -> Book:
    defaults = dict(id=1, title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4", is_borrowed=True, borrower_id=1)
    return Book(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# create_borrower
# ---------------------------------------------------------------------------


def test_create_borrower_success(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    data = BorrowerCreate(name="Alice", email="alice@example.com")

    result = create_borrower(mock_db, data)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert added.email == "alice@example.com"


def test_create_borrower_duplicate_email_raises_409(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _make_borrower()
    data = BorrowerCreate(name="Alice", email="alice@example.com")

    with pytest.raises(HTTPException) as exc:
        create_borrower(mock_db, data)

    assert exc.value.status_code == 409
    mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# get_borrower
# ---------------------------------------------------------------------------


def test_get_borrower_success(mock_db):
    borrower = _make_borrower()
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = get_borrower(mock_db, borrower_id=1)

    assert result.id == 1
    assert result.name == "Alice"


def test_get_borrower_not_found_raises_404(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_borrower(mock_db, borrower_id=99)

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# get_borrowed_books
# ---------------------------------------------------------------------------


def test_get_borrowed_books_returns_list(mock_db):
    books = [_make_book(), _make_book(id=2, isbn="000")]
    borrower = _make_borrower(borrowed_books=books)
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = get_borrowed_books(mock_db, borrower_id=1)

    assert len(result) == 2


def test_get_borrowed_books_empty(mock_db):
    borrower = _make_borrower(borrowed_books=[])
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = get_borrowed_books(mock_db, borrower_id=1)

    assert result == []


def test_get_borrowed_books_borrower_not_found_raises_404(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_borrowed_books(mock_db, borrower_id=99)

    assert exc.value.status_code == 404
