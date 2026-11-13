"""Dated advisory evidence: exact pins, closed custody and offline rejection."""
from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from tools_t7 import dependency_security as security


PINS = {"pip": "26.3", "cryptography": "50.0.2", "cffi": "2.0.0", "pycparser": "3.0",
    "jsonschema": "4.26.0", "attrs": "25.4.0", "jsonschema-specifications": "2025.9.1",
    "referencing": "0.37.0", "rpds-py": "0.30.0", "typing-extensions": "4.15.0",
    "blake3": "1.0.7", "pyyaml": "6.0.2", "pillow": "13.0.0"}


class Response:
    status = 200
    def __init__(self, raw, url=security.SERVICE_URL):
        self.raw, self.url = raw, url
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def geturl(self):
        return self.url
    def read(self, limit):
        return self.raw[:limit]


class DependencySecurityTests(unittest.TestCase):
    def snapshot(self, raw=None):
        if raw is None:
            raw = json.dumps({"results": [{} for _ in PINS]}).encode()
        with patch.object(security.urllib.request, "urlopen", return_value=Response(raw)) as network:
            result = security.audit(PINS)
        request = network.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.osv.dev/v1/querybatch")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {"queries": [
            {"package": {"ecosystem": "PyPI", "name": name}, "version": PINS[name]} for name in sorted(PINS)]})
        self.assertEqual(base64.b64decode(result["response_base64"]), raw)
        return result

    def rehash(self, snapshot):
        return security.rooted({key: value for key, value in snapshot.items() if key != "receipt_root"})

    def test_explicit_audit_and_pure_offline_verification_preserve_exact_response(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot["status"], "NO_MATCHES_AS_OF_SCAN")
        self.assertEqual(snapshot["query_count"], 13)
        self.assertEqual(snapshot["result_count"], 13)
        self.assertEqual(snapshot["advisory_record_count"], 0)
        with patch.object(security.urllib.request, "urlopen", side_effect=AssertionError("offline verifier contacted network")):
            self.assertEqual(security.verify_snapshot(snapshot, PINS), snapshot)
        self.assertEqual(snapshot["authority_effect"], "NONE")
        self.assertIn("NOT_ABSOLUTE_SAFETY", snapshot["scope"])
        self.assertIn("OWNER_ACCEPTED_OUTER_LOCK_ROOT", snapshot["trust_boundary"])

    def test_historical_timestamp_remains_replayable_without_age_promotion(self):
        snapshot = self.snapshot()
        snapshot["scan_timestamp_utc"] = "2000-01-01T00:00:00Z"
        snapshot = self.rehash(snapshot)
        self.assertEqual(security.verify_snapshot(snapshot, PINS)["scan_timestamp_utc"], "2000-01-01T00:00:00Z")
        for value in ("2000-01-01T00:00:00", "2000-01-01T00:00:00+01:00", "2000-02-31T00:00:00Z"):
            altered = deepcopy(snapshot); altered["scan_timestamp_utc"] = value
            with self.subTest(value=value), self.assertRaisesRegex(security.DependencySecurityError, "TIMESTAMP"):
                security.verify_snapshot(self.rehash(altered), PINS)

    def test_exact_pin_set_versions_and_query_order_are_bound(self):
        snapshot = self.snapshot()
        variants = [{key: value for key, value in PINS.items() if key != "pip"}, {**PINS, "extra": "1.0"},
                    {**PINS, "pip": "26.0.1"}, {**PINS, "pip": ">=26"}]
        for pins in variants:
            with self.subTest(pins=pins), self.assertRaises(security.DependencySecurityError):
                security.verify_snapshot(snapshot, pins)
        request = json.loads(base64.b64decode(snapshot["request_base64"]))
        request["queries"].reverse()
        raw = security.canonical(request)
        snapshot["request_base64"] = base64.b64encode(raw).decode()
        snapshot["request_sha256"] = security.sha(raw)
        with self.assertRaisesRegex(security.DependencySecurityError, "QUERY_BINDING"):
            security.verify_snapshot(self.rehash(snapshot), PINS)

    def test_rehashed_metadata_cannot_replace_exact_snapshot_context(self):
        snapshot = self.snapshot()
        for field, value in (("service_url", "https://example.invalid/v1/querybatch"), ("query_count", 12),
                             ("result_count", True), ("request_sha256", "0" * 64),
                             ("response_sha256", "0" * 64), ("status", "SAFE"), ("advisory_record_count", False),
                             ("scope", "ABSOLUTELY_SAFE"), ("authority_effect", "APPROVED")):
            altered = deepcopy(snapshot); altered[field] = value
            with self.subTest(field=field), self.assertRaises(security.DependencySecurityError):
                security.verify_snapshot(self.rehash(altered), PINS)
        altered = deepcopy(snapshot); altered["results"].reverse()
        with self.assertRaisesRegex(security.DependencySecurityError, "SNAPSHOT_BINDING"):
            security.verify_snapshot(self.rehash(altered), PINS)
        altered = deepcopy(snapshot); altered["response_base64"] = "!!!"
        with self.assertRaisesRegex(security.DependencySecurityError, "BASE64"):
            security.verify_snapshot(self.rehash(altered), PINS)

    def test_nonzero_results_raise_typed_rejection_with_snapshot(self):
        response = {"results": [{} for _ in PINS]}
        response["results"][0] = {"vulns": [{"id": "GHSA-fixture-known", "modified": "2026-01-01T00:00:00Z"}]}
        with patch.object(security.urllib.request, "urlopen", return_value=Response(security.canonical(response))):
            with self.assertRaises(security.DependencySecurityError) as raised:
                security.audit(PINS)
        self.assertEqual(raised.exception.code, "MMC_DEPENDENCY_SECURITY_KNOWN_VULNERABILITIES")
        snapshot = raised.exception.snapshot
        self.assertEqual(snapshot["status"], "KNOWN_VULNERABILITIES_FOUND")
        self.assertEqual(snapshot["advisory_record_count"], 1)
        with patch.object(security.urllib.request, "urlopen", side_effect=AssertionError("offline")):
            with self.assertRaisesRegex(security.DependencySecurityError, "KNOWN_VULNERABILITIES"):
                security.verify_snapshot(snapshot, PINS)
        snapshot["results"][0]["advisory_ids"] = []
        snapshot["advisory_record_count"] = 0; snapshot["status"] = "NO_MATCHES_AS_OF_SCAN"
        with self.assertRaisesRegex(security.DependencySecurityError, "SNAPSHOT_BINDING"):
            security.verify_snapshot(self.rehash(snapshot), PINS)

    def test_incomplete_malformed_and_duplicate_responses_never_mean_zero_matches(self):
        good = {"results": [{} for _ in PINS]}
        partial = deepcopy(good); partial["results"][0] = {"next_page_token": "more"}
        malformed = deepcopy(good); malformed["results"][0] = {"vulns": None}
        duplicate = deepcopy(good); duplicate["results"][0] = {"vulns": [{"id": "GHSA-fixture"}, {"id": "GHSA-fixture"}]}
        for raw in (b'{}', b'{"results":[],"results":[]}', security.canonical({"results": []}),
                    security.canonical({"results": good["results"] + [{}]}), security.canonical(partial),
                    security.canonical(malformed), security.canonical(duplicate)):
            with self.subTest(raw=raw), patch.object(security.urllib.request, "urlopen", return_value=Response(raw)):
                with self.assertRaises(security.DependencySecurityError):
                    security.audit(PINS)

    def test_fresh_custody_keeps_raw_bytes_and_failure_terminal(self):
        response = {"results": [{} for _ in PINS]}
        response["results"][0] = {"vulns": [{"id": "GHSA-fixture-known"}]}
        raw = security.canonical(response)
        with tempfile.TemporaryDirectory(prefix="mmc-osv-custody-") as temporary:
            output = Path(temporary) / "failed"
            with patch.object(security.urllib.request, "urlopen", return_value=Response(raw)):
                with self.assertRaisesRegex(security.DependencySecurityError, "KNOWN_VULNERABILITIES"):
                    security.audit(PINS, output=output)
            self.assertEqual((output / "response.json").read_bytes(), raw)
            self.assertTrue((output / "request.json").exists())
            self.assertEqual(json.loads((output / "SNAPSHOT.json").read_bytes())["status"], "KNOWN_VULNERABILITIES_FOUND")
            terminal = json.loads((output / "AUDIT-TERMINAL.json").read_bytes())
            self.assertEqual(terminal["status"], "FAILED")
            original = (output / "AUDIT-TERMINAL.json").read_bytes()
            with patch.object(security.urllib.request, "urlopen") as network:
                with self.assertRaisesRegex(security.DependencySecurityError, "CUSTODY"):
                    security.audit(PINS, output=output)
                network.assert_not_called()
            self.assertEqual((output / "AUDIT-TERMINAL.json").read_bytes(), original)

    def test_network_failure_and_redirect_are_refusals_with_terminal(self):
        with tempfile.TemporaryDirectory(prefix="mmc-osv-network-") as temporary:
            output = Path(temporary) / "network"
            with patch.object(security.urllib.request, "urlopen", side_effect=urllib.error.URLError("fixture offline")):
                with self.assertRaisesRegex(security.DependencySecurityError, "SECURITY_NETWORK"):
                    security.audit(PINS, output=output)
            self.assertEqual(json.loads((output / "AUDIT-TERMINAL.json").read_bytes())["status"], "FAILED")
        raw = security.canonical({"results": [{} for _ in PINS]})
        with patch.object(security.urllib.request, "urlopen", return_value=Response(raw, "https://example.invalid")):
            with self.assertRaisesRegex(security.DependencySecurityError, "HTTP_ORIGIN"):
                security.audit(PINS)


if __name__ == "__main__":
    unittest.main()
