# Upload route-ownership inventory

This inventory is the Phase 7 baseline for extracting upload routes from
`app.py`. It records current observable behavior; it is not a redesign
specification. A route must preserve this behavior until a separately reviewed
change says otherwise.

## Extraction progress

| Date | Route | Change | Contract test |
| --- | --- | --- | --- |
| 2026-09-09 | `POST /accept_warning` | Moved from `app.py` to `routes/uploads.py`; registered directly on the application so its URL and endpoint name remain `accept_warning`. | `tests/integration/test_upload_route_extraction.py` verifies the URL, POST method, and redirect to `/confirmation_request`. |

## Scope

The upload state machine begins at the upload form on `/`, accepts a file at
`/upload`, displays either warnings or the confirmation page, and then either
writes through `/confirmed` or ends at `/error`/`/success`. The routes below
are coupled through the Flask session and the per-upload session directory.

The current Flask endpoint names are the view-function names because the
routes are registered directly on `app`. Moving them to a blueprint would
normally prefix endpoint names (for example, `uploads.confirmed`), so every
`url_for(...)` use and template form action must be reviewed as part of a
route move.

## Route inventory

| URL and methods | Current endpoint | Decorators / locking | Response and downstream behavior | Template context or session dependency | Filesystem / database effects |
| --- | --- | --- | --- | --- | --- |
| `/` `GET`, `POST` | `index` | `log_info` | Renders upload form; maintenance mode renders `maintainance.html`. The error page posts here, although the view does not consume the POST body. | Initializes `error`, `error_message_user`, and `error_message_admin` only when absent. Provides example sheets, sheet types, date formats, and encodings to `index.html`. | Reads the standard-sheet directory. |
| `/upload` `POST` | `upload_file` | `log_info`; `upload_lock` | Parses and stores an upload, then redirects to `duplicate_warning` when warnings exist or `confirmation_request` otherwise. Failures call `general_error_handling()`. | Clears and initializes the upload session. Reads file and parser form fields; stores upload identity, file name, table name, parser options, receipt address, uploader email, encoding, and preflight location metadata. | Creates per-upload directories; saves/copies original input; writes parsed TSV files and optional warning CSVs; reads reference/database metadata during parsing. No application-table insert occurs here. |
| `/duplicate_warning` `GET` | `duplicate_warning` | none | Renders the duplicate/GPS-warning review page. Its Continue action posts to `accept_warning`; Cancel currently goes directly to `/`. | Requires `session_dir`; warning state is represented by files rather than a dedicated session key. | Reads warning CSVs from the per-upload warning directory. |
| `/accept_warning` `POST` | `accept_warning` | `log_info` | Redirects to `confirmation_request`. | Relies on the existing upload session. | None. |
| `/confirmation_request` `GET` | `confirmation_request` | `log_info` | Renders parsed-data summaries and tables; Continue posts to `confirmed`, Cancel goes to `/`. Errors redirect through `general_error_handling()`. | Requires `error`, `file_name`, `database_table_name`, `session_dir`, and `encoding_user_input`. | Reads parsed TSV files. For field-sample uploads, constructs an in-memory Folium map from parsed coordinates. |
| `/confirmed` `POST` | `confirmed` | `log_info`; `lock` | Runs preflight, then either renders `preflight_report.html` (development enforce with errors), or proceeds through the legacy insert flow and redirects to `success`. Any failure calls `general_error_handling()`. | Requires the parsed-upload state above plus `session_id`, `parser_options`, and `preflight_location_metadata`; sets `upload_id`. | Reads parsed TSVs; runs read-only preflight; inserts into application tables; checks row counts; copies successful original file to the global uploaded-files directory; creates an Excel receipt; sends email unless disabled. Error paths may roll back database rows and delete/move files through `general_error_handling()`. |
| `/success` `GET` | `success` | `log_info` | Renders `results.html`; redirects to `index` if session is in an error state. | Requires `error`, `file_name`, `database_table_name`, and `upload_id`. | Reads inserted rows by upload UUID to build tables and summaries. |
| `/error` `GET` | `error` | `log_info` | Renders `error_basic.html`; normalizes absent/scalar user errors to a safe list. | Reads `error_message_user`, `error_message_admin`, and `email_send`; sets `error=True`. | None directly. |
| `/send_error_details` `POST` | `send_error_details` | `log_info` | Sends an error report email, sets `email_send=True`, then redirects to `error`. | Requires administrator error message, file name, session ID, and session directory/archive layout. | Reads failed-session attachment path and sends email. |
| `/cancel_upload` `GET` | `cancel_upload` | `log_info` | Redirects to `index`. | None. | None. This route is not used by the current main confirmation template; `confirmation_request copy.html` instead posts to it even though it accepts only GET. Keep this discrepancy visible until that legacy preview route is retired. |
| `/pretty_data` `GET` | `pretty_data` | none | Renders `confirmation_request copy.html`. | None. | None. This is a legacy preview route, not part of the main upload flow; do not move it in the first extraction bundle. |

## Supporting error behavior

`general_error_handling()` is shared by the upload, confirmation, and success
routes. It can mark the session as failed, delete uploaded/parsed/original
files, move failed-session data, and delete database rows by upload UUID before
redirecting to `error`. The global `@app.errorhandler(Exception)` also calls
this helper. It must remain available to moved routes without changing its
cleanup arguments or redirect target.

## Shared session contract

| Session keys | Produced by | Consumed by |
| --- | --- | --- |
| `error`, `error_message_user`, `error_message_admin`, `email_send` | `index`, `upload_file`, `general_error_handling`, `error`, `send_error_details` | all upload-flow pages and error handling |
| `session_id`, `session_dir`, `file_name`, `database_table_name` | `upload_file` | warning, confirmation, confirmed, success, error/reporting paths |
| `encoding_user_input`, `parser_options`, `send_receipt_to`, `uploader_email` | `upload_file` | confirmation, confirmed, receipt/error paths |
| `preflight_location_metadata` | `upload_file` | `confirmed` only |
| `upload_id` | `confirmed` | confirmed, success, rollback/error paths |
| `visited_success`, `session_dir_created`, `email` | `upload_file` | legacy/implicit state; retain unchanged until their actual consumers are identified or removed under separate approval |

## Filesystem lifecycle contract

| Location | Created or written by | Read or cleaned by |
| --- | --- | --- |
| Per-upload `session_dir` | `upload_file` | all later upload routes; `general_error_handling()` cleans/moves content on failure. |
| `original_files/` and `temp/` below `session_dir` | `upload_file` | `confirmed` copies the original file after a successful write; error handling cleans it according to the current flags. |
| `parsed_sheets/` below `session_dir` | `upload_file` | `confirmation_request`, `confirmed`, and rollback/error paths read these TSV files. |
| warning-data directory below `session_dir` | `upload_file` | `duplicate_warning` reads warning CSVs. |
| `excel_receipts/excel_receipt.xlsx` below `session_dir` | `confirmed` | emailed from `confirmed`; error handling may clean its parent session directory. |
| global `UPLOADED_FILES` directory | `confirmed` | duplicate-file checks in later `/upload` requests. |
| `deleted_session_data/failed_sessions/` | error/cleanup helpers | `send_error_details` reads an attachment from this archive. |

## Redirect and download contract

```text
/  --POST /upload-->  /duplicate_warning  --POST /accept_warning-->  /confirmation_request
                         |                                             |
                         +--cancel GET /                                 +--POST /confirmed
                                                                               |
                  development enforce + preflight errors -------------------+--> preflight_report.html
                                                                               |
                  valid/off/shadow ------------------------------------------+--> /success

Any handled failure ----------------------------------------------------------> /error
```

The preflight report's TSV download is **not** an application route. Its
template serializes metadata-only rows into the page and browser JavaScript
creates the download locally. Extraction must preserve that template context
(`download_rows`) and client-side contract, not register a server download
endpoint.

## Baseline test status

Current Flask test-client coverage exercises preflight blocking/report
rendering and the direct error-page fallback in
`tests/integration/test_preflight_report_rendering.py`. The older
`tests/test_upload_legacy_integration.py` remains an explicit placeholder.
Before moving each route, add a targeted before/after route test for its
current contract above; do not treat the existing preflight test as full route
coverage for `/upload`, warnings, confirmation, successful insertion, or
cleanup behavior.
