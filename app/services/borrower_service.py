from sqlalchemy import delete, exists
from sqlalchemy.orm import Session

from app.exceptions import BorrowerHasActiveLoansError, BorrowerNotFoundError, DuplicateEmailError
from app.models.book import Book
from app.models.borrower import Borrower
from app.models.loan import Loan
from app.schemas.borrower import BorrowerCreate, BorrowerUpdate


def _ensure_email_free(db: Session, email: str, owner_id: int | None = None) -> None:
    """Raise DuplicateEmailError if another borrower (not `owner_id`) already has this email."""
    query = db.query(Borrower).filter(Borrower.email == email)
    if owner_id is not None:
        query = query.filter(Borrower.id != owner_id)
    if query.first() is not None:
        raise DuplicateEmailError(email)


def create_borrower(db: Session, data: BorrowerCreate) -> Borrower:
    """Register a new borrower. Raises DuplicateEmailError if the email exists."""
    _ensure_email_free(db, data.email)
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


def update_borrower(db: Session, borrower_id: int, data: BorrowerUpdate) -> Borrower:
    """Apply the fields that were sent. Raises BorrowerNotFoundError or DuplicateEmailError."""
    borrower = get_borrower(db, borrower_id)
    changes = data.model_dump(exclude_unset=True)

    if "email" in changes:
        _ensure_email_free(db, changes["email"], owner_id=borrower_id)
    for field, value in changes.items():
        setattr(borrower, field, value)

    db.commit()
    db.refresh(borrower)
    return borrower


def delete_borrower(db: Session, borrower_id: int) -> None:
    """Delete a borrower together with their returned-loan history.

    Raises BorrowerNotFoundError, or BorrowerHasActiveLoansError while they hold a copy.
    Same approach as delete_book: returned loans first, then a conditional DELETE that
    fails exactly when an active loan is left, all in one transaction.
    """
    get_borrower(db, borrower_id)
    db.execute(
        delete(Loan)
        .where(Loan.borrower_id == borrower_id, Loan.returned_at.is_not(None))
        .execution_options(synchronize_session=False)
    )
    result = db.execute(
        delete(Borrower)
        .where(Borrower.id == borrower_id, ~exists().where(Loan.borrower_id == Borrower.id))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        raise BorrowerHasActiveLoansError(borrower_id)
    db.commit()


def get_borrowed_books(db: Session, borrower_id: int) -> list[Book]:
    """Return the books a borrower currently has. Raises BorrowerNotFoundError if missing."""
    get_borrower(db, borrower_id)
    return (
        db.query(Book)
        .join(Loan, Loan.book_id == Book.id)
        .filter(Loan.borrower_id == borrower_id, Loan.returned_at.is_(None))
        .all()
    )
