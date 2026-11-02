# PyNormalize

PyNormalize is a local Python web application for importing JSON transaction arrays, detecting three documented input formats, normalizing valid records, and reviewing validation failures and dataset metrics. Processing uses Python `Decimal`; there is no exchange-rate conversion or external data connection.

## Requirements

- Python 3.10 or later
- A modern browser

## Run on Windows

From the project directory, open PowerShell and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.server
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to localhost only.

If PowerShell prevents environment activation, either allow activation for the current terminal according to your local policy or invoke the environment directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.server
```

## Tests

With the virtual environment activated:

```powershell
python -m unittest discover -s tests -v
```

The suite covers the three formats, conversion/validation decisions, duplicate handling, metrics, empty arrays, JSON API serialization, malformed files, and unsupported top-level structures.

## Use

1. Select a `.json` file containing a top-level array of transaction entries.
2. Select **Process dataset**. A successful import replaces the current dataset; an upload or file-level error leaves the current dataset unchanged.
3. Use **Overview** for full-dataset counts and successful totals by currency.
4. Use **Transactions** to search, filter, sort, paginate, and inspect retained valid records.
5. Use **Invalid records** to inspect originals and validation reasons.
6. Use **Rules** to read the same JSON configuration used by the processor.

The sample files are `samples/mixed_transactions.json` (valid, invalid, and duplicate examples) and `samples/valid_transactions.json`. Do not treat either sample as a record of the user's real transactions.

## Project layout

- `app/config/normalization_rules.json`: confirmed schema, input formats, normalization rules, validity policy, duplicate policy, and metric inclusion.
- `app/normalizer.py`: source detection, normalization, validation, and duplicate handling.
- `app/metrics.py`: Decimal-based dataset metrics.
- `app/server.py`: Flask page and JSON upload/rules API.
- `app/templates/` and `app/static/`: responsive website and interactive client.
- `tests/`: automated unit and API tests.
- `samples/`: sample JSON arrays.

## Processing and retention policy

An upload must be valid UTF-8 JSON with a top-level array. Malformed JSON or another top-level structure is a file-level error and does not replace the loaded dataset. Within a valid array, each entry is evaluated independently. Invalid entries (including duplicates) are kept separately with their parsed original record, zero-based index, one-based input position, available identifier/source information, and validation reasons. Only retained valid records appear in the normalized transaction list.

The six normalized fields and all processing decisions are displayed in **Rules** and maintained in `app/config/normalization_rules.json`. Successful totals include only retained `SUCCESS` records and are always grouped separately by USD and EUR. Overview metrics describe the full dataset, not the filtered transaction table.
