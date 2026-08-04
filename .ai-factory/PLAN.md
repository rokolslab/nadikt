# План реализации: ASR coding terms quality triage и normalization pilot

Branch: main
Created: 2026-08-04

## Original Request

ASR coding terms quality triage and normalization pilot

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage

Milestone: "Квалификация критических технических рисков"
Rationale: План закрывает риск качества ASR для русской диктовки с coding terms перед выбором primary/fallback модели и перед переходом к UI/vertical slice.

## Research Context

Source: `.ai-factory/RESEARCH.md` (Active Summary, Updated: 2026-08-03 10:08, SHA256: 893b79d40fa6b54ffe6a5ded5d75814a9c03d4b9388a0f37e1027ac1b2df750f)

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

## Границы и критерии готовности

- Цель плана - выяснить, почему `coding_term_accuracy`, `english_term_accuracy` и `latin_preservation_rate` равны `0.0`, отделив `not_applicable`/zero-denominator от настоящего zero-match, и измерить raw ASR отдельно от post-ASR normalization.
- Не выбирать GigaAM или faster-whisper победителем в рамках этого плана; итогом является evidence для следующего decision gate.
- Frozen coding pilot остаётся `gigaam-multilingual-220m` + `faster-whisper-small-int8`, profile `coding-pilot-v1`, scored categories `ru_short` и `ru_coding_terms`, minimum `3` repeats.
- Private audio, reference, hypothesis, transcript, bindings, model paths и raw backend output остаются только в controlled storage вне Git.
- Любой triage artifact в `/home/oitroot/nadikt-controlled` должен быть privacy-safe: только IDs, metric names, denominator/numerator counts, category/outcome codes, durations и digest prefixes.
- Publishable `benchmarks/asr/results/` не обновлять, пока нет schema v2 aggregate, exact two-candidate matrix, clean SHA, privacy audit и `offline_evidence.status=PASS`.
- В рамках этого плана допустимо оставить rerun private-only. Если schema v2 emission или qualified offline evidence не готовы, publication gate должен явно вернуть `publication_allowed:false`/`BLOCKED`, а не публиковать partial result.
- Raw ASR metrics, normalized metrics и будущий user dictionary/postprocessing не смешивать: raw означает “без post-ASR coding-term normalization”, а не byte-for-byte scoring; каждый view должен иметь явный metric name или policy ID.

## Tasks

### Фаза 1: Triage scoring и dataset assumptions

- [x] **Task 1: Зафиксировать privacy-safe triage protocol и denominator/status gate для coding terms.** Уточнить в `docs/testing.md` и при необходимости в `docs/research/local_asr_performance_benchmark_plan.md`, как выполняется controlled inspection zero-metrics case: кто читает private reference/hypothesis, где остаётся private scratch, какие aggregate fields можно выносить в repo-facing status. До любой интерпретации `0.0` проверить `status`, `numerator`, `denominator`, `sample_measurements`, `applicable_measurements`, `not_applicable_measurements` и `completeness_status` из `benchmarks/asr/benchmark_runner.py`, чтобы отделить `not_applicable`/zero-denominator от настоящего zero-match. Проверить, что `docs/research/local_asr_performance_benchmark_results.md` продолжает явно запрещать выбор модели по непубликуемому run. Логирование: в документах разрешить только `run_id`, `candidate_id`, `sample_id`, `category`, `metric_name`, `numerator`, `denominator`, `status`, `reason_code`; запретить transcript/reference/hypothesis snippets даже в DEBUG.

- [x] **Task 2: Выполнить controlled private zero-metrics inspection и сохранить только safe counts.** В `/home/oitroot/nadikt-controlled` разобрать фактические private reference/hypothesis для последнего measured coding pilot без копирования payload в Git: классифицировать по `sample_id`, `candidate_id`, `metric_name` и reason codes `not_applicable`, `exact_latin_match`, `accepted_variant_match`, `latin_missing`, `variant_missing`, `occurrence_shortfall`, `asr_omission`, `metric_mismatch`. Итоговый private scratch остаётся вне Git; repo-facing вывод допускает только aggregate counts и blocker codes. Если inspection показывает, что `0.0` вызвано denominator/status semantics или scoring mismatch, не проектировать normalizer до исправления scoring. Логирование: controlled script/manual notes не выводят terms, reference/hypothesis snippets, private paths или backend stdout; только IDs, counts, status и reason codes. Зависит от Task 1.

- [x] **Task 3: Усилить contract tests для текущих term metrics перед изменением поведения.** Расширить `tests/contract/test_quality_metrics.py` кейсами для `coding_term_accuracy`, `english_term_accuracy` и `latin_preservation_rate`: `FastAPI route`, `Fast API route`, `docker compose`/`docker-compose`, `React component`, `access token`, `pull request`, `C++`, `.NET`, repeated occurrences, punctuation adjacency, Cyrillic false positives при `require_latin=true`, collision двух accepted variants на один occurrence и недопустимый overcount. Менять `benchmarks/asr/quality_metrics.py` только если тест выявляет defect scoring logic, а не реальную ошибку ASR. Логирование: metric helpers остаются pure и ничего не логируют; tests не печатают private text, только synthetic fixtures.

- [x] **Task 4: Исправить source-of-truth для English/Latin occurrence metrics.** В `benchmarks/asr/quality_metrics.py` определить, что `english_term_accuracy` и `latin_preservation_rate` в coding pilot используют rich `expected_coding_terms` records там, где доступны `accepted_variants`, `expected_occurrences` и `require_latin`, а plain `expected_english_terms` остаётся только fallback для legacy/simple manifests. Обновить `benchmarks/asr/benchmark_worker.py`, чтобы per-sample metrics не теряли variants/occurrences, и покрыть behavior в `tests/contract/test_quality_metrics.py` и `tests/contract/test_benchmark_worker_boundary.py`. Логирование: не логировать canonical/variant strings из private run; safe output содержит только metric names, numerators, denominators, status и version. Зависит от Tasks 2-3.

- [x] **Task 5: Добавить privacy-safe failure taxonomy и persistable sample diagnostics.** В `benchmarks/asr/quality_metrics.py` или отдельном benchmark-only модуле реализовать bounded diagnostics, которые классифицируют failures без вывода текста: `exact_latin_match`, `accepted_variant_match`, `latin_missing`, `variant_missing`, `occurrence_shortfall`, `not_applicable`. В `benchmarks/asr/worker_protocol.py`, `benchmark_worker.py`, `benchmark_runner.py`, `benchmark_results.py`, `privacy_audit.py` и при необходимости `benchmarks/asr/schemas/benchmark_result.v2.schema.json` добавить только allowlisted safe shape для per-sample/repeat diagnostic rows: `sample_id`, `category`, `metric_name`, `view`, `status`, `numerator`, `denominator`, `reason_code`, `count`. Предпочесть encoded metric names / fixed reason-code counts; не добавлять произвольные nested payloads. Покрыть `tests/contract/test_quality_metrics.py`, `tests/contract/test_benchmark_worker_boundary.py`, `tests/contract/test_benchmark_runner.py` и privacy canaries. Логирование: DEBUG допускает только taxonomy code и counts; canonical terms, variants, hypothesis tokens и reference tokens не логировать. Зависит от Task 4.

### Фаза 2: Raw vs normalized scoring

- [ ] **Task 6: Ввести экспериментальный post-ASR normalization view без подмены raw ASR.** Добавить benchmark-only normalization policy для фактически подтверждённых coding-term ошибок из Task 2, например кириллические произносительные формы и space/hyphen/case variants, в `benchmarks/asr/quality_metrics.py` или новом `benchmarks/asr/coding_term_normalization.py`. Не создавать production user dictionary API в этом плане. Raw view означает “текущая punctuation-insensitive token scoring без post-ASR coding-term normalization”; existing metric names остаются raw canonical names, а normalized variants получают явные suffixes вроде `coding_term_accuracy_normalized`, `english_term_accuracy_normalized`, `latin_preservation_rate_normalized` либо safe `scoring_view` field после allowlist/schema update. Метрики должны ссылаться на явный `normalization_policy_id`/metric version и не смешиваться с user dictionary. Логирование: normalizer не логирует input/output text; safe context содержит только `normalization_policy_id`, `view`, counts и status. Зависит от Tasks 2 и 5.

- [ ] **Task 7: Подключить raw и normalized scoring views в worker/runner aggregation.** Обновить `benchmarks/asr/benchmark_worker.py`, `benchmarks/asr/worker_protocol.py`, `benchmarks/asr/benchmark_runner.py`, `benchmarks/asr/benchmark_results.py` и при необходимости `benchmarks/asr/schemas/benchmark_result.v2.schema.json`, чтобы worker вычислял raw и normalized metrics внутри private process, а parent получал только numeric safe DTO. Aggregate logic должна по-прежнему суммировать numerators/denominators, не усреднять проценты, и сохранять category keys без ambiguity; `metric_name.split(":")` logic в `benchmark_runner.py` не должен ломаться при suffixes/views. Privacy audit должен использовать `audit.has_violation`, а не только `canary_present`/`forbidden_payload_count`, чтобы private paths, credentials и raw exceptions тоже блокировали output. Покрыть `tests/contract/test_benchmark_worker_boundary.py`, `tests/contract/test_benchmark_runner.py`, `tests/contract/test_worker_supervisor.py` и `tests/contract/test_offline_privacy_regression.py`. Логирование: parent/worker logs - только IDs, metric names/views, counts, durations, outcome codes; stdout/stderr с private payload должен приводить к privacy failure. Зависит от Task 6.

- [ ] **Task 8: Зафиксировать publication gate для schema v2 и offline evidence без ложного PASS.** Обновить `benchmarks/asr/benchmark_results.py`, `benchmark_runner.py`, result schema tests и docs так, чтобы publishable coding-pilot был возможен только при schema v2 payload, `validity`, exact matrix, clean SHA, privacy audit `has_violation=false` и `offline_evidence.status=PASS`. Если текущий runner продолжает писать schema v1 или top-level `NOT VERIFIED`, rerun остаётся private-only с `publication_allowed:false` и blocker `schema_v2_not_emitted` или `offline_evidence_not_verified`. Не подделывать PASS и не копировать private output в `benchmarks/asr/results/`. Логирование: только publication gate outcome, schema version, evidence status, blocker codes и safe IDs. Зависит от Task 7.

### Фаза 3: Controlled rerun и documentation checkpoint

- [ ] **Task 9: Выполнить manual controlled coding pilot rerun и зафиксировать decision evidence без публикации при blockers.** В `/home/oitroot/nadikt-controlled` запустить exact two-candidate pilot на clean SHA, с текущими local packages и qualified offline monitor если доступен; если monitor или schema v2 emission всё ещё недоступны, сохранить result как private/non-publishable и явно указать blockers `offline_evidence_not_verified`/`schema_v2_not_emitted`. Сравнить raw vs normalized aggregates для `ru_short` и `ru_coding_terms`, отдельно отметить speed/RAM только как secondary signal. Code completion не блокируется отсутствием private assets или monitor; это manual verification gate. Обновить `docs/research/local_asr_performance_benchmark_results.md` только если результат publishable; иначе обновить repo docs минимально: текущий public status остаётся `BLOCKED / NOT PUBLISHED`, а next-step blocker описан без metric payload, reference/hypothesis и private paths. Проверка: `python3 -B -m unittest tests.contract.test_quality_metrics tests.contract.test_benchmark_worker_boundary tests.contract.test_benchmark_runner tests.contract.test_worker_supervisor tests.contract.test_offline_privacy_regression`. Логирование: run output и status содержат только safe aggregates, `offline_evidence.status`, `publication_allowed`, candidate IDs, counts и digest prefixes. Зависит от Task 8.

## Commit Plan

- **Commit 1:** `test(asr-benchmark): cover coding term scoring edge cases` после Tasks 1-5.
- **Commit 2:** `feat(asr-benchmark): add raw and normalized term metrics` после Tasks 6-8.
- **Commit 3:** `docs(asr-benchmark): record coding terms triage gate` после Task 9, только если менялись repo docs/results.
