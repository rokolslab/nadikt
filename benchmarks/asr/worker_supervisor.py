"""Parent-side spawned worker supervisor for local ASR benchmark probes."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from .privacy_audit import audit_text_artifact
from .worker_protocol import WorkerRequest, WorkerResult, loads_result


@dataclass(frozen=True)
class WorkerSupervisor:
    timeout_seconds: float = 120.0

    def run(self, request: WorkerRequest) -> WorkerResult:
        completed = subprocess.run(
            [sys.executable, "-m", "benchmarks.asr.benchmark_worker"],
            input=request.to_worker_json(),
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        audit = audit_text_artifact(completed.stdout + completed.stderr, canary="NADIKT_CONTROLLED_CANARY")
        if audit.canary_present or audit.forbidden_payload_count:
            raise ValueError("worker_output_privacy_violation")
        result = loads_result(completed.stdout)
        if result.nonce != request.nonce:
            raise ValueError("worker_result_nonce_mismatch")
        return result


__all__ = ["WorkerSupervisor"]
