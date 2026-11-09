"""Command-line entry point for deterministic transaction analysis."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

from app.analysis import analyze_transactions, encode_json
from app.reporting import build_report_facts

RULES_PATH = Path(__file__).resolve().parent / "config" / "normalization_rules.json"


class InvalidJSONConstant(ValueError):
    """Raised when an input document uses non-standard JSON constants."""


def _reject_json_constant(value: str) -> NoReturn:
    raise InvalidJSONConstant(f"Invalid non-finite JSON value: {value}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="path to a JSON transaction array")
    parser.add_argument(
        "--report-facts",
        action="store_true",
        help="emit minimized verified facts for explanation instead of original records",
    )
    arguments = parser.parse_args()

    try:
        text = arguments.input.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        parser.error(f"Could not read input file: {exc}")

    try:
        records = json.loads(
            text,
            parse_float=Decimal,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, InvalidJSONConstant) as exc:
        parser.error(f"Malformed JSON: {exc}")
    if not isinstance(records, list):
        parser.error("Input JSON top-level value must be an array.")

    with RULES_PATH.open(encoding="utf-8") as rules_file:
        rules = json.load(rules_file)
    analysis = analyze_transactions(records, rules)
    result = build_report_facts(analysis) if arguments.report_facts else analysis
    print(encode_json(result))


if __name__ == "__main__":
    main()
