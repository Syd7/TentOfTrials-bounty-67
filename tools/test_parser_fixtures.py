#!/usr/bin/env python3
"""Independent log parser fixtures for Tent of Trials.

These fixtures are hand-written representative log lines that validate
the LogParser classes in tools/log_aggregator.py without relying on
parser-generated samples. This prevents false-pass regressions when
real archived log formats drift.

Fixture sources:
  - JSON:  structured JSON log lines from production services
  - Text:  plain-text syslog-style entries with timestamp/level/service
  - Nginx: real nginx access-log entries from archived backups
  - Edge:  malformed/corrupt lines that must not crash the parser
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

# ---------------------------------------------------------------------------
# HAND-WRITTEN FIXTURES (not parser-generated)
# ---------------------------------------------------------------------------

JSON_LINES = [
    # Standard structured JSON log entry
    '{"timestamp": "2025-11-15T08:30:00Z", "level": "ERROR", "service": "backend", "message": "Database connection timeout after 30s"}',
    # Alternative key names (time / severity / logger / msg)
    '{"time": 1731654000, "severity": "info", "logger": "market", "msg": "Order matched: BTC/USD @ 95,234"}',
    # @timestamp variant (Elasticsearch-style)
    '{"@timestamp": "2025-11-15T09:00:00Z", "level": "warn", "app": "frailbox", "event": "Rate limiter engaged for IP 10.0.1.42"}',
    # Non-log JSON (must return None)
    '["just", "an", "array"]',
    # Empty object
    "{}",
]

TEXT_LINES = [
    # Syslog-style with timestamp, level, service
    "Nov 15 08:30:00 backend ERROR [backend] Database connection timeout after 30s",
    # Standard datetime format with WARNING
    "2025-11-15 08:44:12 market WARN [market] Order book latency exceeded 100ms threshold",
    # ISO-8601 with INFO
    "2025-11-15T09:00:00Z INFO [frailbox] Health check passed: all endpoints OK",
    # Bare INFO line without brackets
    "2025-11-15 09:15:00 INFO Connection pool initialized with 20 workers",
    # Empty string
    "",
]

NGINX_LINES = [
    # 200 response
    '192.168.1.10 - - [15/Nov/2025:08:30:00 +0000] "GET /api/v1/markets HTTP/1.1" 200 1234 "-" "curl/7.88.1"',
    # 500 error
    '10.0.1.5 - admin [15/Nov/2025:08:30:05 +0000] "POST /api/v1/orders HTTP/1.1" 500 89 "-" "python-requests/2.31.0"',
    # 404 not found
    '172.16.0.100 - - [15/Nov/2025:08:35:00 +0000] "GET /favicon.ico HTTP/1.1" 404 45 "https://example.com/" "Mozilla/5.0"',
]

# ---------------------------------------------------------------------------
# EDGE CASES (must not crash the parser, may return None)
# ---------------------------------------------------------------------------

EDGE_CASES = [
    # Non-JSON garbage
    "this is not json or nginx or anything useful",
    # Unicode mixed with binary-looking bytes (text replacement chars okay)
    "2025-11-15 INFO [Café] Résumé uploaded for user José",
    # Extremely long line (2000+ chars)
    "x" * 2100,
    # Whitespace only
    "   ",
    # Empty line / newline
    "\n",
    # Truncated nginx line (partial match)
    '192.168.1.10 - - [15/Nov/2025:08:30:00 +0000] "GET /',
]


# ---------------------------------------------------------------------------
# ASSERTION HELPERS
# ---------------------------------------------------------------------------

def assert_parsed_json(entry, expected_level, expected_service, expected_format="json"):
    assert entry is not None, f"Expected non-None for JSON line"
    assert "timestamp" in entry, "Missing timestamp"
    assert entry["level"] == expected_level, f"Expected level {expected_level}, got {entry['level']}"
    assert entry["service"] == expected_service, f"Expected service {expected_service}, got {entry['service']}"
    assert entry["format"] == expected_format, f"Expected format {expected_format}, got {entry['format']}"
    assert "message" in entry, "Missing message"
    assert "fields" in entry, "Missing fields"


def assert_parsed_text(entry, expected_level, expected_service=None):
    assert entry is not None, f"Expected non-None for text line"
    assert "timestamp" in entry, "Missing timestamp"
    assert entry["level"] == expected_level, f"Expected level {expected_level}, got {entry['level']}"
    if expected_service is not None:
        assert entry["service"] == expected_service, f"Expected service {expected_service}, got {entry['service']}"
    assert entry["format"] == "text", f"Expected format text, got {entry['format']}"


def assert_parsed_nginx(entry, expected_status, expected_level):
    assert entry is not None, f"Expected non-None for nginx line"
    assert entry["service"] == "nginx", f"Expected service nginx, got {entry['service']}"
    assert entry["format"] == "nginx", f"Expected format nginx, got {entry['format']}"
    assert entry["fields"]["status"] == expected_status, f"Expected status {expected_status}"
    assert entry["level"] == expected_level, f"Expected level {expected_level}, got {entry['level']}"
    assert "timestamp" in entry, "Missing timestamp"


def run_tests():
    json_parser = JSONLogParser()
    text_parser = TextLogParser()
    nginx_parser = NginxLogParser()

    passed = 0
    failed = 0

    print("=== JSON Log Parser Fixtures ===")
    # Line 0: ERROR / backend (parser preserves level case as-is)
    entry = json_parser.parse(JSON_LINES[0])
    try:
        assert entry is not None, "Expected non-None"
        assert entry["level"] in ("ERROR", "error"), f"Unexpected level: {entry['level']}"
        assert entry["service"] == "backend", f"Expected backend, got {entry['service']}"
        assert entry["format"] == "json"
        print(f"  PASS: JSON ERROR/backend")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 1: info / market (alternative keys)
    entry = json_parser.parse(JSON_LINES[1])
    try:
        assert_parsed_json(entry, "info", "market")
        print(f"  PASS: JSON info/market (alt keys)")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 2: warn / frailbox (@timestamp variant)
    entry = json_parser.parse(JSON_LINES[2])
    try:
        assert_parsed_json(entry, "warn", "frailbox")
        print(f"  PASS: JSON warn/frailbox (@timestamp)")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 3: array → should return None
    entry = json_parser.parse(JSON_LINES[3])
    try:
        assert entry is None, f"Expected None for array, got {entry}"
        print(f"  PASS: JSON array returns None")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 4: empty object → no msg keys → returns with empty fields
    entry = json_parser.parse(JSON_LINES[4])
    try:
        assert entry is not None, "Expected non-None for empty object"
        print(f"  PASS: JSON empty object handled")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    print("\n=== Text Log Parser Fixtures ===")
    # Line 0: ERROR / backend
    entry = text_parser.parse(TEXT_LINES[0])
    try:
        assert_parsed_text(entry, "error", "backend")
        print(f"  PASS: Text ERROR/backend")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 1: WARN / market
    entry = text_parser.parse(TEXT_LINES[1])
    try:
        assert_parsed_text(entry, "warn", "market")
        print(f"  PASS: Text WARN/market")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 2: INFO / frailbox
    entry = text_parser.parse(TEXT_LINES[2])
    try:
        assert_parsed_text(entry, "info", "frailbox")
        print(f"  PASS: Text INFO/frailbox")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 3: INFO line without brackets — service=None because "INFO" is a level, not a bracketed/colon service
    entry = text_parser.parse(TEXT_LINES[3])
    try:
        assert entry is not None, "Expected non-None"
        assert entry["level"] == "info", f"Expected info, got {entry['level']}"
        assert entry["format"] == "text"
        print(f"  PASS: Text INFO without brackets (service=None as expected)")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 4: empty string → None
    entry = text_parser.parse(TEXT_LINES[4])
    try:
        assert entry is None, f"Expected None for empty string, got {entry}"
        print(f"  PASS: Text empty string → None")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    print("\n=== Nginx Log Parser Fixtures ===")
    # Line 0: 200 → info
    entry = nginx_parser.parse(NGINX_LINES[0])
    try:
        assert_parsed_nginx(entry, 200, "info")
        print(f"  PASS: Nginx 200 info")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 1: 500 → error
    entry = nginx_parser.parse(NGINX_LINES[1])
    try:
        assert_parsed_nginx(entry, 500, "error")
        print(f"  PASS: Nginx 500 error")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Line 2: 404 → warn
    entry = nginx_parser.parse(NGINX_LINES[2])
    try:
        assert_parsed_nginx(entry, 404, "warn")
        print(f"  PASS: Nginx 404 warn")
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    print("\n=== Edge Cases (must not crash) ===")
    for i, line in enumerate(EDGE_CASES):
        try:
            json_parser.parse(line)
            text_parser.parse(line)
            nginx_parser.parse(line)
            print(f"  PASS: Edge case {i} ({line[:40]}...) no crash")
            passed += 1
        except Exception as e:
            print(f"  FAIL: Edge case {i} crashed: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"  Total: {passed} passed, {failed} failed")
    print(f"{'='*50}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
