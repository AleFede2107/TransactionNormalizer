# Technical note

## Design decisions

The application separates Flask transport/UI delivery (`app/server.py`), transaction detection and validation (`app/normalizer.py`), and aggregate calculations (`app/metrics.py`). The JSON rules file is the single source of truth consumed by processing and displayed read-only in the interface. The browser keeps the current successful dataset in memory; failed uploads do not overwrite it. Python `Decimal` is used for parsing, precision checks, and totals; the API writes Decimal values as JSON number tokens, while the six-field normalized schema remains distinct from original-record and validation metadata.

The confirmed schema is `id` (string), `amount` (JSON number in major units), `currency` (uppercase code), `timestamp` (UTC ISO 8601 string), `status` (`SUCCESS | FAILED | PENDING`), and `source` (detected format). The rules explicitly distinguish major-unit amounts from format B minor units, require exact two-decimal precision, support only USD/EUR, define per-source status/date mappings, and separate invalid records. Duplicate keys are `(source, normalized id)`; the first valid occurrence is retained. Status counts use valid retained records; monetary totals include only successful retained records and never combine currencies.

## AI use and adjustments

AI was used to scaffold the website, Python implementation, and tests. The generated Stitch interface informed the dark, compact dashboard layout, navigation, and emerald accent. No pre-existing project rules or decision history were found. Rather than silently applying common defaults, the implementation was adjusted to the user's confirmed choices: no source-format priority for ambiguous records, no rounding or currency exchange, no guessed status/date, explicit interpretation of format B's `10050` as 100.50, first-valid duplicate retention, and invalid-record separation with original data preserved. The configuration and tests encode these choices.
