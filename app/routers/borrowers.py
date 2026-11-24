from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.book import BookResponse
from app.schemas.borrower import BorrowerCreate, BorrowerResponse
from app.services import borrower_service

router = APIRouter(prefix="/borrowers", tags=["borrowers"])


@router.post(
    "/",
    response_model=BorrowerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new borrower",
)
def create_borrower(data: BorrowerCreate, db: Session = Depends(get_db)) -> BorrowerResponse:
    """Register a new borrower. Returns 409 if the email is already in use."""
    return borrower_service.create_borrower(db, data)


@router.get(
    "/{borrower_id}",
    response_model=BorrowerResponse,
    summary="Get a borrower by ID",
)
def get_borrower(borrower_id: int, db: Session = Depends(get_db)) -> BorrowerResponse:
    """Return the details of a specific borrower. Returns 404 if not found."""
    return borrower_service.get_borrower(db, borrower_id)


@router.get(
    "/{borrower_id}/books",
    response_model=list[BookResponse],
    summary="List books borrowed by a borrower",
)
def get_borrowed_books(
    borrower_id: int, db: Session = Depends(get_db)
) -> list[BookResponse]:
    """Return all books currently borrowed by the given borrower. Returns 404 if borrower not found."""
    return borrower_service.get_borrowed_books(db, borrower_id)
