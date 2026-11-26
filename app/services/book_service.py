from datetime import UTC, datetime

from opentelemetry import metrics, trace
from sqlalchemy import delete, exists, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from app.exceptions import (
    AlreadyBorrowedByBorrowerError,
    BookHasActiveLoansError,
    BookNotFoundError,
    DuplicateIsbnError,
    LoanNotFoundError,
    NoCopiesAvailableError,
    TotalCopiesBelowLoansError,
)
from app.models.book import Book
from app.models.loan import Loan
from app.schemas.book import BookCreate, BookUpdate
from app.services.borrower_service import get_borrower

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Tracks how many times a book has been successfully borrowed.
# This is the most business-critical operation: it drives inventory decisions,
# capacity planning, and SLA alerting (e.g. alert if borrow rate drops unexpectedly).
books_borrowed_counter = meter.create_counter(
    name="books.borrowed_total",
    description="Total number of successful book borrow operations",
    unit="1",
)


def _page(query: Query[Book], limit: int, offset: int) -> list[Book]:
    # Ordering by id keeps pages stable between requests.
    return query.order_by(Book.id).limit(limit).offset(offset).all()


def list_books(db: Session, limit: int, offset: int) -> list[Book]:
    return _page(db.query(Book), limit, offset)


def list_available_books(db: Session, limit: int, offset: int) -> list[Book]:
    """List the books that have at least one copy available to borrow."""
    return _page(db.query(Book).filter(Book.available_copies > 0), limit, offset)


def _ensure_isbn_free(db: Session, isbn: str, owner_id: int | None = None) -> None:
    """Raise DuplicateIsbnError if another book (not `owner_id`) already has this ISBN."""
    query = db.query(Book).filter(Book.isbn == isbn)
    if owner_id is not None:
        query = query.filter(Book.id != owner_id)
    if query.first() is not None:
        raise DuplicateIsbnError(isbn)


def create_book(db: Session, data: BookCreate) -> Book:
    """Add a new book. Raises DuplicateIsbnError if the ISBN exists."""
    _ensure_isbn_free(db, data.isbn)
    book = Book(
        title=data.title,
        author=data.author,
        isbn=data.isbn,
        total_copies=data.total_copies,
        available_copies=data.total_copies,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def get_book(db: Session, book_id: int) -> Book:
    """Return a book by ID. Raises BookNotFoundError if missing."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise BookNotFoundError(book_id)
    return book


def _set_total_copies(db: Session, book: Book, new_total: int) -> None:
    """Resize the stock atomically; the available copies move by the same amount.

    The WHERE clause refuses a total below the number of copies currently on loan.
    """
    on_loan = book.total_copies - book.available_copies
    result = db.execute(
        update(Book)
        .where(Book.id == book.id, Book.total_copies - Book.available_copies <= new_total)
        .values(
            total_copies=new_total,
            available_copies=Book.available_copies + (new_total - Book.total_copies),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        raise TotalCopiesBelowLoansError(book.id, on_loan)


def update_book(db: Session, book_id: int, data: BookUpdate) -> Book:
    """Apply the fields that were sent.

    Raises BookNotFoundError, DuplicateIsbnError, or TotalCopiesBelowLoansError.
    """
    book = get_book(db, book_id)
    changes = data.model_dump(exclude_unset=True)
    new_total = changes.pop("total_copies", None)

    if "isbn" in changes:
        _ensure_isbn_free(db, changes["isbn"], owner_id=book_id)
    for field, value in changes.items():
        setattr(book, field, value)
    if new_total is not None:
        _set_total_copies(db, book, new_total)

    db.commit()
    db.refresh(book)
    return book


def delete_book(db: Session, book_id: int) -> None:
    """Delete a book together with its returned-loan history.

    Raises BookNotFoundError, or BookHasActiveLoansError while any copy is on loan.
    The returned loans go first (foreign key); after that any loan row left is an
    active one, so the conditional DELETE of the book fails exactly when copies are out.
    Everything runs in one transaction and is rolled back on failure.
    """
    get_book(db, book_id)
    db.execute(
        delete(Loan)
        .where(Loan.book_id == book_id, Loan.returned_at.is_not(None))
        .execution_options(synchronize_session=False)
    )
    result = db.execute(
        delete(Book)
        .where(Book.id == book_id, ~exists().where(Loan.book_id == Book.id))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        raise BookHasActiveLoansError(book_id)
    db.commit()


def _open_loan(db: Session, book_id: int, borrower_id: int) -> None:
    """Insert an active loan; the partial unique index rejects a second one per borrower."""
    db.add(Loan(book_id=book_id, borrower_id=borrower_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AlreadyBorrowedByBorrowerError(book_id, borrower_id) from None


def _take_copy(db: Session, book_id: int) -> None:
    """Atomically decrement available copies; fails if none are left."""
    result = db.execute(
        update(Book)
        .where(Book.id == book_id, Book.available_copies > 0)
        .values(available_copies=Book.available_copies - 1)
    )
    if result.rowcount == 0:
        db.rollback()
        raise NoCopiesAvailableError(book_id)


def borrow_book(db: Session, book_id: int, borrower_id: int) -> Book:
    """Lend one copy of a book to a borrower.

    Copies are interchangeable, so a borrower is linked to the title, and may
    hold only one copy of it at a time. The loan insert and the copy decrement
    commit together or not at all.

    The span covers the whole write path so latency and failures are visible
    per outcome (a raised domain error marks the span as ERROR). The counter
    is incremented only on success, so dashboards reflect real borrows.
    """
    with tracer.start_as_current_span("book.borrow") as span:
        span.set_attribute("book.id", book_id)
        span.set_attribute("borrower.id", borrower_id)

        book = get_book(db, book_id)
        get_borrower(db, borrower_id)

        _open_loan(db, book_id, borrower_id)
        _take_copy(db, book_id)
        db.commit()
        db.refresh(book)

        books_borrowed_counter.add(1, {"book.id": str(book_id), "borrower.id": str(borrower_id)})
        span.set_attribute("book.title", book.title)

        return book


def return_book(db: Session, book_id: int, borrower_id: int) -> Book:
    """Take back the borrower's copy and make it available again.

    Closing the loan is conditional on it still being active, so a repeated
    return fails instead of incrementing the available copies twice.
    """
    book = get_book(db, book_id)
    get_borrower(db, borrower_id)

    closed = db.execute(
        update(Loan)
        .where(
            Loan.book_id == book_id,
            Loan.borrower_id == borrower_id,
            Loan.returned_at.is_(None),
        )
        .values(returned_at=datetime.now(UTC))
    )
    if closed.rowcount == 0:
        raise LoanNotFoundError(book_id, borrower_id)

    db.execute(
        update(Book).where(Book.id == book_id).values(available_copies=Book.available_copies + 1)
    )
    db.commit()
    db.refresh(book)
    return book
