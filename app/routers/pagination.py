from dataclasses import dataclass

from fastapi import Query


@dataclass
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> Pagination:
    """Shared `limit` / `offset` query parameters for list endpoints."""
    return Pagination(limit=limit, offset=offset)
