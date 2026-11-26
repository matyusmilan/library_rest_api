from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.exceptions import ConflictError, NotFoundError


def register_error_handlers(app: FastAPI) -> None:
    """Translate domain exceptions into HTTP responses with a `detail` body."""

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})
