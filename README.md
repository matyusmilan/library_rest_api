# Library Management System

A RESTful API for managing a library's books and borrowers, built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

## Features

- **Books**: list all books, add a new book, borrow a book
- **Borrowers**: register a borrower, retrieve borrower details, list a borrower's currently borrowed books
- **OpenTelemetry**: a span on the borrow operation and a `books.borrowed_total` counter metric
- **Tests**: unit tests (service layer, mocked DB), integration tests (full HTTP stack, in-memory SQLite), and security/boundary tests (input validation, SQL injection resistance, HTTP robustness)
- **Static security analysis**: Bandit scans the application code on every CI run

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) – install with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup

```bash
git clone git@github.com:matyusmilan/library_rest_api.git
cd library_rest_api

# Install all dependencies (including dev tools)
uv sync --extra dev
```

## Running the application

```bash
uv run uvicorn asgi:app --reload
```

The API is available at `http://localhost:8000`.  
Interactive docs (Swagger UI): `http://localhost:8000/docs`  
Alternative docs (ReDoc): `http://localhost:8000/redoc`

The SQLite database file (`library.db`) is created automatically in the project directory on first run.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/books/` | List all books |
| `POST` | `/books/` | Add a new book |
| `POST` | `/books/{book_id}/borrow` | Borrow a book |
| `POST` | `/borrowers/` | Register a new borrower |
| `GET` | `/borrowers/{borrower_id}` | Get borrower details |
| `GET` | `/borrowers/{borrower_id}/books` | List borrower's borrowed books |

### Example requests

**Add a book**
```bash
curl -s -X POST http://localhost:8000/books/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Clean Code", "author": "Robert C. Martin", "isbn": "978-0-13-235088-4"}' | jq
```

**Register a borrower**
```bash
curl -s -X POST http://localhost:8000/borrowers/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Smith", "email": "alice@example.com"}' | jq
```

**Borrow a book**
```bash
curl -s -X POST http://localhost:8000/books/1/borrow \
  -H "Content-Type: application/json" \
  -d '{"borrower_id": 1}' | jq
```

**List books borrowed by a borrower**
```bash
curl -s http://localhost:8000/borrowers/1/books | jq
```

## Running tests

```bash
# Unit tests only (fast, no server or DB required)
uv run pytest tests/unit/ -v

# Integration tests only (full HTTP stack, in-memory SQLite)
uv run pytest tests/integration/ -v

# All tests with coverage report
uv run pytest --cov=app --cov-report=term-missing
```

## Security analysis

```bash
# Static analysis with Bandit (checks for common security issues)
uv run bandit -r app/ -c pyproject.toml
```

Bandit scans the `app/` directory for common security issues (hardcoded credentials, insecure functions, SQL injection patterns, etc.). It runs automatically in CI on every push and PR.

The integration tests also include a dedicated security suite (`tests/integration/test_input_validation.py`) covering:
- Input boundary validation (min/max length, field constraints)
- ISBN format validation (ISBN-10 and ISBN-13)
- SQL injection resistance (tautology, stacked queries, UNION-based payloads)
- HTTP robustness (missing/wrong Content-Type, malformed JSON, empty body)

## Linting and formatting

```bash
# Check for lint issues
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

## Project structure

```
library/
├── app/
│   ├── main.py              # FastAPI app entry point, OTel setup
│   ├── database.py          # SQLAlchemy engine and session
│   ├── models/
│   │   ├── book.py          # Book ORM model
│   │   └── borrower.py      # Borrower ORM model
│   ├── schemas/
│   │   ├── book.py          # Book Pydantic schemas
│   │   └── borrower.py      # Borrower Pydantic schemas
│   ├── routers/
│   │   ├── books.py         # /books endpoints
│   │   └── borrowers.py     # /borrowers endpoints
│   └── services/
│       ├── book_service.py  # Book business logic + OTel instrumentation
│       └── borrower_service.py
├── tests/
│   ├── unit/                # Service-layer tests with mocked DB
│   └── integration/         # End-to-end HTTP tests with in-memory SQLite
├── .github/workflows/
│   ├── ci.yml               # Run tests on every push/PR
│   └── lint.yml             # Ruff lint, format check, and Bandit security scan
├── pyproject.toml           # Dependencies, Ruff config, pytest config
└── uv.lock                  # Locked dependency versions
```

## OpenTelemetry

The application uses console exporters by default (output visible in the terminal). In production, replace `ConsoleSpanExporter` and `ConsoleMetricExporter` in `app/main.py` with an OTLP exporter pointing at your collector.

**Instrumentation choices:**

- **Span – `book.borrow`**: wraps the entire borrow operation (DB lookups + write). This is the most critical write path: it enforces business rules (book exists, not already borrowed, borrower exists) and mutates state. A span here lets you observe latency, error rate, and the specific failure mode (book not found vs. borrower not found) in your tracing backend.

- **Counter – `books.borrowed_total`**: incremented on every successful borrow. This drives inventory dashboards and capacity planning (e.g. alert if the borrow rate drops unexpectedly, indicating a service degradation rather than genuine low demand).
