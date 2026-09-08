# Field-sample preflight parity: initial rule slice

This document records the intentionally limited first Python preflight slice.
It runs on canonical field-sample rows after the legacy parser has normalised
the uploaded template. PostgreSQL remains the authoritative final integrity
boundary.

| Stable rule ID | PostgreSQL source | Preflight behaviour |
| --- | --- | --- |
| `field_sample.template_version_required` | `uploaded_data.field_sample_required_insert_check()` | Reports a missing `template_version`. |
| `field_sample.primary_sampling_method_not_allowed` | `fk_primary_sampling_method` | Reports an unknown nonblank `primary_sampling_method`. |
| `field_sample.collected_as_field_control_not_allowed` | `fk_collected_as_field_control` | Reports an unknown nonblank `collected_as_field_control`. |
| `field_sample.age_interval_order` | `valid_age_interval_check` | Reports when `field_sample_age_estimate_oldest` is less than `field_sample_age_estimate_youngest`. |
| `field_sample.environment_context_pair_invalid` | `uploaded_data.check_env_context_compatibility()` | Reports a local/broad environmental-context pair that is absent from `allowed_values.local_env_context`. |
| `field_sample.water_depth_required_for_aquatic_context` | `uploaded_data.check_water_depth_conditionals()` | Reports a missing water depth for the trigger's marine and freshwater broad contexts. |
| `field_sample.interval_sampling_method_requires_interval_depth_only` | `uploaded_data.check_depth_conditionals()` | For Monolith sampling, Coring, and Bulk sampling, requires both interval endpoints and no discrete depth. |
| `field_sample.discrete_sampling_method_requires_discrete_depth_only` | `uploaded_data.check_depth_conditionals()` | For Tube, Syringe, Column, Scraping, and Block sampling, requires discrete depth and no interval endpoints. |
| `field_sample.filter_sampling_method_requires_no_depth` | `uploaded_data.check_depth_conditionals()` | For Filter sampling, rejects any discrete or interval depth. |
| `field_sample.depth_required_for_non_air_water_medium` | `uploaded_data.check_depth_conditionals()` | Requires at least one depth field for a nonblank sampling medium that is neither air nor water. |
| `field_sample.discrete_and_interval_depth_mutually_exclusive` | `uploaded_data.check_depth_conditionals()` | Rejects a discrete depth combined with either interval endpoint. |
| `field_sample.interval_depth_endpoints_must_be_paired` | `uploaded_data.check_depth_conditionals()` | Requires interval top and bottom depth to be both present or both absent. |
| `field_sample.interval_depth_must_be_ascending` | `uploaded_data.check_depth_conditionals()` | Rejects an interval top depth greater than its bottom depth. |
| `field_sample.depth_inference_method_required` | `uploaded_data.check_depth_conditionals()` | Requires `depth_inference_method` when discrete depth or interval top depth is supplied. |
| `field_sample.depth_inference_method_without_depth` | `uploaded_data.check_depth_conditionals()` | Rejects `depth_inference_method` when every depth field is empty. |
| `field_sample.other_values_required_for_primary_sampling_method` | `uploaded_data.validate_other_values()` | Requires a nonblank Other values field when primary sampling method is Other. |

## Intentional differences and boundaries

- The preflight treats a whitespace-only string as absent. The legacy required
  trigger checks `NULL`; the current parser is expected to normalise blank
  template cells to `NULL` before either path reaches PostgreSQL.
- The field-control foreign key accepts `NULL`, so its membership rule skips
  blank values. Other required-field rules are outside this initial slice and
  remain enforced by the database.
- PostgreSQL `CHECK` semantics allow a null age endpoint. The preflight also
  skips the age-order comparison if either endpoint is blank. Numeric parsing
  itself remains the legacy parser's responsibility.
- The environmental-context trigger rejects a missing local or broad value
  because its `EXISTS` lookup is false. Preflight reports the same invalid-pair
  outcome, without querying reference data when either component is blank.
- The database water-depth trigger also rejects a supplied water depth when the
  broad context is not marine or freshwater. That converse rule is deliberately
  deferred: this checkpoint implements only the planned aquatic-context
  requirement and documents the gap rather than silently expanding scope.
- PostgreSQL has no valid no-depth state; see the dedicated deferred-policy
  section below. The relevant parity tests verify database rejection, but
  cannot supply a valid control until the conflict is resolved.
- PostgreSQL has the additional table check `"Invalid depth interval"`, which
  requires `field_sampling_interval_to > field_sampling_interval_from`.
  The depth trigger and Python preflight permit equal endpoints (`from <= to`).
  The parity test exercises strictly ascending endpoints; equality remains a
  documented database-only rejection until the policy is reconciled.
- `Other (specify in "Other values" column)`, `Data not collected`, and any
  other approved method outside the trigger's three fixed category arrays do
  not receive a category-specific finding. They receive the generic depth
  checks, matching the trigger's fall-through behavior.
- The database's `validate_other_values()` trigger parses each entry, maps a
  template header to a canonical column name, and requires an entry for every
  dropdown set to Other. This first preflight rule detects the unambiguous
  missing/blank case for `primary_sampling_method` only; malformed entries,
  mismatched column entries, and Other values in other dropdown columns remain
  database-enforced until name-map-aware validation is added.
- This slice deliberately does not yet reproduce all requirements in
  `field_sample_required_insert_check()` or all field-sample triggers. Those
  rules remain database-enforced until a later, explicitly documented slice.
- A reference-data provider failure is an operational error and propagates as
  `ReferenceDataLookupError`; it is never converted into an allowed-value
  result or a user-data validation finding.

## Deferred database policy issue: no-depth rows

Status: unresolved database-policy contradiction, discovered during Phase 6
parity testing. Do not change either trigger merely to make the Python tests
pass; decide the intended metadata policy first and implement a reviewed
migration later.

Two database triggers currently impose mutually exclusive requirements:

- `uploaded_data.check_depth_conditionals()` requires
  `depth_inference_method` to be `NULL` whenever all of the following are
  `NULL`:
  - `field_sampling_depth_discrete`;
  - `field_sampling_interval_from`;
  - `field_sampling_interval_to`.
- `uploaded_data.field_sample_required_insert_check()` unconditionally rejects
  every insert whose `depth_inference_method` is `NULL`.

Consequently, neither possible value can produce a valid no-depth row:

| Depth fields | `depth_inference_method` | PostgreSQL result |
| --- | --- | --- |
| all empty | empty | `field_sample_required_insert_check()` rejects the row: `depth_inference_method is required` |
| all empty | supplied | `check_depth_conditionals()` rejects the row: `depth_inference_method should not be filled when no depth fields are filled` |

### Affected cases

- `Filter sampling`, whose category rule explicitly requires no discrete or
  interval depth;
- air and water sampling media, whose depth trigger explicitly forbids all
  depth fields;
- any future workflow that correctly represents a sample without a sampling
  depth;
- the Python rule
  `field_sample.depth_inference_method_without_depth`, which accurately mirrors
  the depth trigger but cannot by itself lead to a database-acceptable row.

This does **not** make every freshwater or marine-context row impossible. A
row may have a freshwater broad/local environmental-context pair, a water
depth, and a non-water sampling medium such as sediment with a normal sampling
depth. That is the valid control used by the water-depth parity test.

### Current test treatment

The SMDB-dev parity suite deliberately does the following:

- verifies that invalid Filter rows containing a depth are rejected by
  `check_depth_conditionals()`;
- verifies that a no-depth row with a supplied depth-inference method is
  rejected by `check_depth_conditionals()`;
- does not claim that a valid no-depth control exists, because PostgreSQL
  rejects the alternative with an empty depth-inference method as well.

The relevant tests therefore document actual database behavior rather than
masking it with a test-only bypass or disabled trigger.

### Decision required before a later fix

The database owners need to decide whether no-depth samples are legitimate
metadata. If they are, a future reviewed migration should make the required
insert rule conditional—for example, require `depth_inference_method` only
when a depth is supplied—while retaining the existing category and generic
depth checks. If they are not legitimate, the template dropdown choices and
user-facing guidance for Filter/air/water cases must be reconciled with that
policy instead. Either option needs production-impact review, a migration, and
new SMDB-dev parity cases before deployment.

## Expected differences and database-only conditions

The following differences are intentional for the first preflight release.
They are not Python failures to be hidden or silently relaxed: PostgreSQL
remains authoritative for each item.

| Area | What preflight does | What only PostgreSQL can guarantee | Operational treatment |
| --- | --- | --- | --- |
| Concurrent uploads and direct SQL | Validates the row and reference values observed during the preflight read. | Enforces uniqueness, foreign keys, and trigger conditions at the exact write transaction. Another session can insert the same ID or change a reference value after preflight has completed. | Keep all constraints and triggers enabled. A database rejection after a clean preflight is possible and must remain a normal, actionable upload error. |
| Field-sample identity and parent relationships | Does not validate generated IDs, duplicate IDs, or ancestry. | `field_sample_id_validate_alpha2_only()`, the primary key, the self-reference foreign key, and cycle-prevention trigger validate current table state. | Treat as database-only until an explicitly scoped ID/parent validation slice is designed. |
| Storage allocation and storage state | Does not allocate or inspect `storage_id`. | `sample_set_storage_id()`, `enforce_storage_id_when_check()`, and `allocate_storage_id()` use storage-location and current allocation state. | Database-only: allocating an identifier in Python would be race-prone and could consume or duplicate IDs. |
| Dynamic allowed values and name maps | Uses cached read-only reference lookups for the narrow implemented rule set. | Foreign keys and `validate_other_values()` use the database's current allowed-value tables and name-map records at write time. | A reference-data change between preflight and insert can cause a later database rejection. Refresh caches per workflow only; do not treat a cached result as a write guarantee. |
| Other-values validation outside primary sampling method | Detects a missing/blank entry for `primary_sampling_method = Other`. | `validate_other_values()` validates every allowed-values dropdown column, template-header mapping, malformed entries, and values that duplicate an allowed option. | Database-enforced until a name-map-aware preflight expansion is explicitly approved. |
| Trigger ordering and aggregate feedback | Returns all independent implemented findings in one report. | PostgreSQL executes triggers and constraints in database order and normally returns the first failure only. A different database error may therefore appear before the mapped rule. | This is the intended UX improvement; it is not a semantic mismatch when PostgreSQL rejects the same row for an earlier rule. |
| No-depth rows | Reports the mapped depth-inference finding. | The conflicting required-insert and depth triggers make all no-depth rows impossible; see the deferred-policy section above. | Documented database-policy issue. Do not enable a no-depth preflight success path until a reviewed migration resolves it. |
| Equal interval endpoints | Permits equal endpoints because the mirrored trigger only rejects `from > to`. | The table check `"Invalid depth interval"` additionally requires `to > from`. | Documented database-only rejection until the policy is reconciled and parity behavior is updated. |
| Auditing, logging, and side effects | Performs no write and has no audit side effects. | Database triggers may allocate values or write audit records as part of a real insert/update. | Preflight must remain side-effect free. Transactional parity tests roll back their controlled inserts. |

### Parity interpretation

For this release, **parity** means the following: when preflight reports a
chosen implemented rule for a synthetic row, SMDB-dev rejects the corresponding
invalid row under its current database policy. It does not mean that Python can
prove a later insert will succeed under concurrent changes, dynamic reference
data, or unimplemented cross-table rules. PostgreSQL is intentionally retained
as the final authority for those cases.
