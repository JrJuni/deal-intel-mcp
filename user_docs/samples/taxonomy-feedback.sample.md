# Taxonomy Feedback Sample

Use this file to collect feedback about primary industry, industry tags, and
customer segment classification.

## Mental Model

- `industry`: the main business vertical used for pipeline and forecast
  grouping.
- `industry_tags`: additional verticals for cross-industry accounts.
- `customer_segment`: maturity, ownership, size, funding stage, or public-sector
  style descriptor.

Example:

```text
보험·금융·대기업 -> industry=Insurance, industry_tags=[Insurance, Finance],
customer_segment=enterprise
```

## Classification Feedback

| Date | Company | Current classification | User feedback | Desired classification | Confidence |
|---|---|---|---|---|---|
| YYYY-MM-DD | Example Co | industry=IT | This is really Healthcare AI | industry=Healthcare, tags=[Healthcare, IT] | medium |

## Alias Candidates

Use this when the same label appears repeatedly and should become a taxonomy
rule.

| Raw label | Suggested canonical industry | Suggested tags | Suggested segment | Notes |
|---|---|---|---|---|
| 항공MRO | Aviation Mobility | Aviation Mobility | mid_market | If repeated, add as an alias |

## Research Rows

When the product returns a `research_missing_industry` row, paste the result
here after web lookup.

| Date | Company | Research query | Finding | Update applied? |
|---|---|---|---|---|

## Decision Log

| Date | Decision | Why | Applied how |
|---|---|---|---|
