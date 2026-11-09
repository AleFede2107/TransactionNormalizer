# TransactionNormalizer Baseline Assessment

## Scope and baseline identity

This assessment records the repository state before the proposed skills and
agent-profile refactor. No refactor was implemented as part of this assessment.

- **Baseline commit:** `df7e329ffca0c838f1343d3fba8ab798154719c0`
- **Python used for tests and sample processing:** Python 3.11.9, from
  `.venv\Scripts\python.exe`
- **Requirements:** `README.md` specifies Python 3.10 or later.
- **Test framework:** Python `unittest`; no dependency installation was needed.

The test and sample results below were observed on this baseline. Recommendations
are explicitly marked separately.

## Commands and execution actually performed

Commands run from the repository root:

```powershell
git status --short
git --no-pager log -1 --oneline
git rev-parse HEAD
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The test command completed successfully: **15 tests ran, all passed**. The suite
covers normalization, validation, duplicate handling, metrics, and API behavior
(`tests/test_normalizer.py`).

The sample was processed using the Pylance Python code execution tool with the
repository venv explicitly selected and the repository root as the working
directory. It loaded `samples/mixed_transactions.json` with `Decimal` parsing,
then called `normalize_dataset(records, rules)` and
`calculate_metrics(dataset)`. This was a Python snippet execution, not a shell
command. The observed outputs are recorded below.

Repository inspection also checked tracked files, Git status, the adjacent
`AIforDevs` project folders for skill/profile templates, and project source,
configuration, tests, and documentation. No repository `AGENTS.md` or
`SKILL.md`/agent/prompt template was found in the repository or the adjacent
course project folders that were inspected.

## Observed sample-processing results

Input: `samples/mixed_transactions.json`; configured rules:
`app/config/normalization_rules.json`.

- **Processed:** 24
- **Valid and retained:** 17
- **Rejected:** 7
- **Status counts among retained records:** SUCCESS 9, FAILED 4, PENDING 4
- **Successful totals among retained records:** USD 216.75, EUR 123.99
- **Invariant:** 24 processed = 17 valid + 7 rejected

Normalized records (input position, ID, source, amount, currency, UTC timestamp,
status):

| Position | ID | Source | Amount | Currency | UTC timestamp | Status |
|---:|---|---|---:|---|---|---|
| 1 | `tx_001` | `format_a` | 100.50 | USD | `2025-03-10T14:22:00Z` | SUCCESS |
| 2 | `204` | `format_b` | 100.50 | USD | `2025-03-10T14:22:00Z` | SUCCESS |
| 3 | `A-77` | `format_c` | 99.99 | EUR | `2025-03-10T14:22:00Z` | SUCCESS |
| 4 | `tx_failed` | `format_a` | 4.25 | USD | `2025-03-11T08:15:00Z` | FAILED |
| 5 | `tx_pending` | `format_a` | 12.00 | EUR | `2025-03-12T11:30:00Z` | PENDING |
| 6 | `tx_page_001` | `format_a` | 1.25 | USD | `2025-03-15T09:00:00Z` | SUCCESS |
| 7 | `tx_page_002` | `format_a` | 2.50 | EUR | `2025-03-16T09:00:00Z` | FAILED |
| 8 | `tx_page_003` | `format_a` | 3.75 | USD | `2025-03-17T09:00:00Z` | PENDING |
| 9 | `tx_page_004` | `format_a` | 4.00 | EUR | `2025-03-18T09:00:00Z` | SUCCESS |
| 10 | `tx_page_005` | `format_a` | 5.25 | USD | `2025-03-19T09:00:00Z` | SUCCESS |
| 11 | `tx_page_006` | `format_a` | 6.50 | EUR | `2025-03-20T09:00:00Z` | FAILED |
| 12 | `tx_page_007` | `format_a` | 7.75 | USD | `2025-03-21T09:00:00Z` | PENDING |
| 13 | `tx_page_008` | `format_a` | 8.00 | EUR | `2025-03-22T09:00:00Z` | SUCCESS |
| 14 | `tx_page_009` | `format_a` | 9.25 | USD | `2025-03-23T09:00:00Z` | SUCCESS |
| 15 | `tx_page_010` | `format_a` | 10.50 | EUR | `2025-03-24T09:00:00Z` | FAILED |
| 16 | `tx_page_011` | `format_a` | 11.75 | USD | `2025-03-25T09:00:00Z` | PENDING |
| 17 | `tx_page_012` | `format_a` | 12.00 | EUR | `2025-03-26T09:00:00Z` | SUCCESS |

Rejected entries, with the observed validation reason(s):

| Position | Identifier | Source | Reason |
|---:|---|---|---|
| 18 | `tx_001` | `format_a` | Duplicate; first valid occurrence is at input position 1. |
| 19 | `tx_bad_amount` | `format_a` | Amount string mixes period and comma separators; unsupported currency `GBP`; unknown status `unknown`. |
| 20 | `tx_bad_date` | `format_a` | Timestamp is invalid or does not match the accepted format for the source. |
| 21 | `tx_bad_minor` | `format_b` | Total must contain an integer number of minor units. |
| 22 | `tx_bad_zone` | `format_c` | Timestamp requires ISO 8601 with an explicit timezone. |
| 23 | `tx_incomplete` | Not identified | Unknown or incomplete source format. |
| 24 | Not available | Not identified | Record must be a JSON object. |

## Observed architecture and findings

- `app/normalizer.py` contains source detection, per-record normalization and
  validation (`normalize_record`, line 255), and dataset processing including
  first-valid duplicate retention (`normalize_dataset`, line 352). Its
  lower-level conversion helpers include `_decimal` (line 67),
  `_normalize_amount_and_currency` (line 125),
  `_normalize_timestamp` (line 187), and `_normalize_status` (line 223).
- `app/metrics.py` contains `calculate_metrics` (line 9), which counts retained
  statuses and sums retained SUCCESS amounts by currency.
- `app/server.py` contains the `/api/import` handler (`import_dataset`, line
  71), which parses uploads, calls `normalize_dataset` and
  `calculate_metrics` (lines 95–96), formats currency totals for display, and
  returns the existing API response.
- `app/config/normalization_rules.json` documents format signatures (line 34),
  amount rules (line 64), status mappings (line 90), duplicate policy (line
  143), and metric policy (line 157). Some behavior remains explicit in Python:
  for example, format-specific amount conversion in `_decimal`, date parsing in
  `_normalize_timestamp`, and status/currency aggregation defaults in
  `calculate_metrics`.
- A small, concrete repeated operation exists in incomplete/unknown source
  handling: `_source_hint` (normalizer line 28) determines which formats'
  required keys are present, while `normalize_record` (line 272) independently
  constructs the candidate formats using required-key intersection.
- Existing application-level composition is tied to the upload route: no
  separate analysis entry point was found for a skill or other caller. The
  normalizer and metrics are already callable Python functions, so the verified
  processing logic need not be reimplemented to make them reusable.
- `tests/test_normalizer.py` includes independent expected metrics and API
  serialization tests. `README.md` documents the current web workflow and test
  command; `TECHNICAL_NOTE.md` records the design decisions. No skill or profile
  convention was found in the inspected project/course templates.

These are observed implementation properties, not claims that the current
program is malfunctioning. The existing suite passed on the recorded baseline.

## Recommendations (not implemented)

1. Add a deterministic `analyze_transactions` application entry point that
   composes the existing `normalize_dataset` and `calculate_metrics` functions.
   Route `/api/import` through it while preserving the API response shape and
   current UI behavior.
2. Make the `analyze_transactions` skill a thin caller of that Python entry
   point. If it must accept local files without the web application, add only a
   small file/CLI adapter to the same entry point; do not duplicate processing
   rules in skill instructions.
3. Make `explain_results` explain only the returned normalized records,
   transformation details, rejection reasons, and computed metrics. Keep
   validation, duplicate decisions, and arithmetic in deterministic Python.
4. Define Auditor and Support Analyst as report-format profiles over the same
   analysis result. For a testable distinction, the Auditor report could
   emphasize traceable counts, amounts, positions, and exceptions; the Support
   Analyst report could use plain language and practical next steps grounded in
   recorded rejection reasons.
5. In the absence of an existing project/course template, consider conventional
   repo-local VS Code Copilot files: skills under
   `.github/skills/<skill-name>/SKILL.md` and profiles under
   `.github/agents/<profile-name>.agent.md`. This is a recommendation, not a
   discovered repository convention.
6. Preserve current normalization, validation, duplicate, metrics, and interface
   behavior. Add focused tests for the new entry point, both explanations, and
   visibly distinct reports; use the recorded sample results above as regression
   expectations.

No implementation, dependency installation, or additional validation was
performed while writing this assessment.
