import io
import json
import unittest
from decimal import Decimal
from pathlib import Path

from app.metrics import calculate_metrics
from app.normalizer import normalize_dataset
from app.server import create_app


ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "app" / "config" / "normalization_rules.json").open(encoding="utf-8") as file:
    RULES = json.load(file)


def format_a(
    identifier="a-1",
    amount="10.00",
    currency="USD",
    timestamp="2025-03-10 14:22:00",
    status="completed",
):
    return {
        "id": identifier,
        "amount": amount,
        "currency": currency,
        "timestamp": timestamp,
        "status": status,
    }


def format_b(
    identifier=204,
    total=10050,
    currency="usd",
    created_at="10/03/2025 14:22",
    state="OK",
):
    return {
        "transaction_id": identifier,
        "total": total,
        "currency_code": currency,
        "created_at": created_at,
        "state": state,
    }


def format_c(
    identifier="A-77",
    amount="€99,99",
    date="2025-03-10T14:22:00Z",
    result="success",
):
    return {"ref": identifier, "amount": amount, "date": date, "result": result}


class NormalizationTests(unittest.TestCase):
    def normalize_one(self, record):
        return normalize_dataset([record], RULES)

    def test_normalizes_all_three_source_formats(self):
        result = normalize_dataset(
            [format_a(), format_b(), format_c()],
            RULES,
        )
        self.assertEqual(result["valid_count"], 3)
        self.assertEqual(result["invalid_count"], 0)
        self.assertEqual(
            [entry["normalized"] for entry in result["transactions"]],
            [
                {
                    "id": "a-1",
                    "amount": Decimal("10.00"),
                    "currency": "USD",
                    "timestamp": "2025-03-10T14:22:00Z",
                    "status": "SUCCESS",
                    "source": "format_a",
                },
                {
                    "id": "204",
                    "amount": Decimal("100.50"),
                    "currency": "USD",
                    "timestamp": "2025-03-10T14:22:00Z",
                    "status": "SUCCESS",
                    "source": "format_b",
                },
                {
                    "id": "A-77",
                    "amount": Decimal("99.99"),
                    "currency": "EUR",
                    "timestamp": "2025-03-10T14:22:00Z",
                    "status": "SUCCESS",
                    "source": "format_c",
                },
            ],
        )

    def test_id_types_extra_keys_and_whitespace(self):
        record = format_a(identifier="  invoice-7  ", currency=" usd ")
        record["extra"] = "allowed"
        result = self.normalize_one(record)
        self.assertEqual(result["transactions"][0]["normalized"]["id"], "invoice-7")
        self.assertEqual(result["transactions"][0]["normalized"]["currency"], "USD")

        integer_id = self.normalize_one(format_a(identifier=21))
        self.assertEqual(integer_id["transactions"][0]["normalized"]["id"], "21")
        for invalid_id in (True, 1.5, None, "  ", [], {}):
            with self.subTest(invalid_id=invalid_id):
                result = self.normalize_one(format_a(identifier=invalid_id))
                self.assertEqual(result["invalid_count"], 1)
                self.assertTrue(any("ID" in reason for reason in result["invalid_records"][0]["errors"]))

    def test_source_specific_status_mappings(self):
        mapping_cases = [
            (format_a(status=" SUCCESS "), "SUCCESS"),
            (format_a(status="failed"), "FAILED"),
            (format_a(status="pending"), "PENDING"),
            (format_b(state="error"), "FAILED"),
            (format_b(state="pending"), "PENDING"),
            (format_c(result="error"), "FAILED"),
            (format_c(result="pending"), "PENDING"),
        ]
        for record, expected in mapping_cases:
            with self.subTest(record=record):
                result = self.normalize_one(record)
                self.assertEqual(result["transactions"][0]["normalized"]["status"], expected)

        for bad_status in ("", "mystery", None, 2):
            with self.subTest(bad_status=bad_status):
                result = self.normalize_one(format_a(status=bad_status))
                self.assertTrue(any("status" in reason.lower() for reason in result["invalid_records"][0]["errors"]))

    def test_amount_units_precision_and_symbols(self):
        self.assertEqual(
            self.normalize_one(format_a(amount=" €99,9900 ", currency="EUR"))["transactions"][0]["normalized"]["amount"],
            Decimal("99.99"),
        )
        self.assertEqual(
            self.normalize_one(format_a(amount="$12.30", currency=""))["transactions"][0]["normalized"]["currency"],
            "USD",
        )
        self.assertEqual(
            self.normalize_one(format_b(total=10050))["transactions"][0]["normalized"]["amount"],
            Decimal("100.50"),
        )
        self.assertEqual(
            self.normalize_one(format_b(total=Decimal("10050.0")))["valid_count"],
            1,
        )
        for amount in ("1.001", "1.00,1", "1,2,3", "$ 1.00", "1e2", "£1.00", True, None, 0, -1):
            with self.subTest(amount=amount):
                result = self.normalize_one(format_a(amount=amount))
                self.assertEqual(result["invalid_count"], 1)

        for total in (10050.5, "10050", None, True):
            with self.subTest(total=total):
                result = self.normalize_one(format_b(total=total))
                self.assertEqual(result["invalid_count"], 1)

    def test_currency_support_fallback_and_conflicts(self):
        self.assertEqual(
            self.normalize_one(format_a(amount="€12,00", currency=None))["transactions"][0]["normalized"]["currency"],
            "EUR",
        )
        for record in (
            format_a(amount="$12", currency="EUR"),
            format_a(amount="€12", currency="GBP"),
            format_a(amount="12", currency=""),
            format_a(amount="12", currency="GBP"),
            format_c(amount="12.00"),
        ):
            with self.subTest(record=record):
                self.assertEqual(self.normalize_one(record)["invalid_count"], 1)

    def test_source_detection_ambiguous_unknown_and_non_object(self):
        ambiguous = format_a()
        ambiguous.update(format_c(identifier="other"))
        result = self.normalize_one(ambiguous)
        self.assertIn("Ambiguous source format.", result["invalid_records"][0]["errors"])
        self.assertEqual(result["invalid_records"][0]["source"], None)

        result = self.normalize_one({"id": "incomplete", "amount": "1.00"})
        self.assertIn(
            "Unknown or incomplete source format.",
            result["invalid_records"][0]["errors"],
        )
        result = self.normalize_one(["not", "an", "object"])
        self.assertIn("Record must be a JSON object.", result["invalid_records"][0]["errors"])

    def test_date_formats_timezone_and_fractional_seconds(self):
        result = self.normalize_one(format_b(created_at="10/03/2025 14:22"))
        self.assertEqual(result["transactions"][0]["normalized"]["timestamp"], "2025-03-10T14:22:00Z")
        result = self.normalize_one(
            format_c(date="2025-03-10T16:22:00.120000+02:00")
        )
        self.assertEqual(
            result["transactions"][0]["normalized"]["timestamp"],
            "2025-03-10T14:22:00.12Z",
        )
        result = self.normalize_one(
            format_c(date="2025-03-10T14:22:00.123456-05:00")
        )
        self.assertEqual(
            result["transactions"][0]["normalized"]["timestamp"],
            "2025-03-10T19:22:00.123456Z",
        )
        for date in (
            "2025-02-30 14:22:00",
            "2025-3-10 14:22:00",
            "10/13/2025 14:22",
            "2025-03-10T14:22:00",
            "2025-03-10",
            None,
            "",
        ):
            record = format_a(timestamp=date) if not isinstance(date, str) or "T" not in date else format_c(date=date)
            with self.subTest(date=date):
                self.assertEqual(self.normalize_one(record)["invalid_count"], 1)

    def test_required_key_absence_and_multiple_reasons(self):
        incomplete = format_a()
        del incomplete["status"]
        result = self.normalize_one(incomplete)
        self.assertEqual(result["invalid_records"][0]["errors"], ["Unknown or incomplete source format."])

        invalid = format_a(amount="bad", currency="GBP", timestamp="bad-date", status="unknown")
        result = self.normalize_one(invalid)
        reasons = result["invalid_records"][0]["errors"]
        self.assertGreaterEqual(len(reasons), 4)
        self.assertTrue(any("amount" in reason.lower() for reason in reasons))
        self.assertTrue(any("currency" in reason.lower() for reason in reasons))
        self.assertTrue(any("timestamp" in reason.lower() for reason in reasons))
        self.assertTrue(any("status" in reason.lower() for reason in reasons))

    def test_duplicate_policy_and_invalid_record_preservation(self):
        first = format_a(identifier="same")
        invalid_before = format_a(identifier="later", amount="bad")
        later_valid = format_a(identifier="later")
        duplicate = format_a(identifier="same", amount="25.00")
        result = normalize_dataset([first, invalid_before, later_valid, duplicate], RULES)
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["invalid_count"], 2)
        self.assertEqual(result["invalid_records"][0]["position"], 2)
        duplicate_result = result["invalid_records"][1]
        self.assertEqual(duplicate_result["position"], 4)
        self.assertIn("position 1", duplicate_result["errors"][0])
        self.assertEqual(duplicate_result["original"], duplicate)

    def test_metrics_use_independent_expected_values(self):
        records = [
            format_a(identifier="a-success", amount="10.00"),
            format_b(identifier=204, total=10050, state="OK"),
            format_c(identifier="c-success", amount="€99,99"),
            format_a(identifier="a-failed", amount="3.00", status="failed"),
            format_c(identifier="c-pending", amount="€5.00", result="pending"),
            format_a(identifier="a-success", amount="1.00"),
            format_a(identifier="bad", amount="bad"),
            {"id": "missing-status", "amount": "1.00", "currency": "USD", "timestamp": "2025-03-10 14:22:00"},
            42,
            {"arbitrary": "unknown"},
        ]
        dataset = normalize_dataset(records, RULES)
        metrics = calculate_metrics(dataset)
        self.assertEqual(
            metrics,
            {
                "processed": 10,
                "valid": 5,
                "invalid": 5,
                "status_counts": {"SUCCESS": 3, "FAILED": 1, "PENDING": 1},
                "currency_totals": {"USD": Decimal("110.50"), "EUR": Decimal("99.99")},
            },
        )
        self.assertEqual(metrics["processed"], metrics["valid"] + metrics["invalid"])

    def test_empty_dataset_metrics(self):
        dataset = normalize_dataset([], RULES)
        self.assertEqual(dataset["transactions"], [])
        self.assertEqual(dataset["invalid_records"], [])
        self.assertEqual(
            calculate_metrics(dataset),
            {
                "processed": 0,
                "valid": 0,
                "invalid": 0,
                "status_counts": {"SUCCESS": 0, "FAILED": 0, "PENDING": 0},
                "currency_totals": {"USD": Decimal("0.00"), "EUR": Decimal("0.00")},
            },
        )


class ImportAPITests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def upload(self, filename, content):
        return self.client.post(
            "/api/import",
            data={"file": (io.BytesIO(content), filename)},
            content_type="multipart/form-data",
        )

    def test_import_returns_decimal_amounts_as_json_numbers(self):
        response = self.upload(
            "mixed.json",
            json.dumps([format_a(amount="0.10")]).encode("utf-8"),
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('"amount":0.10', body)
        self.assertIsInstance(response.json["transactions"][0]["normalized"]["amount"], float)
        self.assertEqual(response.json["metrics"]["currency_totals_display"]["USD"], "0.10")

    def test_empty_array_is_successful_and_rules_are_read_only(self):
        response = self.upload("empty.json", b"[]")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["metrics"]["processed"], 0)
        self.assertEqual(self.client.get("/api/rules").status_code, 200)

    def test_malformed_and_unsupported_documents_are_file_errors(self):
        malformed = self.upload("broken.json", b"[{")
        self.assertEqual(malformed.status_code, 400)
        self.assertIn("Malformed JSON", malformed.json["error"])
        top_level = self.upload("object.json", b'{"transactions":[]}')
        self.assertEqual(top_level.status_code, 400)
        self.assertIn("top-level value must be an array", top_level.json["error"])
        non_finite = self.upload("nan.json", b"[NaN]")
        self.assertEqual(non_finite.status_code, 400)
        self.assertIn("Malformed JSON", non_finite.json["error"])

    def test_file_name_and_missing_file_validation(self):
        response = self.upload("transactions.txt", b"[]")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/import", data={}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
