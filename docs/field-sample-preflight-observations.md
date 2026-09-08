# Field-sample preflight observations

This is the reviewed, version-controlled record for field-sample preflight
measurements and suspected false positives. It intentionally contains no
uploaded rows, filenames, user identities, email addresses, database errors,
or credentials.

Operational aggregate events are written to the web-app log as compact JSON
after the text prefix `SMDB preflight event=`. The file is currently named
`log_file.csv`, but it is application log output rather than a reliable CSV
dataset. Retain and analyse it using log tooling, not spreadsheet import.

## Event types

| Event | Meaning | Measurement use |
| --- | --- | --- |
| `smdb_preflight_report` | One preflight result for an implemented table type. Contains a random correlation ID, mode, row count, error/warning counts, and stable rule IDs. | Count preflight errors per upload and identify frequently triggered rules. |
| `smdb_preflight_legacy_database_success` | The legacy write committed after a successful preflight run. | Denominator for observed post-preflight legacy write outcomes. |
| `smdb_preflight_legacy_database_error` | The legacy write raised an error after preflight. Contains only the database exception class, not its message. | Count database errors that preflight did not prevent. |
| `smdb_preflight_legacy_write_blocked` | Enforce mode prevented the legacy write because preflight found errors. | Distinguish prevented writes from database failures. |
| `smdb_preflight_unexpected_failure` | Preflight itself failed unexpectedly and legacy upload continued. Contains an exception class and sanitized stack locations. | Investigate operational defects without retaining upload content. |

Events sharing a correlation ID belong to one request. The ID is randomly
generated for that preflight run; it is not a database upload UUID, user ID,
or filename.

## Review cadence

During development/enforce evaluation, review aggregate logs after a meaningful
set of uploads and before any production rollout. Record the summary below:

- number of uploads with a preflight report;
- total and median preflight errors per report;
- number of legacy database errors after a preflight report;
- number of unexpected preflight failures;
- suspected or confirmed false positives.

## False-positive review register

A false positive is a preflight finding that is incorrect under the intended
and documented SMDB policy. A database rejection caused by an unimplemented
rule, a concurrent change, or a known contradiction is **not** automatically a
false positive.

| Review date | Rule ID | Status | Evidence summary without upload data | Decision / follow-up |
| --- | --- | --- | --- | --- |
| _No reviews recorded yet._ |  |  |  |  |

## Aggregate review history

| Period / environment | Preflight reports | Errors per report | Legacy DB errors after preflight | Unexpected failures | False positives | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| _No measurement period recorded yet._ |  |  |  |  |  |  |
