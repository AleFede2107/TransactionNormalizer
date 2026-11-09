---
name: analyze-transactions
description: "Analyze a JSON transaction array with the project's deterministic Python normalization, validation, duplicate handling, and metrics. Use when processing or checking transaction datasets."
argument-hint: "Path to a JSON transaction array"
---

# Analyze Transactions

## Purpose

Produce a verified analysis result using the application's existing Python
normalizer and metrics implementation. Do not reproduce transaction rules in
prompts or calculate metrics in the model.

## Invocation conditions

Use when a user asks to process, normalize, validate, deduplicate, or calculate
metrics for a transaction JSON array.

## Inputs

- One UTF-8 JSON file whose top-level value is an array.
- Processing rules are read from `app/config/normalization_rules.json`.

## Procedure

1. Run from the repository root:

   ```powershell
   .\.venv\Scripts\python.exe -m app.analyze path\to\transactions.json
   ```

2. Treat the command's JSON output as the verified analysis result. The output
   contains `processed`, `valid_count`, `invalid_count`, `transactions`,
   `invalid_records`, and `metrics`.
3. If an explanation is requested, emit only the minimized report facts:

   ```powershell
   .\.venv\Scripts\python.exe -m app.analyze --report-facts path\to\transactions.json
   ```

4. Pass the minimized facts, not the full result with original records, to
   `explain-results`.

## Outputs

By default, one full JSON analysis object. Amounts and currency totals are
emitted as exact JSON number tokens. Each retained transaction includes the
normalized record, original record, input position, and recorded
transformations. Each rejected record includes its original input and recorded
validation reasons. With `--report-facts`, output is a minimized verified fact
packet with metrics, positions, sources, transformations, and validation
reasons, omitting raw originals, transaction identifiers, normalized amounts,
and timestamps.

## Failure handling

- A missing, unreadable, malformed, non-finite, or non-array input is a command
  error; report the error and do not claim an analysis was produced.
- Record-level validation failures are expected analysis output in
  `invalid_records`; do not discard them or reinterpret their reasons.
- Python/configuration errors must be reported as failures, not replaced with
  invented or partial success-shaped results.
