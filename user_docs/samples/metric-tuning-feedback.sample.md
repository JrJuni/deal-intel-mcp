# Metric Tuning Feedback Sample

Use this file to collect feedback before changing metric config or scoring
logic. The goal is to avoid changing thresholds based on one awkward example.

## Current Questions To Watch

- Are `healthy`, `watch`, and `at_risk` bands too optimistic or too strict?
- Are stuck thresholds realistic by stage?
- Are expected close defaults realistic by industry or customer segment?
- Does health reflect real deal strength, or only how much information has been
  collected?
- Should missing evidence increase uncertainty instead of receiving a neutral
  score?

## Feedback Log

| Date | Deal / report | Observed output | User feedback | Possible config or product change |
|---|---|---|---|---|
| YYYY-MM-DD | Example deal | Healthy 72%, but many unknowns | Looks too confident | Raise uncertainty; revisit unknown-first scoring |

## Candidate Config Changes

Only move an item here after similar feedback appears repeatedly.

### Health Bands

Current defaults:

```yaml
metrics:
  health_bands:
    healthy_min: 70
    watch_min: 40
```

Candidate change:

```yaml
metrics:
  health_bands:
    healthy_min:
    watch_min:
```

Reason:

### Stuck Thresholds

Candidate stage-specific thresholds:

```yaml
pipeline:
  stuck_threshold_days_by_stage:
    discovery:
    qualification:
    proposal:
    negotiation:
```

Reason:

### Expected Close Defaults

Candidate defaults:

```yaml
pipeline:
  expected_close:
    default_days:
    days_by_segment:
      startup:
      enterprise:
      public_sector:
    days_by_industry:
      Finance:
      Healthcare:
```

Reason:

## Decision Log

| Date | Decision | Why | Applied in config? | Follow-up check |
|---|---|---|---|---|
