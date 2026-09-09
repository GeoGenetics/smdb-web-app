# SMDB web application

This repo contains the SMDB web portal for uploads, downloads, and database template information.
You can access this app at: [ https://smdb.ggsc.ku.dk]( https://smdb.ggsc.ku.dk).

SMDB-webapp is a web portal that connects to the SMDB postgres database and provides limited access
to its content. For more information please read the [SMDB user guide](https://github.com/GeoGenetics/geogenetics-internal/wiki/Sample-Metadata-Database-(SMDB)-%E2%80%90-Data-access-guide).

# For developers

This repo can also be used to deploy a test instance of the web portal from here on refered as
devSMDB-web. Together with a development deployment of the SMDB postgres database (devSMDB-psql),
the entire GeoGenetic's Sample Metadata DataBase can be tested and modified.

## Quickguide

After SSH forwarding is configured, the local web app connects to the
development database through its own localhost port:

```text
Your computer                                                <SERVER>

_______________________              ____________________
|devSMDB-web           |             |SSH tunnel         |     devSMDB-psql
|SMDB_DB_HOST=127.0.0.1|             |ssh -L             |    PostgreSQL
|SMDB_DB_PORT=5433     |             |5433:127.0.0.1:5433|     127.0.0.1:5433
|______________________|             |___________________|
      │                                    │                       ▲
      └── TCP to 127.0.0.1:5433 ───────────┴── encrypted SSH ──────┘
```

This quickguide assumes a devSMDB-psql has been configured and is reachable thru 127.0.0.1:5433.

- Clone repository and chanche to dev branch
```bash
git clone https://github.com/GeoGenetics/smdb-web-app
cd smdb-web-app
git checkout dev
```
- Install dependencies in a container
```bash
python -mvenv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r REQUIREMENTS.txt
```
- Configure the web app environment
```bash
cp .env.example .env
#edit .env to the desired configuration
set -a
source .env
set +a
```
- Set ssh tunnel to db hosting server
```bash
ssh -o ExitOnForwardFailure=yes -f -N -L 5433:127.0.0.1:5433 <USER>@<SERVER>
```
- Start web app
```bash
python python app.py -p 5101
```

After these steps devSMDV-web can be accessed thru [http://127.0.0.1:5101](http://127.0.0.1:5101)

## web app environment configuration

```.env``` controls certain aspects of the web portal such as postgres users,
and developmental features being used.

```bash
cat .env.example
# Development database access through the SSH tunnel.
RUN_MODE=development
# Upload preflight is additive. Keep off by default; set shadow to log
# non-blocking field-sample preflight results while preserving legacy uploads.
# In development, enforce blocks field-sample writes only when preflight finds errors.
SMDB_PREFLIGHT_MODE=off
# Skip receipt and administrative email delivery in local development.
SMDB_DISABLE_EMAIL=true
SMDB_DB_HOST=127.0.0.1
SMDB_DB_PORT=5433
SMDB_DB_READ_USER=smdb_app_read
SMDB_DB_READ_PASSWORD=smdb_app_read
SMDB_DB_WRITE_USER=smdb_app_write
SMDB_DB_WRITE_PASSWORD=smdb_app_write
SMDB_DB_NAME=smdb
SMDB_DB_SCHEMA=uploaded_data
```

`RUN_MODE` selects the application’s operating profile. Set `RUN_MODE=development`
when running the web app against devSMDB-psql. It uses development defaults (localhost on port
5433, intended for the SSH-tunnelled user-owned database), enables Flask debug mode, and permits
the additive upload-preflight modes `shadow` and `enforce`. This should be the normal setting for
all development, testing, and user-acceptance work. `RUN_MODE` is not itself a database-security
boundary—explicit `SMDB_DB_*` variables can still override connection settings—so always verify
that your .env points to devSMDB-psql before starting the app.

The only other accepted value is:
- `RUN_MODE=production` — uses production-oriented defaults, runs Flask without debug mode, and does not permit non-off preflight modes.
- `RUN_MODE=development` — uses development-oriented defaults, runs Flask with debug mode, and permits other preflight modes.
If unset, the code defaults to development. Any value other than development or production causes startup to fail.

### Database connection variables

The `SMDB_DB_*` variables identify the PostgreSQL instance and the role used
to access it. Use the development values from `.env.example` when connecting
through the SSH tunnel; do not commit a real `.env` file or passwords.

| Variable | Purpose | Development guidance |
| --- | --- | --- |
| `SMDB_DB_HOST` | PostgreSQL host as seen by the web-app process. | Use `127.0.0.1` when the SSH tunnel terminates locally. |
| `SMDB_DB_PORT` | PostgreSQL TCP port. | Use `5433` for the documented SMDB-dev tunnel. |
| `SMDB_DB_NAME` | Name of the PostgreSQL database to connect to. | Normally `smdb`. |
| `SMDB_DB_SCHEMA` | Schema used for application writes and database-table operations. | Normally `uploaded_data`. |

### Database users and passwords

The application needs both a read configuration and a write configuration.
For simple local development, set the shared pair `SMDB_DB_USER` and
`SMDB_DB_PASSWORD`; the application uses those values for both operations.
For least-privilege deployments, set `SMDB_DB_READ_USER` with
`SMDB_DB_READ_PASSWORD`, and `SMDB_DB_WRITE_USER` with
`SMDB_DB_WRITE_PASSWORD`. The role-specific values take precedence over the
shared values for their respective operation.

If no `SMDB_DB_*_PASSWORD` variable is set, the application falls back to
`PGPASSWORD`; if that is also absent, PostgreSQL/libpq may use a local
`.pgpass` file. Prefer a protected environment file or `.pgpass` over placing
credentials in shell history, source code, or a committed `.env` file.

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

## Tests

Run the complete test suite from the repository root after activating the
virtual environment, loading the development configuration, and starting the
SMDB-dev SSH tunnel. The runner enables the opt-in live tests and refuses a
non-development configuration or a port other than `5433`.

```bash
source .venv/bin/activate
set -a
source .env
set +a

bash scripts/run_tests.sh
```

To run only framework-free tests, with no web server, database connection,
SSH tunnel, or `.env` file, use:

```bash
bash scripts/run_tests.sh --skip-live-db
```

The pure-test mode deliberately omits `tests/date_parser_test.py` and
`tests/integration/`: the legacy parser currently opens a database connection
during import. The full SMDB-dev run covers those tests.

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
    tests.integration.test_parse_floats_diagnostics \
    tests.integration.test_field_sample_postgres_parity
```

Field-sample uploader acceptance is a separate human step; follow
`docs/field-sample-preflight-user-acceptance.md` using only SMDB-dev and
non-production test data.

The project currently uses only Python's standard-library `unittest`; no
developer-only test dependency is required.
