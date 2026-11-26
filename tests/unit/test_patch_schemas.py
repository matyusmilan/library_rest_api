"""Unit tests for PATCH request bodies: what counts as a valid partial update."""

import pytest
from pydantic import ValidationError

from app.schemas.book import BookUpdate


def test_book_update_accepts_a_single_field():
    update = BookUpdate(title="New title")

    assert update.model_fields_set == {"title"}
    assert update.model_dump(exclude_unset=True) == {"title": "New title"}


def test_book_update_rejects_an_empty_body():
    with pytest.raises(ValidationError, match="At least one field"):
        BookUpdate()


@pytest.mark.parametrize("field", ["title", "author", "isbn", "total_copies"])
def test_book_update_rejects_a_null_field(field):
    with pytest.raises(ValidationError, match="cannot be null"):
        BookUpdate(**{field: None})


@pytest.mark.parametrize(
    "body",
    [{"isbn": "notanisbn"}, {"total_copies": 0}, {"total_copies": 1001}, {"title": ""}],
)
def test_book_update_applies_the_same_field_rules_as_create(body):
    with pytest.raises(ValidationError):
        BookUpdate(**body)
