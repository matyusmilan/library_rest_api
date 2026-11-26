"""
Unit tests for the borrower service layer.

The database session is mocked so these tests run in isolation
without any real database or network calls.
"""

import pytest

from app.exceptions import BorrowerNotFoundError, DuplicateEmailError
from app.schemas.borrower import BorrowerCreate
from app.services.borrower_service import create_borrower, get_borrowed_books, get_borrower
from tests.unit.factories import make_book, make_borrower

# ---------------------------------------------------------------------------
# create_borrower
# ---------------------------------------------------------------------------


def test_create_borrower_success(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    data = BorrowerCreate(name="Alice", email="alice@example.com")

    create_borrower(mock_db, data)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert added.email == "alice@example.com"


def test_create_borrower_duplicate_email_raises_conflict(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = make_borrower()
    data = BorrowerCreate(name="Alice", email="alice@example.com")

    with pytest.raises(DuplicateEmailError):
        create_borrower(mock_db, data)

    mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# get_borrower
# ---------------------------------------------------------------------------


def test_get_borrower_success(mock_db):
    borrower = make_borrower()
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = get_borrower(mock_db, borrower_id=1)

    assert result.id == 1
    assert result.name == "Alice"


def test_get_borrower_not_found_raises_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(BorrowerNotFoundError):
        get_borrower(mock_db, borrower_id=99)


# ---------------------------------------------------------------------------
# get_borrowed_books
# ---------------------------------------------------------------------------


def test_get_borrowed_books_returns_list(mock_db):
    books = [
        make_book(is_borrowed=True, borrower_id=1),
        make_book(id=2, isbn="000", is_borrowed=True, borrower_id=1),
    ]
    borrower = make_borrower(borrowed_books=books)
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = get_borrowed_books(mock_db, borrower_id=1)

    assert len(result) == 2


def test_get_borrowed_books_empty(mock_db):
    borrower = make_borrower(borrowed_books=[])
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = get_borrowed_books(mock_db, borrower_id=1)

    assert result == []


def test_get_borrowed_books_borrower_not_found_raises_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(BorrowerNotFoundError):
        get_borrowed_books(mock_db, borrower_id=99)
