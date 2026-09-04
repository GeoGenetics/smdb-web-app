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

The project currently uses only Python's standard-library `unittest`; no
developer-only test dependency is required.
