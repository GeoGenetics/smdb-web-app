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

`SMDB_DB_USER` configures one role for both reads and writes. Alternatively,
set `SMDB_DB_READ_USER` and `SMDB_DB_WRITE_USER` (and their corresponding
password variables) when separate roles are available.
