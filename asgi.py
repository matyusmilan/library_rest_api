"""
ASGI entry point for uvicorn.

Usage:
    uvicorn asgi:app --reload

Keeping this separate from app/main.py ensures that the module-level
`app` instance (which starts OTel background threads) is only created
when the server is actually launched, never during test collection.
"""

from app.main import create_app

app = create_app()
