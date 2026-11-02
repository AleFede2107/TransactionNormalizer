"""Transaction format detection, normalization, and record-level validation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


_NUMERIC_STRING = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$")
_FORMAT_A_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
_FORMAT_B_TIMESTAMP = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")
_FORMAT_C_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)


def _format_matches(record: dict[str, Any], config: dict[str, Any]) -> list[str]:
    return [
        name
        for name, spec in config["source_detection"]["formats"].items()
        if all(key in record for key in spec["required_keys"])
    ]


def _source_hint(record: dict[str, Any], config: dict[str, Any]) -> str | None:
    possible = []
    for name, spec in config["source_detection"]["formats"].items():
        present = set(spec["required_keys"]).intersection(record)
        if present:
            possible.append(name)
    return possible[0] if len(possible) == 1 else None


def _identifier(record: dict[str, Any], source: str | None, config: dict[str, Any]) -> str | None:
    formats = config["source_detection"]["formats"]
    keys = [formats[source]["required_keys"][0]] if source else [
        formats[name]["required_keys"][0] for name in formats
    ]
    values = []
    for key in keys:
        if key not in record:
            continue
        value = record[key]
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, int) and not isinstance(value, bool):
            values.append(str(value))
    return values[0] if len(values) == 1 else None


def _normalize_id(value: Any) -> tuple[str, str]:
    if isinstance(value, bool):
        raise ValueError("ID must be a nonblank string or an integer, not a boolean.")
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValueError("ID must not be blank.")
        return normalized, "Kept the string identifier after trimming surrounding whitespace."
    if isinstance(value, int):
        return str(value), "Converted the integer identifier to a string."
    raise ValueError("ID must be a nonblank string or an integer.")


def _decimal(value: Any, source: str) -> tuple[Decimal, str | None, str]:
    if isinstance(value, bool) or value is None:
        raise ValueError("Amount must be a finite JSON number or an allowed numeric string.")

    symbol_currency: str | None = None
    if source == "format_b":
        if not isinstance(value, (int, Decimal)):
            raise ValueError("Format B total must be a JSON number of integer minor units.")
        amount = Decimal(value)
        if not amount.is_finite():
            raise ValueError("Amount must be finite.")
        if amount != amount.to_integral_value():
            raise ValueError("Format B total must contain an integer number of minor units.")
        return amount / Decimal(100), None, "Converted integer minor units in total to major currency units."

    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Amount must not be blank.")
        if text[0] in "$€":
            symbol_currency = {"$": "USD", "€": "EUR"}[text[0]]
            text = text[1:]
        if "." in text and "," in text:
            raise ValueError("Amount string must not mix period and comma separators.")
        if text.count(".") > 1 or text.count(",") > 1:
            raise ValueError("Amount string must not repeat a decimal separator.")
        if not _NUMERIC_STRING.fullmatch(text):
            raise ValueError("Amount string must be numeric, use at most one decimal separator, and contain no thousands separators or embedded spaces.")
        amount = Decimal(text.replace(",", "."))
        detail = "Parsed the major-unit amount string."
        if "," in text:
            detail += " Interpreted the comma as the decimal separator."
        if symbol_currency:
            detail += f" Mapped the leading symbol to {symbol_currency}."
    elif isinstance(value, (int, Decimal)):
        amount = Decimal(value)
        detail = "Parsed the JSON number as a major-unit amount."
    else:
        raise ValueError("Amount must be a finite JSON number or an allowed numeric string.")

    if not amount.is_finite():
        raise ValueError("Amount must be finite.")
    return amount, symbol_currency, detail


def _to_cents(amount: Decimal) -> Decimal:
    sign, digits, exponent = amount.as_tuple()
    digits = list(digits)
    if exponent < -2:
        trailing = -2 - exponent
        if trailing > len(digits) or any(digits[-trailing:]):
            raise ValueError("Amount has more than two decimal places and would require rounding.")
        digits = digits[:-trailing]
    else:
        digits.extend([0] * (exponent + 2))
    return Decimal((sign, tuple(digits or [0]), -2))


def _normalize_amount_and_currency(
    record: dict[str, Any],
    source: str,
    config: dict[str, Any],
) -> tuple[Decimal | None, str | None, list[str], list[str]]:
    source_spec = config["source_detection"]["formats"][source]
    raw_amount = record[source_spec["amount_key"]]
    symbol_currency = None
    if source != "format_b" and isinstance(raw_amount, str):
        symbol = raw_amount.strip()[:1]
        symbol_currency = config["amount_rules"]["symbol_mapping"].get(symbol)
    amount_errors: list[str] = []
    explanations: list[str] = []
    normalized_amount: Decimal | None = None
    try:
        amount, detected_symbol, explanation = _decimal(raw_amount, source)
        symbol_currency = detected_symbol or symbol_currency
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        normalized_amount = _to_cents(amount)
        explanations.append(explanation)
        explanations.append("Kept the amount in major currency units and normalized it to two decimal places.")
    except ValueError as exc:
        amount_errors.append(str(exc))

    explicit_currency = None
    currency_errors: list[str] = []
    currency_key = source_spec["currency_key"]
    if currency_key is not None:
        raw_currency = record[currency_key]
        if raw_currency is not None and not (
            isinstance(raw_currency, str) and not raw_currency.strip()
        ):
            if not isinstance(raw_currency, str):
                currency_errors.append(
                    f"{currency_key} must be a currency-code string or blank when a symbol supplies it."
                )
            else:
                explicit_currency = raw_currency.strip().upper()
                if explicit_currency not in config["currency_rules"]["supported"]:
                    currency_errors.append(f"Unsupported currency code: {explicit_currency}.")

    if explicit_currency and symbol_currency and explicit_currency != symbol_currency:
        currency_errors.append(
            f"Currency code {explicit_currency} conflicts with the amount symbol for {symbol_currency}."
        )
    if source == "format_c" and symbol_currency is None:
        currency_errors.append("Format C currency must be inferred from a leading $ or € amount symbol.")
    currency_invalid = bool(currency_errors)
    currency = None if currency_invalid else explicit_currency or symbol_currency
    if currency is None and not currency_invalid:
        currency_errors.append(
            "Currency is unresolved; provide a supported code or a recognized leading amount symbol."
        )

    if currency_key is not None and explicit_currency:
        explanations.append(f"Trimmed and uppercased the explicit currency code to {currency}.")
    elif symbol_currency and currency:
        explanations.append(f"Resolved currency to {currency} from the leading amount symbol.")
    return normalized_amount, currency, amount_errors + currency_errors, explanations


def _normalize_timestamp(value: Any, source: str, config: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string.")
    text = value.strip()
    if not text:
        raise ValueError("Timestamp must not be blank.")

    try:
        if source == "format_a":
            if not _FORMAT_A_TIMESTAMP.fullmatch(text):
                raise ValueError("Format A requires YYYY-MM-DD HH:mm:ss.")
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            explanation = "Parsed YYYY-MM-DD HH:mm:ss and treated the zone-less timestamp as UTC."
        elif source == "format_b":
            if not _FORMAT_B_TIMESTAMP.fullmatch(text):
                raise ValueError("Format B requires DD/MM/YYYY HH:mm.")
            parsed = datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
            explanation = "Parsed DD/MM/YYYY HH:mm day-first, set seconds to 00, and treated the zone-less timestamp as UTC."
        else:
            if not _FORMAT_C_TIMESTAMP.fullmatch(text):
                raise ValueError("Format C requires ISO 8601 seconds and an explicit timezone; fractional seconds may have one to six digits.")
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            explanation = "Parsed the ISO 8601 timestamp with its explicit timezone and converted it to UTC."
    except ValueError as exc:
        if str(exc).startswith("Format C"):
            raise
        raise ValueError("Timestamp is invalid or does not match the accepted format for its source.") from exc

    utc_value = parsed.astimezone(timezone.utc)
    output = utc_value.strftime("%Y-%m-%dT%H:%M:%S")
    if utc_value.microsecond:
        fraction = f"{utc_value.microsecond:06d}".rstrip("0")
        output += f".{fraction}"
    return f"{output}Z", explanation


def _normalize_status(value: Any, source: str, config: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError("Status must be a string.")
    input_status = value.strip().lower()
    if not input_status:
        raise ValueError("Status must not be blank.")
    mapping = config["status_rules"]["mappings"][source]
    if input_status not in mapping:
        raise ValueError(f"Unknown status {value.strip()!r} for {source}.")
    status = mapping[input_status]
    return status, f"Mapped {source} status {input_status!r} to {status}."


def _invalid_entry(
    record: Any,
    index: int,
    source: str | None,
    candidates: list[str],
    reasons: list[str],
    identifier: str | None,
) -> dict[str, Any]:
    return {
        "index": index,
        "position": index + 1,
        "identifier": identifier,
        "source": source,
        "source_candidates": candidates,
        "errors": reasons,
        "original": record,
    }


def normalize_record(
    record: Any,
    index: int,
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(record, dict):
        return None, _invalid_entry(
            record,
            index,
            None,
            [],
            ["Record must be a JSON object."],
            None,
        )

    matches = _format_matches(record, config)
    if len(matches) != 1:
        candidates = [
            name
            for name, spec in config["source_detection"]["formats"].items()
            if set(spec["required_keys"]).intersection(record)
        ]
        reason = (
            "Ambiguous source format."
            if len(matches) > 1
            else "Unknown or incomplete source format."
        )
        source_hint = _source_hint(record, config) if len(matches) == 0 else None
        return None, _invalid_entry(
            record,
            index,
            source_hint,
            candidates,
            [reason],
            _identifier(record, source_hint, config),
        )

    source = matches[0]
    spec = config["source_detection"]["formats"][source]
    errors: list[str] = []
    explanations = [f"Detected {source} by its complete required-key signature."]
    normalized: dict[str, Any] = {"source": source}

    try:
        normalized["id"], explanation = _normalize_id(record[spec["required_keys"][0]])
        explanations.append(explanation)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        amount, currency, amount_errors, amount_explanations = _normalize_amount_and_currency(
            record, source, config
        )
        errors.extend(amount_errors)
        if amount is not None:
            normalized["amount"] = amount
        if currency is not None:
            normalized["currency"] = currency
        explanations.extend(amount_explanations)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        normalized["timestamp"], explanation = _normalize_timestamp(
            record[spec["date_key"]], source, config
        )
        explanations.append(explanation)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        normalized["status"], explanation = _normalize_status(
            record[spec["status_key"]], source, config
        )
        explanations.append(explanation)
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        return None, _invalid_entry(
            record,
            index,
            source,
            [source],
            errors,
            normalized.get("id") or _identifier(record, source, config),
        )

    return {
        "index": index,
        "position": index + 1,
        "normalized": normalized,
        "original": record,
        "transformations": explanations,
    }, None


def normalize_dataset(records: list[Any], config: dict[str, Any]) -> dict[str, Any]:
    transactions: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    first_valid_by_key: dict[tuple[str, str], int] = {}

    for index, record in enumerate(records):
        valid_record, invalid_record = normalize_record(record, index, config)
        if invalid_record is not None:
            invalid_records.append(invalid_record)
            continue

        assert valid_record is not None
        normalized = valid_record["normalized"]
        duplicate_key = (normalized["source"], normalized["id"])
        if duplicate_key in first_valid_by_key:
            retained_position = first_valid_by_key[duplicate_key] + 1
            invalid_records.append(
                _invalid_entry(
                    record,
                    index,
                    normalized["source"],
                    [normalized["source"]],
                    [f"Duplicate transaction; the first valid occurrence is at input position {retained_position}."],
                    normalized["id"],
                )
            )
            continue

        first_valid_by_key[duplicate_key] = index
        transactions.append(valid_record)

    return {
        "processed": len(records),
        "valid_count": len(transactions),
        "invalid_count": len(invalid_records),
        "transactions": transactions,
        "invalid_records": invalid_records,
    }
