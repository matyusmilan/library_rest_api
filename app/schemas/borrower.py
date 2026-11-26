from pydantic import BaseModel, EmailStr, Field


class BorrowerCreate(BaseModel):
    """Request body for registering a new borrower."""

    name: str = Field(..., min_length=1, max_length=255, examples=["Alice Smith"])
    email: EmailStr = Field(..., examples=["alice@example.com"])


class BorrowerResponse(BaseModel):
    """Response body representing a borrower."""

    id: int
    name: str
    email: str

    model_config = {"from_attributes": True}
