"""
Unit tests for the borrower service layer.

The database session is mocked so these tests run in isolation
without any real database or network calls.
"""

import pytest

from app.exceptions import (
    BorrowerHasActiveLoansError,
    BorrowerNotFoundError,
    DuplicateEmailError,
)
from app.schemas.borrower import BorrowerCreate, BorrowerUpdate
from app.services.borrower_service import (
    create_borrower,
    delete_borrower,
    get_borrowed_books,
    get_borrower,
    list_borrowers,
    update_borrower,
)
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
# list_borrowers
# ---------------------------------------------------------------------------


def test_list_borrowers_returns_the_requested_page(mock_db):
    borrowers = [make_borrower(id=1), make_borrower(id=2, email="b@example.com")]
    ordered = mock_db.query.return_value.order_by.return_value
    ordered.limit.return_value.offset.return_value.all.return_value = borrowers

    result = list_borrowers(mock_db, limit=10, offset=20)

    assert result == borrowers
    ordered.limit.assert_called_once_with(10)
    ordered.limit.return_value.offset.assert_called_once_with(20)


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


def _stub_active_loan_books(mock_db, borrower, books):
    """Stub the borrower lookup and the join query over active loans."""
    mock_db.query.return_value.filter.return_value.first.return_value = borrower
    mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = books


def test_get_borrowed_books_returns_books_from_active_loans(mock_db):
    books = [make_book(id=1, available_copies=0), make_book(id=2, isbn="000", available_copies=0)]
    _stub_active_loan_books(mock_db, make_borrower(), books)

    result = get_borrowed_books(mock_db, borrower_id=1)

    assert result == books


def test_get_borrowed_books_empty(mock_db):
    _stub_active_loan_books(mock_db, make_borrower(), [])

    result = get_borrowed_books(mock_db, borrower_id=1)

    assert result == []


def test_get_borrowed_books_borrower_not_found_raises_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(BorrowerNotFoundError):
        get_borrowed_books(mock_db, borrower_id=99)


# ---------------------------------------------------------------------------
# update_borrower
# ---------------------------------------------------------------------------


def _stub_borrower_and_email_owner(mock_db, borrower, email_owner=None):
    """get_borrower finds `borrower`; the duplicate-email lookup finds `email_owner` (or nobody)."""
    query = mock_db.query.return_value
    query.filter.return_value.first.return_value = borrower
    query.filter.return_value.filter.return_value.first.return_value = email_owner


def test_update_borrower_changes_only_the_sent_fields(mock_db):
    borrower = make_borrower(name="Old name", email="keep@example.com")
    mock_db.query.return_value.filter.return_value.first.return_value = borrower

    result = update_borrower(mock_db, 1, BorrowerUpdate(name="New name"))

    assert (result.name, result.email) == ("New name", "keep@example.com")
    mock_db.commit.assert_called_once()


def test_update_borrower_email_owned_by_another_raises_conflict(mock_db):
    _stub_borrower_and_email_owner(mock_db, make_borrower(), email_owner=make_borrower(id=2))

    with pytest.raises(DuplicateEmailError):
        update_borrower(mock_db, 1, BorrowerUpdate(email="taken@example.com"))

    mock_db.commit.assert_not_called()


def test_update_borrower_free_email_is_applied(mock_db):
    borrower = make_borrower()
    _stub_borrower_and_email_owner(mock_db, borrower, email_owner=None)

    update_borrower(mock_db, 1, BorrowerUpdate(email="new@example.com"))

    assert borrower.email == "new@example.com"


def test_update_borrower_not_found_raises_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(BorrowerNotFoundError):
        update_borrower(mock_db, 99, BorrowerUpdate(name="New"))


# ---------------------------------------------------------------------------
# delete_borrower
# ---------------------------------------------------------------------------


def test_delete_borrower_removes_history_then_borrower_and_commits(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = make_borrower()
    mock_db.execute.return_value.rowcount = 1

    delete_borrower(mock_db, borrower_id=1)

    assert mock_db.execute.call_count == 2  # returned loans, then the borrower
    mock_db.commit.assert_called_once()


def test_delete_borrower_holding_a_book_raises_conflict_and_rolls_back(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = make_borrower()
    mock_db.execute.return_value.rowcount = 0  # an active loan still references the borrower

    with pytest.raises(BorrowerHasActiveLoansError):
        delete_borrower(mock_db, borrower_id=1)

    mock_db.rollback.assert_called_once()  # the history delete is undone as well
    mock_db.commit.assert_not_called()


def test_delete_borrower_not_found_raises_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(BorrowerNotFoundError):
        delete_borrower(mock_db, borrower_id=99)

    mock_db.execute.assert_not_called()
