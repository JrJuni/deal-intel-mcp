# BI Metric Contract

BI, CSV, and Atlas Charts must use the same definitions in this document.
Implementation helpers live in `deal_intel.schema.metrics`.
The shared pipeline-health summary lives in
`deal_intel.schema.pipeline_metrics`.

## Part A - Pipeline Scope and Health

### Pipeline populations

| Population | Included stages | Meaning |
|---|---|---|
| Active | `discovery`, `qualification`, `proposal`, `negotiation` | Deals with ongoing sales activity |
| Stalled | `stalled` | Open deals that need recovery or explicit closure |
| Open | Active + Stalled | Every deal not yet closed |
| Terminal | `won`, `lost` | Closed outcomes |

Stalled value must not be presented as active pipeline value. A report may show
Open value, but it must also expose Active and Stalled values separately.

### Health assessment

- `filled_count >= 1` with a finite numeric `health_pct` means Assessed.
- Assessed deals use the existing MEDDPICC formula. Missing dimensions already
  contribute zero through that formula.
- Deals without a valid assessment are `unassessed`, not `at_risk`.
- Average health must use Assessed deals only.
- Every average health result must include health coverage and unassessed count.

### Health bands

The default bands are:

| Band | Default rule |
|---|---|
| `healthy` | `health_pct >= 70` |
| `watch` | `40 <= health_pct < 70` |
| `at_risk` | `health_pct < 40` |
| `unassessed` | No valid health assessment |

These are MEDDPICC qualification bands, not win probabilities.

The boundaries are operating configuration:

```yaml
metrics:
  health_bands:
    healthy_min: 70
    watch_min: 40
```

Override them in `~/.deal-intel/config.yaml`. Valid configuration must satisfy:

```text
0 <= watch_min < healthy_min <= 100
```

Invalid, non-numeric, or non-finite values fail explicitly instead of being
silently corrected.

## Part B - Pipeline Value

### Amount classifications

`deal_size_krw` is the current central estimate of contract value, not a
probability-weighted forecast. Its confidence and source are represented by
`deal_size_status`.

| Status | Meaning | Valid amount |
|---|---|---|
| `unknown` | The opportunity is real but it is too early to estimate value | No amount or range |
| `rough_estimate` | Seller estimate based on scope, seats, or comparable deals | Positive amount; optional positive range |
| `customer_budget` | The customer disclosed a budget or budget range | Positive amount; optional positive range |
| `quoted` | A quote or formal commercial proposal was sent | Positive amount; optional positive range |
| `strategic_zero` | Deliberate no-revenue work such as a reference project or free sample | Exactly zero |

The optional range fields are `deal_size_low_krw` and
`deal_size_high_krw`. When omitted, both default to `deal_size_krw` for metric
calculation. A range must contain the central estimate.

`None` and zero have different meanings:

- Missing amount with `unknown` means the value is not known yet.
- Zero is valid only with `strategic_zero`.
- A zero or negative amount without `strategic_zero` is invalid data.

Existing positive `deal_size_krw` values without a status remain included for
backward compatibility, but they increment `unclassified_amount_count`.

### Pipeline value outputs

For each requested stage population:

- `pipeline_value_krw`: sum of valid central amounts
- `pipeline_value_low_krw` / `pipeline_value_high_krw`: known value range
- `validated_pipeline_value_krw`: sum of `customer_budget` and `quoted`
  central amounts
- `amount_coverage_pct`: known values, including `strategic_zero`, divided by
  all deals in the population
- `missing_amount_count`: valid unknown or missing values
- `invalid_amount_count`: contradictory or malformed amount data
- `unclassified_amount_count`: legacy positive amounts without a status
- `strategic_zero_count`: intentional zero-revenue opportunities

Unknown and invalid amounts are excluded from value sums. They are never
silently imputed as zero. When the population is empty,
`amount_coverage_pct` is `null`, not 100%.

Active, Stalled, and Open pipeline values use the stage populations from Part
A. Won and lost amounts are excluded from current pipeline value and belong
to historical outcome metrics.

Weighted forecast is deliberately separate. It will require an explicit
probability contract and must not reuse MEDDPICC health bands as win
probabilities.

### Expected versus actual close date

- `expected_close_date` is the current sales estimate and may change while a
  deal is open.
- `actual_close_date` is the business-effective won/lost date and exists only
  for terminal deals.
- `stage_history.entered_at` is the system mutation timestamp used for audit
  and stage velocity. It is not a substitute for the business close date.
- Moving a terminal deal back to an open stage clears `actual_close_date`.

When win-rate period filtering is implemented, it must use
`actual_close_date`. Terminal records without a valid actual date are excluded
from period metrics and produce a data-quality warning. They do not silently
fall back to the stage-history timestamp.

### Expected close defaults

When a new deal omits `expected_close_date`, the system derives one from
configuration:

```yaml
pipeline:
  expected_close:
    default_days: 7
    days_by_industry:
      공공: 60
      대기업: 28
```

- A user-provided ISO date always wins and records
  `expected_close_date_source: user_provided`.
- An exact case-insensitive industry match records `config_industry`.
- Otherwise `default_days` is used and records `config_default`.
- Default and industry day values must be non-negative integers.
- These defaults are operating assumptions, not customer-confirmed dates.

### User approval before persistence

Meeting analysis may propose a value, range, status, and evidence, but it must
not mutate stored deal-value fields.

1. Surface the proposed status, central value, range, and evidence.
2. Ask the user whether that classification should be saved.
3. Persist it only after an affirmative response through an explicit
   deal-value update operation.

A value explicitly supplied by the user while creating or editing a deal
counts as approval. LLM inference, meeting-note extraction, bulk backfill, and
similar-deal estimation do not. The future update tool must enforce this
boundary and store the user's optional rationale in `deal_size_note`.

`create_deal` accepts the approved initial value fields directly:
`deal_size_krw`, `deal_size_status`, `deal_size_low_krw`,
`deal_size_high_krw`, and `deal_size_note`. The same validation contract above
applies before storage. A bare `deal_size_krw: 0` does not save immediately;
it returns a clarification error instructing the assistant to ask whether the
deal is an intentional `strategic_zero` or an `unknown` amount. If the caller
explicitly sends `deal_size_status: unknown` with zero amount fields, the
system normalizes those amount fields to `null` before storage. A known status
such as `quoted` still requires a positive amount. A positive amount supplied
through `create_deal` also requires an explicit status (`rough_estimate`,
`customer_budget`, or `quoted`) so new records do not enter BI as unclassified
amounts.

## Part C - Stuck, Overdue, and Win Rate

### Stuck

- Only Active deals can be stuck.
- `days_in_stage >= configured threshold` means stuck.
- Thresholds remain configurable per stage.
- A zero threshold disables stuck classification for that stage.
- Stalled and terminal deals are `not_applicable`, not stuck.
- Missing, malformed, future, or current-stage-mismatched history is
  `unassessed`, not healthy.
- Recent meeting activity does not change stuck status.

### Overdue

- An Open deal is overdue when
  `as_of - expected_close_date > grace_days`.
- Active and Stalled deals are eligible; terminal deals are not.
- Today is not overdue when the default grace period is zero.
- Missing and invalid expected close dates remain separate assessment states.
- `overdue_days` reports calendar days past the expected date.

```yaml
metrics:
  overdue:
    grace_days: 0
```

### Win rate

```text
win_rate_pct = won / (won + lost) * 100
```

- Active and Stalled deals are excluded.
- No closed deals returns `null`, not zero percent.
- Strategic zero Won deals count in deal-count win rate.
- Period filtering uses inclusive `actual_close_date` boundaries.
- Missing or invalid actual dates are excluded from period metrics with
  warnings.
- A small sample still returns its rate with an insufficient-sample warning.

```yaml
metrics:
  win_rate:
    minimum_closed_sample: 10
```

Amount-weighted win rate is not part of Part C.

### Attention reasons

A deal can preserve multiple reasons in priority order:

```text
stalled -> overdue -> stuck -> at_risk
```

Reason counts may overlap. A future total attention-deal KPI must count unique
deals rather than summing reason counts.

## Part D - Data Quality and Reporting Context

### Field quality states

Each governed field has one of five states:

| State | Meaning |
|---|---|
| `valid` | Present, structurally valid, and confirmed |
| `estimated` | Present and usable, but derived from an operating assumption |
| `missing` | Required for the deal's current lifecycle stage but absent |
| `invalid` | Present but contradictory, malformed, or unclassified |
| `not_applicable` | Not required for the deal's current lifecycle stage |

Coverage counts both `valid` and `estimated` fields as usable. Confirmed
coverage counts only `valid` fields. Reports must expose both values so an
estimate is never presented as customer-confirmed data.

### Lifecycle requirements

The universal fields are company, industry, deal stage, and stage history.

- Open deals also require an expected close date and classified deal value.
- Qualification and later stages require at least one meeting and a valid
  MEDDPICC health assessment.
- Won and Lost deals require `actual_close_date`.
- Lost deals additionally require `close_reason`.

Config-derived expected close dates and `rough_estimate` amounts are
`estimated`. User-provided close dates and classified customer budget, quote,
unknown, or strategic-zero values are `valid`.

### Reporting context

```yaml
reporting:
  timezone: Asia/Seoul
```

- Stored system timestamps remain timezone-aware UTC.
- Business-date defaults use the configured IANA timezone.
- Responses that represent a report snapshot expose `as_of`, `timezone`, and
  UTC `generated_at`.
- Callers may supply `as_of` as `YYYY-MM-DD` for reproducible date arithmetic.
- An explicit `as_of` evaluates the current collection using that date. It
  does not reconstruct historical document state for current-state metrics.
  `pipeline_trend` reads from the M5 `analytics_snapshots` collection.
- Invalid timezones fail as configuration errors. Invalid `as_of` values fail
  as input errors.

Parts A through D complete the Milestone 1.1 metric contract.

## Milestone 1.2 - Shared Pipeline Health Summary

`build_pipeline_health_summary` is the official in-memory calculator for
pipeline health metrics. It accepts already-fetched deal documents, an `as_of`
business date, metric settings, and optional exact `stage` / `industry`
filters. It does not access MongoDB, embeddings, or LLM providers.

The summary applies filters before calculation and returns:

- `filters`: applied exact-match filters.
- `kpis`: active/open/stalled/terminal counts, active/open value, active
  average health and coverage, stuck/overdue/attention counts, win rate, and
  data-quality coverage.
- `stage_breakdown`: all canonical stages in this order:
  `discovery`, `qualification`, `proposal`, `negotiation`, `stalled`, `won`,
  `lost`.
- `health_bands`: `healthy`, `watch`, `at_risk`, `unassessed` counts.
- `attention_reasons`: overlapping reason counts plus unique attention deals.
- `pipeline_values`: Active, Stalled, and Open value summaries from Part B.
- `win_rate`: terminal-only win-rate summary from Part C.
- `data_quality`: usable and confirmed quality coverage from Part D.
- `warnings`: data-quality and sample-size warning codes.

`get_insights("pipeline_overview")` consumes this shared calculator. Its
legacy aliases remain available:

- `stages`
- `total_deals`
- `total_size_krw`

`total_size_krw` now follows the Part B contract and equals
`pipeline_values.open.pipeline_value_krw`, not a sum of every terminal and open
deal amount.

`get_metrics(metric_type="pipeline_health")` is the direct MCP metric view over
the same calculator. It supports exact `stage` and `industry` filters and
returns the full summary surface without LLM or embedding work.

## Milestone 5.6 - Pipeline Trend

`get_metrics(metric_type="pipeline_trend")` reads the M5
`analytics_snapshots` collection and compares the latest snapshot per deal at
the start and end of a lookback window.

Defaults and limits:

- `lookback_days`: default `7`, valid range `1..365`
- `as_of`: business end date, default from reporting timezone
- `stage`: optional exact snapshot `deal_stage` match
- `industry`: optional exact snapshot `industry` match

The trend summary includes:

- `window`: start/end date and lookback length
- `start` and `end`: active/open counts, open pipeline value, average health,
  attention count, won count, lost count
- `delta`: end minus start for each comparable KPI
- `stage_changes`: stage transitions plus deals entering or exiting the
  window baseline
- `warnings`: `no_snapshots_in_window`, `missing_start_baseline`,
  `missing_end_baseline`, `insufficient_snapshots`

The calculator dedupes repeated `event_id` snapshots defensively. It does not
call an LLM, does not use embeddings, and does not write to MongoDB.

## Milestone 5.7 - Pipeline Trend Report

`export_report(report_type="pipeline_trend")` converts the M5.6 trend summary
into local CSV and Markdown artifacts. It uses the same `lookback_days`,
`as_of`, `stage`, and `industry` contracts as `get_metrics(metric_type="pipeline_trend")`.

The CSV rows are intentionally flat:

- KPI rows: start, end, and delta values
- stage transition rows
- stage entered rows
- stage exited rows

This report reads from `analytics_snapshots`, does not call an LLM or embedding
provider, and does not write to MongoDB.

## Milestone 4.1 - Deal Gaps

`get_deal_gaps` is the first user-facing data-quality action view. It does not
try to make every table field complete. Instead, it turns existing metric
signals into prioritized customer-attack gaps:

- missing or weak information needed for the next sales action
- estimated or invalid forecast fields that reduce forecast trust
- terminal deal postmortem fields such as `actual_close_date` and `close_reason`

The tool reuses the shared metric primitives:

- `assess_deal_data_quality`
- `assess_pipeline_timing`
- `classify_health`
- `build_attention_reasons`
- `meddpicc_latest.gaps`

It is read-only, uses `list_deals_for_metrics()`, and does not call LLMs,
embedding providers, or MongoDB writes. Raw meeting notes, contacts, and vectors
stay out of the response.
