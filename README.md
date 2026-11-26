# Library Management System

A RESTful API for managing a library's books and borrowers, built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

## Features

- **Books**: list all books, add a book with several copies, borrow a copy, return a copy
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
| `GET` | `/books/` | List every book in the library |
| `GET` | `/books/available` | List books with at least one copy available to borrow |
| `GET` | `/books/{book_id}` | Get one book |
| `POST` | `/books/` | Add a new book (`201`, `Location` header) |
| `POST` | `/books/{book_id}/borrow` | Borrow a copy of a book |
| `POST` | `/books/{book_id}/return` | Return a borrowed copy |
| `GET` | `/borrowers/` | List borrowers |
| `POST` | `/borrowers/` | Register a new borrower (`201`, `Location` header) |
| `GET` | `/borrowers/{borrower_id}` | Get borrower details |
| `GET` | `/borrowers/{borrower_id}/books` | List borrower's borrowed books |

All list endpoints take `limit` (1-100, default 50) and `offset` (default 0) and return items
ordered by ID, for example `GET /books/available?limit=10&offset=20`. Invalid values return `422`.

### Example requests

**Add a book**
```bash
curl -s -X POST http://localhost:8000/books/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Clean Code", "author": "Robert C. Martin", "isbn": "978-0-13-235088-4", "total_copies": 3}' | jq
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

**Return a book**
```bash
curl -s -X POST http://localhost:8000/books/1/return \
  -H "Content-Type: application/json" \
  -d '{"borrower_id": 1}' | jq
```

**List books borrowed by a borrower**
```bash
curl -s http://localhost:8000/borrowers/1/books | jq
```

## Business rules

A library usually owns several copies of the same book, and it does not matter which physical
copy a reader takes. The API therefore models a **title** with a number of interchangeable copies,
not individual copies.

| Rule | Behaviour |
|---|---|
| Copies | `POST /books/` takes `total_copies` (1-1000, default 1). A book reports `total_copies` and `available_copies`. |
| One copy per title per borrower | A borrower may hold **at most one copy of a given title at a time**. A second borrow of the same title returns `409`. The same borrower can borrow *different* titles, and can borrow the title again after returning it. |
| Borrow | `404` if the book or borrower does not exist. `409` if the borrower already holds a copy, or if no copy is available. |
| Return | Closes the borrower's active loan and frees one copy. `404` if the book, the borrower or the borrower's active loan does not exist. Returning twice returns `404`. |
| Invariant | `available_copies == total_copies - active loans`, always. |
| Not covered yet | Due dates and late returns. A loan records `borrowed_at` and `returned_at` only. |

Borrowing and returning are atomic. A loan is stored in its own table (`loans`) and the copy
counter is changed with a conditional `UPDATE ... WHERE available_copies > 0` in the same
transaction, so concurrent requests cannot hand out the last copy twice. Two database
constraints back this up: a `CHECK` that keeps `0 <= available_copies <= total_copies`, and a
partial unique index that allows only one active loan per borrower and title.

> **Upgrading from an earlier version:** the schema changed (`books.is_borrowed` and
> `books.borrower_id` were replaced by copy counts and a `loans` table). The app creates
> tables with `create_all` and has no migrations, so delete an old `library.db` and let the app
> create a new one.

## Running tests

```bash
# Unit tests only (fast, no server or DB required)
uv run pytest tests/unit/ -v

# Integration tests only (full HTTP stack, in-memory SQLite)
uv run pytest tests/integration/ -v

# All tests with coverage report (fails below 90%, branch coverage on)
uv run pytest --cov=app --cov-report=term-missing
```

For a full description of every test case see [TESTING.md](TESTING.md).

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
│   ├── exceptions.py        # Domain exceptions raised by the services
│   ├── error_handlers.py    # Maps domain exceptions to HTTP 404/409 responses
│   ├── models/
│   │   ├── book.py          # Book ORM model (title with total/available copies)
│   │   ├── borrower.py      # Borrower ORM model
│   │   └── loan.py          # Loan ORM model (one borrowed copy, active until returned)
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

- **Span – `book.borrow`**: wraps the entire borrow operation (DB lookups + write). This is the most critical write path: it enforces business rules (book and borrower exist, the borrower does not already hold a copy, a copy is available) and mutates state. A span here lets you observe latency, error rate, and the specific failure mode in your tracing backend: a domain error marks the span as ERROR and records the exception, so "no copies left" is distinguishable from "borrower not found".

- **Counter – `books.borrowed_total`**: incremented on every successful borrow. This drives inventory dashboards and capacity planning (e.g. alert if the borrow rate drops unexpectedly, indicating a service degradation rather than genuine low demand).
