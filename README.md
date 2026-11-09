# PyNormalize

PyNormalize is a local Python web application for importing JSON transaction
arrays, detecting three documented input formats, normalizing valid records,
and reviewing validation failures and dataset metrics. Processing uses Python
`Decimal`; there is no exchange-rate conversion. Report generation is the
optional external connection described below.

## Requirements

- Python 3.10 or later
- A modern browser

## Setup and run on Windows

From the project directory, create the environment, install the declared
dependency, and run the test suite:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Before starting the application, enter the OpenAI API key in the current
PowerShell session (input is hidden):

```powershell
$secureKey = Read-Host -Prompt "OpenAI API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
```

`OPENAI_MODEL` is optional and defaults to `gpt-6-luna`; set it in the same
session to use another model available to your API account. The application
does not persist the API key.

Start the application:

```powershell
.\.venv\Scripts\python.exe -m app.server
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to
localhost only. Activation is not required. The report action currently returns
an explicit configuration failure if `OPENAI_API_KEY` is not set.

Generating a report sends aggregate metrics, input positions, source formats,
transformation descriptions, and validation reason text to OpenAI. Original
records, identifiers, normalized amounts, and timestamps are excluded from the
request. Validation reason text can include invalid input values. Do not send
datasets you are not permitted to share with the selected provider.

## Analyze a file from the command line

The reusable deterministic analysis entry point can also be run without
starting Flask:

```powershell
.\.venv\Scripts\python.exe -m app.analyze samples\mixed_transactions.json
```

The command reads `app/config/normalization_rules.json` and writes one JSON
analysis result to standard output. File, JSON, or configuration errors are
reported as errors; rejected transaction entries remain in the successful
analysis result under `invalid_records`.

To produce minimized, verified facts for a profile-based explanation without
passing raw records to the model:

```powershell
.\.venv\Scripts\python.exe -m app.analyze --report-facts samples\mixed_transactions.json
```

This omits original records, identifiers, normalized amounts, and timestamps.
Validation reason text is retained and may include a malformed input value.

## Use the website

1. Select a `.json` file containing a top-level transaction array.
2. Select **Process dataset**. A successful import replaces the current dataset;
   a file-level error leaves it unchanged.
3. Use **Overview** for full-dataset counts and successful totals by currency.
4. Use **Transactions** to search, filter, sort, paginate, and inspect retained
   valid records.
5. Use **Invalid records** to inspect originals and validation reasons.
6. Use **Rules** to read the same JSON configuration used by the processor.
7. Select a report profile and choose **Generate Analysis**. The report panel
   shows loading, generated, and failure states. A report is generated using
   the OpenAI Responses API; provider failures are shown explicitly and are
   never replaced with template text.

The sample files are `samples/mixed_transactions.json` (valid, invalid, and
duplicate examples) and `samples/valid_transactions.json`. Do not treat either
sample as a record of the user's real transactions.

## Analysis and skill architecture

- `app/analysis.py`: `analyze_transactions` orchestrates the existing
  normalization, validation, duplicate handling, and metrics functions. It
  also provides the exact-decimal JSON encoder shared by the API and CLI.
- `app/normalizer.py`: source detection, normalization, validation, and
  duplicate handling.
- `app/metrics.py`: Decimal-based dataset metrics.
- `app/analyze.py`: command-line adapter for deterministic analysis.
- `app/reporting.py`: minimized report-fact construction and OpenAI Responses
  API integration for the explanation skill.
- `app/server.py`: Flask page and JSON upload, rules, profile, and report APIs.
- `app/config/normalization_rules.json`: confirmed schema, input formats,
  normalization rules, validity policy, duplicate policy, and metric inclusion.
- `app/config/agent_profiles.json`: Auditor and Support Analyst reporting
  emphasis and shared evidence constraints.
- `.github/skills/analyze-transactions/SKILL.md`: workflow contract for the
  analysis skill.
- `.github/skills/explain-results/SKILL.md`: workflow contract for profile-based
  explanation of verified results.
- `.github/agents/transaction-agent.agent.md`: coordinates the two skills in
  sequence without duplicating processing logic.
- `app/templates/` and `app/static/`: website and interactive client.
- `tests/`: automated unit, API, analysis, profile, and customization-contract
  tests.
- `samples/`: sample JSON arrays.

### Skill contracts

**Analyze Transactions** takes a JSON file path, uses the CLI to call the
deterministic Python processing path, and returns the complete analysis JSON.
The result includes valid normalized transactions, rejected original records
with reasons and positions, and metrics. Malformed files and configuration or
runtime errors are explicit failures; record-level rejects are normal results.

**Explain Results** takes the minimized report-facts JSON emitted by the
analysis CLI, configured rules, and a profile ID. It explains verified facts
but does not calculate or alter them. It fails explicitly for missing or
inconsistent analysis, unsupported profiles, or unavailable report generation;
it must not replace failures with a template-shaped report.

### Profiles

- **Auditor** emphasizes validation reasons, record positions, recorded
  transformations, applicable rules, exceptions, and traceability.
- **Support Analyst** explains the same facts in plain language and suggests
  practical corrections only when supported by the recorded reason and
  configured rules. Unknown business values are left for the user to confirm.

Both profiles follow the same contract: no invented reasons or facts, and
successful totals remain separate by currency.

## Processing and retention policy

An upload must be valid UTF-8 JSON with a top-level array. Malformed JSON or
another top-level structure is a file-level error and does not replace the
loaded dataset. Within a valid array, each entry is evaluated independently.
Invalid entries (including duplicates) are kept separately with their parsed
original record, zero-based index, one-based input position, available
identifier/source information, and validation reasons. Only retained valid
records appear in the normalized transaction list.

The six normalized fields and all processing decisions are displayed in
**Rules** and maintained in `app/config/normalization_rules.json`. Successful
totals include only retained `SUCCESS` records and are always grouped
separately by USD and EUR. Overview metrics describe the full dataset, not the
filtered transaction table.

## AI-assisted work

This homework refactor was AI-assisted. The implementation reuses the existing
normalizer and metrics functions, keeps transaction decisions in deterministic
Python, and uses the baseline sample output as a regression expectation. The
repository and inspected course project folders did not provide a skill or
custom-agent template, so the skills and agent use the VS Code Copilot workspace
conventions. No change to the transaction rules is intended. The user selected
OpenAI as the report provider during this refactor. The implementation uses its
Responses API, keeps the API key in a local environment variable, and does not
send original records, identifiers, normalized amounts, or timestamps in the
report request. Tests mock the HTTP response and make no live provider request;
actual model access still depends on the user's key and account configuration.
