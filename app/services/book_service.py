from fastapi import HTTPException, status
from opentelemetry import metrics, trace
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.borrower import Borrower
from app.schemas.book import BookCreate

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
    """Add a new book. Raises 409 if ISBN already exists."""
    existing = db.query(Book).filter(Book.isbn == data.isbn).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A book with ISBN '{data.isbn}' already exists.",
        )
    book = Book(title=data.title, author=data.author, isbn=data.isbn)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def borrow_book(db: Session, book_id: int, borrower_id: int) -> Book:
    """
    Borrow a book by marking it as borrowed and linking it to a borrower.

    A span wraps the entire operation so we can observe latency and errors
    for the most critical write path in the system. The borrow counter is
    incremented only on success, so dashboards always reflect real activity.
    """
    with tracer.start_as_current_span("book.borrow") as span:
        span.set_attribute("book.id", book_id)
        span.set_attribute("borrower.id", borrower_id)

        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            span.set_attribute("error", True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book with id {book_id} not found.",
            )

        if book.is_borrowed:
            span.set_attribute("error", True)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Book with id {book_id} is already borrowed.",
            )

        borrower = db.query(Borrower).filter(Borrower.id == borrower_id).first()
        if not borrower:
            span.set_attribute("error", True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Borrower with id {borrower_id} not found.",
            )

        book.is_borrowed = True
        book.borrower_id = borrower_id
        db.commit()
        db.refresh(book)

        books_borrowed_counter.add(1, {"book.id": str(book_id), "borrower.id": str(borrower_id)})
        span.set_attribute("book.title", book.title)

        return book
