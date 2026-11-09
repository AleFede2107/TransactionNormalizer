"""Reusable transaction analysis orchestration and JSON encoding."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app.metrics import calculate_metrics
from app.normalizer import normalize_dataset


def analyze_transactions(
    records: list[Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    dataset = normalize_dataset(records, rules)
    return {
        **dataset,
        "metrics": calculate_metrics(dataset),
    }


def encode_json(value: Any) -> str:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite Decimal values cannot be serialized as JSON.")
        return format(value, "f")
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value, allow_nan=False)
    if isinstance(value, list):
        return "[" + ",".join(encode_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{encode_json(item)}"
            for key, item in value.items()
        ) + "}"
    raise TypeError(f"Unsupported JSON value type: {type(value).__name__}.")
