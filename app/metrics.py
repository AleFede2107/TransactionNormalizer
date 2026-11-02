"""Dataset-level metrics calculated only from retained normalized records."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def calculate_metrics(dataset: dict[str, Any]) -> dict[str, Any]:
    status_counts = {"SUCCESS": 0, "FAILED": 0, "PENDING": 0}
    currency_totals = {"USD": Decimal("0.00"), "EUR": Decimal("0.00")}

    for entry in dataset["transactions"]:
        transaction = entry["normalized"]
        status_counts[transaction["status"]] += 1
        if transaction["status"] == "SUCCESS":
            currency_totals[transaction["currency"]] += transaction["amount"]

    return {
        "processed": dataset["processed"],
        "valid": dataset["valid_count"],
        "invalid": dataset["invalid_count"],
        "status_counts": status_counts,
        "currency_totals": currency_totals,
    }
