from opentelemetry import metrics, trace
from sqlalchemy.orm import Session

from app.exceptions import (
    BookAlreadyBorrowedError,
    BookNotFoundError,
    DuplicateIsbnError,
)
from app.models.book import Book
from app.schemas.book import BookCreate
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


def list_books(db: Session) -> list[Book]:
    """Return all books in the library."""
    return db.query(Book).all()


def create_book(db: Session, data: BookCreate) -> Book:
    """Add a new book. Raises DuplicateIsbnError if the ISBN exists."""
    existing = db.query(Book).filter(Book.isbn == data.isbn).first()
    if existing:
        raise DuplicateIsbnError(data.isbn)
    book = Book(title=data.title, author=data.author, isbn=data.isbn)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def _get_available_book(db: Session, book_id: int) -> Book:
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise BookNotFoundError(book_id)
    if book.is_borrowed:
        raise BookAlreadyBorrowedError(book_id)
    return book


def borrow_book(db: Session, book_id: int, borrower_id: int) -> Book:
    """Mark a book as borrowed by the given borrower.

    The span covers the whole write path so latency and failures are visible
    per outcome (a raised domain error marks the span as ERROR). The counter
    is incremented only on success, so dashboards reflect real borrows.
    """
    with tracer.start_as_current_span("book.borrow") as span:
        span.set_attribute("book.id", book_id)
        span.set_attribute("borrower.id", borrower_id)

        book = _get_available_book(db, book_id)
        get_borrower(db, borrower_id)

        book.is_borrowed = True
        book.borrower_id = borrower_id
        db.commit()
        db.refresh(book)

        books_borrowed_counter.add(1, {"book.id": str(book_id), "borrower.id": str(borrower_id)})
        span.set_attribute("book.title", book.title)

        return book
