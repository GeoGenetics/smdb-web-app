# Field-sample preflight: user-acceptance protocol

This is the final human-validation step for the Phase 5 development rollout.
It must use SMDB-dev and fictional or otherwise non-production upload data.
No production deployment decision follows automatically from a passing test.

## Participants

Obtain feedback from at least two people who routinely prepare or review
field-sample upload templates. Record their name or role, date, and the
SMDB-dev environment used.

## Test procedure

1. Start the local web app against SMDB-dev with `RUN_MODE=development` and
   `SMDB_PREFLIGHT_MODE=enforce`.
2. Upload a known-invalid synthetic field-sample sheet that produces multiple
   independent errors.
3. Confirm that the report:
   - says no data was written;
   - identifies the relevant template row and column;
   - provides understandable messages for the user to correct;
   - groups multiple findings without hiding later rows;
   - downloads a metadata-only TSV without submitted values.
4. Upload a known-valid synthetic field-sample sheet.
5. Confirm that it follows the existing confirmation and successful-insert
   workflow without a preflight report.

## Acceptance record

| Date | Participant or role | Invalid-report feedback | Valid-upload result | Accepted? | Follow-up |
| --- | --- | --- | --- | --- | --- |
| | | | | | |
| | | | | | |

Mark the Phase 5 user-acceptance checklist item complete only after the
recorded participants accept the report experience or all recorded follow-ups
have been resolved and rechecked.
