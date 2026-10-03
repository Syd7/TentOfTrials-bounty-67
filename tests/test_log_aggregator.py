import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "log_aggregator"
sys.path.insert(0, str(REPO_ROOT / "tools"))

import log_aggregator


class LogParserFixtureTests(unittest.TestCase):
    def test_json_fields_match_hand_written_fixture_expectation(self):
        line = (FIXTURES / "json.log").read_text(encoding="utf-8").strip()
        self.assertEqual(
            log_aggregator.JSONLogParser().parse(line),
            {
                "timestamp": 1705314600,
                "level": "ERROR",
                "service": "payments",
                "message": "charge declined",
                "fields": {
                    "timestamp": 1705314600,
                    "level": "ERROR",
                    "service": "payments",
                    "message": "charge declined",
                    "request_id": "req-42",
                },
                "format": "json",
            },
        )

    def test_plain_text_timestamp_level_service_and_message(self):
        lines = (FIXTURES / "plain_text.log").read_text(encoding="utf-8").splitlines()
        parser = log_aggregator.TextLogParser()
        self.assertEqual(
            [parser.parse(line) for line in lines],
            [
                {
                    "timestamp": 1705314600,
                    "level": "warn",
                    "service": "checkout",
                    "message": "2024-01-15 10:30:00 WARN [checkout] connection slow",
                    "fields": {"raw": "2024-01-15 10:30:00 WARN [checkout] connection slow"},
                    "format": "text",
                },
                {
                    "timestamp": 1705314720,
                    "level": "info",
                    "service": "inventory",
                    "message": "2024-01-15T10:32:00 INFO [inventory] refresh complete",
                    "fields": {"raw": "2024-01-15T10:32:00 INFO [inventory] refresh complete"},
                    "format": "text",
                },
            ],
        )

    def test_nginx_fixture_is_routed_to_nginx_parser(self):
        line = (FIXTURES / "nginx.log").read_text(encoding="utf-8").strip()
        aggregator = log_aggregator.LogAggregator()
        self.assertTrue(aggregator._parse_line(line))
        self.assertEqual(
            aggregator.entries,
            [
                {
                    "timestamp": 1705314660,
                    "level": "error",
                    "service": "nginx",
                    "message": "GET /health HTTP/1.1",
                    "fields": {
                        "remote_addr": "203.0.113.7",
                        "remote_user": "alice",
                        "request": "GET /health HTTP/1.1",
                        "status": 503,
                        "body_bytes": "17",
                        "referer": "-",
                        "user_agent": "fixture-agent/1.0",
                    },
                    "format": "nginx",
                }
            ],
        )

    def test_malformed_and_unsupported_records_do_not_raise(self):
        lines = (FIXTURES / "malformed.log").read_text(encoding="utf-8").splitlines()
        json_parser = log_aggregator.JSONLogParser()
        self.assertIsNone(json_parser.parse(lines[0]))
        self.assertIsNone(json_parser.parse(lines[1]))

        aggregator = log_aggregator.LogAggregator()
        for line in lines:
            with self.subTest(line=line):
                self.assertTrue(aggregator._parse_line(line))
        self.assertEqual(len(aggregator.entries), 3)
        self.assertTrue(all(entry["format"] == "text" for entry in aggregator.entries))

    def test_cli_input_output_format_compatibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "log_aggregator.py"),
                    "--input",
                    str(FIXTURES / "json.log"),
                    "--output",
                    str(output),
                    "--format",
                    "json",
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("Summary:", result.stdout)
            self.assertEqual(report["summary"]["total_entries"], 1)
            self.assertEqual(report["entries"][0]["format"], "json")
            self.assertEqual(report["entries"][0]["service"], "payments")

    def test_cli_malformed_input_without_timestamps_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "log_aggregator.py"),
                    "--input",
                    str(FIXTURES / "malformed.log"),
                    "--output",
                    str(output),
                    "--format",
                    "json",
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("Time range: N/A to N/A", result.stdout)
            self.assertEqual(report["summary"]["total_entries"], 3)
            self.assertTrue(all(entry["format"] == "text" for entry in report["entries"]))


if __name__ == "__main__":
    unittest.main()
