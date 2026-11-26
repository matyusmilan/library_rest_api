"""Domain exceptions raised by the service layer.

They carry no HTTP knowledge; app/error_handlers.py maps them to responses.
"""


class DomainError(Exception):
    """Base class for business-rule violations."""


class NotFoundError(DomainError):
    """A referenced entity does not exist."""


class ConflictError(DomainError):
    """The operation conflicts with the current state of the data."""


class BookNotFoundError(NotFoundError):
    def __init__(self, book_id: int):
        super().__init__(f"Book with id {book_id} not found.")


class BorrowerNotFoundError(NotFoundError):
    def __init__(self, borrower_id: int):
        super().__init__(f"Borrower with id {borrower_id} not found.")


class DuplicateIsbnError(ConflictError):
    def __init__(self, isbn: str):
        super().__init__(f"A book with ISBN '{isbn}' already exists.")


class DuplicateEmailError(ConflictError):
    def __init__(self, email: str):
        super().__init__(f"A borrower with email '{email}' already exists.")


class BookAlreadyBorrowedError(ConflictError):
    def __init__(self, book_id: int):
        super().__init__(f"Book with id {book_id} is already borrowed.")


class NoCopiesAvailableError(ConflictError):
    def __init__(self, book_id: int):
        super().__init__(f"No copies of book with id {book_id} are available.")


class AlreadyBorrowedByBorrowerError(ConflictError):
    def __init__(self, book_id: int, borrower_id: int):
        super().__init__(f"Borrower {borrower_id} already has a copy of book {book_id}.")


class LoanNotFoundError(NotFoundError):
    def __init__(self, book_id: int, borrower_id: int):
        super().__init__(f"Borrower {borrower_id} has no active loan for book {book_id}.")
