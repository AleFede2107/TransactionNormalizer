---
name: explain-results
description: "Explain verified TransactionNormalizer analysis results in the Auditor or Support Analyst profile. Use after deterministic transaction analysis to produce a traceable or plain-language report."
argument-hint: "Verified analysis JSON and profile name"
---

# Explain Results

## Purpose

Turn a verified analysis result into a profile-adapted explanation. This skill
does not normalize records, validate transactions, resolve duplicates, or
recalculate metrics.

## Invocation conditions

Use only after `analyze-transactions` or another trusted caller has supplied
the minimized report-facts JSON derived from a complete, verified analysis.
Use the selected `auditor` or `support_analyst` profile from
`app/config/agent_profiles.json`.

## Inputs

- The verified, minimized report-facts JSON emitted by
  `app.analyze --report-facts`.
- Profile ID: `auditor` or `support_analyst`.
- The configured transaction rules, for explaining recorded transformations
  and evidence-supported input corrections.

## Procedure

1. Confirm the report-facts object has `processed`, `valid_count`,
   `invalid_count`, `transactions`, `invalid_records`, and `status_counts` /
   `currency_totals`.
2. Read the selected profile and `report_contract` from
   `app/config/agent_profiles.json`.
3. Build the report from those verified facts only. Preserve all currencies as
   separate totals and do not alter any counts or reasons.
4. For corrections, cite the recorded reason and configured rule. If the
   intended business value is unknown, ask the user to confirm it rather than
   proposing a guessed value.
5. Return the report as model-generated explanatory text; never label a
   template, placeholder, or unavailable-provider message as a generated report.

## Outputs

A concise report for the requested profile. The Auditor emphasizes validation
reasons, positions, recorded transformations, applicable rules, and traceability.
The Support Analyst explains the same facts in plain language and suggests only
practical corrections supported by the input and rules.

## Failure handling

- Missing required result fields, an unsupported profile, or inconsistent
  metrics must be reported as an inability to explain the result; do not repair
  or silently recalculate it.
- If analysis is missing, run `analyze-transactions` first.
- If model/report generation is unavailable or fails, return an explicit
  failure, not a template presented as an LLM report.
- For empty datasets, explain the verified zero counts and totals without
  implying there were records to review.
