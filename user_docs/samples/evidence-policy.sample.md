# Evidence Policy Sample

Use this file to define which sources should affect scoring and which should be
stored as context only.

## Source Trust Rules

| Source type | Default scoring behavior | Notes |
|---|---|---|
| Meeting notes | Can update MEDDPICC and customer themes | Use when customer statements are represented |
| Inbound email reply | Can update MEDDPICC and customer themes | Treat explicit customer statements as evidence |
| User interview | Can update MEDDPICC and customer themes | Usually customer-stated evidence |
| Outbound seller email | Store as context only by default | Do not improve health based only on seller claims |
| Internal note | Store as context only by default | Useful for planning, not customer-validated evidence |

## Feedback Log

| Date | Interaction | Current behavior | User feedback | Desired behavior |
|---|---|---|---|---|
| YYYY-MM-DD | Example outbound email | Stored, not scored | Correct | Keep outbound_unconfirmed out of health |

## Custom Interaction Types

Add proposed custom types here before changing config.

| Type | Meaning | Should score? | Default source confidence |
|---|---|---|---|
| security_review | Customer security review notes | yes, if customer-stated | customer_stated |

Candidate config:

```yaml
interactions:
  custom_types:
    - security_review
```

## Decision Log

| Date | Decision | Why | Applied in config? |
|---|---|---|---|
