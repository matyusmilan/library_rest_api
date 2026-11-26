from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from app.schemas.patch import PartialUpdate

# Field rule shared by BorrowerCreate and BorrowerUpdate.
Name = Annotated[str, Field(min_length=1, max_length=255)]


class BorrowerCreate(BaseModel):
    """Request body for registering a new borrower."""

    name: Name = Field(..., examples=["Alice Smith"])
    email: EmailStr = Field(..., examples=["alice@example.com"])


class BorrowerUpdate(PartialUpdate):
    """Request body for changing a borrower. Send only the fields to change."""

    name: Name | None = None
    email: EmailStr | None = None


class BorrowerResponse(BaseModel):
    """Response body representing a borrower."""

    id: int
    name: str
    email: str

    model_config = {"from_attributes": True}
