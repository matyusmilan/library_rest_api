from sqlalchemy.orm import Session

from app.exceptions import BorrowerNotFoundError, DuplicateEmailError
from app.models.book import Book
from app.models.borrower import Borrower
from app.models.loan import Loan
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


def list_borrowers(db: Session, limit: int, offset: int) -> list[Borrower]:
    # Ordering by id keeps pages stable between requests.
    return db.query(Borrower).order_by(Borrower.id).limit(limit).offset(offset).all()


def get_borrower(db: Session, borrower_id: int) -> Borrower:
    """Return a borrower by ID. Raises BorrowerNotFoundError if missing."""
    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).first()
    if not borrower:
        raise BorrowerNotFoundError(borrower_id)
    return borrower


def get_borrowed_books(db: Session, borrower_id: int) -> list[Book]:
    """Return the books a borrower currently has. Raises BorrowerNotFoundError if missing."""
    get_borrower(db, borrower_id)
    return (
        db.query(Book)
        .join(Loan, Loan.book_id == Book.id)
        .filter(Loan.borrower_id == borrower_id, Loan.returned_at.is_(None))
        .all()
    )
