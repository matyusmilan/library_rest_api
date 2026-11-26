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
from app.models import Book, Loan


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _book(total: int, available: int) -> Book:
    return Book(
        title="Clean Code",
        author="Robert C. Martin",
        isbn="978-0-13-235088-4",
        total_copies=total,
        available_copies=available,
    )


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


def test_second_active_loan_for_same_book_and_borrower_is_rejected(db_session):
    db_session.add(Loan(book_id=1, borrower_id=1))
    db_session.flush()

    db_session.add(Loan(book_id=1, borrower_id=1))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_different_borrowers_may_hold_the_same_book(db_session):
    db_session.add_all([Loan(book_id=1, borrower_id=1), Loan(book_id=1, borrower_id=2)])

    db_session.flush()


def test_same_borrower_may_hold_different_books(db_session):
    db_session.add_all([Loan(book_id=1, borrower_id=1), Loan(book_id=2, borrower_id=1)])

    db_session.flush()


def test_borrower_may_borrow_again_once_the_previous_loan_is_returned(db_session):
    db_session.add(Loan(book_id=1, borrower_id=1, returned_at=datetime.now(UTC)))
    db_session.flush()

    db_session.add(Loan(book_id=1, borrower_id=1))

    db_session.flush()
