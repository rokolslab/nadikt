# План реализации: поставка ASR-моделей и benchmark диктовки для разработки

Ветка: `feature/asr-model-delivery-coding-benchmark`
Создан: 2026-08-03

## Original Request

ASR model delivery and coding dictation benchmark
Цель: превратить сохранённые решения из .ai-factory/RESEARCH.md в конкретный план работ: docs updates, model package delivery policy, ru_coding_terms dataset, real offline load gates и первый benchmark.

## Настройки

- Testing: yes
- Logging: verbose
- Docs: yes

## Связь с roadmap

Milestone: "Квалификация критических технических рисков"
Rationale: План закрывает следующий измеримый риск milestone: реальную локальную загрузку ASR packages и первый воспроизводимый quality/resource benchmark на CPU.

## Research Context

Source: `.ai-factory/RESEARCH.md` (Active Summary, Updated: 2026-08-03 10:08, SHA256: `893b79d40fa6b54ffe6a5ded5d75814a9c03d4b9388a0f37e1027ac1b2df750f`)

Topic: ASR model delivery and coding-dictation benchmark direction for Nadikt MVP.

Goal: Preserve fully local/private runtime while allowing practical model delivery options for installation and prioritizing accurate Russian dictation with coding-related English terms.

Constraints:
- Runtime dictation, ASR, insertion, dictionary, and normalization must work without internet after installation.
- Internet during installation is allowed only as fallback if embedded installer, separate model pack, or removable media delivery is not practical.
- Runtime must accept only a local verified model package path with checksum/package validation; Hub model names or implicit network downloads remain forbidden.
- Separate model pack files next to the installer or copied from a flash drive are acceptable.
- Installer/model pack size is not currently a major constraint.
- Manual model pack selection/installation by the user is acceptable for MVP.
- ASR priority is Russian accuracy with coding anglicisms, library names, commands, identifiers, abbreviations, and technical terms.
- Full mixed Russian-English dictation can be postponed or marked experimental after the first usable MVP.

Decisions:
- Separate install-time delivery from runtime package validation.
- Support multiple delivery channels for the same local model package format: embedded installer, separate offline package, and online installer fallback.
- Reframe early MVP ASR target from generic `Russian` vs full `Russian + English` to `Russian with coding terms` as the practical priority.
- Do not choose final ASR model until real local package load/probe and quality/resource benchmark results exist.

Open questions:
- Which concrete model packages can be legally redistributed or downloaded by the installer.
- Whether GigaAM cache-style local package loading works with real `.ckpt` and tokenizer files under blocked-network conditions.
- Whether faster-whisper CTranslate2 local packages provide enough Russian/coding-term quality on CPU INT8.
- What minimal coding-dictation dataset best represents the user's real workflow.
- Which Windows packaging mechanism will support model pack import/download with checksum verification.

Success signals:
- Real local package probe loads, warms up, short-transcribes, and closes at least one candidate under externally blocked network.
- Missing/corrupted package fails before backend import/load and never attempts network access.
- First coding-dictation benchmark covers Russian phrases with code terms such as `pytest`, `docker compose`, `React component`, `FastAPI route`, `access token`, `pull request`, and common identifiers.
- Benchmark compares quality, RTF, latency, CPU, and peak RAM on the current i3 12th gen development machine before later Windows baseline validation.
- A decision matrix can recommend one MVP ASR path and one fallback path without weakening runtime privacy/offline guarantees.

Next step: Create a full AI Factory plan for `ASR model delivery and coding dictation benchmark`, including documentation updates, dataset expansion, real model package preparation outside Git, offline load gates, and first quality/resource benchmark.

## Границы реализации

- Первый run является coding-focused pilot на текущей WSL2/i3 12-го поколения машине, а не Windows acceptance и не заменой полного набора с `long_10m`.
- Минимальный доказуемый результат включает один реально загруженный candidate; сравнительная рекомендация основного и резервного пути допустима только при сопоставимых результатах как минимум двух кандидатов.
- Installer/download implementation не входит в эту ветку: здесь фиксируются policy, channel-neutral package contract и проверяемый локальный runtime input.
- Model weights, SDK caches, audio, references, private bindings и raw transcripts остаются вне Git. В репозитории хранятся только schema, safe metadata, code, tests и агрегированные результаты.
- Raw ASR измеряется отдельно от пользовательского словаря и постобработки; `ru_coding_terms` является dataset category, а не новым пользовательским режимом.
- Offline delivery остаётся обязательным release channel. Явно запрошенный online acquisition допустим только как дополнительный installer-time канал и никогда не становится runtime fallback.
- `docs/requirements/Nadikt_TZ_v0.2.md` остаётся неизменной согласованной редакцией. Новые delivery decisions оформляются отдельной policy/amendment; новая редакция ТЗ требует отдельного product approval.

## План коммитов

- **Commit 1** (после задач 1-4): `feat(asr): define reproducible model package contract`
- **Commit 2** (после задач 5-9): `feat(asr): add verified coding benchmark worker`
- **Commit 3** (после задачи 10): `feat(asr): add privacy-safe benchmark runner`
- **Commit 4** (после задач 11-13): `docs(asr): publish first coding dictation pilot`

Commit 3 является обязательным code-freeze checkpoint: реальные измерения в задачах 11-12 выполняются только на чистом SHA этого коммита. Однозадачный checkpoint здесь намеренный, чтобы последующие docs/result changes не изменили измеряемую revision.

## Задачи

### Фаза 1: Базовая реализация, delivery policy и environment

- [x] **Задача 1: Интегрировать predecessor offline package prototype и подтвердить baseline**

  **Результат:** ветка содержит уже реализованные checksum/local-path gates, lifecycle probe, fake-backed GigaAM/faster-whisper adapters и contract tests из `feature/offline-local-model-package-prototype`, без повторной реализации и без несвязанных OpenCode changes. Если predecessor не слит в `main`, перенести `c352250`, затем `19e6d03`, при необходимости plan-source commit `bf32c7f`; не переносить `0beefc7`.

  **Файлы:** `.ai-factory/RESEARCH.md`, `.gitignore`, `benchmarks/asr/local_model_probe.py`, `benchmarks/asr/package_integrity.py`, `benchmarks/asr/probe_results.py`, `src/nadikt/infrastructure/asr/faster_whisper.py`, `src/nadikt/infrastructure/asr/gigaam.py`, `tests/contract/test_*probe.py`, `tests/contract/test_model_package_integrity.py`, `tests/contract/test_offline_privacy_regression.py` и связанные docs из predecessor branch. При selective transfer исключить `.ai-factory.json` и `opencode.json`.

  **Проверка:** до переноса проверить dirty worktree; после переноса проверить `git diff main...HEAD`, ожидаемый список ASR/docs paths и весь `tests/contract` suite. Реальные packages по-прежнему имеют статус `NOT RUN`, а fake-backed tests не представлены как real offline evidence.

  **Логирование:** сохранить whitelist-only DEBUG/INFO schema predecessor; проверить, что stdout/stderr/logs не содержат transcript, audio path, package absolute path, exception text или canary value. Новые логи на этапе интеграции не добавлять.

  **Зависимости:** нет; блокирует все последующие задачи.

- [x] **Задача 2: Зафиксировать channel-neutral model package delivery policy и trust model**

  **Результат:** каноническая policy разделяет install-time delivery и runtime loading. Embedded installer, отдельный offline pack, removable media и явно запрошенный online-installer fallback производят один и тот же локальный проверенный package; runtime не знает о канале доставки и никогда не принимает Hub ID или URL вместо local path. Offline package остаётся обязательным каналом, online acquisition не является единственным способом установки.

  **Файлы:** создать `docs/requirements/model_package_delivery_policy.md`; обновить ссылками `docs/requirements/Nadikt_multilingual_ASR_requirements.md`, `docs/README.md`, `model_packs/README.md`. `docs/requirements/Nadikt_TZ_v0.2.md` только проверить на непротиворечивость, не редактировать; нормативное изменение требует отдельного amendment или новой версии ТЗ.

  **Проверка:** описать staging, checksum/license/provenance validation, atomic registration, compatibility gate, manual MVP selection, rollback и failure behavior. Expected manifest digest должен поступать из встроенного installer index либо отдельно проверяемого signed release index; digest внутри загруженного package не является trust anchor. Развести статусы local evaluation, redistribution, bundling и installer download; не утверждать конкретный installer или право распространения до review.

  **Логирование:** policy разрешает только package/candidate IDs, phase/outcome codes, durations, checksum prefixes и resource aggregates. Даже при `verbose` запрещены URLs, tokens, абсолютные пути, model/audio payload и license document content.

  **Зависимости:** задача 1.

- [x] **Задача 3: Ввести versioned package schemas и расширить существующие validation gates**

  **Результат:** versioned sidecar manifest описывает immutable package/model revisions, backend/Nadikt compatibility, provenance, capabilities, licenses/notices и critical-file SHA-256. Local inventory не дублирует metadata и связывает `package_id` с `package_path`, `manifest_relative_path` и `manifest_sha256`. Existing predecessor integrity/path/checksum gates расширяются, а не реализуются повторно.

  **Файлы:** создать `model_packs/schemas/model_package_manifest.v1.schema.json`, `model_packs/schemas/model_inventory.v1.schema.json`, `model_packs/model_package_manifest.example.json`, `tests/contract/test_model_package_manifests.py`; обновить `model_packs/model_inventory.example.json`, `model_packs/README.md`, `benchmarks/asr/manifests.py`, `benchmarks/asr/package_integrity.py`, `benchmarks/asr/dry_run.py`, `tests/contract/test_asr_benchmark_harness.py`, `tests/contract/test_model_package_integrity.py`.

  **Проверка:** валидировать schema versions, unique/non-empty IDs, SHA-256/size/role critical files, sidecar binding, symlink/traversal containment, backend/package format/Nadikt compatibility и fail-before-SDK-import. Независимые rights statuses `local_evaluation`, `redistribution`, `bundling`, `installer_download` принимают только `approved`, `prohibited`, `review_required` и содержат `review_record_id`. Benchmark gate требует approved local evaluation; release gate дополнительно требует соответствующие distribution approvals. Non-example manifests отклоняют placeholders/all-zero digests. Manifest не содержит self-referential checksum.

  **Логирование:** DEBUG для безопасных этапов manifest/integrity validation, INFO для итогового gate, WARN для benchmark-only license status, ERROR только с safe outcome code. Не сериализовать provenance URL, filesystem path или raw exception.

  **Зависимости:** задачи 1 и 2.

- [x] **Задача 4: Зафиксировать воспроизводимое benchmark environment и backend dependency locks**

  **Результат:** real load и benchmark запускаются из воспроизводимого benchmark-only environment с pinned Python/backend/native dependencies. Base harness, faster-whisper и optional GigaAM имеют отдельные lock closures при конфликтах; runtime/install packaging dependencies этим не фиксируются.

  **Файлы:** создать `pyproject.toml` с минимальной project/test metadata, `requirements/benchmark/README.md`, backend-specific lock files в `requirements/benchmark/`, `benchmarks/asr/environment_fingerprint.py`, `tests/contract/test_environment_fingerprint.py`; обновить `docs/getting-started.md`, `docs/testing.md`.

  **Проверка:** зафиксировать Python minor/platform, exact SDK/CTranslate2/PyTorch/native versions, hashes, model conversion tool/version, system dependencies и offline wheelhouse procedure. Real run не выполняет `pip install`, dependency resolution или network access. `cpu_threads`, OpenMP/BLAS variables, locale и inference defaults получают concrete values вместо `auto`. Safe environment fingerprint содержит только package/version/lock digests и разрешённые platform fields, без hostname, username, interpreter path, argv и environment values.

  **Логирование:** DEBUG/INFO содержат environment profile ID, Python/platform IDs, lock digest prefixes и package versions. Wheel/cache paths, environment values, proxy/credential values и install command output запрещены.

  **Зависимости:** задача 3; блокирует real adapters, worker, lifecycle gates, assets и pilot run.

<!-- Commit checkpoint: tasks 1-4 -->

### Фаза 2: Dataset, metrics, adapters и offline worker

- [x] **Задача 5: Добавить versioned coding-pilot dataset contract и fail-closed controlled storage**

  **Результат:** public metadata-only profiles покрывают `ru_coding_terms`, короткий `ru_short` regression set и отдельный non-scored warm-up sample. Private bindings вне Git однозначно связывают sample IDs с относительными audio/reference files и digests под явно переданным controlled root.

  **Файлы:** создать `benchmarks/asr/datasets/ru_coding_terms.v1.json`, `benchmarks/asr/datasets/coding_pilot.v1.json`, `benchmarks/asr/schemas/dataset_bindings.v1.schema.json`, `benchmarks/asr/dataset_bindings.py`, `benchmarks/asr/dataset_storage.py`, `tests/contract/test_ru_coding_terms_dataset.py`; обновить `benchmarks/asr/datasets/dataset.example.json`, `benchmarks/asr/datasets/README.md`, `benchmarks/asr/manifests.py`, `.gitignore`.

  **Проверка:** ввести `manifest_kind` (`example`, `full_benchmark`, `dataset_profile`, `coding_pilot`), сохранив обязательные categories только для full benchmark. Expected terms используют versioned records `term_id`, `canonical`, `accepted_variants`, `expected_occurrences`, `require_latin`; включить минимум `pytest`, `docker compose`, `React component`, `FastAPI route`, `access token`, `pull request`. Private bindings содержат public manifest digest, exact one-to-one sample mapping и audio/reference SHA-256. Resolver отклоняет duplicate/missing/extra IDs, absolute/traversal/symlink/device paths и digest drift. До SDK import проверить WAV PCM/container/channels/sample rate/frame duration, UTF-8 reference size/encoding, rights/consent enums и отсутствие NUL. Existing `ru_en_terms` и full-manifest behavior сохранить.

  **Логирование:** DEBUG/INFO содержат только dataset revision, sample ID, category, duration bucket, term occurrence count и outcome code. Resolved audio/reference paths и содержимое reference никогда не логируются и не включаются в `repr`.

  **Зависимости:** задачи 1, 2 и 3.

- [x] **Задача 6: Реализовать occurrence-based coding-term metrics и воспроизводимое агрегирование**

  **Результат:** term matching учитывает token/phrase boundaries, canonical spelling, frozen variants, expected occurrences и значимые символы (`_`, `.`, `/`, `-`, `+`) без substring false positives. WER/CER/term metrics возвращают numerator, denominator, value, status и version для corpus aggregation; raw ASR отделён от punctuation-sensitive и будущего post-normalization views.

  **Файлы:** обновить `benchmarks/asr/quality_metrics.py`; создать или расширить `tests/contract/test_quality_metrics.py` и `tests/contract/test_ru_coding_terms_dataset.py`.

  **Проверка:** заморозить Unicode normalization, casefold, punctuation/symbol policy и occurrence-based denominator до run; private reference должен содержать declared expected occurrences. Покрыть multiword/repeated terms, identifiers, `C++`/`.NET`, Cyrillic transliteration mismatch, latin preservation и zero-denominator `not_applicable`. Corpus values вычислять суммированием numerators/denominators, не средним процентов. Threshold `>= 90%` применять только к заранее согласованному coding-term occurrence set; не вводить WER/RTF thresholds до измерений.

  **Логирование:** pure metric functions не логируют и не получают logger. Orchestration логирует только metric name/version, anonymous sample ID, numerator, denominator, status и numeric value. Reference, hypothesis, matched/missed terms и normalization intermediate values запрещены.

  **Зависимости:** задача 5.

- [x] **Задача 7: Уточнить SDK-neutral lifecycle contract для real warm-up и safe instrumentation**

  **Результат:** `AsrEngine` выражает actual inference warm-up на проверенном non-scored segment, typed safe failures и SDK-neutral timing/inference observer для `load_done`, `first_result`, `transcribe_done`. Контракт не содержит benchmark DTO или SDK types.

  **Файлы:** обновить `src/nadikt/domain/ports/asr.py`; создать или обновить общий conformance contract в `tests/contract/test_asr_engine_contract.py`; обновить `tests/contract/test_asr_adapter_import_boundaries.py`.

  **Проверка:** `warm_up()` принимает `AsrSegmentInput` и доказывает inference, observer получает только phase/timing data, typed failure не содержит raw SDK message, а `AsrSegmentTranscript` остаётся единственным text-bearing result type. Зафиксировать idempotent close/cancel semantics и сборку нескольких backend fragments в один segment transcript.

  **Логирование:** observer/log context содержит только engine/package/segment IDs, phase IDs, durations и safe outcome codes. Transcript, transcript length, audio path, SDK exception/traceback и object repr запрещены.

  **Зависимости:** задачи 4 и 5.

- [x] **Задача 8: Реализовать backend adapters и общий conformance suite**

  **Результат:** reusable GigaAM/faster-whisper adapters реализуют уточнённый `AsrEngine`; infrastructure больше не зависит от `benchmarks/asr`. faster-whisper принимает только verified local CTranslate2 directory, CPU INT8 и fully consumes lazy generator. GigaAM package layout привязан к pinned SDK revision, все потенциально нужные SDK files проверены до import/load, segment duration ограничен `<= 25s`.

  **Файлы:** переработать `src/nadikt/infrastructure/asr/faster_whisper.py`, `src/nadikt/infrastructure/asr/gigaam.py`; обновить `tests/contract/test_asr_engine_contract.py`, `tests/contract/test_asr_adapter_import_boundaries.py`, `tests/contract/test_faster_whisper_probe.py`, `tests/contract/test_gigaam_probe.py`.

  **Проверка:** lazy imports, local-path-only initialization, pinned concrete threads/config, readiness, real warm-up, first-result event, full transcription, cancel и idempotent close проходят общий suite. faster-whisper собирает все yielded segments в один Nadikt transcript; GigaAM получает фактическую WAV duration. Process termination остаётся окончательной гарантией освобождения native state, `close()` является обязательным best-effort lifecycle step.

  **Логирование:** DEBUG для lifecycle transitions, INFO для load/warm-up/transcribe/close durations, ERROR только с typed safe outcome. Transcript, audio/package path, SDK info/result/exception repr и backend stdout запрещены.

  **Зависимости:** задачи 3, 4 и 7.

- [x] **Задача 9: Ввести spawned worker/supervisor boundary и привязанное offline evidence**

  **Результат:** parent валидирует schemas/package/bindings, но не импортирует ASR SDK и не получает transcript/reference. Spawned worker выполняет load, warm-up, transcription и metrics; parent получает только bounded, versioned, allowlist JSON DTO. Тот же supervisor используется lifecycle probe и benchmark runner.

  **Файлы:** создать `benchmarks/asr/benchmark_worker.py`, `benchmarks/asr/worker_protocol.py`, `benchmarks/asr/worker_supervisor.py`, `benchmarks/asr/offline_supervisor.py`, `benchmarks/asr/offline_evidence.py`, `benchmarks/asr/schemas/offline_evidence.v1.schema.json`, `tests/contract/test_benchmark_worker_boundary.py`, `tests/integration/__init__.py`, `tests/integration/test_real_local_asr_load.py`; обновить `benchmarks/asr/local_model_probe.py`, `benchmarks/asr/offline_check.py`, `benchmarks/asr/probe_results.py`, `tests/contract/test_local_model_probe.py`, `tests/contract/test_offline_privacy_regression.py`, `docs/testing.md`.

  **Проверка:** использовать spawn, не fork; private paths передавать через bounded IPC, не argv/environment; не использовать pickle. Protocol включает version, nonce, max message size, timeout, terminate/kill/reap и PID/start-time identity. Offline evidence разделено на preflight default-deny/clean-cache attestation и post-run process-tree observation, связано с run nonce, Nadikt SHA, package/lock digests и monitor interval. Принимать только квалифицированный allowlisted mechanism/version; stale/unbound/self-declared evidence даёт `NOT VERIFIED`, любая network attempt даёт `FAIL`. Real PASS требует load/readiness/actual warm-up/short transcription/close/worker exit/finalized evidence; отсутствие assets/locks/evidence даёт `SKIP/NOT RUN`.

  **Логирование:** parent/worker logs используют safe IDs, nonce digest prefix, phase, PID-safe handle, counts, durations и outcomes. Transcript/reference, private paths, IPC payload, network destination, raw monitor output, environment values, backend stdout/stderr и traceback запрещены; captured backend output проходит canary audit и уничтожается.

  **Зависимости:** задачи 4, 5, 6 и 8.

<!-- Commit checkpoint: tasks 5-9 -->

### Фаза 3: Runner, controlled assets, pilot и публикация

- [x] **Задача 10: Реализовать privacy-safe benchmark CLI, result schema и worker resource sampling**

  **Результат:** benchmark CLI запускает по одному spawned candidate worker на independent cold repeat, использует coding-pilot profile/private bindings/offline supervisor и атомарно создаёт schema-validated safe result. Reference/hypothesis остаются внутри worker; parent получает только numeric metrics, timings и outcome codes.

  **Файлы:** создать `benchmarks/asr/benchmark_runner.py`, `benchmarks/asr/benchmark_results.py`, `benchmarks/asr/schemas/benchmark_result.v1.schema.json`, `benchmarks/asr/measurement_backends/linux_proc.py`, `benchmarks/asr/results/README.md`, `tests/contract/test_benchmark_runner.py`, `tests/contract/test_resource_measurement.py`; обновить `benchmarks/asr/resource_measurement.py`, `benchmarks/asr/privacy_audit.py`, `benchmarks/asr/segmentation_manifest.py`, `benchmarks/asr/__init__.py`, `.gitignore`.

  **Проверка:** зафиксировать CLI arguments для inventory, package manifest, dataset profile, private bindings, candidate, offline mechanism, repeats и output. Raw/private workspace: ignored `benchmarks/asr/runs/`; publishable aggregates: `benchmarks/asr/results/`. Recursive allowlist builder запрещает unknown fields, paths, URLs, argv/environment, hostnames, free-form SDK errors/notes и raw traceback. Раздельные canaries покрывают reference, hypothesis, paths, SDK error и bindings. Linux/WSL sampler измеряет worker process tree, CPU user/system и нормализованные percentages, RSS/peak, interval/missed samples, PID start time; `resource.getrusage()` используется только как worker-exit cross-check и импортируется безопасно на Windows. RTF берётся из фактической WAV frame duration; first-result для faster-whisper измеряется до первого yield. Определить deterministic sample/candidate order, минимум три cold repeats, percentile algorithm и concrete inference config.

  **Логирование:** verbose DEBUG только для run/candidate/sample IDs, repeat/phase и sampler status; INFO для durations/aggregates; WARN/ERROR для safe outcomes. Structured log records проходят allowlist audit. Reference/hypothesis, audio/model/dataset paths, environment/argv, backend output, free-form errors и canaries запрещены в logs, stdout/stderr и JSON.

  **Зависимости:** задачи 6 и 9.

<!-- Code-freeze checkpoint: task 10 -->

- [x] **Задача 11: Подготовить immutable model packages и coding-pilot assets вне Git**

  **Результат:** controlled storage содержит immutable packages, sidecar manifests, local inventory, legal-review records, `ru_coding_terms`, `ru_short` и non-scored warm-up WAV/reference assets с private bindings. Минимум один доступный candidate проходит real lifecycle gate; faster-whisper CTranslate2 CPU INT8 является первым практическим кандидатом, но не объявляется победителем. GigaAM добавляется только при подтверждённом `.ckpt`/tokenizer layout и approved local evaluation.

  **Пути:** `<controlled-model-root>/<package-id>/<manifest-name>`, `<controlled-model-root>/model_inventory.json`, `<controlled-dataset-root>/audio/`, `<controlled-dataset-root>/references/`, `<controlled-dataset-root>/bindings.json`, отдельные empty writable cache и offline wheelhouse; repository-facing instructions в `model_packs/README.md`, `benchmarks/asr/datasets/README.md`, `requirements/benchmark/README.md`, `docs/testing.md`.

  **Проверка:** не коммитить assets, inventories, private paths или legal documents. Зафиксировать full digests, provenance/conversion recipe, package/public profile/private bindings digests, WAV format/duration и rights/consent. Package tree сделать read-only на run, writable cache держать отдельно, digests проверить до и после lifecycle. Environment создаётся только из locks/offline wheelhouse. Real gate использует Task 9 supervisor; placeholders, example manifests и `review_required` local evaluation отклоняются. Для недоступного/запрещённого candidate сохранить `NOT AVAILABLE/NOT RUN`, не ослаблять gate.

  **Логирование:** сохранять только package/dataset IDs, revisions, checksum prefixes, evidence IDs, counts, durations и outcomes. Не логировать URLs источников, абсолютные controlled paths, reference text, hypotheses, audio metadata с персональными данными или license text.

  **Зависимости:** задачи 4, 5, 8, 9 и 10; требует доступных локальных model/audio assets и квалифицированного network-block/observation mechanism.

- [ ] **Задача 12: Выполнить coding-focused pilot на чистом reproducible SHA**

  **Результат:** на текущей i3 12-го поколения WSL2 машине выполнен `run_kind=coding_pilot` для `ru_coding_terms` и `ru_short` с real packages, finalized blocked-network evidence, quality, RTF, latency, CPU и peak RAM. Publishable safe aggregate ссылается на clean pre-run SHA Commit 3; private workspace остаётся ignored.

  **Файлы:** private ephemeral files в ignored `benchmarks/asr/runs/`; validated publishable aggregate `benchmarks/asr/results/pilot-ru-coding-<run-id>.json`; команды и preflight checklist в `docs/testing.md`.

  **Проверка:** перед запуском потребовать clean worktree и записать pre-run SHA. Выполнить dry-run, contract suite, real lifecycle integration, privacy gate и минимум три independent cold-process repeats. Artifact содержит schema/run kind, sanitized hardware/OS/kernel/Python fingerprint, lock/package/public profile/private binding digest prefixes, inference/thread config, sample/repeat counts, measurement backend и evidence status. Failed run не перезаписывает successful artifact. Неиспытанные candidates остаются `NOT RUN`, недоступные — `NOT AVAILABLE`, failed gates — `FAIL`. WSL2 pilot не закрывает Windows baseline, `long_10m`, full segmentation, installer или redistribution gates.

  **Логирование:** перед atomic publication проверить worker/parent stdout, stderr, structured logs, failure envelopes и result JSON на all canaries/unknown fields. Сохранять только safe aggregates, anonymous IDs, digest prefixes, evidence status и controlled outcomes; transcript/reference/path/backend output уничтожаются после in-memory audit.

  **Зависимости:** задачи 10 и 11; запуск только после Commit 3 и проверки clean worktree.

- [ ] **Задача 13: Опубликовать benchmark evidence и синхронизировать документацию**

  **Результат:** benchmark protocol/results явно отделяют coding pilot от full benchmark. Technical recommendation primary/fallback допускается только для минимум двух candidates с одинаковыми dataset/segmentation revisions, comparable repeats и verified offline evidence; иначе recommendation остаётся `NOT DECIDED` с точными blockers.

  **Файлы:** обновить `docs/research/local_asr_performance_benchmark_plan.md`, `docs/research/local_asr_performance_benchmark_results.md`, `docs/testing.md`, `docs/getting-started.md`, `docs/README.md`; после canonical docs синхронизировать `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` progress note и `AGENTS.md`.

  **Проверка:** переносить данные только из schema/privacy-validated Task 12 artifact. Добавить отдельные `ru_coding_terms` и `run_kind=coding_pilot`, exact revisions/config/counts и limitations. Full candidate matrix, `long_10m`, Windows acceptance, installer, release selection и незапущенные candidates не отмечать завершёнными. Обязательный docs checkpoint выполнить через `/aif-docs`, roadmap progress note — через `/aif-roadmap`; milestone не закрывать. `.ai-factory/*` и `AGENTS.md` являются context/index updates, не каноническими требованиями.

  **Логирование:** в docs публикуются только aggregates, status enums, revisions/digest prefixes, measurement/evidence IDs и limitations. Transcript examples, per-sample sensitive errors, raw paths, URLs, monitor output и free-form SDK failures запрещены.

  **Зависимости:** задача 12 и успешная schema/privacy validation aggregate artifact.

  **Ограниченный режим 2026-08-05:** publishable evidence не публикуется, потому что `offline_evidence.status=NOT VERIFIED`. Task 13 выполняется только как docs/status sync: `NOT PUBLISHED / NOT DECIDED`, без копирования private artifact в `benchmarks/asr/results/` и без final ASR recommendation.

<!-- Commit checkpoint: tasks 11-13 -->

## Session Notes 2026-08-05

- Commit `1a7539c4b3462f7b23b07a4d88d12b34eae5b433` fixed GigaAM controlled ffmpeg discovery; clean-SHA Task 11 local package probe, dataset bindings and real local ASR lifecycle passed for `gigaam-multilingual-220m` and `faster-whisper-small-int8`.
- Task 12 private measured run completed outside Git: schema v2 `coding_pilot`, exact frozen two-candidate matrix, three completed repeats per candidate, `outcome=success`, `publication_allowed=false`, blocker `offline_evidence_not_verified`.
- Operator decision: proceed with GigaAM as working candidate for the next normalization/dictionary engineering iteration, keep faster-whisper as baseline/fallback, do not publish benchmark and keep final ASR decision `NOT DECIDED`.
- Task 13 scope is limited to public docs/status synchronization in `NOT PUBLISHED / NOT DECIDED` mode. Do not update `benchmarks/asr/results/` from the private artifact.

## Критерии завершения плана

- Реальный local package как минимум одного candidate проходит validate/load/actual warm-up/short-transcribe/close/worker-exit под внешней default-deny блокировкой и полным process-tree observation.
- Missing/corrupted package завершается до worker/SDK import/load; stale, self-declared или incomplete evidence не получает PASS.
- Package/inventory schemas разделяют immutable metadata и local binding, имеют explicit trust anchor, compatibility и независимые legal gate statuses.
- `coding_pilot` имеет замороженные public revisions, private binding digests, verified WAV/reference assets и occurrence-based term metrics.
- Parent process не импортирует ASR SDK и не получает transcript/reference; worker IPC/result/log schemas являются bounded и allowlist-only.
- Benchmark environment воспроизводим из pinned locks/offline wheelhouse; artifact ссылается на clean pre-run SHA и exact lock/package/dataset revisions.
- Первый pilot публикует quality, RTF, first-result latency, CPU и peak worker/process-tree RAM без audio/reference/hypothesis/path payload.
- Все contract tests проходят; opt-in integration tests честно различают `PASS`, `FAIL`, `NOT AVAILABLE` и `NOT RUN`.
- Канонические docs описывают delivery policy и coding pilot; Windows, `long_10m`, full segmentation, installer, redistribution и release-selection gates остаются открытыми.
