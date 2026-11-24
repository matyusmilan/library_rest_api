from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.book import BookCreate, BookResponse, BorrowRequest
from app.services import book_service

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/", response_model=list[BookResponse], summary="List all books")
def list_books(db: Session = Depends(get_db)) -> list[BookResponse]:
    """Return all books in the library."""
    return book_service.list_books(db)


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
def borrow_book(
    book_id: int, body: BorrowRequest, db: Session = Depends(get_db)
) -> BookResponse:
    """
    Mark a book as borrowed by a given borrower.
    Returns 404 if the book or borrower does not exist, 409 if the book is already borrowed.
    """
    return book_service.borrow_book(db, book_id, body.borrower_id)
