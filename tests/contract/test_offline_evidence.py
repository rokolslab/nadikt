from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.offline_evidence import OfflineMonitorObservation, qualified_evidence, unverified_evidence


class OfflineEvidenceTest(unittest.TestCase):
    def test_unverified_evidence_is_explicit_non_pass_without_private_payload(self) -> None:
        evidence = unverified_evidence("nonce-1234567890", reason="monitor_missing").to_json()

        rendered = json.dumps(evidence, ensure_ascii=False, sort_keys=True)

        self.assertEqual("NOT VERIFIED", evidence["status"])
        self.assertFalse(evidence["network_attempted"])
        self.assertEqual("monitor_missing", evidence["reason"])
        self.assertIn("nonce_prefix", evidence)
        self.assertNotIn("/private", rendered)
        self.assertNotIn("credential", rendered)

    def test_qualified_evidence_pass_requires_finalized_zero_attempts_and_controls(self) -> None:
        evidence = qualified_evidence(
            "nonce-abcdef123456",
            observation=_observation(),
            nadikt_revision="f" * 40,
            lock_digest_prefix="abc123def456",
            package_digest_prefix="fed456cba123",
        ).to_json()

        self.assertEqual("PASS", evidence["status"])
        self.assertFalse(evidence["network_attempted"])
        self.assertEqual(0, evidence["missed_event_count"])
        self.assertTrue(evidence["finalized_after_reap"])
        self.assertEqual(200, evidence["monitor_interval_ms"])
        self.assertEqual({"pid_start_time_ticks": 12345, "process_tree_root": "worker"}, evidence["process_identity"])

    def test_qualified_evidence_fail_and_not_verified_rules_are_fail_closed(self) -> None:
        fail = qualified_evidence(
            "nonce-abcdef123456",
            observation=_observation(observed_attempt_count=1),
            nadikt_revision="f" * 40,
            lock_digest_prefix="abc123def456",
            package_digest_prefix="fed456cba123",
        ).to_json()
        missed = qualified_evidence(
            "nonce-abcdef123456",
            observation=_observation(missed_event_count=1),
            nadikt_revision="f" * 40,
            lock_digest_prefix="abc123def456",
            package_digest_prefix="fed456cba123",
        ).to_json()
        stale = qualified_evidence(
            "nonce-abcdef123456",
            observation=_observation(finalized_after_reap=False),
            nadikt_revision="f" * 40,
            lock_digest_prefix="abc123def456",
            package_digest_prefix="fed456cba123",
        ).to_json()

        self.assertEqual("FAIL", fail["status"])
        self.assertTrue(fail["network_attempted"])
        self.assertEqual("network_attempt_observed", fail["reason"])
        self.assertEqual("NOT VERIFIED", missed["status"])
        self.assertEqual("monitor_missed_events", missed["reason"])
        self.assertEqual("NOT VERIFIED", stale["status"])
        self.assertEqual("monitor_not_finalized_after_reap", stale["reason"])


def _observation(
    *,
    finalized_after_reap: bool = True,
    observed_attempt_count: int = 0,
    missed_event_count: int = 0,
    positive_control_passed: bool = True,
    negative_control_passed: bool = True,
) -> OfflineMonitorObservation:
    return OfflineMonitorObservation(
        mechanism="wsl2-default-deny-observer",
        mechanism_version="v1",
        finalized_after_reap=finalized_after_reap,
        observed_attempt_count=observed_attempt_count,
        missed_event_count=missed_event_count,
        monitor_interval_ms=200,
        positive_control_passed=positive_control_passed,
        negative_control_passed=negative_control_passed,
        process_identity={"process_tree_root": "worker", "pid_start_time_ticks": 12345},
    )


if __name__ == "__main__":
    unittest.main()
