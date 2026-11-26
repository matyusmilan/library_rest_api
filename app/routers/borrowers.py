from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.pagination import Pagination, pagination
from app.schemas.book import BookResponse
from app.schemas.borrower import BorrowerCreate, BorrowerResponse, BorrowerUpdate
from app.services import borrower_service

router = APIRouter(prefix="/borrowers", tags=["borrowers"])


@router.get("/", response_model=list[BorrowerResponse], summary="List all borrowers")
def list_borrowers(
    page: Pagination = Depends(pagination), db: Session = Depends(get_db)
) -> list[BorrowerResponse]:
    """Return the registered borrowers, ordered by ID."""
    return borrower_service.list_borrowers(db, page.limit, page.offset)


@router.post(
    "/",
    response_model=BorrowerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new borrower",
)
def create_borrower(
    data: BorrowerCreate, request: Request, response: Response, db: Session = Depends(get_db)
) -> BorrowerResponse:
    """Register a new borrower. Returns 409 if the email is already in use.

    The `Location` header points to the new borrower.
    """
    borrower = borrower_service.create_borrower(db, data)
    response.headers["Location"] = str(
        request.app.url_path_for("get_borrower", borrower_id=borrower.id)
    )
    return borrower


@router.get(
    "/{borrower_id}",
    response_model=BorrowerResponse,
    summary="Get a borrower by ID",
)
def get_borrower(borrower_id: int, db: Session = Depends(get_db)) -> BorrowerResponse:
    """Return the details of a specific borrower. Returns 404 if not found."""
    return borrower_service.get_borrower(db, borrower_id)


@router.patch("/{borrower_id}", response_model=BorrowerResponse, summary="Update a borrower")
def update_borrower(
    borrower_id: int, data: BorrowerUpdate, db: Session = Depends(get_db)
) -> BorrowerResponse:
    """Change the fields that are sent; the others stay as they are.

    Returns 404 if the borrower does not exist, and 409 if the email belongs to another borrower.
    """
    return borrower_service.update_borrower(db, borrower_id, data)


@router.delete(
    "/{borrower_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a borrower"
)
def delete_borrower(borrower_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a borrower together with their returned-loan history.

    Returns 404 if the borrower does not exist, and 409 while they hold a borrowed book.
    """
    borrower_service.delete_borrower(db, borrower_id)


@router.get(
    "/{borrower_id}/books",
    response_model=list[BookResponse],
    summary="List books borrowed by a borrower",
)
def get_borrowed_books(borrower_id: int, db: Session = Depends(get_db)) -> list[BookResponse]:
    """Return all books currently borrowed by the given borrower.

    Returns 404 if borrower not found.
    """
    return borrower_service.get_borrowed_books(db, borrower_id)
