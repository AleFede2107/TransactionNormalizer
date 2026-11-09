# Technical note

## Design decisions

The application separates Flask transport/UI delivery (`app/server.py`), transaction detection and validation (`app/normalizer.py`), and aggregate calculations (`app/metrics.py`). The JSON rules file is the single source of truth consumed by processing and displayed read-only in the interface. The browser keeps the current successful dataset in memory; failed uploads do not overwrite it. Python `Decimal` is used for parsing, precision checks, and totals; the API writes Decimal values as JSON number tokens, while the six-field normalized schema remains distinct from original-record and validation metadata.

The confirmed schema is `id` (string), `amount` (JSON number in major units), `currency` (uppercase code), `timestamp` (UTC ISO 8601 string), `status` (`SUCCESS | FAILED | PENDING`), and `source` (detected format). The rules explicitly distinguish major-unit amounts from format B minor units, require exact two-decimal precision, support only USD/EUR, define per-source status/date mappings, and separate invalid records. Duplicate keys are `(source, normalized id)`; the first valid occurrence is retained. Status counts use valid retained records; monetary totals include only successful retained records and never combine currencies.

## Skills, profiles, and report generation

`app/analysis.py` composes the existing `normalize_dataset` and
`calculate_metrics` functions. The Flask import route and
`python -m app.analyze` use this same deterministic path. The CLI's
`--report-facts` option validates the metrics against the existing calculation
function and emits a minimized packet for explanation.

The workspace skills under `.github/skills/` document analysis and explanation
contracts, and `.github/agents/transaction-agent.agent.md` describes their
sequence. `app/config/agent_profiles.json` defines Auditor and Support Analyst
emphases over the same factual packet. The OpenAI integration in
`app/reporting.py` re-analyzes the uploaded source on the server and sends only
metrics, input positions, source types, transformation descriptions, and
validation reason text. Original records, transaction identifiers, normalized
amounts, and timestamps are omitted. Reason text may contain invalid values,
and the interface discloses that data transfer before report generation.

The user selected OpenAI for report generation. The app uses the Responses API,
sets `store` to false, reads `OPENAI_API_KEY` from the process environment, and
defaults to `gpt-6-luna`, which can be overridden with `OPENAI_MODEL`. No
credential is stored in the repository. Tests use a mocked HTTP response; no
live provider request or generated report was used to verify this implementation.

## AI use and adjustments

AI was used to scaffold the website, Python implementation, and tests. The generated Stitch interface informed the dark, compact dashboard layout, navigation, and emerald accent. No pre-existing project rules or decision history were found. Rather than silently applying common defaults, the implementation was adjusted to the user's confirmed choices: no source-format priority for ambiguous records, no rounding or currency exchange, no guessed status/date, explicit interpretation of format B's `10050` as 100.50, first-valid duplicate retention, and invalid-record separation with original data preserved. The configuration and tests encode these choices.

The custom-skill refactor was also AI-assisted at the user's request. It reuses
the existing normalization and metrics code rather than changing transaction
rules, uses no added dependency, and keeps report facts derived by Python. The
user selected OpenAI before the provider integration was implemented. During
verification, tests caught a missing upload-filename binding introduced while
extracting shared upload parsing; the binding was restored, and the final full
test run passed. No provider output was observed, so report quality remains
unverified against a live model.
