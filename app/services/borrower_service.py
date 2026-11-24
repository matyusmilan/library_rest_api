from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.borrower import Borrower
from app.schemas.borrower import BorrowerCreate


def create_borrower(db: Session, data: BorrowerCreate) -> Borrower:
    """Register a new borrower. Raises 409 if email is already taken."""
    existing = db.query(Borrower).filter(Borrower.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A borrower with email '{data.email}' already exists.",
        )
    borrower = Borrower(name=data.name, email=data.email)
    db.add(borrower)
    db.commit()
    db.refresh(borrower)
    return borrower


def get_borrower(db: Session, borrower_id: int) -> Borrower:
    """Return a borrower by ID. Raises 404 if not found."""
    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).first()
    if not borrower:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Borrower with id {borrower_id} not found.",
        )
    return borrower


def get_borrowed_books(db: Session, borrower_id: int) -> list[Book]:
    """Return all books currently borrowed by a borrower. Raises 404 if borrower not found."""
    borrower = get_borrower(db, borrower_id)
    return borrower.borrowed_books
