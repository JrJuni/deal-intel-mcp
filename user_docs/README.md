# User Docs

This folder is the repo-local memory for non-developer users.

Use `docs/` when an AI agent is developing custom tools, changing code, or
checking technical contracts. Use `user_docs/` when a user is operating Deal
Intelligence and wants the assistant to gradually adapt the product to their
sales motion, reporting taste, terminology, risk tolerance, and evidence rules.

In short:

- `docs/` = developer reference for building and maintaining the tool.
- `user_docs/` = user memory for making the tool fit one team's workflow.

## How An AI Assistant Should Use This Folder

When helping a non-developer user, read the relevant user docs before proposing
config changes, report changes, taxonomy changes, or scoring behavior changes.
Treat these files as user preference and operating context, not as executable
truth.

Recommended flow:

1. Record the user's feedback in one of the sample formats below.
2. Look for repeated patterns across several deals or reports.
3. Suggest a config, taxonomy, report, or tool behavior change only when the
   pattern is stable.
4. Keep destructive or high-stakes changes behind explicit user confirmation.
5. Keep draft-first behavior for low-risk classification and reporting polish.

## Included Samples

| File | Purpose |
|---|---|
| `samples/operating-preferences.sample.md` | How this team wants AI to behave, what needs confirmation, and what can be auto-drafted |
| `samples/metric-tuning-feedback.sample.md` | Feedback about health bands, stuck/overdue thresholds, expected-close defaults, and scoring behavior |
| `samples/taxonomy-feedback.sample.md` | Notes about industry, industry tags, customer segments, aliases, and unresolved classification cases |
| `samples/report-review-feedback.sample.md` | Feedback on BI dashboards, CSV/Markdown reports, and executive summaries |
| `samples/evidence-policy.sample.md` | What kinds of customer evidence should affect scoring versus be stored as context only |

## Privacy And Safety

Do not put API keys, MongoDB URIs, OAuth tokens, or other secrets in these
files. Prefer summaries over raw customer-sensitive records. If raw customer
content must be kept, store it in the product data store and reference the deal
or interaction id here.

## Suggested Personal Copies

The files under `samples/` are templates. A real workspace can create files such
as:

- `user_docs/operating-preferences.md`
- `user_docs/metric-tuning-feedback.md`
- `user_docs/taxonomy-feedback.md`
- `user_docs/report-review-feedback.md`
- `user_docs/evidence-policy.md`

Keep the sample files unchanged so future users and AI agents always have a
fresh template.
