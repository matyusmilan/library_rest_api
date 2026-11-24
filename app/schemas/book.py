from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    """Request body for adding a new book."""

    title: str = Field(..., min_length=1, max_length=255, examples=["The Pragmatic Programmer"])
    author: str = Field(..., min_length=1, max_length=255, examples=["David Thomas"])
    isbn: str = Field(..., min_length=10, max_length=20, examples=["978-0-13-595705-9"])


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
