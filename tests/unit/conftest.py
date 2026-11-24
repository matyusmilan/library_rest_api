"""Shared fixtures for unit tests."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def mock_db() -> MagicMock:
    """Return a MagicMock that quacks like a SQLAlchemy Session."""
    return MagicMock(spec=Session)
