# План реализации: GigaAM Coding Terms Normalization And Dictionary Spike

Ветка: feature/gigaam-coding-terms-normalization-dictionary
Создано: 2026-08-05

## Original Request
GigaAM coding terms normalization and dictionary spike

## Настройки
- Testing: yes
- Logging: verbose
- Docs: yes

## Привязка к roadmap
Milestone: "Квалификация критических технических рисков"
Rationale: Spike проверяет ASR/coding-term risk area, GigaAM local behavior, benchmark scoring separation и privacy/offline gates до выбора MVP ASR path.

## Исследовательский контекст
Source: .ai-factory/RESEARCH.md (Active Summary, Updated: 2026-08-03 10:08, SHA256: 893b79d40fa6b54ffe6a5ded5d75814a9c03d4b9388a0f37e1027ac1b2df750f)

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

## План коммитов
- **Commit 1** (после tasks 1-3): "feat: define coding term dictionary spike core"
- **Commit 2** (после tasks 4-7): "feat: harden coding term benchmark metadata"
- **Commit 3** (после tasks 8-11): "test: cover coding term normalization gates"
- **Commit 4** (после tasks 12-13): "test: verify schema privacy and offline gates"
- **Commit 5** (после tasks 14-15): "docs: document coding term spike constraints"

## Задачи

### Phase 1: Границы spike и переносимое domain-ядро
- [x] Task 1: Зафиксировать scope spike, policy IDs и privacy-safe generic модель правил для coding-term normalization.
  Deliverable: Добавить небольшой pure-domain модуль `src/nadikt/domain/text/coding_terms.py` с immutable rule/policy dataclasses или value objects для generic matching mechanics и `coding-term-dictionary-spike-v1`; модуль должен оставаться SDK-neutral, SQLite-free, Qt-free, stdlib-only и независимым от GigaAM internals.
  Expected behavior: Domain содержит только generic rule/value objects, validation results и matching semantics; public benchmark mappings остаются в `benchmarks/asr/coding_term_normalization.py` или benchmark-only adapter и не становятся production user dictionary data. Policy ownership явно разделён: raw scoring normalization policy `asr-raw-punctuation-insensitive-v1`, benchmark post-ASR coding-term policy `coding-term-normalization-ru-pronunciation-v1`, domain dictionary spike policy `coding-term-dictionary-spike-v1`.
  Files: `src/nadikt/domain/text/coding_terms.py`, `src/nadikt/domain/text/__init__.py`.
  Logging requirements: Domain code не логирует raw input, output, dictionary entries, variants, transcripts или user text; dataclasses/exceptions/diagnostics используют `repr=False`, safe `__repr__`, safe exception messages и возвращают только safe policy ID, rule count, conflict count и reason codes для application/infrastructure callers на DEBUG/INFO.
  Dependencies: none.

- [x] Task 2: Реализовать deterministic portable text normalization для public coding-term variants.
  Deliverable: Добавить pure function или небольшой service в `src/nadikt/domain/text/normalization.py`, который применяет explicit replacement rules через stdlib-only implementation (`re`, `unicodedata`, `dataclasses`) с boundary-safe matching и deterministic ordering.
  Expected behavior: Реализовать NFKC/casefold comparison, deterministic longest-span/overlap resolution, idempotency, punctuation adjacency, underscore/slash/hyphen boundaries и no substring false positives; покрыть coding cases вроде `C++`, `.NET`, `C#`, `CI/CD`, `Node.js` и identifiers. Public examples вроде `пайтест`, `докер компоуз`, `реакт компонент`, `фаст апи роут`, `аксес токен` и `пул реквест` используются только через benchmark adapter/rules, не как hard-coded production dictionary.
  Files: `src/nadikt/domain/text/normalization.py`, `src/nadikt/domain/text/coding_terms.py`.
  Logging requirements: Не логировать source text, normalized text, matched terms или replacement payload; optional safe diagnostics допускают только counts by reason code и policy ID на DEBUG без payload leakage.
  Dependencies: Task 1.

- [x] Task 3: Добавить минимальный engine-independent dictionary facade для spike.
  Deliverable: Добавить `src/nadikt/domain/text/dictionary.py` с in-memory dictionary/rule set abstraction, который позже можно заменить SQLite-backed storage без изменения normalization semantics.
  Expected behavior: Поддержать caller-provided replacement rules как data, предсказуемо валидировать duplicate/conflicting rules и не реализовывать persistence в этом spike. Конфликты определены как duplicate rule IDs, NFKC/casefold duplicate source variants mapping to different canonicals, empty variants, canonical without Latin when `require_latin=true`, ambiguous direction и replacement cycles.
  Files: `src/nadikt/domain/text/dictionary.py`, `src/nadikt/domain/text/__init__.py`.
  Logging requirements: Validation diagnostics могут возвращать rule counts, conflict counts и bounded reason codes на DEBUG/INFO; dataclasses/exceptions/diagnostics используют `repr=False` или safe `__repr__`; нельзя логировать dictionary entries, spoken variants, canonical terms, raw text или exception strings с payload.
  Dependencies: Task 1.

### Phase 2: Benchmark integration без маскировки raw ASR quality
- [x] Task 4: Связать benchmark-only normalization с domain spike, сохранив raw-vs-normalized separation.
  Deliverable: Обновить `benchmarks/asr/coding_term_normalization.py`, чтобы existing benchmark-only scoring view использовал shared deterministic matching behavior или equivalent adapter, не превращая benchmark code в production dictionary storage.
  Expected behavior: Сохранить `DEFAULT_NORMALIZATION_POLICY_ID = "coding-term-normalization-ru-pronunciation-v1"`, текущие public replacements, current metric names и отдельные raw ASR metrics/normalized diagnostics в `quality_metrics.py`, `benchmark_worker.py` и benchmark results. Не менять `run_profiles/coding_pilot.v1.json` raw `normalization_policy_id` на dictionary policy ID.
  Files: `benchmarks/asr/coding_term_normalization.py`, `benchmarks/asr/quality_metrics.py` if needed.
  Logging requirements: Benchmark helpers не логируют hypothesis, reference, normalized text, user dictionary entries или matched term payload; разрешены только safe metric names, policy IDs, counts, sample IDs и reason codes на DEBUG/INFO.
  Dependencies: Tasks 1-3.

- [x] Task 5: Расширить public coding-term dataset metadata для GigaAM-oriented triage без private transcripts.
  Deliverable: Расширить `benchmarks/asr/datasets/ru_coding_terms.v1.json` и при необходимости `benchmarks/asr/datasets/coding_pilot.v1.json` дополнительными safe `expected_coding_terms` records для library names, commands, identifiers, abbreviations и mixed technical terms.
  Expected behavior: Public manifests содержат только stable sample IDs, categories, expected term metadata, accepted variants, occurrence counts и safe labels; raw audio/reference transcripts остаются вне Git. Cyrillic spoken replacement variants не добавляются в raw `expected_coding_terms.accepted_variants` для `require_latin=true`; они принадлежат benchmark normalization policy/domain rules, иначе raw metrics будут маскировать ASR misses.
  Files: `benchmarks/asr/datasets/ru_coding_terms.v1.json`, `benchmarks/asr/datasets/coding_pilot.v1.json`, `benchmarks/asr/datasets/README.md` if metadata rules change.
  Logging requirements: Dataset validation output может логировать sample IDs, category, term record counts и validation reason codes; нельзя логировать private paths, reference text, hypotheses или sensitive term payload из controlled storage.
  Dependencies: Task 4.

- [x] Task 6: Усилить validation для privacy-safe `expected_coding_terms` metadata.
  Deliverable: Обновить `_validate_expected_coding_terms()` и связанные tests, чтобы rich term records имели allowlist keys и не могли содержать unsafe public metadata.
  Expected behavior: Validator отклоняет unknown fields, empty/duplicate `term_id`, malformed variants, absolute paths, URLs, credential markers, transcript/reference/hypothesis markers и user-specific dictionary payload; `expected_english_terms` sync с rich records явно определён и покрыт тестами.
  Files: `benchmarks/asr/manifests.py`, `benchmarks/asr/datasets/README.md`, `tests/contract/test_ru_coding_terms_dataset.py`, `tests/contract/test_asr_benchmark_harness.py` if relevant.
  Logging requirements: Validation logs и errors содержат только sample index/ID, term index, bounded reason codes и counts; не включать canonical/variant text, private paths, URLs, tokens или transcript-like payload.
  Dependencies: Task 5.

- [x] Task 7: Добавить dataset/run-profile/private-bindings consistency gate.
  Deliverable: Зафиксировать и протестировать, как изменения `coding_pilot.v1.json`/`ru_coding_terms.v1.json` влияют на dataset revision, `run_profiles/coding_pilot.v1.json`, expected durations и private bindings digest.
  Expected behavior: Если добавляются samples или меняются durations, intentionally обновить dataset revision, `expected_sample_durations`, preflight tests и private binding instructions; если меняется только term metadata без audio/reference changes, явно зафиксировать revision policy. Real benchmark runs считаются invalid, пока controlled private bindings/audio/reference storage вне Git не синхронизированы с public manifest digest.
  Files: `benchmarks/asr/datasets/coding_pilot.v1.json`, `benchmarks/asr/datasets/ru_coding_terms.v1.json`, `benchmarks/asr/run_profiles/coding_pilot.v1.json`, `benchmarks/asr/datasets/README.md`, `tests/contract/test_ru_coding_terms_dataset.py`, `tests/contract/test_benchmark_runner.py` if run profile changes.
  Logging requirements: Consistency checks логируют только dataset ID/revision, sample IDs, duration counts, digest status и bounded reason codes; без private paths, reference text, hypotheses или term payload.
  Dependencies: Tasks 5-6.

- [x] Task 8: Подтвердить candidate-neutral normalized diagnostic view и schema-compatible output.
  Deliverable: Проверить, что existing candidate-neutral normalized view в `benchmark_worker.py` и `quality_metrics.py` достаточен для spike; не добавлять GigaAM-only scoring, кроме private non-comparable triage с явным docs warning.
  Expected behavior: Raw metrics остаются primary ASR comparison; normalized metrics маркируются как post-ASR dictionary/normalization diagnostics и не могут выбрать GigaAM без offline evidence и full benchmark results. Если result/DTO shape не меняется, явно оставить `worker_protocol.py`, `benchmark_runner.py`, `benchmark_results.py` и `benchmark_result.v2.schema.json` без новых fields; если новый shape genuinely required, создать новую schema version вместо mutation v2.
  Files: `benchmarks/asr/benchmark_worker.py`, `benchmarks/asr/quality_metrics.py`, `benchmarks/asr/worker_protocol.py`, `benchmarks/asr/benchmark_runner.py`, `benchmarks/asr/benchmark_results.py`, `benchmarks/asr/schemas/benchmark_result.v2.schema.json`, `tests/contract/test_benchmark_worker_boundary.py`, `tests/contract/test_benchmark_runner.py` if output shape changes.
  Logging requirements: Worker/supervisor logs включают только candidate ID, sample ID, view name, metric names, numerators/denominators, policy ID и bounded reason codes на DEBUG/INFO; без transcripts, hypotheses, references, normalized text, backend stdout/stderr, private paths или raw exceptions.
  Dependencies: Tasks 4-5.

### Phase 3: Automated tests и privacy gates
- [x] Task 9: Добавить unit tests для deterministic domain normalization и dictionary conflict handling.
  Deliverable: Создать `tests/unit/__init__.py`, `tests/unit/test_text_normalization.py` и `tests/unit/test_text_dictionary.py` в текущем `unittest` style с existing `src` path setup.
  Expected behavior: Тесты покрывают boundary-safe replacement, NFKC/casefold, deterministic longest/ordered matching, overlap resolution, idempotency, conflict rejection/reason codes, Latin-preservation rules, no substring false positives, coding symbols/identifiers и отсутствие sensitive payload в `repr`/diagnostics.
  Files: `tests/unit/__init__.py`, `tests/unit/test_text_normalization.py`, `tests/unit/test_text_dictionary.py`.
  Logging requirements: Test logs/assertions не должны печатать full input/output phrases при проверке payload safety; использовать synthetic public tokens умеренно и проверять safe reason codes/counts.
  Dependencies: Tasks 1-3.

- [x] Task 10: Расширить import-boundary и dependency-boundary tests для `domain/text`.
  Deliverable: Обновить `tests/contract/test_asr_adapter_import_boundaries.py` или добавить отдельный boundary test для всех `src/nadikt/domain/text/*.py`.
  Expected behavior: Tests подтверждают, что `domain/text` не импортирует `benchmarks.asr`, `nadikt.infrastructure`, `sqlite3`, PySide6, GigaAM, faster-whisper, ASR SDKs или non-stdlib dependencies; benchmark adapter может импортировать domain mechanics, но domain не импортирует benchmark code.
  Files: `tests/contract/test_asr_adapter_import_boundaries.py`, `src/nadikt/domain/text/*.py`.
  Logging requirements: Boundary tests не печатают source snippets с payload; failure messages используют только file path, forbidden import token и bounded reason code.
  Dependencies: Tasks 1-3.

- [x] Task 11: Расширить benchmark contract tests для normalized scoring separation, schema compatibility и dataset metadata completeness.
  Deliverable: Обновить contract tests, чтобы raw metrics, normalized metrics и coding-term dataset records оставались валидными после spike.
  Expected behavior: Existing raw `coding_term_accuracy`, `english_term_accuracy` и `latin_preservation_rate` не меняются; normalized metrics получают explicit version/policy coverage; dataset tests отклоняют malformed term records без payload exposure; emitted v2 aggregate валидируется против `benchmark_result.v2.schema.json` и `benchmark_results.validate_result_payload` без in-place schema mutation.
  Files: `tests/contract/test_quality_metrics.py`, `tests/contract/test_ru_coding_terms_dataset.py`, `tests/contract/test_benchmark_worker_boundary.py`, `tests/contract/test_benchmark_runner.py`, `benchmarks/asr/schemas/benchmark_result.v2.schema.json` read-only unless new schema version is explicitly introduced.
  Logging requirements: Contract tests должны assert только safe JSON/diagnostic fields и не печатать transcript, hypothesis, reference, private path или dictionary payload в failure messages.
  Dependencies: Tasks 4-8.

- [x] Task 12: Автоматизировать privacy audit для dictionary/normalization leakage risks.
  Deliverable: Добавить или расширить tests around `benchmarks/asr/privacy_audit.py`, worker/supervisor output и domain diagnostics с canaries для raw text, normalized text, dictionary canonical terms, spoken variants, private paths, backend stderr/stdout и exception strings.
  Expected behavior: Generated benchmark/result artifacts fail on `audit.has_violation` when forbidden payload appears; domain validation diagnostics and exceptions expose only reason codes/counts, not payload; worker JSON не сериализует domain rule objects, `QualityMetricResult.to_json()` payload variants или raw normalized text.
  Files: `benchmarks/asr/privacy_audit.py` if rules need extension, `tests/contract/test_offline_privacy_regression.py`, `tests/contract/test_worker_supervisor.py`, `tests/contract/test_benchmark_worker_boundary.py`, `tests/unit/test_text_dictionary.py`.
  Logging requirements: Privacy tests могут использовать synthetic canaries but must not print them on success/failure; failure output contains only violation counts, safe marker IDs и bounded reason codes.
  Dependencies: Tasks 1-11.

- [x] Task 13: Запустить automated verification commands, schema/privacy gates и исправить regressions.
  Deliverable: Выполнить `python3 -B -m unittest discover -s tests`, `python3 -m benchmarks.asr.dry_run --dataset benchmarks/asr/datasets/dataset.example.json --models model_packs/model_inventory.example.json`, `python3 -m benchmarks.asr.local_model_probe --models model_packs/model_inventory.example.json --dry-run --offline-required` и dry-run/preflight для `coding_pilot.v1.json` если controlled config доступен вне Git.
  Expected behavior: Все existing tests проходят; new tests проходят; benchmark dry-run остаётся offline и не импортирует real ASR SDKs без явной конфигурации; local model probe records offline-required state; real GigaAM package runs остаются opt-in через private assets. Если план или docs полагаются на `NADIKT_BENCHMARK_OFFLINE_REQUIRED` в `dry_run.py`, reconciliate behavior: либо implement/test marker, либо исправить docs/plan wording.
  Files: no source file required unless fixes are needed.
  Logging requirements: Verification output проверить на отсутствие audio, transcript, reference, hypothesis, normalized text payload, dictionary entries, private paths, URLs, tokens и backend raw stderr/stdout; сохранять только safe IDs, counts, statuses и reason codes.
  Dependencies: Tasks 9-12.

### Phase 4: Documentation и границы решений
- [x] Task 14: Обновить requirements, benchmark docs и testing docs с описанием spike boundary.
  Deliverable: Задокументировать, что spike является engine-independent post-ASR normalization/dictionary work с GigaAM как candidate diagnostic path, а не final ASR decision.
  Expected behavior: Docs объясняют raw-vs-normalized metric separation, deterministic rule ordering, accepted variants, safe coding-term metadata, dataset/run-profile/private-bindings revision policy, offline/runtime constraints, publication gate и запрет логирования user dictionary payload. Documentation ownership разделён: product requirements фиксируют engine-independent dictionary/normalization behavior, research docs фиксируют spike/benchmark interpretation, dataset README фиксирует manifest privacy rules, testing docs фиксируют commands и controlled asset gates.
  Files: `docs/requirements/Nadikt_TZ_v0.2.md`, `docs/requirements/Nadikt_multilingual_ASR_requirements.md`, `docs/research/local_asr_performance_benchmark_plan.md`, `docs/testing.md`, `benchmarks/asr/datasets/README.md`, `benchmarks/asr/results/README.md`.
  Logging requirements: Documentation examples не должны использовать realistic private user phrases и не должны рекомендовать logging raw transcripts, dictionary entries, clipboard text, private paths, URLs, tokens или backend stdout/stderr.
  Dependencies: Tasks 1-13.

- [x] Task 15: Обновить benchmark results template, offline prototype notes и repository map только safe status language.
  Deliverable: Если implementation меняет measured views, lifecycle assumptions или создаёт real `src/nadikt/domain/text/` package, обновить `docs/research/local_asr_performance_benchmark_results.md`, `docs/research/local_asr_offline_package_prototype.md`, `AGENTS.md` и при необходимости `.ai-factory/ARCHITECTURE.md`/`docs/README.md`.
  Expected behavior: Сохранить ASR decision status `NOT DECIDED`, пока нет publishable evidence; фиксировать blockers вроде `offline_evidence_not_verified` или missing real package evidence как status, а не как model-quality conclusions. Ничего не копировать в `benchmarks/asr/results/` как publishable result без schema v2, exact matrix, clean revision, privacy audit clean и `offline_evidence.status=PASS`; private diagnostic runs сохраняют `publication_allowed=false`.
  Files: `docs/research/local_asr_performance_benchmark_results.md`, `docs/research/local_asr_offline_package_prototype.md`, `AGENTS.md`, `.ai-factory/ARCHITECTURE.md` if implemented structure changes, `docs/README.md` only if new public doc is added.
  Logging requirements: Docs/results включают только safe IDs, categories, metric names, numerator/denominator counts, status и bounded reason codes; без transcript, reference, hypothesis, coding-term snippets, private paths, URLs, tokens или raw backend output.
  Dependencies: Tasks 13-14.
