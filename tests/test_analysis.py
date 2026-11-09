import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app.analysis import analyze_transactions
from app.reporting import (
    ReportConfigurationError,
    ReportGenerationError,
    build_report_facts,
    explain_results,
)
from app.server import create_app


ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "app" / "config" / "normalization_rules.json").open(encoding="utf-8") as file:
    RULES = json.load(file)
with (ROOT / "app" / "config" / "agent_profiles.json").open(encoding="utf-8") as file:
    PROFILE_CONFIG = json.load(file)


class AnalysisTests(unittest.TestCase):
    def test_baseline_sample_analysis_results_and_metrics(self):
        sample_path = ROOT / "samples" / "mixed_transactions.json"
        records = json.loads(sample_path.read_text(encoding="utf-8"), parse_float=Decimal)
        result = analyze_transactions(records, RULES)

        self.assertEqual(
            (result["processed"], result["valid_count"], result["invalid_count"]),
            (24, 17, 7),
        )
        self.assertEqual(
            result["metrics"],
            {
                "processed": 24,
                "valid": 17,
                "invalid": 7,
                "status_counts": {"SUCCESS": 9, "FAILED": 4, "PENDING": 4},
                "currency_totals": {
                    "USD": Decimal("216.75"),
                    "EUR": Decimal("123.99"),
                },
            },
        )
        self.assertEqual(result["transactions"][0]["normalized"]["amount"], Decimal("100.50"))
        self.assertEqual(result["invalid_records"][0]["position"], 18)
        self.assertIn("position 1", result["invalid_records"][0]["errors"][0])

    def test_cli_emits_analysis_json_with_decimal_number_tokens(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.analyze",
                str(ROOT / "samples" / "mixed_transactions.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        analysis = json.loads(result.stdout, parse_float=Decimal)
        self.assertEqual(analysis["metrics"]["currency_totals"]["USD"], Decimal("216.75"))
        self.assertEqual(analysis["transactions"][0]["normalized"]["amount"], Decimal("100.50"))

    def test_cli_report_facts_are_verified_and_minimized(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.analyze",
                "--report-facts",
                str(ROOT / "samples" / "mixed_transactions.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        facts = json.loads(result.stdout)
        serialized = json.dumps(facts)
        self.assertEqual(
            (facts["processed"], facts["valid_count"], facts["invalid_count"]),
            (24, 17, 7),
        )
        self.assertEqual(facts["currency_totals"], {"USD": "216.75", "EUR": "123.99"})
        self.assertNotIn("tx_001", serialized)
        self.assertNotIn('"original"', serialized)
        self.assertNotIn('"amount"', serialized)
        self.assertNotIn('"timestamp"', serialized)

    def test_cli_rejects_non_array_input(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "object.json"
            input_path.write_text('{"transactions":[]}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "app.analyze", str(input_path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("top-level value must be an array", result.stderr)

    def test_empty_analysis_returns_zero_metrics(self):
        result = analyze_transactions([], RULES)
        self.assertEqual(result["transactions"], [])
        self.assertEqual(result["invalid_records"], [])
        self.assertEqual(
            result["metrics"],
            {
                "processed": 0,
                "valid": 0,
                "invalid": 0,
                "status_counts": {"SUCCESS": 0, "FAILED": 0, "PENDING": 0},
                "currency_totals": {
                    "USD": Decimal("0.00"),
                    "EUR": Decimal("0.00"),
                },
            },
        )


class ReportProfileTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_profiles_endpoint_exposes_both_configured_profiles(self):
        response = self.client.get("/api/profiles")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json), {"auditor", "support_analyst"})
        self.assertEqual(response.json["auditor"]["name"], "Auditor")
        self.assertEqual(response.json["support_analyst"]["name"], "Support Analyst")

    def test_profiles_share_verified_facts_but_differ_in_emphasis(self):
        auditor = PROFILE_CONFIG["profiles"]["auditor"]
        support = PROFILE_CONFIG["profiles"]["support_analyst"]
        self.assertNotEqual(auditor["emphasis"], support["emphasis"])
        self.assertIn("input positions", auditor["description"])
        self.assertIn("plain-language", support["description"].lower())
        self.assertIn(
            "Keep successful currency totals separate; never combine currencies.",
            PROFILE_CONFIG["report_contract"],
        )

    def test_report_endpoint_fails_explicitly_without_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            response = self.client.post(
                "/api/report",
                data={
                    "profile": "auditor",
                    "file": (io.BytesIO(b"[]"), "empty.json"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json["error"])

    def test_api_report_uses_mocked_openai_and_returns_actual_model_text(self):
        response_body = {
            "output": [
                {"type": "reasoning", "summary": []},
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Verified report text."},
                    ],
                },
            ],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return json.dumps(response_body).encode("utf-8")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.reporting.urlopen", return_value=FakeResponse()) as openai_request:
                response = self.client.post(
                    "/api/report",
                    data={
                        "profile": "support_analyst",
                        "file": (io.BytesIO(b"[]"), "empty.json"),
                    },
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["provider"], "OpenAI")
        self.assertEqual(response.json["profile"], "support_analyst")
        self.assertEqual(response.json["report"], "Verified report text.")
        request = openai_request.call_args.args[0]
        request_payload = json.loads(request.data)
        serialized_input = json.dumps(request_payload)
        self.assertNotIn("test-key", serialized_input)
        self.assertNotIn('"original"', serialized_input)
        self.assertNotIn('"identifier"', serialized_input)
        self.assertFalse(request_payload["store"])
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertIn("Explain Results", request_payload["input"][0]["content"])


class ReportingTests(unittest.TestCase):
    def setUp(self):
        sample_path = ROOT / "samples" / "mixed_transactions.json"
        records = json.loads(sample_path.read_text(encoding="utf-8"), parse_float=Decimal)
        self.analysis = analyze_transactions(records, RULES)

    def test_report_facts_omit_raw_transaction_data(self):
        facts = build_report_facts(self.analysis)
        self.assertEqual(facts["processed"], 24)
        self.assertEqual(facts["currency_totals"]["USD"], "216.75")
        serialized = json.dumps(facts)
        self.assertNotIn("tx_001", serialized)
        self.assertNotIn('"original"', serialized)
        self.assertNotIn('"amount"', serialized)
        self.assertNotIn('"timestamp"', serialized)
        self.assertIn("position", serialized)
        self.assertIn("errors", serialized)

    def test_explain_results_requires_local_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(ReportConfigurationError):
                explain_results(
                    self.analysis,
                    "auditor",
                    RULES,
                    PROFILE_CONFIG,
                    "Explain verified results.",
                )

    def test_inconsistent_analysis_is_rejected_before_provider_request(self):
        inconsistent = dict(self.analysis)
        inconsistent["metrics"] = dict(self.analysis["metrics"])
        inconsistent["metrics"]["valid"] += 1
        with patch("app.reporting.urlopen") as openai_request:
            with self.assertRaisesRegex(ValueError, "metrics do not match"):
                with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                    explain_results(
                        inconsistent,
                        "auditor",
                        RULES,
                        PROFILE_CONFIG,
                        "Explain verified results.",
                    )
        openai_request.assert_not_called()

    def test_openai_response_without_output_text_is_reported_as_failure(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"output":[{"type":"reasoning","summary":[] }]}'

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.reporting.urlopen", return_value=FakeResponse()):
                with self.assertRaises(ReportGenerationError):
                    explain_results(
                        self.analysis,
                        "auditor",
                        RULES,
                        PROFILE_CONFIG,
                        "Explain verified results.",
                    )

    def test_profiles_send_same_verified_facts_with_different_emphasis(self):
        requests = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"output":[{"type":"message","content":[{"type":"output_text","text":"Report."}]}]}'

        def capture_request(request, timeout):
            requests.append(json.loads(request.data))
            return FakeResponse()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("app.reporting.urlopen", side_effect=capture_request):
                for profile_id in ("auditor", "support_analyst"):
                    explain_results(
                        self.analysis,
                        profile_id,
                        RULES,
                        PROFILE_CONFIG,
                        "Explain verified results.",
                    )

        request_data = [
            json.loads(next(
                item["content"] for item in payload["input"] if item["role"] == "user"
            ))
            for payload in requests
        ]
        self.assertEqual(
            request_data[0]["verified_analysis"],
            request_data[1]["verified_analysis"],
        )
        self.assertNotEqual(
            request_data[0]["profile"]["emphasis"],
            request_data[1]["profile"]["emphasis"],
        )

    def test_skills_document_contracts_and_agent_coordinates_both(self):
        skills_root = ROOT / ".github" / "skills"
        for skill_name in ("analyze-transactions", "explain-results"):
            skill_text = (skills_root / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for section in (
                "Purpose",
                "Invocation conditions",
                "Inputs",
                "Outputs",
                "Failure handling",
            ):
                with self.subTest(skill=skill_name, section=section):
                    self.assertIn(section, skill_text)

        agent_text = (
            ROOT / ".github" / "agents" / "transaction-agent.agent.md"
        ).read_text(encoding="utf-8")
        self.assertIn("analyze-transactions", agent_text)
        self.assertIn("explain-results", agent_text)


if __name__ == "__main__":
    unittest.main()
