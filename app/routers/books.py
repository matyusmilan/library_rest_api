from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.book import BookCreate, BookResponse, LoanRequest
from app.services import book_service

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/", response_model=list[BookResponse], summary="List all books")
def list_books(db: Session = Depends(get_db)) -> list[BookResponse]:
    """Return all books in the library."""
    return book_service.list_books(db)


@router.get("/{book_id}", response_model=BookResponse, summary="Get a book by ID")
def get_book(book_id: int, db: Session = Depends(get_db)) -> BookResponse:
    """Return a single book. Returns 404 if it does not exist."""
    return book_service.get_book(db, book_id)


@router.post(
    "/",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new book",
)
def create_book(data: BookCreate, db: Session = Depends(get_db)) -> BookResponse:
    """Add a new book to the library. Returns 409 if the ISBN already exists."""
    return book_service.create_book(db, data)


@router.post(
    "/{book_id}/borrow",
    response_model=BookResponse,
    summary="Borrow a book",
)
def borrow_book(book_id: int, body: LoanRequest, db: Session = Depends(get_db)) -> BookResponse:
    """
    Lend one copy of the book to the borrower.

    Returns 404 if the book or borrower does not exist. Returns 409 if no copy is
    available, or if the borrower already holds a copy of this book.
    """
    return book_service.borrow_book(db, book_id, body.borrower_id)


@router.post(
    "/{book_id}/return",
    response_model=BookResponse,
    summary="Return a borrowed book",
)
def return_book(book_id: int, body: LoanRequest, db: Session = Depends(get_db)) -> BookResponse:
    """
    Take back the borrower's copy and make it available again.

    Returns 404 if the book, the borrower or the borrower's active loan does not exist.
    """
    return book_service.return_book(db, book_id, body.borrower_id)
