from typing import Self

from pydantic import BaseModel, model_validator


class PartialUpdate(BaseModel):
    """Base for PATCH bodies: every field is optional, but at least one must be sent.

    A field that is sent may not be null: null would be ambiguous between
    "clear the value" and "leave it alone", and no field here is nullable.
    """

    @model_validator(mode="after")
    def _require_a_change_without_nulls(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(nulls)}.")
        return self
