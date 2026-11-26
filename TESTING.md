# Test Suite Documentation

This document describes all 71 test cases organised by type and area.
Run the full suite with:

```bash
uv run pytest -v
```

---

## Unit Tests — Service Layer

These tests target the business logic in `app/services/` in isolation. Services raise
domain exceptions (`app/exceptions.py`); the HTTP status mapping is covered by the
integration tests.
The database session is replaced with a `MagicMock(spec=Session)`, so no
real database or network is involved. They are fast and deterministic.

### Book Service (`tests/unit/test_book_service.py`)

| Test | What it verifies |
|---|---|
| `test_list_books_returns_all` | Returns all books from the DB query |
| `test_list_books_empty` | Returns an empty list when no books exist |
| `test_create_book_success` | Adds a book and calls `add`, `commit`, `refresh` |
| `test_create_book_duplicate_isbn_raises_conflict` | Raises `DuplicateIsbnError` if the ISBN already exists |
| `test_borrow_book_success` | Marks book as borrowed, links borrower, increments OTel counter |
| `test_borrow_book_not_found_raises_not_found` | Raises `BookNotFoundError` when the book ID does not exist |
| `test_borrow_book_already_borrowed_raises_conflict` | Raises `BookAlreadyBorrowedError` when the book is already borrowed |
| `test_borrow_book_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError` when the borrower ID does not exist |

### Borrower Service (`tests/unit/test_borrower_service.py`)

| Test | What it verifies |
|---|---|
| `test_create_borrower_success` | Adds a borrower and calls `add`, `commit` |
| `test_create_borrower_duplicate_email_raises_conflict` | Raises `DuplicateEmailError` if the email already exists |
| `test_get_borrower_success` | Returns the correct borrower by ID |
| `test_get_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError` when the borrower ID does not exist |
| `test_get_borrowed_books_returns_list` | Returns the list of books borrowed by a borrower |
| `test_get_borrowed_books_empty` | Returns an empty list when borrower has no books |
| `test_get_borrowed_books_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError` when the borrower ID does not exist |

---

## Integration Tests — API Endpoints

These tests exercise the full HTTP stack (router → service → SQLAlchemy → SQLite)
using FastAPI's `TestClient` backed by a fresh in-memory SQLite database per test.

### Books API (`tests/integration/test_books_api.py`)

| Test | Endpoint | Expected | What it verifies |
|---|---|---|---|
| `test_list_books_empty` | `GET /books/` | 200 `[]` | Empty list on fresh database |
| `test_list_books_returns_added_books` | `GET /books/` | 200 `[…]` | Returns all added books |
| `test_create_book_returns_201_with_book` | `POST /books/` | 201 | Response body contains correct fields |
| `test_create_book_duplicate_isbn_returns_409` | `POST /books/` | 409 | Duplicate ISBN rejected |
| `test_create_book_missing_field_returns_422` | `POST /books/` | 422 | Missing required field rejected |
| `test_borrow_book_success` | `POST /books/{id}/borrow` | 200 | Book marked as borrowed, borrower linked |
| `test_borrow_book_not_found_returns_404` | `POST /books/{id}/borrow` | 404 | Non-existent book ID rejected |
| `test_borrow_book_already_borrowed_returns_409` | `POST /books/{id}/borrow` | 409 | Re-borrowing a borrowed book rejected |
| `test_borrow_book_borrower_not_found_returns_404` | `POST /books/{id}/borrow` | 404 | Non-existent borrower ID rejected |

### Borrowers API (`tests/integration/test_borrowers_api.py`)

| Test | Endpoint | Expected | What it verifies |
|---|---|---|---|
| `test_create_borrower_returns_201_with_borrower` | `POST /borrowers/` | 201 | Response body contains correct fields |
| `test_create_borrower_duplicate_email_returns_409` | `POST /borrowers/` | 409 | Duplicate email rejected |
| `test_create_borrower_invalid_email_returns_422` | `POST /borrowers/` | 422 | Malformed email rejected |
| `test_create_borrower_missing_name_returns_422` | `POST /borrowers/` | 422 | Missing required field rejected |
| `test_get_borrower_success` | `GET /borrowers/{id}` | 200 | Returns correct borrower |
| `test_get_borrower_not_found_returns_404` | `GET /borrowers/{id}` | 404 | Non-existent ID returns 404 |
| `test_get_borrowed_books_empty` | `GET /borrowers/{id}/books` | 200 `[]` | Empty list when no books borrowed |
| `test_get_borrowed_books_returns_borrowed_book` | `GET /borrowers/{id}/books` | 200 `[…]` | Returns the borrowed book with correct fields |
| `test_get_borrowed_books_borrower_not_found_returns_404` | `GET /borrowers/{id}/books` | 404 | Non-existent borrower returns 404 |

---

## Integration Tests — Security & Validation

All tests in `tests/integration/test_input_validation.py`.
They treat the API as a black box and verify the security contract
independently of any framework or DB internals.

### Input Boundaries — Book fields

| Test | Field | Input | Expected |
|---|---|---|---|
| `test_book_title_empty_string_returns_422` | `title` | `""` | 422 |
| `test_book_title_at_max_length_returns_201` | `title` | 255 chars | 201 |
| `test_book_title_exceeds_max_length_returns_422` | `title` | 256 chars | 422 |
| `test_book_author_empty_string_returns_422` | `author` | `""` | 422 |
| `test_book_author_at_max_length_returns_201` | `author` | 255 chars | 201 |
| `test_book_author_exceeds_max_length_returns_422` | `author` | 256 chars | 422 |

### Input Boundaries — Borrower fields

| Test | Field | Input | Expected |
|---|---|---|---|
| `test_borrower_name_empty_string_returns_422` | `name` | `""` | 422 |
| `test_borrower_name_at_max_length_returns_201` | `name` | 255 chars | 201 |
| `test_borrower_name_exceeds_max_length_returns_422` | `name` | 256 chars | 422 |
| `test_borrower_email_no_at_sign_returns_422` | `email` | `"notanemail"` | 422 |
| `test_borrower_email_missing_domain_returns_422` | `email` | `"bob@"` | 422 |
| `test_borrower_email_whitespace_only_returns_422` | `email` | `"   "` | 422 |

### Input Boundaries — `borrower_id` constraint (`gt=0`)

| Test | Input | Expected | Why |
|---|---|---|---|
| `test_borrow_borrower_id_zero_returns_422` | `0` | 422 | Violates `gt=0` |
| `test_borrow_borrower_id_negative_returns_422` | `-1` | 422 | Violates `gt=0` |
| `test_borrow_borrower_id_one_is_valid_gt_constraint` | `1` | 404 | Passes `gt=0`; borrower not found is a business error, not a validation error |

### ISBN Format Validation

The `isbn` field accepts ISBN-10 and ISBN-13 with or without hyphens.
Hyphens and spaces are stripped before matching.

| Test | Input | Expected | Why |
|---|---|---|---|
| `test_book_isbn10_compact_valid` | `"0306406152"` | 201 | Valid ISBN-10 |
| `test_book_isbn10_hyphenated_valid` | `"0-306-40615-2"` | 201 | Valid ISBN-10 with hyphens |
| `test_book_isbn10_with_x_check_digit_valid` | `"0-306-40615-X"` | 201 | `X` is a valid ISBN-10 check digit |
| `test_book_isbn13_compact_valid` | `"9780306406157"` | 201 | Valid ISBN-13 |
| `test_book_isbn13_hyphenated_valid` | `"978-0-306-40615-7"` | 201 | Valid ISBN-13 with hyphens |
| `test_book_isbn13_979_prefix_valid` | `"9790306406157"` | 201 | ISBN-13 with `979` prefix |
| `test_book_isbn_random_string_returns_422` | `"notanisbn"` | 422 | Not a valid ISBN format |
| `test_book_isbn_all_letters_returns_422` | `"ABCDEFGHIJ"` | 422 | Letters only |
| `test_book_isbn_wrong_length_digits_returns_422` | `"12345678901"` | 422 | 11 digits — no valid ISBN length |
| `test_book_isbn13_wrong_prefix_returns_422` | `"9770306406157"` | 422 | Prefix `977` is not valid for ISBN-13 |
| `test_book_isbn_special_characters_returns_422` | `"!@#$%^&*()"` | 422 | Special characters |

### SQL Injection Resistance

Payloads tested: `' OR '1'='1`, `'; DROP TABLE books;--`,
`' UNION SELECT * FROM borrowers --`, `' OR 1=1--`, `\'; DROP TABLE books;--`

| Test | Target field | What it verifies |
|---|---|---|
| `test_sql_injection_in_book_title_does_not_crash` | `title` | None of the payloads cause a 500 |
| `test_sql_injection_in_book_title_does_not_leak_data` | `title` | Tautology payload does not return extra rows — stored as a literal string |
| `test_sql_injection_in_book_author_does_not_crash` | `author` | None of the payloads cause a 500 |
| `test_sql_injection_in_borrower_name_does_not_crash` | `name` | None of the payloads cause a 500 |
| `test_sql_injection_in_borrower_email_does_not_crash` | `email` | `EmailStr` rejects the payloads with 422, never 500 |
| `test_sql_injection_in_borrow_endpoint_does_not_crash` | `borrower_id` (int) | String payload rejected with 422 by Pydantic, never 500 |

### HTTP Robustness

| Test | Input | Expected | Why |
|---|---|---|---|
| `test_missing_content_type_returns_422` | No `Content-Type` header | 422 | FastAPI cannot parse the body |
| `test_wrong_content_type_returns_422` | `Content-Type: text/plain` | 422 | FastAPI expects `application/json` |
| `test_malformed_json_unclosed_brace_returns_422` | `{"title":"X"` | 422 | JSON parse error |
| `test_malformed_json_plain_text_returns_422` | `"not json at all"` | 422 | JSON parse error |
| `test_empty_body_returns_422` | `""` | 422 | Required fields missing |
| `test_duplicate_json_key_last_value_wins` | `{"title":"first","title":"last",…}` | 201, `title == "last"` | RFC 8259 undefined behaviour — Python keeps the last value; documented as an explicit contract |

---

## Static Security Analysis

**Tool**: [Bandit](https://bandit.readthedocs.io/)  
**Scope**: `app/` (all application code, excluding tests and `.venv`)  
**Runs**: automatically in CI on every push and PR (`lint.yml` → `bandit` job)

```bash
uv run bandit -r app/ -c pyproject.toml
```

Bandit checks for common Python security issues including hardcoded credentials,
insecure random number generators, SQL string concatenation, and unsafe
deserialization. Current baseline: **0 findings**.
