"""Flask API and local web server for transaction normalization."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from app.metrics import calculate_metrics
from app.normalizer import normalize_dataset

ROOT = Path(__file__).resolve().parent
RULES_PATH = ROOT / "config" / "normalization_rules.json"


class InvalidJSONConstant(ValueError):
    """Raised when an uploaded document uses non-standard JSON constants."""


def _reject_json_constant(value: str) -> None:
    raise InvalidJSONConstant(f"Invalid non-finite JSON value: {value}.")


def _encode_json(value: Any) -> str:
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
        return "[" + ",".join(_encode_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{_encode_json(item)}"
            for key, item in value.items()
        ) + "}"
    raise TypeError(f"Unsupported JSON value type: {type(value).__name__}.")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False

    with RULES_PATH.open(encoding="utf-8") as rules_file:
        rules = json.load(rules_file)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/rules")
    def get_rules() -> Response:
        return jsonify(rules)

    @app.post("/api/import")
    def import_dataset() -> Response:
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"error": "Choose a JSON file to process."}), 400
        if not upload.filename.lower().endswith(".json"):
            return jsonify({"error": "The selected file must have a .json extension."}), 400

        raw = upload.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return jsonify({"error": "The uploaded file must be UTF-8 encoded JSON."}), 400

        try:
            payload = json.loads(
                text,
                parse_float=Decimal,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, InvalidJSONConstant) as exc:
            return jsonify({"error": f"Malformed JSON: {exc}"}), 400
        if not isinstance(payload, list):
            return jsonify({"error": "Unsupported JSON structure: the top-level value must be an array."}), 400

        dataset = normalize_dataset(payload, rules)
        metrics = calculate_metrics(dataset)
        metrics["currency_totals_display"] = {
            currency: format(total, ".2f")
            for currency, total in metrics["currency_totals"].items()
        }
        response_data = {
            "filename": upload.filename,
            **dataset,
            "metrics": metrics,
        }
        return Response(_encode_json(response_data), mimetype="application/json")

    @app.errorhandler(413)
    def request_too_large(_error: Exception) -> tuple[Response, int]:
        return jsonify({"error": "The uploaded file is too large to process."}), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
