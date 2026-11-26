"""
Unit tests for the book service layer.

The database session is mocked so these tests run entirely in memory
without touching SQLite or the network. Each test targets a single
business-logic branch.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.exceptions import (
    AlreadyBorrowedByBorrowerError,
    BookNotFoundError,
    BorrowerNotFoundError,
    DuplicateIsbnError,
    LoanNotFoundError,
    NoCopiesAvailableError,
)
from app.models.book import Book
from app.models.loan import Loan
from app.schemas.book import BookCreate
from app.services.book_service import (
    borrow_book,
    create_book,
    get_book,
    list_books,
    return_book,
)
from tests.unit.factories import make_book, make_borrower

# ---------------------------------------------------------------------------
# list_books
# ---------------------------------------------------------------------------


def test_list_books_returns_all(mock_db):
    books = [make_book(id=1), make_book(id=2, isbn="000")]
    mock_db.query.return_value.all.return_value = books

    result = list_books(mock_db)

    assert result == books
    mock_db.query.assert_called_once_with(Book)


def test_list_books_empty(mock_db):
    mock_db.query.return_value.all.return_value = []

    result = list_books(mock_db)

    assert result == []


# ---------------------------------------------------------------------------
# get_book
# ---------------------------------------------------------------------------


def test_get_book_returns_the_book(mock_db):
    book = make_book(id=7)
    mock_db.query.return_value.filter.return_value.first.return_value = book

    assert get_book(mock_db, book_id=7) is book


def test_get_book_not_found_raises_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(BookNotFoundError):
        get_book(mock_db, book_id=99)


# ---------------------------------------------------------------------------
# create_book
# ---------------------------------------------------------------------------


def test_create_book_success(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    data = BookCreate(title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4")

    create_book(mock_db, data)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()
    added_book = mock_db.add.call_args[0][0]
    assert added_book.isbn == data.isbn


def test_create_book_makes_all_copies_available(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    data = BookCreate(
        title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4", total_copies=5
    )

    create_book(mock_db, data)

    added_book = mock_db.add.call_args[0][0]
    assert added_book.total_copies == 5
    assert added_book.available_copies == 5


def test_create_book_duplicate_isbn_raises_conflict(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = make_book()
    data = BookCreate(title="Clean Code", author="Robert C. Martin", isbn="978-0-13-235088-4")

    with pytest.raises(DuplicateIsbnError):
        create_book(mock_db, data)

    mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Helpers for borrow / return
# ---------------------------------------------------------------------------


def _stub_lookups(mock_db, book=None, borrower=None):
    """Make db.query(Book|Borrower).filter().first() return the given entities."""

    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = book if model is Book else borrower
        return q

    mock_db.query.side_effect = query_side_effect


def _stub_update_rowcount(mock_db, rowcount):
    """Set how many rows the next UPDATE statements report as changed."""
    mock_db.execute.return_value.rowcount = rowcount


# ---------------------------------------------------------------------------
# borrow_book
# ---------------------------------------------------------------------------


def test_borrow_book_success_opens_loan_and_commits(mock_db):
    book = make_book()
    _stub_lookups(mock_db, book=book, borrower=make_borrower())
    _stub_update_rowcount(mock_db, 1)

    with patch("app.services.book_service.books_borrowed_counter") as mock_counter:
        result = borrow_book(mock_db, book_id=1, borrower_id=1)

    assert result is book
    loan = mock_db.add.call_args[0][0]
    assert isinstance(loan, Loan)
    assert (loan.book_id, loan.borrower_id) == (1, 1)
    mock_db.commit.assert_called_once()
    mock_counter.add.assert_called_once()


def test_borrow_book_not_found_raises_not_found(mock_db):
    _stub_lookups(mock_db, book=None, borrower=make_borrower())

    with pytest.raises(BookNotFoundError):
        borrow_book(mock_db, book_id=99, borrower_id=1)

    mock_db.add.assert_not_called()


def test_borrow_book_borrower_not_found_raises_not_found(mock_db):
    _stub_lookups(mock_db, book=make_book(), borrower=None)

    with pytest.raises(BorrowerNotFoundError):
        borrow_book(mock_db, book_id=1, borrower_id=99)

    mock_db.add.assert_not_called()


def test_borrow_book_borrower_already_holds_copy_raises_conflict(mock_db):
    _stub_lookups(mock_db, book=make_book(), borrower=make_borrower())
    mock_db.flush.side_effect = IntegrityError("INSERT INTO loans", {}, Exception("UNIQUE"))

    with pytest.raises(AlreadyBorrowedByBorrowerError):
        borrow_book(mock_db, book_id=1, borrower_id=1)

    mock_db.rollback.assert_called_once()
    mock_db.execute.assert_not_called()  # no copy was taken
    mock_db.commit.assert_not_called()


def test_borrow_book_no_copies_left_raises_conflict_and_rolls_back(mock_db):
    _stub_lookups(mock_db, book=make_book(available_copies=0), borrower=make_borrower())
    _stub_update_rowcount(mock_db, 0)

    with patch("app.services.book_service.books_borrowed_counter") as mock_counter:
        with pytest.raises(NoCopiesAvailableError):
            borrow_book(mock_db, book_id=1, borrower_id=1)

    mock_db.rollback.assert_called_once()  # the loan insert is undone
    mock_db.commit.assert_not_called()
    mock_counter.add.assert_not_called()


# ---------------------------------------------------------------------------
# return_book
# ---------------------------------------------------------------------------


def test_return_book_success_closes_loan_and_restores_copy(mock_db):
    book = make_book(available_copies=0)
    _stub_lookups(mock_db, book=book, borrower=make_borrower())
    _stub_update_rowcount(mock_db, 1)

    result = return_book(mock_db, book_id=1, borrower_id=1)

    assert result is book
    assert mock_db.execute.call_count == 2  # close the loan, then increment the copies
    mock_db.commit.assert_called_once()


def test_return_book_without_active_loan_raises_not_found(mock_db):
    _stub_lookups(mock_db, book=make_book(), borrower=make_borrower())
    _stub_update_rowcount(mock_db, 0)

    with pytest.raises(LoanNotFoundError):
        return_book(mock_db, book_id=1, borrower_id=1)

    assert mock_db.execute.call_count == 1  # copies were not incremented
    mock_db.commit.assert_not_called()


def test_return_book_book_not_found_raises_not_found(mock_db):
    _stub_lookups(mock_db, book=None, borrower=make_borrower())

    with pytest.raises(BookNotFoundError):
        return_book(mock_db, book_id=99, borrower_id=1)


def test_return_book_borrower_not_found_raises_not_found(mock_db):
    _stub_lookups(mock_db, book=make_book(), borrower=None)

    with pytest.raises(BorrowerNotFoundError):
        return_book(mock_db, book_id=1, borrower_id=99)
