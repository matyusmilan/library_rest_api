# Test Suite Documentation

This document describes all 162 test cases organised by type and area.
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
| `test_list_books_returns_the_requested_page` | Orders by ID and applies the given `limit` and `offset` |
| `test_list_books_empty` | Returns an empty list when no books exist |
| `test_list_available_books_filters_on_available_copies` | Applies the `available_copies > 0` filter before paging |
| `test_get_book_returns_the_book` | Returns the book with the given ID |
| `test_get_book_not_found_raises_not_found` | Raises `BookNotFoundError` when the book ID does not exist |
| `test_create_book_success` | Adds a book and calls `add`, `commit`, `refresh` |
| `test_create_book_makes_all_copies_available` | A new book starts with `available_copies == total_copies` |
| `test_create_book_duplicate_isbn_raises_conflict` | Raises `DuplicateIsbnError` if the ISBN already exists |
| `test_borrow_book_success_opens_loan_and_commits` | Inserts a `Loan` for the book and borrower, commits once, increments the OTel counter |
| `test_borrow_book_not_found_raises_not_found` | Raises `BookNotFoundError`; nothing is written |
| `test_borrow_book_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError`; nothing is written |
| `test_borrow_book_borrower_already_holds_copy_raises_conflict` | Raises `AlreadyBorrowedByBorrowerError` on a duplicate active loan, rolls back, takes no copy |
| `test_borrow_book_no_copies_left_raises_conflict_and_rolls_back` | Raises `NoCopiesAvailableError`, rolls back the loan insert, does not commit or count |
| `test_return_book_success_closes_loan_and_restores_copy` | Closes the loan and increments the available copies in one commit |
| `test_return_book_without_active_loan_raises_not_found` | Raises `LoanNotFoundError`; the copies are not incremented |
| `test_return_book_book_not_found_raises_not_found` | Raises `BookNotFoundError` |
| `test_return_book_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError` |

### Borrower Service (`tests/unit/test_borrower_service.py`)

| Test | What it verifies |
|---|---|
| `test_create_borrower_success` | Adds a borrower and calls `add`, `commit` |
| `test_create_borrower_duplicate_email_raises_conflict` | Raises `DuplicateEmailError` if the email already exists |
| `test_list_borrowers_returns_the_requested_page` | Orders by ID and applies the given `limit` and `offset` |
| `test_get_borrower_success` | Returns the correct borrower by ID |
| `test_get_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError` when the borrower ID does not exist |
| `test_get_borrowed_books_returns_books_from_active_loans` | Returns the books of the borrower's active loans |
| `test_get_borrowed_books_empty` | Returns an empty list when the borrower has no active loans |
| `test_get_borrowed_books_borrower_not_found_raises_not_found` | Raises `BorrowerNotFoundError` when the borrower ID does not exist |

### Database Dependency (`tests/unit/test_database.py`)

Integration tests override `get_db`, so these are the only tests that run the real dependency.

| Test | What it verifies |
|---|---|
| `test_get_db_yields_session_and_closes_it` | Yields a session and closes it when the request finishes |
| `test_get_db_closes_session_when_request_fails` | Closes the session even when the request raises |

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
| `test_book_response_exposes_copy_counts_not_a_borrowed_flag` | `POST /books/` | 201 | Response has exactly `id`, `title`, `author`, `isbn`, `total_copies`, `available_copies` |
| `test_create_book_defaults_to_single_available_copy` | `POST /books/` | 201 | Omitted `total_copies` means one copy, available |
| `test_create_book_with_multiple_copies_makes_all_available` | `POST /books/` | 201 | `total_copies: 5` gives `available_copies: 5` |
| `test_create_book_sets_location_header_to_the_new_book` | `POST /books/` | 201 | `Location` is `/books/{id}` and resolves to the created book |
| `test_create_book_duplicate_isbn_returns_409` | `POST /books/` | 409 | Duplicate ISBN rejected |
| `test_get_book_returns_the_book` | `GET /books/{id}` | 200 | Returns the same body the create call returned |
| `test_get_book_not_found_returns_404` | `GET /books/{id}` | 404 | Non-existent ID rejected |
| `test_create_book_missing_field_returns_422` | `POST /books/` | 422 | Missing required field rejected |
| `test_borrow_book_success` | `POST /books/{id}/borrow` | 200 | Single-copy book ends with `available_copies == 0` |
| `test_borrow_book_not_found_returns_404` | `POST /books/{id}/borrow` | 404 | Non-existent book ID rejected |
| `test_borrow_book_twice_by_same_borrower_returns_409` | `POST /books/{id}/borrow` | 409 | Same borrower cannot borrow the same title twice |
| `test_borrow_book_borrower_not_found_returns_404` | `POST /books/{id}/borrow` | 404 | Non-existent borrower ID rejected |

### Borrowers API (`tests/integration/test_borrowers_api.py`)

| Test | Endpoint | Expected | What it verifies |
|---|---|---|---|
| `test_create_borrower_returns_201_with_borrower` | `POST /borrowers/` | 201 | Response body contains correct fields |
| `test_create_borrower_sets_location_header_to_the_new_borrower` | `POST /borrowers/` | 201 | `Location` is `/borrowers/{id}` and resolves to the created borrower |
| `test_create_borrower_duplicate_email_returns_409` | `POST /borrowers/` | 409 | Duplicate email rejected |
| `test_create_borrower_invalid_email_returns_422` | `POST /borrowers/` | 422 | Malformed email rejected |
| `test_create_borrower_missing_name_returns_422` | `POST /borrowers/` | 422 | Missing required field rejected |
| `test_get_borrower_success` | `GET /borrowers/{id}` | 200 | Returns correct borrower |
| `test_get_borrower_not_found_returns_404` | `GET /borrowers/{id}` | 404 | Non-existent ID returns 404 |
| `test_get_borrowed_books_empty` | `GET /borrowers/{id}/books` | 200 `[]` | Empty list when no books borrowed |
| `test_get_borrowed_books_returns_borrowed_book` | `GET /borrowers/{id}/books` | 200 `[…]` | Returns the borrowed book with correct fields |
| `test_get_borrowed_books_borrower_not_found_returns_404` | `GET /borrowers/{id}/books` | 404 | Non-existent borrower returns 404 |

### Listing and pagination (`tests/integration/test_listing_api.py`)

`GET /books/all` returns every book. `GET /books/available` returns only books with at least
one copy left. `GET /books/` is an alias of `/books/all`. All list endpoints share `limit`
(1-100, default 50) and `offset`, and order by ID.

| Test | Endpoint | What it verifies |
|---|---|---|
| `test_all_lists_every_book_including_fully_borrowed_ones` | `/books/all` | Books with no copy left are still listed |
| `test_available_excludes_books_with_no_copy_left` | `/books/available` | Fully borrowed books are left out |
| `test_available_includes_a_book_with_some_copies_still_free` | `/books/available` | 2 copies, 1 borrowed: still listed |
| `test_returned_book_is_available_again` | `/books/available` | A return puts the book back on the list |
| `test_available_is_empty_on_a_fresh_library` | `/books/available` | Empty list, not an error |
| `test_books_root_is_an_alias_of_all` | `/books/` | Same body as `/books/all` (also proves `/all` is not captured by `/{book_id}`) |
| `test_limit_and_offset_select_a_page_in_id_order` | all three book lists | Pages follow ID order and do not overlap |
| `test_offset_past_the_end_returns_an_empty_page` | all three book lists | Empty list, not an error |
| `test_default_page_size_is_50` | `/books/all` | 51 books yield 50 items |
| `test_limit_of_100_is_accepted` | `/books/all` | Upper boundary of `limit` |
| `test_invalid_pagination_returns_422` | all three book lists | `limit` 0, 101, `abc` and `offset` -1, `x` rejected |
| `test_borrowers_list_is_empty_on_a_fresh_library` | `/borrowers/` | Empty list |
| `test_borrowers_list_returns_everyone_in_id_order` | `/borrowers/` | All borrowers, ordered by ID |
| `test_borrowers_limit_and_offset_select_a_page` | `/borrowers/` | Paging works |
| `test_borrowers_default_page_size_is_50` | `/borrowers/` | 51 borrowers yield 50 items |
| `test_borrowers_invalid_pagination_returns_422` | `/borrowers/` | Same invalid values rejected |

### Lending: copies, borrow and return (`tests/integration/test_lending_api.py`)

Business rules these tests pin down (see the README for the rationale):
a title has interchangeable copies, a borrower holds **at most one copy of a title**
at a time, a return frees exactly one copy, and
`available_copies == total_copies − active loans` always holds.

| Test | Expected | What it verifies |
|---|---|---|
| `test_each_borrow_takes_one_copy` | 200, 200 | 3 copies: two borrowers leave 1 available |
| `test_borrow_returns_409_when_all_copies_are_out` | 409 | The borrower who misses out gets no loan and no copy is taken |
| `test_borrower_cannot_hold_two_copies_of_the_same_title` | 409 | Second borrow by the same borrower rejected, no copy consumed |
| `test_borrower_can_hold_different_titles_at_once` | 200, 200 | The rule is per title, not per borrower |
| `test_return_makes_the_copy_available_again` | 200 | `available_copies` restored; the borrower's list is empty |
| `test_borrower_can_borrow_again_after_returning` | 200 | A returned loan no longer blocks a new one |
| `test_returned_copy_can_be_borrowed_by_someone_else` | 409 → 200 | A waiting borrower succeeds after the return |
| `test_return_without_an_active_loan_returns_404` | 404 | Nothing to return; copies unchanged |
| `test_repeated_return_returns_404_and_does_not_inflate_copies` | 404 | A second return cannot push `available_copies` above the real number |
| `test_return_of_unknown_book_returns_404` | 404 | Non-existent book ID |
| `test_return_by_unknown_borrower_returns_404` | 404 | Non-existent borrower ID |
| `test_available_copies_equals_total_minus_active_loans` | – | Invariant after several borrows and one return, checked through the API only |

### Database constraints (`tests/integration/test_db_constraints.py`)

These talk to an in-memory SQLite database directly. The service layer relies on
them as the last line of defence under concurrent requests.

| Test | What it verifies |
|---|---|
| `test_available_copies_outside_zero_to_total_is_rejected` | CHECK rejects `available > total` and `available < 0` |
| `test_available_copies_within_zero_to_total_is_accepted` | CHECK accepts the boundaries (0, total, 1 of 1) |
| `test_second_active_loan_for_same_book_and_borrower_is_rejected` | Partial unique index: one active loan per borrower and title |
| `test_different_borrowers_may_hold_the_same_book` | The index does not block other borrowers |
| `test_same_borrower_may_hold_different_books` | The index does not block other titles |
| `test_borrower_may_borrow_again_once_the_previous_loan_is_returned` | Returned loans are outside the index |
| `test_loan_must_reference_an_existing_book_and_borrower` | Foreign keys are enforced: an unknown book or borrower is rejected (`PRAGMA foreign_keys=ON` is set in `app/database.py`) |

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
| `test_book_total_copies_within_range_returns_201` | `total_copies` | `1`, `5`, `1000` | 201, value echoed back |
| `test_book_total_copies_out_of_range_or_invalid_returns_422` | `total_copies` | `0`, `-1`, `1001`, `2.5`, `"three"`, `null` | 422 |

### Input Boundaries — Borrower fields

| Test | Field | Input | Expected |
|---|---|---|---|
| `test_borrower_name_empty_string_returns_422` | `name` | `""` | 422 |
| `test_borrower_name_at_max_length_returns_201` | `name` | 255 chars | 201 |
| `test_borrower_name_exceeds_max_length_returns_422` | `name` | 256 chars | 422 |
| `test_borrower_email_no_at_sign_returns_422` | `email` | `"notanemail"` | 422 |
| `test_borrower_email_missing_domain_returns_422` | `email` | `"bob@"` | 422 |
| `test_borrower_email_whitespace_only_returns_422` | `email` | `"   "` | 422 |

### Input Boundaries — `borrower_id` constraint (`gt=0`, borrow and return)

| Test | Input | Expected | Why |
|---|---|---|---|
| `test_borrow_borrower_id_zero_returns_422` | `0` | 422 | Violates `gt=0` |
| `test_borrow_borrower_id_negative_returns_422` | `-1` | 422 | Violates `gt=0` |
| `test_borrow_borrower_id_one_is_valid_gt_constraint` | `1` | 404 | Passes `gt=0`; borrower not found is a business error, not a validation error |
| `test_return_borrower_id_not_positive_returns_422` | `0`, `-1` | 422 | The return endpoint enforces the same constraint |

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

---

## Coverage

Branch coverage is enabled and the build fails below **90%** (`[tool.coverage.report] fail_under`).

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Business logic (services, routers, schemas, exceptions) is at 100%. The remaining gap is
`configure_otel()` in `app/main.py`: tests deliberately run without telemetry, because the
console exporters start background threads that outlive the test session.
