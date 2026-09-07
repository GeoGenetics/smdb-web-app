# SMDB web application

## Development database configuration

Start the SSH tunnel to the user-owned development PostgreSQL cluster, then
create a local `.env` file from `.env.example`. The real `.env` is ignored by
Git and must not contain production credentials.

Create and populate a Python environment before starting the application:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r REQUIREMENTS.txt
```

Load the development variables before starting the app:

```bash
set -a
source .env
set +a
python app.py
```

Set `SMDB_DISABLE_EMAIL=true` in local development to skip outbound receipt
and administrative emails without changing the uploader recorded in the
database. Configure a working mail transport and set it to `false` (or remove
the variable) when email delivery is required.

`SMDB_PREFLIGHT_MODE` controls the additive upload-preflight rollout. It
defaults to `off`, which preserves the legacy upload behavior. The supported
values are `off`, `shadow`, and `enforce`; non-`off` modes are currently
permitted only with `RUN_MODE=development`. In `shadow` mode, a field-sample
upload runs the new read-only preflight immediately before the existing legacy
write path and logs only a summary (table, row count, error/warning counts, and
rule IDs). It never blocks, changes, or reports on the user-visible legacy
upload flow. In `enforce` mode, development field-sample uploads with preflight
errors show an aggregate report and do not open the legacy write transaction;
valid uploads continue through the existing confirmation and insert flow.
The report can generate a metadata-only TSV in the browser. Submitted values
are not added to that download or retained server-side.

`SMDB_DB_USER` configures one role for both reads and writes. Alternatively,
set `SMDB_DB_READ_USER` and `SMDB_DB_WRITE_USER` (and their corresponding
password variables) when separate roles are available.

## Tests

Run the test suite from the repository root after activating the virtual
environment and loading the development configuration. The current legacy
parser imports database configuration, so the SSH tunnel and `.env` settings
must be available for the full suite.

```bash
source .venv/bin/activate
set -a
source .env
set +a

python -m unittest discover -s tests -t . -p '*.py'
```

New preflight-validation tests must remain independently runnable without a
web server, database connection, SSH tunnel, or `.env` file:

```bash
python -m unittest discover -s tests/validation -p 'test_*.py'
```

The SMDB-dev preflight integration checks are intentionally opt-in. They use
real read-only reference-data lookups through the local port-`5433` tunnel and
assert that a unique synthetic field-sample ID remains absent before and after
the tests. They never insert, update, or delete database rows.

```bash
set -a
source .env
set +a
SMDB_RUN_INTEGRATION_TESTS=1 \
  python -m unittest \
    tests.integration.test_upload_preflight_smdb_dev \
    tests.integration.test_preflight_report_rendering \
    tests.integration.test_parse_floats_diagnostics
```

Field-sample uploader acceptance is a separate human step; follow
`docs/field-sample-preflight-user-acceptance.md` using only SMDB-dev and
non-production test data.

The project currently uses only Python's standard-library `unittest`; no
developer-only test dependency is required.
