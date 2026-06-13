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

## User-Created Documents

Users may create their own memory documents in this folder. "User-created" also
includes documents that the user explicitly asks an AI assistant to create.

Examples:

- `user_docs/public-sector-sales-notes.md`
- `user_docs/pricing-objections.md`
- `user_docs/founder-sales-style.md`
- `user_docs/enterprise-security-feedback.md`

Keep custom documents as plain Markdown files directly under `user_docs/`.
Prefer short, readable slugs such as `pricing-objections.md`. Do not create
nested folders unless the project later adds an explicit convention for them.

AI assistants should prefer existing documents when the topic clearly fits. They
should create a new custom document only when the user explicitly asks for one,
or when the user's feedback introduces a stable topic that does not fit the
existing memory files.

## Future MCP User-Memory Tool Policy

If this project adds MCP tools for user memory, they should be narrow memory
tools, not general-purpose file editors.

Recommended tools:

- `record_user_memory`: append durable user feedback to an existing or
  user-requested memory document.
- `get_user_memory`: read relevant memory documents so an AI assistant can adapt
  answers, reports, taxonomy suggestions, and metric-tuning proposals.

Recommended write rules:

- Append by default. Avoid rewriting whole documents unless the user explicitly
  asks for cleanup or consolidation.
- Allow both built-in categories and user-requested custom Markdown documents.
- Restrict writes to safe Markdown files directly under `user_docs/` or an
  explicitly configured user-memory directory.
- Reject path traversal, absolute paths, hidden files, executable extensions,
  and nested paths unless a future policy explicitly allows them.
- Require safe document slugs, for example `pricing-objections.md`.
- Use the tool only when the user gives durable feedback or explicitly says to
  remember, record, store, or update a preference.

Recommended secret handling:

- Never store API keys, OAuth tokens, MongoDB URIs, private keys, session
  cookies, or credential-like strings.
- Mask low-risk accidental snippets when possible.
- Reject high-risk secret-shaped values instead of silently writing them.
- General preference statements such as "we use OpenAI API in pro mode" are
  fine; actual credentials are not.

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
files. Prefer summaries over raw customer-sensitive records.

If raw customer content must be kept, store it in the product data store and
reference the deal or interaction id here. User-memory files should capture the
lesson, preference, or operating rule learned from the interaction, not become a
shadow data store for full emails, meeting transcripts, or contact lists.

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
