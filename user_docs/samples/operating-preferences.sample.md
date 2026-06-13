# Operating Preferences Sample

Use this file to teach the AI how this team wants Deal Intelligence to behave.

## Team Context

- Team type:
- Product sold:
- Typical buyer:
- Typical deal size:
- Typical sales cycle:
- Main sales motion:

Example:

```text
We are a small AI product team selling to mid-market and enterprise customers.
We do not have a dedicated sales operations team. The AI should draft sensible
classifications and follow-up questions, then ask for confirmation only when
the change could materially alter forecast, stage, or deletion behavior.
```

## Confirmation Policy

Things the AI may draft without stopping:

- Primary industry, industry tags, and customer segment.
- Report wording and dashboard interpretation.
- Suggested questions for missing information.
- Low-risk cleanup proposals that can be corrected later.

Things that need explicit user confirmation:

- Marking a deal as `won` or `lost`.
- Deleting or hard-archiving real data.
- Changing deal value status or amount basis.
- Treating a zero-value deal as strategic.
- Overwriting user config or changing global scoring thresholds.

## Preferred Tone

- Be direct about risks.
- Separate objective alerts from judgment-sensitive observations.
- Do not overstate win probability.
- Explain uncertainty instead of hiding it.

## AI Behavior Notes

Record feedback here when the AI response felt too cautious, too aggressive, or
too vague.

| Date | Situation | Feedback | Desired behavior |
|---|---|---|---|
| YYYY-MM-DD | Example: industry cleanup | Do not leave missing industry as vague human review | Draft if possible; otherwise return a web research task |
