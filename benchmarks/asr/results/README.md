# ASR Benchmark Results

This directory stores publishable, privacy-safe aggregate benchmark results only.

Raw audio, references, hypotheses, worker stdout/stderr captures and private run workspaces stay under ignored controlled storage such as `benchmarks/asr/runs/` or an external controlled root.

`pilot-ru-coding-20260803T121525Z.json` was removed from publishable results on 2026-08-03. It is schema-invalid legacy evidence for the `coding_pilot` direction: it covers only one candidate, has `offline_evidence.status=NOT VERIFIED`, uses schema v1 rather than the required v2 aggregate, and therefore must not be treated as a published benchmark result.
