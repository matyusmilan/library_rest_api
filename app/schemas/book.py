import re

from pydantic import BaseModel, Field, field_validator

# Applied after stripping hyphens and spaces, so "0-306-40615-2" and "0306406152" both pass.
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
