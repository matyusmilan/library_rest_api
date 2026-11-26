"""
Database-level guarantees.

The service layer relies on these as the last line of defence: the CHECK
constraint keeps copy counts consistent and the partial unique index enforces
"one active loan per borrower and title" even under concurrent requests.
Tests talk to a real in-memory SQLite database, bypassing the service layer.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Book, Borrower, Loan


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _book(total: int = 2, available: int = 2, **overrides) -> Book:
    fields = {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "isbn": "978-0-13-235088-4",
        "total_copies": total,
        "available_copies": available,
    } | overrides
    return Book(**fields)


@pytest.fixture
def seeded_session(db_session):
    """A session holding books 1 and 2 and borrowers 1 and 2; loans need real parents."""
    db_session.add_all(
        [
            _book(id=1, isbn="9780000000001"),
            _book(id=2, isbn="9780000000002"),
            Borrower(id=1, name="Alice", email="alice@example.com"),
            Borrower(id=2, name="Bob", email="bob@example.com"),
        ]
    )
    db_session.flush()
    return db_session


# ---------------------------------------------------------------------------
# books: 0 <= available_copies <= total_copies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("total, available", [(2, 3), (2, -1)])
def test_available_copies_outside_zero_to_total_is_rejected(db_session, total, available):
    db_session.add(_book(total, available))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("total, available", [(2, 0), (2, 2), (1, 1)])
def test_available_copies_within_zero_to_total_is_accepted(db_session, total, available):
    db_session.add(_book(total, available))

    db_session.flush()


# ---------------------------------------------------------------------------
# loans: one active loan per (book, borrower)
# ---------------------------------------------------------------------------


def test_second_active_loan_for_same_book_and_borrower_is_rejected(seeded_session):
    seeded_session.add(Loan(book_id=1, borrower_id=1))
    seeded_session.flush()

    seeded_session.add(Loan(book_id=1, borrower_id=1))

    with pytest.raises(IntegrityError):
        seeded_session.flush()


def test_different_borrowers_may_hold_the_same_book(seeded_session):
    seeded_session.add_all([Loan(book_id=1, borrower_id=1), Loan(book_id=1, borrower_id=2)])

    seeded_session.flush()


def test_same_borrower_may_hold_different_books(seeded_session):
    seeded_session.add_all([Loan(book_id=1, borrower_id=1), Loan(book_id=2, borrower_id=1)])

    seeded_session.flush()


def test_borrower_may_borrow_again_once_the_previous_loan_is_returned(seeded_session):
    seeded_session.add(Loan(book_id=1, borrower_id=1, returned_at=datetime.now(UTC)))
    seeded_session.flush()

    seeded_session.add(Loan(book_id=1, borrower_id=1))

    seeded_session.flush()


# ---------------------------------------------------------------------------
# loans: foreign keys (SQLite enforces them only because app.database enables the pragma)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("book_id, borrower_id", [(99, 1), (1, 99)])
def test_loan_must_reference_an_existing_book_and_borrower(seeded_session, book_id, borrower_id):
    seeded_session.add(Loan(book_id=book_id, borrower_id=borrower_id))

    with pytest.raises(IntegrityError):
        seeded_session.flush()
