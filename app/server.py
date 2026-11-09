"""Flask API and local web server for transaction normalization."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from app.analysis import analyze_transactions, encode_json
from app.reporting import (
    ReportConfigurationError,
    ReportGenerationError,
    explain_results,
)

ROOT = Path(__file__).resolve().parent
RULES_PATH = ROOT / "config" / "normalization_rules.json"
PROFILES_PATH = ROOT / "config" / "agent_profiles.json"
EXPLAIN_SKILL_PATH = ROOT.parent / ".github" / "skills" / "explain-results" / "SKILL.md"


class InvalidJSONConstant(ValueError):
    """Raised when an uploaded document uses non-standard JSON constants."""


def _reject_json_constant(value: str) -> None:
    raise InvalidJSONConstant(f"Invalid non-finite JSON value: {value}.")


def _parse_upload(upload: Any) -> tuple[list[Any] | None, tuple[str, int] | None]:
    if upload is None or not upload.filename:
        return None, ("Choose a JSON file to process.", 400)
    if not upload.filename.lower().endswith(".json"):
        return None, ("The selected file must have a .json extension.", 400)

    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, ("The uploaded file must be UTF-8 encoded JSON.", 400)

    try:
        payload = json.loads(
            text,
            parse_float=Decimal,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, InvalidJSONConstant) as exc:
        return None, (f"Malformed JSON: {exc}", 400)
    if not isinstance(payload, list):
        return None, (
            "Unsupported JSON structure: the top-level value must be an array.",
            400,
        )
    return payload, None


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False

    with RULES_PATH.open(encoding="utf-8") as rules_file:
        rules = json.load(rules_file)
    with PROFILES_PATH.open(encoding="utf-8") as profiles_file:
        profiles = json.load(profiles_file)
    skill_text = EXPLAIN_SKILL_PATH.read_text(encoding="utf-8")
    skill_instructions = skill_text.split("---", 2)[-1].strip()

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/rules")
    def get_rules() -> Response:
        return jsonify(rules)

    @app.get("/api/profiles")
    def get_profiles() -> Response:
        return jsonify({
            profile_id: {
                "name": profile["name"],
                "description": profile["description"],
            }
            for profile_id, profile in profiles["profiles"].items()
        })

    @app.post("/api/import")
    def import_dataset() -> Response | tuple[Response, int]:
        upload = request.files.get("file")
        payload, error = _parse_upload(upload)
        if error is not None:
            return jsonify({"error": error[0]}), error[1]
        if payload is None:
            return jsonify({"error": "The transaction file could not be parsed."}), 400

        analysis = analyze_transactions(payload, rules)
        metrics = analysis["metrics"]
        metrics["currency_totals_display"] = {
            currency: format(total, ".2f")
            for currency, total in metrics["currency_totals"].items()
        }
        response_data = {
            "filename": upload.filename,
            **analysis,
        }
        return Response(encode_json(response_data), mimetype="application/json")

    @app.post("/api/report")
    def generate_report() -> tuple[Response, int]:
        profile_id = request.form.get("profile", "")
        if profile_id not in profiles["profiles"]:
            return jsonify({"error": "Choose a supported report profile."}), 400

        payload, error = _parse_upload(request.files.get("file"))
        if error is not None:
            return jsonify({"error": error[0]}), error[1]
        if payload is None:
            return jsonify({"error": "The transaction file could not be parsed."}), 400

        analysis = analyze_transactions(payload, rules)
        try:
            report = explain_results(
                analysis,
                profile_id,
                rules,
                profiles,
                skill_instructions,
            )
        except ReportConfigurationError as exc:
            return jsonify({"error": str(exc)}), 503
        except ReportGenerationError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({
            "provider": "OpenAI",
            "profile": profile_id,
            "report": report,
        })

    @app.errorhandler(413)
    def request_too_large(_error: Exception) -> tuple[Response, int]:
        return jsonify({"error": "The uploaded file is too large to process."}), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
