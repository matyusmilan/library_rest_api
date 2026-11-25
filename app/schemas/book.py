import re

from pydantic import BaseModel, Field, field_validator

# Matches ISBN-10 (e.g. 0-306-40615-2 or 030640615X)
# and ISBN-13 (e.g. 978-0-306-40615-7 or 9780306406157).
# Hyphens are stripped before matching so both hyphenated and
# compact forms are accepted.
_ISBN_10_RE = re.compile(r"^\d{9}[\dX]$")
_ISBN_13_RE = re.compile(r"^97[89]\d{10}$")


class BookCreate(BaseModel):
    """Request body for adding a new book."""

    title: str = Field(..., min_length=1, max_length=255, examples=["The Pragmatic Programmer"])
    author: str = Field(..., min_length=1, max_length=255, examples=["David Thomas"])
    isbn: str = Field(..., examples=["978-0-13-595705-9"])

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str) -> str:
        """Accept ISBN-10 and ISBN-13, with or without hyphens."""
        compact = value.replace("-", "").replace(" ", "")
        if _ISBN_10_RE.match(compact) or _ISBN_13_RE.match(compact):
            return value
        raise ValueError(
            "Invalid ISBN. Must be a 10-digit ISBN-10 (last digit may be X) "
            "or a 13-digit ISBN-13 starting with 978 or 979. "
            "Hyphens and spaces are ignored."
        )


class BookResponse(BaseModel):
    """Response body representing a book."""

    id: int
    title: str
    author: str
    isbn: str
    is_borrowed: bool
    borrower_id: int | None

    model_config = {"from_attributes": True}


class BorrowRequest(BaseModel):
    """Request body for borrowing a book."""

    borrower_id: int = Field(..., gt=0, examples=[1])
