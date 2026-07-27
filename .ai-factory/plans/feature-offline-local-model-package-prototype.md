# План реализации: offline local model package prototype для GigaAM и faster-whisper

Branch: feature/offline-local-model-package-prototype
Created: 2026-07-27

## Original Request

согласовано

## Настройки

- Testing: yes - план включает contract/unit tests для package validation, fake backend lifecycle, lazy segment consumption, safe failures и privacy audit; реальные model runs выполняются только при наличии локальных packages вне Git.
- Logging: verbose - DEBUG/INFO для lifecycle phases, package IDs, checksum prefixes, durations и outcome codes; audio, transcript, reference text, user dictionary, clipboard payload, absolute user paths и tokens не логируются.
- Docs: yes - mandatory documentation checkpoint: prototype findings должны попасть в `docs/research/` и связаться с существующим local ASR benchmark protocol/results template.

## Roadmap Linkage

Milestone: "Квалификация критических технических рисков"

Rationale: offline local package prototype закрывает риск автономной загрузки GigaAM/faster-whisper до запуска реального benchmark качества и производительности.

## Цель

Доказать или явно заблокировать локальный offline lifecycle для GigaAM и faster-whisper без выбора финальной модели: package manifest -> checksum validation -> local path load -> readiness -> warm-up -> one segment transcription/probe -> close/release -> privacy-safe outcome.

Этот план не скачивает model weights, не добавляет model weights в Git и не утверждает победителя ASR. Если локальные packages отсутствуют, реализация должна проходить missing/corrupted-package gates и фиксировать real-load checks как `NOT RUN`, а не подменять их Hub download.

## Scope

В scope:

- локальный package root policy и `.gitignore`/docs protection от случайного commit model weights;
- checksum validation critical files из `model_packs/model_inventory.example.json`-совместимого manifest;
- fake-backed lifecycle tests для `AsrEngine` semantics;
- faster-whisper probe только через local CTranslate2 directory, `device="cpu"`, `compute_type="int8"`, полное потребление lazy `segments` generator;
- GigaAM source/API probe для подтверждения или блокировки local loading path; `.transcribe` только для сегментов <= 25 seconds;
- controlled CLI/probe command без сетевых вызовов и без transcript/audio в logs/stdout;
- corrupted package, missing package, invalid path, incompatible backend и license marker outcomes;
- documentation of exact environment, commands, skipped checks and blockers.

Вне scope:

- скачивание GigaAM, Whisper, CTranslate2 или иных model weights;
- автоматическая загрузка моделей по Hub name;
- полноценный benchmark WER/CER/RTF на реальных данных;
- audio capture, VAD implementation, long dictation segmentation implementation;
- PySide6 UI, Windows hotkeys/insertion, SQLite settings, installer;
- выбор final MVP model.

## Инварианты

1. Runtime/probe принимает только локальный model package path, прошедший manifest/path/checksum validation.
2. Hub names вроде `small`, `openai/...`, `systran/...` или GigaAM model identifiers не являются допустимым runtime input.
3. Любой отсутствующий package или checksum mismatch даёт handled outcome без download attempt.
4. GigaAM local loading API нельзя придумывать: если исходный SDK не подтверждает offline local loading, outcome фиксируется как blocker/unsupported, а не обходится сетевой загрузкой.
5. faster-whisper `segments` generator должен быть полностью потреблён внутри измеряемой phase.
6. В памяти одновременно загружается не более одного backend object; probe runner закрывает текущий engine перед следующим.
7. Logs/stdout/results содержат только package IDs, candidate IDs, backend, checksum prefixes, phase IDs, durations, resource aggregates и outcome codes.
8. Audio path/user path/transcript/reference text не попадают в `repr`, exceptions, logs или JSON summary.
9. Все real model packages и local test audio хранятся вне Git; committed fixtures остаются synthetic metadata only.

## Предварительные Решения

- Использовать существующий `src/nadikt/domain/ports/asr.py` как boundary для lifecycle semantics.
- Размещать optional SDK-dependent adapters/probes в `src/nadikt/infrastructure/asr/` или `benchmarks/asr/` так, чтобы `domain` не импортировал SDK.
- Держать SDK imports lazy/optional: отсутствие `gigaam` или `faster_whisper` должно давать controlled skipped/unavailable outcome в tests/probe, а не import-time crash.
- Реальные model package paths должны приходить из local inventory file, не из code constants.

## Commit Plan

- **Commit 1** (после задач 1-4): `feat(asr): validate local model packages`
- **Commit 2** (после задач 5-9): `feat(asr): add offline backend probe harness`
- **Commit 3** (после задач 10-12): `test(asr): verify offline model package lifecycle`

## Задачи

### Фаза 1. Package Safety И Integrity

- [x] **Задача 1. Защитить репозиторий от model weights и локальных payload**
  - Deliverable: добавить или обновить root `.gitignore` и docs policy так, чтобы локальные model packages, Hub caches, raw audio, reference transcripts и probe outputs не попадали в Git.
  - Поведение: разрешить committed example manifests/docs, запретить `local-packages/`, Hub caches, model weights, tokenizer/checkpoint binaries, audio fixtures, controlled raw audio/reference storage и generated run artifacts вроде `benchmarks/asr/runs/`.
  - Проверки: `git status --ignored` или документированный equivalent показывает, что sample local package paths игнорируются; existing docs не обещают хранение weights в Git.
  - Logging: нет runtime logging; в docs фиксировать только safe path patterns, без пользовательских абсолютных путей.
  - Files: `.gitignore`, `model_packs/README.md`, `benchmarks/asr/datasets/README.md`, `docs/testing.md`.

- [x] **Задача 2. Реализовать checksum validation для model package inventory**
  - Deliverable: добавить standard-library package integrity validator critical files/checksum prefixes для локальных packages и интегрировать его в существующие `offline_check.validate_local_package()` и `dry_run.run_dry_run()`, чтобы не создать parallel unused validator.
  - Поведение: validate package root stays inside configured inventory root after `resolve()`; reject missing critical file, checksum mismatch, bad checksum format, unsafe absolute/Windows/traversal paths for `package_path` and `critical_files.relative_path`; license marker `TO_BE_VERIFIED` is reported as `license_not_verified` packaging warning/gate outcome, not as fatal manifest schema error.
  - Зависимости: задача 1.
  - Проверки: contract tests покрывают valid synthetic package, missing package, missing file, checksum mismatch, invalid checksum, symlink/root escape, traversal path и Windows absolute path; dry-run summary includes integrity outcomes and keeps deterministic missing-package behavior for example packages.
  - Logging: DEBUG для package validation phase and decision; INFO для counts/outcome; logs include package ID and checksum prefix only, never absolute user path.
  - Files: `benchmarks/asr/package_integrity.py`, `benchmarks/asr/manifests.py`, `benchmarks/asr/offline_check.py`, `benchmarks/asr/dry_run.py`, `tests/contract/test_model_package_integrity.py`.

- [x] **Задача 3. Нормализовать example inventory checksum placeholders**
  - Deliverable: обновить `model_packs/model_inventory.example.json` и docs snippet так, чтобы committed example checksums были синтаксически валидными dummy SHA-256 values или явно не проходили только в dedicated corrupted fixture.
  - Поведение: existing example inventory remains valid for dry-run schema validation; bad checksum format проверяется отдельным test case, а не ломает baseline example manifest.
  - Зависимости: задача 2.
  - Проверки: `test_example_manifests_are_valid` продолжает проходить; отдельный corrupted/checksum-format test доказывает rejection invalid checksum.
  - Logging: нет runtime logging; docs не раскрывают реальные package paths или hashes.
  - Files: `model_packs/model_inventory.example.json`, `model_packs/README.md`, `tests/contract/test_model_package_integrity.py`.

- [x] **Задача 4. Подготовить safe local package fixtures без weights**
  - Deliverable: добавить tiny synthetic package fixture под tests или generated temp fixture helpers, не похожий на реальные model weights.
  - Поведение: fixture содержит текстовые dummy critical files с known checksums для validation tests; не используется для реального ASR load.
  - Зависимости: задача 2.
  - Проверки: tests создают fixture во временном каталоге или используют committed tiny text files only; privacy audit не находит transcript/audio markers.
  - Logging: fixture setup logs only fixture case ID and outcome; no file content dumps.
  - Files: `tests/contract/test_model_package_integrity.py`, возможно `tests/fixtures/model_packages/README.md`.

### Фаза 2. Backend Probe Harness

- [x] **Задача 5. Создать common offline probe outcome model**
  - Deliverable: определить safe DTO/result types и benchmark/probe outcome enum для package validation, backend availability, load, readiness, warm-up, transcribe probe, close и resource release.
  - Поведение: JSON summary содержит run ID, package ID, candidate ID, backend, phase outcomes, durations, checksum prefixes и `NOT RUN`/`SKIPPED` reasons; не содержит transcript/audio/user paths. Outcome enum maps to existing `AsrFailureCode` where applicable and defines benchmark-only codes such as `backend_unavailable`, `local_loading_unconfirmed`, `hub_identifier_rejected`, `not_run` and safe load/probe failures.
  - Зависимости: задачи 1-2.
  - Проверки: unit tests проверяют `repr`/JSON redaction и deterministic outcome codes.
  - Logging: DEBUG phase start/end; INFO final outcome; ERROR unexpected exceptions with safe exception class/code only.
  - Files: `benchmarks/asr/local_model_probe.py`, `benchmarks/asr/probe_results.py`, `tests/contract/test_local_model_probe.py`.

- [x] **Задача 6. Создать infrastructure ASR package boundary**
  - Deliverable: создать package tree для optional SDK-backed ASR adapters без eager SDK imports.
  - Поведение: `nadikt.domain` не импортирует `nadikt.infrastructure`; `src/nadikt/infrastructure/asr/` импортируется без установленного `gigaam` или `faster_whisper`; concrete SDK imports остаются внутри load/probe path.
  - Зависимости: задача 5.
  - Проверки: import/boundary smoke tests подтверждают lazy optional SDK imports and no infrastructure imports from `nadikt.domain`.
  - Logging: нет runtime logging.
  - Files: `src/nadikt/infrastructure/__init__.py`, `src/nadikt/infrastructure/asr/__init__.py`, `tests/contract/test_asr_adapter_import_boundaries.py`.

- [x] **Задача 7. Реализовать faster-whisper local adapter/probe с lazy optional import**
  - Deliverable: добавить probe adapter, который импортирует `faster_whisper` только внутри load/probe path и принимает только local CTranslate2 directory.
  - Поведение: `WhisperModel(str(local_dir), device="cpu", compute_type="int8")`; reject Hub names; `segments` generator fully consumed; text не печатается и не попадает в result/logs; при отсутствующем package/dependency возвращается controlled outcome.
  - Зависимости: задачи 2, 5 и 6.
  - Проверки: fake `WhisperModel` tests подтверждают local path, CPU INT8 config, generator consumption, missing dependency outcome, transcribe exception outcome и `close`/resource cleanup hook где возможно.
  - Logging: DEBUG для backend availability/load/warmup/transcribe/close phases; INFO для outcome/duration; no segment text, hypothesis, audio path or user path.
  - Files: `src/nadikt/infrastructure/asr/faster_whisper.py`, `benchmarks/asr/local_model_probe.py`, `tests/contract/test_faster_whisper_probe.py`.

- [x] **Задача 8. Провести GigaAM local loading API probe без придумывания SDK behavior**
  - Deliverable: добавить GigaAM probe wrapper и prototype note, который явно отделяет confirmed local path support от unsupported/unknown state.
  - Поведение: сначала inspect/import available SDK metadata and documented API; if only `gigaam.load_model(model_name)` is available and local package path is not documented/proven, return `local_loading_unconfirmed` and do not call network-capable load by model name. `.transcribe` allowed only for segments <= 25 seconds.
  - Зависимости: задачи 2, 5 и 6.
  - Проверки: fake GigaAM module tests cover missing dependency, local loading supported path, model-name-only path rejected, segment too long rejected, transcribe exception outcome.
  - Logging: DEBUG for GigaAM API capability checks and phase outcomes; WARN for unconfirmed local loading; no audio path/transcript/model user path.
  - Files: `src/nadikt/infrastructure/asr/gigaam.py`, `docs/research/local_asr_offline_package_prototype.md`, `tests/contract/test_gigaam_probe.py`.

- [x] **Задача 9. Добавить single-engine lifecycle probe runner**
  - Deliverable: CLI/module command, который читает inventory, validates one package at a time, запускает выбранный backend probe, закрывает engine перед следующим package и пишет safe JSON summary.
  - Поведение: supports `--models`, `--candidate`, `--backend`, `--offline-required`, `--dry-run`, optional `--audio-file <local path>` for controlled storage outside Git and separate safe `--audio-label <opaque label>` for logs/results; real transcribe probe runs only when package and controlled audio path are explicitly provided outside Git.
  - Зависимости: задачи 2 и 5-8.
  - Проверки: tests with fake backends confirm one active engine, close on failure, no second load before close, missing/corrupt package paths stop before backend import, faster-whisper generator consumed, argparse errors/JSON/logs never include `--audio-file` path.
  - Logging: DEBUG for runner phases and selected package IDs; INFO summary counts; ERROR unexpected runner failure with safe outcome only.
  - Files: `benchmarks/asr/local_model_probe.py`, `tests/contract/test_local_model_probe.py`, `docs/research/local_asr_offline_package_prototype.md`.

### Фаза 3. Offline Acceptance, Tests И Docs

- [x] **Задача 10. Добавить offline/privacy regression tests**
  - Deliverable: расширить contract tests для network-block marker, forbidden Hub names, direct optional import safety, log/stdout privacy audit и corrupted package outcomes.
  - Поведение: tests не требуют установленных GigaAM/faster-whisper или model weights; fake modules simulate SDK behavior. Real integration tests are skipped unless explicit env/local paths are provided.
  - Зависимости: задачи 2-9.
  - Проверки: `python3 -B -m unittest discover -s tests` passes without network/model packages; privacy audit canary absent from JSON/log captures.
  - Logging: test captures may include only safe outcome codes and IDs; canary value is never printed in assertion messages.
  - Files: `tests/contract/`, `benchmarks/asr/privacy_audit.py` if extension is needed.

- [x] **Задача 11. Выполнить controlled prototype run и зафиксировать limitations**
  - Deliverable: run documented commands for dry-run/missing package/corrupted synthetic package; if local real packages are available outside Git, run load/warm-up/close probes under blocked-network policy and record facts.
  - Поведение: absent real packages produce `NOT RUN` for real load checks, not failure; no automatic downloads; clean cache/profile requirement documented if not executable in current environment.
  - Зависимости: задачи 1-10.
  - Проверки: commands and outcomes are reproducible; `git status` contains no weights/audio/run artifacts; logs/results contain no transcript/audio/user path.
  - Logging: INFO for command purpose, environment, package IDs and outcomes; WARN for skipped real model checks; no raw SDK tracebacks with local paths or payload.
  - Files: `docs/research/local_asr_offline_package_prototype.md`, `docs/research/local_asr_performance_benchmark_results.md`.

- [x] **Задача 12. Обновить benchmark protocol и next-step decision gates**
  - Deliverable: связать prototype findings с existing benchmark plan/results, зафиксировать go/no-go criteria для перехода к real ASR quality benchmark.
  - Поведение: если GigaAM local load unconfirmed, next step is SDK/source investigation or alternative packaging strategy; if faster-whisper local load works, mark it eligible for real benchmark only after license/package checks. Не выбирать final model.
  - Зависимости: задача 11.
  - Проверки: docs clearly separate confirmed facts, skipped checks, blockers, and next actions; no claim that WSL2/i3 12th results replace Windows MVP baseline.
  - Logging: documentation includes only safe aggregate outcomes and package IDs, not raw logs.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`, `docs/research/local_asr_performance_benchmark_results.md`, `docs/README.md` if new prototype doc is added.

## Verification Gate

- All package validators and probe commands run without network/model packages and return deterministic safe outcomes.
- Contract tests pass on current WSL2 Ubuntu environment with standard library plus fake SDK modules.
- No model weights, tokenizer files, real audio, transcripts, reference text, Hub cache or probe output artifacts are tracked by Git.
- GigaAM local loading is either confirmed by code/prototype evidence or explicitly blocked as `local_loading_unconfirmed`.
- faster-whisper local path probe rejects Hub identifiers and consumes lazy `segments` generator in tests.
- Logs/stdout/JSON summaries pass privacy audit: no audio path, transcript, reference text, user dictionary, clipboard payload, absolute user paths or tokens.
- Docs state which checks are real, fake-backed, skipped, or blocked; final ASR model remains `NOT DECIDED`.

## Точка Остановки

После создания этого плана не начинать реализацию автоматически. Пользователь должен отдельно запустить `/aif-implement` после review плана.
