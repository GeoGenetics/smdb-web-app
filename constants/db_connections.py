"""Database configuration shared by the SMDB web application.

Configure the application through environment variables. Development mode is
the default and is deliberately pointed at the locally forwarded development
database, never at the production PostgreSQL service.
"""

import os

import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


RUN_MODE_OPTIONS = ("production", "development")
RUN_MODE = os.environ.get("RUN_MODE", "development").lower()

if RUN_MODE not in RUN_MODE_OPTIONS:
    raise RuntimeError(
        f"Unknown RUN_MODE {RUN_MODE!r}; expected one of {RUN_MODE_OPTIONS}."
    )


def _environment(name, default=None):
    """Return a non-empty environment value, otherwise the supplied default."""
    return os.environ.get(name) or default


if RUN_MODE == "production":
    _default_host = "dandypdb01fl"
    _default_port = "5432"
    _default_read_user = "read_user"
    _default_write_user = "upload_user"
else:
    # The development database is exposed locally through an SSH tunnel.
    _default_host = "127.0.0.1"
    _default_port = "5433"
    _default_read_user = None
    _default_write_user = None


active_database_name = _environment("SMDB_DB_NAME", "smdb")
active_host = _environment("SMDB_DB_HOST", _default_host)
active_port = _environment("SMDB_DB_PORT", _default_port)

# SMDB_DB_USER is a convenient single-role setting for local development.
# Separate values allow a future least-privilege read/write deployment.
shared_user = _environment("SMDB_DB_USER")
read_user = _environment("SMDB_DB_READ_USER", shared_user or _default_read_user)
write_user = _environment("SMDB_DB_WRITE_USER", shared_user or _default_write_user)

if not read_user or not write_user:
    raise RuntimeError(
        "Set SMDB_DB_USER, or set both SMDB_DB_READ_USER and "
        "SMDB_DB_WRITE_USER."
    )

# SMDB_DB_PASSWORD is the shared-password counterpart to SMDB_DB_USER. The
# existing PGPASSWORD convention remains a fallback, and omitted passwords let
# libpq use a local .pgpass file when available.
shared_password = _environment("SMDB_DB_PASSWORD", os.environ.get("PGPASSWORD"))
read_password = _environment("SMDB_DB_READ_PASSWORD", shared_password)
write_password = _environment("SMDB_DB_WRITE_PASSWORD", shared_password)


def _psycopg_config(*, user, password):
    config = {
        "host": active_host,
        "dbname": active_database_name,
        "port": active_port,
        "user": user,
    }
    if password is not None:
        config["password"] = password
    return config


def _engine(config):
    """Create an engine without placing credentials in a URL string."""
    url = URL.create(
        "postgresql+psycopg2",
        username=config["user"],
        password=config.get("password"),
        host=config["host"],
        port=int(config["port"]),
        database=config["dbname"],
    )
    return create_engine(url, pool_pre_ping=True)


DATABASE_CONFIG_READ_ONLY = _psycopg_config(
    user=read_user,
    password=read_password,
)

SQL_ALCH_CONFIG = {
    "host": active_host,
    "database": active_database_name,
    "port": active_port,
    "user": write_user,
    "password": write_password,
    "schema_name": _environment("SMDB_DB_SCHEMA", "uploaded_data"),
}

PSYCON_CONFIG = _psycopg_config(user=write_user, password=write_password)

ENGINE_READ_ONLY = _engine(DATABASE_CONFIG_READ_ONLY)
ENGINE = _engine(PSYCON_CONFIG)

# These names are retained for compatibility with the current application.
# New request-handling code should prefer ENGINE.connect() or a fresh
# psycopg2.connect(**PSYCON_CONFIG) call so a PostgreSQL restart cannot leave
# the application using a stale global connection.
PSY_CONN_READ_ONLY = psycopg2.connect(**DATABASE_CONFIG_READ_ONLY)
PSY_CONN = psycopg2.connect(**PSYCON_CONFIG)
