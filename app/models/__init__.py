"""Import every model so SQLAlchemy can resolve string-based relationships."""

from app.models.book import Book
from app.models.borrower import Borrower
from app.models.loan import Loan

__all__ = ["Book", "Borrower", "Loan"]
