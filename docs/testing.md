[← Начало работы](getting-started.md) · [К проекту](../README.md) · [ТЗ →](requirements/Nadikt_TZ_v0.2.md)

# Тестирование

## Текущий Test Suite

Production test suite только начинает появляться. Сейчас есть contract tests
для локального ASR benchmark harness и отдельный исполняемый набор disposable
Windows insertion spike; оба используют стандартный `unittest`.

```powershell
python3 -m unittest discover -s tests
```

Команда проверяет manifest validation, dry-run, privacy audit, quality metrics
и ASR contract redaction без реальных моделей и без пользовательских payload.

ASR benchmark environment metadata находится в `pyproject.toml` и
`requirements/benchmark/`. Эти locks относятся только к benchmark/probe runs и
не фиксируют runtime или installer dependencies приложения.

Корневой `.gitignore` дополнительно защищает локальные ASR packages, Hub caches,
raw audio, reference transcripts и generated probe outputs. В Git допускаются
только example manifests, documentation и tiny synthetic metadata/text fixtures.

Disposable Windows insertion spike запускается отдельно:

```powershell
cd experiments/windows_insertion
python -m unittest discover -s tests
```

Документированная baseline для merged spike: 63 unit/contract tests.

## Что Проверяется

| Уровень | Примеры |
|---|---|
| Contracts | Opaque target token, privacy-safe `repr`, outcome codes |
| Orchestration | Повторный request, pending restoration, interrupts, races |
| Target adapter | Changed window/control, password, integrity, PID reuse |
| Clipboard adapter | Formats, ownership sequence, partial writes, recovery |
| Input adapter | UTF-16, modifiers, partial `SendInput`, poisoned cleanup |
| CLI/fixtures | Dry-run, confirmation gates, controlled synthetic input |
| ASR benchmark | Manifest validation, missing package outcomes, privacy-safe dry-run, metric helpers |

## Compile Check

```powershell
python -m compileall -q insertion_spike fixtures
```

## Controlled Fixture

```powershell
python fixtures/classic_target.py --self-check
```

Ожидаются safe outcome codes без вывода payload. Не запускайте несколько
self-check процессов параллельно: они конкурируют за foreground.

## Privacy Gate

Tests и diagnostics не должны содержать:

- request text или transcript;
- clipboard bytes, filenames и format payload;
- HWND, PID, titles или control content;
- пользовательские данные и реальные credentials.

Вместо этого разрешены case IDs, capability flags, outcome codes, durations и
aggregate event/format counts.

## ASR Benchmark Dry Run

```powershell
python3 -m benchmarks.asr.dry_run --dataset benchmarks/asr/datasets/dataset.example.json --models model_packs/model_inventory.example.json
```

Ожидаемый результат: deterministic `missing_package` outcomes для example
packages, `network_attempted=false`, отсутствие transcript/audio payload в JSON
summary.

Для локальных real-package проверок используйте ignored package roots и run
directories, например `local-packages/` и `benchmarks/asr/runs/`. Абсолютные
пути, raw audio labels, transcripts и reference text не должны попадать в logs,
stdout или JSON summaries.

Для controlled offline acceptance можно выставить
`NADIKT_BENCHMARK_OFFLINE_REQUIRED=1`. Эта переменная только фиксирует требование
в dry-run summary; фактическая блокировка исходящей сети выполняется внешними
средствами ОС или изолированной среды.

## ASR Benchmark Environment Fingerprint

```powershell
python3 -m benchmarks.asr.environment_fingerprint
```

Fingerprint содержит только allowlisted fields: Python version/implementation,
platform system/release/machine, locale encoding, package versions, lock digest
prefixes и concrete inference defaults. Он не должен включать hostname,
username, interpreter path, argv, environment values, wheel/cache paths или
proxy/credential settings.

Real ASR run должен использовать заранее подготовленный environment:

1. Materialize selected backend lock under `requirements/benchmark/` with exact approved wheel hashes and no `Status: NOT_MATERIALIZED` marker.
2. Build/install from offline wheelhouse only with `--no-index --require-hashes`.
3. Set concrete thread defaults, for example `cpu_threads=4`, `OMP_NUM_THREADS=4`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.
4. Run fingerprint and store only safe JSON fields with benchmark results.
5. Do not run `pip install`, dependency resolution or network access inside the benchmark run.

## ASR Local Package Probe Dry Run

```powershell
python3 -m benchmarks.asr.local_model_probe --models model_packs/model_inventory.example.json --dry-run --offline-required
```

Ожидаемый результат без local packages: deterministic `missing_package`
outcomes, `network_attempted=false`, backend adapters не создаются, audio path и
transcript payload отсутствуют в JSON summary. Реальный `--audio-file`
допускается только для controlled storage вне Git и должен сопровождаться safe
`--audio-label`.

Для следующего GigaAM real-load spike package directory должен быть заранее
заполнен в cache-style layout SDK: `<gigaam_model_name>.ckpt` и, для `e2e` или
`v1_rnnt`, `<gigaam_model_name>_tokenizer.model`. После обновления checksum в
local inventory запуск выполняется той же командой без `--dry-run`, при внешне
заблокированной сети.

## ASR Coding Pilot Controlled Assets

Coding-pilot real runs use controlled storage outside Git:

```text
<controlled-root>/
|-- models/
|   |-- inventory.json
|   |-- <package-id>.manifest.json
|   `-- packages/<package-id>/...
|-- datasets/
|   |-- audio/*.wav
|   |-- references/*.txt
|   `-- bindings.json
|-- wheelhouse/<backend-profile>/
|-- cache/
`-- runs/
```

Requirements before a measured run:

1. Build/install each candidate benchmark venv from its controlled wheelhouse, not from an online index.
2. Confirm the frozen pair is exactly `gigaam-multilingual-220m` and `faster-whisper-small-int8`.
3. Store real audio/reference files only under controlled storage outside Git.
4. Validate private bindings against `benchmarks/asr/datasets/coding_pilot.v1.json`.
5. Validate model package sidecar/inventory, including trusted index digest, exact package/candidate/backend binding, package format roles, file sizes and SHA-256, then make the model package tree read-only.
6. Keep writable caches outside the immutable package directory.
7. Run the WSL2 network evidence positive/negative controls for `qualified-wsl2-default-deny-v1`.

Reference validation command:

```powershell
python3 - <<'PY'
from pathlib import Path
from benchmarks.asr.dataset_bindings import validate_dataset_bindings
result = validate_dataset_bindings(
    Path('benchmarks/asr/datasets/coding_pilot.v1.json'),
    Path('<controlled-root>/datasets/bindings.json'),
    Path('<controlled-root>/datasets'),
)
print(result.outcome, len(result.resolved_samples), list(result.errors))
PY
```

First lifecycle gate:

```powershell
python3 -m benchmarks.asr.local_model_probe --models <controlled-root>/models/inventory.json --candidate faster-whisper-small-int8 --audio-file <controlled-root>/datasets/audio/warmup_001.wav --audio-label controlled-audio:warmup_001
```

Coding-pilot matrix preflight/dry-run command:

```powershell
python3 -m benchmarks.asr.benchmark_runner --inventory <controlled-root>/models/inventory.json --dataset-profile benchmarks/asr/datasets/coding_pilot.v1.json --run-profile benchmarks/asr/run_profiles/coding_pilot.v1.json --private-bindings <controlled-root>/datasets/bindings.json --controlled-root <controlled-root>/datasets --repeats 3 --dry-run --output <controlled-root>/runs/pilot-ru-coding-preflight.json
```

The run profile rejects single-candidate filters, missing/extra/duplicate candidates,
repeats below 3, dataset revision drift and duration drift before worker spawn. The
measured runner must use the same `--run-profile` and complete both candidates.

If external default-deny network observation is not active, the publishable
artifact must keep `offline_evidence.status=NOT VERIFIED` even when load and
transcription phases succeed.

## Real ASR Lifecycle Opt-In

Real model loading is disabled by default. Without both opt-in variables the
integration test reports an explicit `SKIP`, not pass/fail:

```powershell
python3 -B -m unittest tests.integration.test_real_local_asr_load
```

Private config lives outside Git and contains only local controlled paths:

```json
{
  "inventory": "<controlled-root>/models/inventory.json",
  "dataset_profile": "benchmarks/asr/datasets/coding_pilot.v1.json",
  "private_bindings": "<controlled-root>/datasets/bindings.json",
  "controlled_root": "<controlled-root>/datasets",
  "candidates": ["gigaam-multilingual-220m", "faster-whisper-small-int8"],
  "sample_id": "warmup_001",
  "duration_seconds": 1.0,
  "require_offline_evidence_pass": true
}
```

Execution sequence for a real lifecycle gate:

1. Install each candidate interpreter from an offline wheelhouse only: `python3 -m pip install --no-index --find-links <wheelhouse> --require-hashes -r requirements/benchmark/<profile>.lock.txt`.
2. Validate bindings with the command above and fix any `bindings_invalid` result before ASR load.
3. Validate both package probes: `python3 -m benchmarks.asr.local_model_probe --models <controlled-root>/models/inventory.json --candidate <candidate-id> --audio-file <controlled-root>/datasets/audio/warmup_001.wav --audio-label controlled-audio:warmup_001 --offline-required`.
4. Run qualified evidence self-tests for `qualified-wsl2-default-deny-v1`; positive control must observe a synthetic attempt and negative control must observe zero attempts.
5. Run the opt-in integration test: `NADIKT_REAL_ASR_ASSETS=1 NADIKT_REAL_ASR_CONFIG=<private-config.json> python3 -B -m unittest tests.integration.test_real_local_asr_load`.
6. Run the measured pilot only after lifecycle and evidence gates pass: `python3 -m benchmarks.asr.benchmark_runner --inventory <controlled-root>/models/inventory.json --dataset-profile benchmarks/asr/datasets/coding_pilot.v1.json --run-profile benchmarks/asr/run_profiles/coding_pilot.v1.json --private-bindings <controlled-root>/datasets/bindings.json --controlled-root <controlled-root>/datasets --repeats 3 --output <controlled-root>/runs/pilot-ru-coding-private.json`.
7. Validate the private output with schema/privacy gates before copying any sanitized aggregate into `benchmarks/asr/results/`.

If `require_offline_evidence_pass=true` and the observer is unavailable, the
integration test fails with `FAIL: offline_evidence_not_verified`. That is the
intended acceptance behavior: successful load/warm-up/transcribe without
qualified offline evidence is `NOT VERIFIED`, not an acceptance pass.

## Manual Matrix

Notepad, browser, Word, 1C, elevated target, Windows 10 и real image/file-list
clipboard cases пока имеют статус `NOT RUN`. Они не должны автоматически
считаться pass на основании unit tests.

Полная matrix находится в
[experiment README](../experiments/windows_insertion/README.md), решение — в
[результатах spike](research/windows_insertion_spike_results.md).

## Будущая Структура

После появления production source планируются:

- unit tests для domain/application без SDK и ОС;
- contract tests для всех реализаций ports;
- integration tests для SQLite, ASR packages и audio pipeline;
- отдельные Windows acceptance checks;
- CI на Windows и Ubuntu.

## См. Также

- [Начало работы](getting-started.md)
- [Техническое задание](requirements/Nadikt_TZ_v0.2.md)
- [Архитектура](../.ai-factory/ARCHITECTURE.md)
