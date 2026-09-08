#!/usr/bin/env bash
# Run the SMDB web-app test suites from the repository root.
#
# Default: run all discovered tests, including the opt-in SMDB-dev integration
# checks.  --skip-live-db: run only the tests that must not need a database,
# tunnel, web server, or .env file.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/run_tests.sh [--skip-live-db]

Without arguments, runs the complete unittest discovery suite and enables
SMDB-dev integration tests. Load the development .env and start the SSH tunnel
first. The command refuses non-development settings and any port other than
5433.

--skip-live-db
    Run only pure validation and service tests. This mode deliberately omits
    legacy parser tests and tests/integration because the legacy parser still
    opens a database connection during import.
EOF
}

skip_live_db=false
case "${1:-}" in
    "") ;;
    --skip-live-db) skip_live_db=true ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
python_command="${PYTHON:-python}"

if [[ "$skip_live_db" == true ]]; then
    echo "Running pure tests only (SMDB-dev integration tests disabled)."
    "$python_command" -m unittest discover -v -s tests/validation -t . -p 'test_*.py'
    "$python_command" -m unittest discover -v -s tests/services -t . -p 'test_*.py'
    "$python_command" -m unittest -v tests.test_upload_legacy_integration
    exit 0
fi

if [[ "${RUN_MODE:-development}" != "development" ]]; then
    echo "Refusing live database tests: RUN_MODE must be development." >&2
    exit 2
fi

if [[ "${SMDB_DB_PORT:-5433}" != "5433" ]]; then
    echo "Refusing live database tests: SMDB_DB_PORT must be 5433 (SMDB-dev)." >&2
    exit 2
fi

echo "Running complete suite with SMDB-dev integration tests enabled."
SMDB_RUN_INTEGRATION_TESTS=1 \
    "$python_command" -m unittest discover -v -s tests -t . -p '*.py'
