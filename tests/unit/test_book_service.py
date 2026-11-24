"""
Unit tests for the book service layer.

The database session is mocked so these tests run entirely in memory
without touching SQLite or the network. Each test targets a single
business-logic branch.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.book import Book
from app.models.borrower import Borrower
from app.schemas.book import BookCreate
from app.services.book_service import borrow_book, create_book, list_books


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(**kwargs) -> Book:
    defaults = dict(id=1, title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4", is_borrowed=False, borrower_id=None)
    return Book(**{**defaults, **kwargs})


def _make_borrower(**kwargs) -> Borrower:
    defaults = dict(id=1, name="Alice", email="alice@example.com")
    return Borrower(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# list_books
# ---------------------------------------------------------------------------


def test_list_books_returns_all(mock_db):
    books = [_make_book(id=1), _make_book(id=2, isbn="000")]
    mock_db.query.return_value.all.return_value = books

    result = list_books(mock_db)

    assert result == books
    mock_db.query.assert_called_once_with(Book)


def test_list_books_empty(mock_db):
    mock_db.query.return_value.all.return_value = []

    result = list_books(mock_db)

    assert result == []


# ---------------------------------------------------------------------------
# create_book
# ---------------------------------------------------------------------------


def test_create_book_success(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    data = BookCreate(title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4")

    result = create_book(mock_db, data)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()
    added_book = mock_db.add.call_args[0][0]
    assert added_book.isbn == data.isbn


def test_create_book_duplicate_isbn_raises_409(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _make_book()
    data = BookCreate(title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4")

    with pytest.raises(HTTPException) as exc:
        create_book(mock_db, data)

    assert exc.value.status_code == 409
    mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# borrow_book
# ---------------------------------------------------------------------------


def test_borrow_book_success(mock_db):
    book = _make_book()
    borrower = _make_borrower()

    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = book if model is Book else borrower
        return q

    mock_db.query.side_effect = query_side_effect

    with patch("app.services.book_service.books_borrowed_counter") as mock_counter:
        result = borrow_book(mock_db, book_id=1, borrower_id=1)

    assert result.is_borrowed is True
    assert result.borrower_id == 1
    mock_db.commit.assert_called_once()
    mock_counter.add.assert_called_once()


def test_borrow_book_not_found_raises_404(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        borrow_book(mock_db, book_id=99, borrower_id=1)

    assert exc.value.status_code == 404


def test_borrow_book_already_borrowed_raises_409(mock_db):
    book = _make_book(is_borrowed=True)
    mock_db.query.return_value.filter.return_value.first.return_value = book

    with pytest.raises(HTTPException) as exc:
        borrow_book(mock_db, book_id=1, borrower_id=1)

    assert exc.value.status_code == 409


def test_borrow_book_borrower_not_found_raises_404(mock_db):
    book = _make_book()

    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = book if model is Book else None
        return q

    mock_db.query.side_effect = query_side_effect

    with pytest.raises(HTTPException) as exc:
        borrow_book(mock_db, book_id=1, borrower_id=99)

    assert exc.value.status_code == 404
