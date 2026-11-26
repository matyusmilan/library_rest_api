"""Unit tests for the production get_db dependency.

Integration tests replace get_db with an in-memory override, so these tests
are the only place where the real dependency is exercised.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.database import get_db


def test_get_db_yields_session_and_closes_it():
    session = MagicMock()
    with patch("app.database.SessionLocal", return_value=session):
        dependency = get_db()

        assert next(dependency) is session
        session.close.assert_not_called()

        with pytest.raises(StopIteration):
            next(dependency)

    session.close.assert_called_once()


def test_get_db_closes_session_when_request_fails():
    session = MagicMock()
    with patch("app.database.SessionLocal", return_value=session):
        dependency = get_db()
        next(dependency)

        with pytest.raises(RuntimeError):
            dependency.throw(RuntimeError("request failed"))

    session.close.assert_called_once()
