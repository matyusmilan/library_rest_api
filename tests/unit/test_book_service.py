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
    TotalCopiesBelowLoansError,
)
from app.models.book import Book
from app.models.loan import Loan
from app.schemas.book import BookCreate, BookUpdate
from app.services.book_service import (
    borrow_book,
    create_book,
    get_book,
    list_available_books,
    list_books,
    return_book,
    update_book,
)
from tests.unit.factories import make_book, make_borrower

# ---------------------------------------------------------------------------
# list_books
# ---------------------------------------------------------------------------


def _stub_page(query, books):
    """Make query.order_by().limit().offset().all() return the given books."""
    ordered = query.order_by.return_value
    ordered.limit.return_value.offset.return_value.all.return_value = books
    return ordered


def test_list_books_returns_the_requested_page(mock_db):
    books = [make_book(id=1), make_book(id=2, isbn="000")]
    ordered = _stub_page(mock_db.query.return_value, books)

    result = list_books(mock_db, limit=10, offset=20)

    assert result == books
    mock_db.query.assert_called_once_with(Book)
    ordered.limit.assert_called_once_with(10)
    ordered.limit.return_value.offset.assert_called_once_with(20)


def test_list_books_empty(mock_db):
    _stub_page(mock_db.query.return_value, [])

    assert list_books(mock_db, limit=50, offset=0) == []


def test_list_available_books_filters_on_available_copies(mock_db):
    books = [make_book(id=1)]
    filtered = mock_db.query.return_value.filter.return_value
    _stub_page(filtered, books)

    result = list_available_books(mock_db, limit=50, offset=0)

    assert result == books
    mock_db.query.return_value.filter.assert_called_once()


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


# ---------------------------------------------------------------------------
# update_book
# ---------------------------------------------------------------------------


def _stub_book_and_isbn_owner(mock_db, book, isbn_owner=None):
    """get_book finds `book`; the duplicate-ISBN lookup finds `isbn_owner` (or nobody)."""
    query = mock_db.query.return_value
    query.filter.return_value.first.return_value = book
    query.filter.return_value.filter.return_value.first.return_value = isbn_owner


def test_update_book_changes_only_the_sent_fields(mock_db):
    book = make_book(title="Old title", author="Keep me")
    _stub_lookups(mock_db, book=book)

    result = update_book(mock_db, 1, BookUpdate(title="New title"))

    assert (result.title, result.author) == ("New title", "Keep me")
    mock_db.execute.assert_not_called()  # the stock was not touched
    mock_db.commit.assert_called_once()


def test_update_book_isbn_owned_by_another_book_raises_conflict(mock_db):
    _stub_book_and_isbn_owner(mock_db, make_book(), isbn_owner=make_book(id=2))

    with pytest.raises(DuplicateIsbnError):
        update_book(mock_db, 1, BookUpdate(isbn="9780306406157"))

    mock_db.commit.assert_not_called()


def test_update_book_free_isbn_is_applied(mock_db):
    book = make_book()
    _stub_book_and_isbn_owner(mock_db, book, isbn_owner=None)

    update_book(mock_db, 1, BookUpdate(isbn="9780306406157"))

    assert book.isbn == "9780306406157"


def test_update_book_total_copies_runs_one_conditional_update(mock_db):
    _stub_lookups(mock_db, book=make_book(total_copies=3, available_copies=1))
    _stub_update_rowcount(mock_db, 1)

    update_book(mock_db, 1, BookUpdate(total_copies=5))

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


def test_update_book_total_copies_below_loans_raises_conflict_and_rolls_back(mock_db):
    _stub_lookups(mock_db, book=make_book(total_copies=3, available_copies=1))
    _stub_update_rowcount(mock_db, 0)

    with pytest.raises(TotalCopiesBelowLoansError):
        update_book(mock_db, 1, BookUpdate(title="New", total_copies=1))

    mock_db.rollback.assert_called_once()  # the title change is discarded too
    mock_db.commit.assert_not_called()


def test_update_book_not_found_raises_not_found(mock_db):
    _stub_lookups(mock_db, book=None)

    with pytest.raises(BookNotFoundError):
        update_book(mock_db, 99, BookUpdate(title="New"))
