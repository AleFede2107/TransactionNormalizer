# Refactor Verification

## Status and baseline

The deterministic analysis, customization files, profile configuration, OpenAI
Responses API integration, and website reporting controls are implemented.
OpenAI was selected by the user. No live OpenAI request was made during
verification.

- **Refactor starting commit:** `f5787542fb45bb8d2a02abe79a10e10535417a64`
- **Baseline assessment commit recorded in** `evidence/baseline-assessment.md`:
  `df7e329ffca0c838f1343d3fba8ab798154719c0`
- **Python used:** Python 3.11.9 at `.venv\Scripts\python.exe`
- **Dependencies installed:** None. The integration uses Python's standard
  library HTTP client.
- **Provider model default:** `gpt-6-luna`, overridable with `OPENAI_MODEL`.
  The model name was checked against the
  [official OpenAI model page](https://developers.openai.com/api/docs/models/gpt-6-luna).
- **API contract:** OpenAI Responses API
  ([official create-response reference](https://developers.openai.com/api/reference/resources/responses/methods/create)).

## Commands run and automated results

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app tests
node --check .\app\static\app.js
git diff --check
.\.venv\Scripts\python.exe -m app.analyze samples\mixed_transactions.json
.\.venv\Scripts\python.exe -m app.analyze samples\mixed_transactions.json | .\.venv\Scripts\python.exe -c "import json,sys; from decimal import Decimal; d=json.load(sys.stdin, parse_float=Decimal); print({'counts':(d['processed'],d['valid_count'],d['invalid_count']),'metrics':d['metrics'],'rejected_positions':[r['position'] for r in d['invalid_records']]})"
.\.venv\Scripts\python.exe -m app.analyze --report-facts samples\mixed_transactions.json
```

Results:

- The final unittest run passed: **30 tests**, including all 15 existing tests
  and 15 new focused tests.
- Python compilation passed.
- JavaScript syntax check passed.
- `git diff --check` passed.
- The CLI processed the baseline sample and emitted exact JSON decimal number
  tokens.
- The `--report-facts` CLI mode produced the verified, minimized report packet;
  automated tests assert its counts, separate currency totals, and omitted raw
  transaction data.
- OpenAI API behavior was tested with a mocked HTTP response. Tests did not
  make a live provider request.

The supplied `evidence/baseline-tests.txt` contains PowerShell error text
interleaved with test output, although it ends with `Ran 15 tests` and `OK`.
Accordingly, the baseline test command was run directly in `.venv` before
implementation and the full suite was rerun after implementation rather than
relying solely on that captured file.

## Baseline sample comparison

The post-refactor `analyze_transactions` path produced the same sample results:

- 24 processed, 17 retained valid, 7 rejected.
- Status counts: SUCCESS 9, FAILED 4, PENDING 4.
- Successful totals: USD 216.75 and EUR 123.99.
- Retained records at positions 1–17 had the same IDs, sources, amounts,
  currencies, UTC timestamps, and statuses recorded in
  `evidence/baseline-assessment.md`.
- Rejected positions and reasons were unchanged: 18 duplicate of position 1;
  19 mixed amount separators, GBP, and unknown status; 20 invalid timestamp;
  21 fractional Format B minor units; 22 Format C timestamp missing timezone;
  23 incomplete source; and 24 non-object record.

The new test `AnalysisTests.test_baseline_sample_analysis_results_and_metrics`
asserts these baseline counts and metrics, retained amount, and duplicate
position. The focused runtime comparison also printed every retained ID,
amount, currency, status, and every rejection reason.

## Skills, agent, and profiles

- The `analyze-transactions` CLI is executable independently of Flask and was
  tested against `samples/mixed_transactions.json`. Its output preserves
  Decimal values as JSON number tokens.
- The report endpoint recomputes analysis from the uploaded file and passes the
  `explain-results` skill instructions plus a minimized, verified fact packet to
  OpenAI. A mocked Responses API test exercised that path and the extraction of
  actual response text.
- The minimized fact-packet test confirms it contains positions and rejection
  reasons while omitting original records, transaction identifiers, normalized
  amounts, and timestamps.
- The skill-contract tests check that both skills document purpose, invocation
  conditions, inputs, outputs, and failure handling. The integration test
  confirms the explanation skill instructions are included in the model
  request.
- The agent-contract test confirms the Transaction Agent references both
  skills in sequence.
- The profile API test confirms both configured profile names and IDs. A
  mocked request test confirms both profiles receive the same verified analysis
  facts while their emphasis configuration differs. Both share the rule to
  preserve separate currency totals.

## Website checks

The Flask server was started for browser checks with `OPENAI_API_KEY` explicitly
empty, so the browser could not send any sample data to OpenAI.

- Profile selector populated with Auditor and Support Analyst.
- Importing `mixed_transactions.json` displayed 24 processed, 17 valid, and
  7 invalid records.
- Clicking Generate Analysis showed the explicit missing-`OPENAI_API_KEY`
  failure; the report panel did not display fabricated text.
- A delayed mocked browser response showed the loading state and then the
  explicit mocked failure state. No model output was simulated as a successful
  report.
- Importing an empty `[]` JSON file succeeded and displayed zero processed,
  valid, and invalid records. Clicking Generate Analysis displayed the missing
  key failure.
- After successful import of `valid_transactions.json`, a simulated stale
  report-panel string was cleared and the content remained hidden.
- The existing API tests confirm empty-array imports remain successful; new
  tests confirm zero analysis metrics and explicit report configuration
  failure.

## Not yet verified

- **Live OpenAI generation:** No API key was configured and no actual request
  was made. Runtime behavior still depends on the user's API key, account
  access, quota, and selected model availability.
- **Actual generated text quality:** The deterministic fact packet, separate
  profile emphases, request construction, and response parsing were verified;
  whether live Auditor and Support Analyst responses always stick to facts and
  provide only safe corrections requires provider-backed evaluation.
- **Successful report display in a real browser:** The backend's mocked API
  success path returned model response text; browser loading, failure, and
  clearing states were exercised. A live success response was not available.
- **Full Transaction Agent runtime coordination:** Its skill ordering and
  references were checked statically; live invocation by the editor's agent
  runtime was not available as an automated test.
- **Live network error and timeout behavior:** Explicit handling exists, but
  these paths were not exercised against a real network or a simulated socket
  failure.

No live provider-generated report is claimed.
