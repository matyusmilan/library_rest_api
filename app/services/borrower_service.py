from sqlalchemy.orm import Session

from app.exceptions import BorrowerNotFoundError, DuplicateEmailError
from app.models.book import Book
from app.models.borrower import Borrower
from app.schemas.borrower import BorrowerCreate


def create_borrower(db: Session, data: BorrowerCreate) -> Borrower:
    """Register a new borrower. Raises DuplicateEmailError if the email exists."""
    existing = db.query(Borrower).filter(Borrower.email == data.email).first()
    if existing:
        raise DuplicateEmailError(data.email)
    borrower = Borrower(name=data.name, email=data.email)
    db.add(borrower)
    db.commit()
    db.refresh(borrower)
    return borrower


def get_borrower(db: Session, borrower_id: int) -> Borrower:
    """Return a borrower by ID. Raises BorrowerNotFoundError if missing."""
    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).first()
    if not borrower:
        raise BorrowerNotFoundError(borrower_id)
    return borrower


def get_borrowed_books(db: Session, borrower_id: int) -> list[Book]:
    """Return the books a borrower currently has. Raises BorrowerNotFoundError if missing."""
    borrower = get_borrower(db, borrower_id)
    return borrower.borrowed_books
