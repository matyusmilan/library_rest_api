"""
Test object factories for unit tests.

Each factory returns a plain ORM model instance with sensible defaults
that can be overridden via keyword arguments. Keeping factories here
(rather than in conftest.py) separates test-data construction from
pytest infrastructure.
"""

from app.models.book import Book
from app.models.borrower import Borrower


def make_book(**kwargs) -> Book:
    defaults = dict(
        id=1,
        title="Clean Code",
        author="Robert C. Martin",
        isbn="978-0-13-235088-4",
        total_copies=1,
        available_copies=1,
        is_borrowed=False,
        borrower_id=None,
    )
    return Book(**{**defaults, **kwargs})


def make_borrower(**kwargs) -> Borrower:
    defaults = dict(
        id=1,
        name="Alice",
        email="alice@example.com",
        borrowed_books=[],
    )
    return Borrower(**{**defaults, **kwargs})
