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
- `Other (specify in "Other values" column)`, `Data not collected`, and any
  other approved method outside the trigger's three fixed category arrays do
  not receive a category-specific finding. They will receive the generic depth
  checks in the next Phase 3 checkpoint, matching the trigger's fall-through
  behavior.
- This slice deliberately does not yet reproduce all requirements in
  `field_sample_required_insert_check()` or all field-sample triggers. Those
  rules remain database-enforced until a later, explicitly documented slice.
- A reference-data provider failure is an operational error and propagates as
  `ReferenceDataLookupError`; it is never converted into an allowed-value
  result or a user-data validation finding.
