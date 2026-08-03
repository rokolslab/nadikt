# План реализации: реальный ASR coding-pilot с локальными model packages

Branch: main
Created: 2026-08-03

## Original Request

run real coding-pilot ASR benchmark with local model packages and validate CPU/RSS/RTF/quality results

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage

Milestone: "Квалификация критических технических рисков"
Rationale: Реальный сопоставимый CPU-only pilot GigaAM и faster-whisper проверяет основной ASR-риск до реализации vertical slice.

## Границы и критерии готовности

- Scope ограничен профилем `coding_pilot`: отдельный non-scored warm-up, `ru_short` и `ru_coding_terms`. Полный `long_10m`, segmentation acceptance, Windows baseline и выбор релизной модели остаются вне этого плана.
- Frozen pair для `coding-pilot-v1`: `gigaam-multilingual-220m` и `faster-whisper-small-int8`. Missing, extra, duplicate или substituted candidate делает matrix неполной.
- Для каждого кандидата выполняются не менее трёх независимых repeat с одинаковыми dataset revision, scoring/metric policy и thread limits; backend-specific inference settings и execution profiles публикуются явно.
- Warm-up audio не участвует в quality и RTF. Модель загружается один раз на repeat, прогревается отдельным sample и затем обрабатывает scored corpus, чтобы отделить cold load от steady-state inference.
- Результат содержит phase-aware average/max CPU и `sampled_peak_process_tree_rss_mib` для lifecycle и inference, cold load/warm-up durations, corpus RTF `sum(inference time) / sum(audio duration)`, per-repeat distribution, median/nearest-rank p95 sample RTF, WER, CER, coding-term accuracy и Latin preservation с числителями/знаменателями.
- Run validity и model quality разделены: плохие WER/CER/RTF являются измеренным результатом, а не поводом скрыть валидный run; неполная matrix, evidence, schema, privacy или denominators делают run непубликуемым.
- Publishable JSON создаётся только из private run workspace после schema v2, finite-number, offline и privacy validation; аудио, reference, hypothesis, private paths, credentials, raw backend output и raw network evidence в Git не попадают.
- Если любой package, hash-locked environment, право на local evaluation, controlled dataset или qualified offline mechanism не готов, execution фиксирует blocker без placeholder metrics и без ослабления matrix.
- Pilot не объявляет победителя ASR и не закрывает полный milestone без long-dictation, Windows и license/package follow-up.

## Commit Plan

- **Commit 1** (после Tasks 0-3): `feat(asr-benchmark): define coding pilot contracts`
- **Commit 2** (после Tasks 4-8): `feat(asr-benchmark): measure validated offline runs`
- **Commit 3** (после Tasks 9-10): `test(asr-benchmark): qualify real coding pilot workflow`
- **Clean-SHA checkpoint:** Tasks 11-12 выполняются только на clean Commit 3 SHA.
- **Commit 4** (после Tasks 11-12): `docs(asr-benchmark): publish validated coding pilot results`

## Tasks

### Фаза 1: Prerequisites и contracts

- [x] **Task 0: Зафиксировать readiness contract и исполнимую environment strategy.** Обновить `requirements/benchmark/README.md`, backend lock recipes и benchmark docs: frozen pair равна `gigaam-multilingual-220m` + `faster-whisper-small-int8`; использовать отдельные per-candidate interpreter profiles с полными transitive hash locks без `REVIEW_REQUIRED`, зафиксированными Python/platform ABI и offline wheelhouse verification; выбрать и квалифицировать WSL2 network enforcement/observation profile. Проверить наличие approved private packages/dataset как external readiness gate. Классифицировать `benchmarks/asr/results/pilot-ru-coding-20260803T121525Z.json` как schema-invalid legacy evidence и убрать его из publishable results, сохранив только явно маркированную sanitized historical fixture при необходимости regression test. Логировать только profile IDs, digest prefixes и readiness outcome; private paths, package provenance и lock source URL не логировать.

- [x] **Task 1: Ввести versioned `coding-pilot-v1` run profile и fail-closed matrix preflight.** Добавить отдельный run-profile manifest/schema в `benchmarks/asr/`, не перегружая dataset manifest environment-настройками; обновить `benchmarks/asr/benchmark_runner.py` и `benchmarks/asr/manifests.py`. Profile фиксирует exact ordered pair, `repeats>=3`, public dataset revision, отдельный non-scored warm-up, обязательные `ru_short`/`ru_coding_terms`, scoring/normalization/metric/percentile/thread policy IDs и per-candidate launcher profile. CLI и Python API одинаково отклоняют empty/missing/extra/duplicate/unknown candidates и duration drift за установленным tolerance; result сохраняет requested/effective settings. Логировать безопасные IDs, revisions, counts и structured preflight outcomes. Зависит от Task 0.

- [x] **Task 2: Определить typed worker protocol и benchmark result v2 до изменения lifecycle.** Переработать `benchmarks/asr/worker_protocol.py`, `benchmarks/asr/benchmark_results.py` и добавить immutable `benchmarks/asr/schemas/benchmark_result.v2.schema.json`: repeat request содержит отдельный warm-up и ordered scored samples с anonymous ID/category/scored flag; result содержит typed phase/sample/repeat outcomes, metric versions и safe identity без arbitrary nested mappings. Раздельно валидировать request/result schema versions, required/allowed keys, enums, nonce, finite values и `allow_nan=False`; неизвестная версия завершается fail-closed. Сохранить v1 schema неизменной и добавить version dispatch. Логировать только protocol/schema versions и validation outcomes. Зависит от Task 1.

- [x] **Task 3: Усилить trusted package identity, integrity и compatibility gate.** Обновить `benchmarks/asr/manifests.py`, `benchmarks/asr/package_integrity.py`, package schemas/examples и runner preflight: принимать отдельно проверенный trusted index/digest, связывать и проверять уникальность inventory/sidecar `package_id` и exact candidate/backend, сохранять и применять package format, Nadikt/backend version compatibility и `local_evaluation=approved`. Проверять local relative path grammar, URI/Hub/alias rejection, root `is_dir()`, versioned approved file-tree roles, actual sizes/SHA-256 и pre/post-run digest stability для pinned CTranslate2 и GigaAM layouts. Любой failure завершается до worker spawn и SDK import; tests доказывают этот ordering. Логировать только IDs, checksum prefixes и typed gate outcomes. Зависит от Tasks 0-2.

### Фаза 2: Lifecycle, измерения и evidence

- [x] **Task 4: Реализовать один ASR lifecycle на candidate repeat.** Обновить `benchmarks/asr/benchmark_worker.py` и `benchmarks/asr/benchmark_runner.py`: один worker соответствует `(candidate_id, repeat_index)`, выполняет load -> readiness -> отдельный non-scored warm-up -> ordered scored corpus -> close. `readiness=false` останавливает inference; после успешного engine construction `close()` гарантирован для всех outcomes. Полное потребление faster-whisper generator и GigaAM segment limit остаются regression invariants. Логировать безопасные phase/repeat/sample IDs, durations и typed outcomes без hypothesis/reference. Зависит от Tasks 2-3.

- [x] **Task 5: Сделать supervisor failures и phase timeline структурированными.** Обновить `benchmarks/asr/worker_supervisor.py` и protocol: возвращать typed outcomes `completed`, `timeout`, `terminated`, `killed`, `protocol_error`, `privacy_error`, `spawn_error`, `nonzero_exit`; wrong nonce/version, empty/malformed/oversized output и sampler failure не прерывают весь runner traceback. Передавать bounded monotonic phase boundaries через live event channel либо итоговый typed event timeline, пригодный для сопоставления с supervisor samples. Логировать только safe process outcome, phase IDs и elapsed times; raw stdout/stderr и PID не публиковать. Зависит от Tasks 2 и 4.

- [x] **Task 6: Реализовать phase-aware CPU/RSS и корректный RTF.** Расширить `benchmarks/asr/resource_measurement.py`, `benchmarks/asr/measurement_backends/linux_proc.py` и runner aggregation: строить phase resource reports для load/warm-up/scored inference/whole lifecycle со status, sample/missed counts, boundary coverage, maximum gap и reasons `phase_too_short`/`boundary_missing`/`sampling_gap`. Сохранять CPU normalization, average/max CPU и `sampled_peak_process_tree_rss_mib`; корректно учитывать завершившихся descendants. Считать pooled corpus RTF, per-repeat corpus RTF и sample distribution с median/nearest-rank p95/max только по successful scored samples, всегда публикуя `n`; unavailable не заменять нулём. Логировать sampler metadata и aggregate outcomes без PID/private paths. Зависит от Task 5.

- [x] **Task 7: Реализовать complete quality aggregation, safe execution fingerprint и publication validation.** Обновить `benchmarks/asr/quality_metrics.py`, `benchmarks/asr/environment_fingerprint.py`, `benchmarks/asr/benchmark_results.py` и schemas: category/corpus WER, CER, coding-term accuracy и Latin preservation используют expected/measured numerators/denominators, deterministic non-overlapping variants и `require_latin`; warm-up/failed samples не улучшают quality, а completeness публикуется отдельно. Fingerprint строится из canonical safe payload с full Git SHA/clean flag, CPU/RAM/WSL, launcher/lock/package/thread/inference IDs без private bindings paths. Использовать hash-pinned offline `jsonschema` tooling profile для v1/v2 validation до atomic publication; invalid legacy v1 обрабатывается согласно Task 0. Логировать schema/metric versions, counts и validation outcomes. Зависит от Tasks 0, 2, 4 и 6.

- [ ] **Task 8: Реализовать квалифицированное offline/privacy evidence.** Доработать `benchmarks/asr/offline_supervisor.py`, `benchmarks/asr/offline_evidence.py`, `benchmarks/asr/privacy_audit.py` и supervisor capture. Qualified WSL2/Linux profile отдельно обеспечивает default-deny enforcement и observation полного worker process tree, проходит positive/negative control и связывает evidence с run nonce, full SHA, lock/package digest, process start identity и monitor interval; `PASS` требует finalized monitor after reap, zero attempts и zero missed events, observed attempt даёт `FAIL`, stale/self-declared/partial evidence даёт `NOT VERIFIED`. Ограничить streaming stdout/stderr hard byte cap, разрешить только structured output и проверять randomized canaries для audio/reference/hypothesis/private paths/credentials/exceptions; raw captures уничтожать после private audit. Логировать mechanism/version и aggregate counts/outcomes. Зависит от Tasks 3 и 5.

### Фаза 3: Automated и real qualification

- [ ] **Task 9: Закрыть deterministic contract coverage.** Дополнить runner, protocol, result-schema, manifest, package, resource, quality, supervisor, privacy и backend probe tests в `tests/contract/`. Проверить exact matrix, API/CLI profile validation, integrity-before-spawn, launches=`candidates*repeats`, один load/warm-up/close на repeat, readiness/timeout/nonzero/malformed/wrong-version failures, phase coverage, exited-child accounting, pooled/percentile RTF, complete quality denominators, offline evidence controls, bounded output и каждый committed result artifact. Каноническая команда: `python3 -B -m unittest discover -s tests/contract -p 'test_*.py'`. Логировать только synthetic IDs, phases и outcomes; fixture payload не выводить. Зависит от Tasks 1-8.

- [ ] **Task 10: Реализовать opt-in real lifecycle contract и operator runbook.** Превратить `tests/integration/test_real_local_asr_load.py` из sentinel в matrix-driven test через private config: отсутствие opt-in/config/assets даёт точный `SKIP`, но заявленные prerequisites с broken validate/load/readiness/warm-up/short-transcribe/close/exit дают `FAIL`; offline observer недоступен означает `NOT VERIFIED`, а не acceptance pass. Обновить `docs/testing.md`, `model_packs/README.md` и benchmark plan командами lock/wheelhouse verification, `--no-index --require-hashes` install, bindings validation, оба package probes, evidence self-test, integration run, measured pilot и result validators. Логировать только candidate IDs, phases, safe prerequisite codes и outcomes; private config/path не выводить. Зависит от Task 9.

- [ ] **Task 11: Подготовить controlled assets и выполнить real lifecycle/offline preflight на clean Commit 3 SHA.** Вне Git материализовать hash-verified wheelhouse/interpreter profiles, оба immutable package tree, approved local-evaluation records, coding-pilot WAV/reference/bindings, empty writable caches и private evidence workspace. Проверить bindings/rights/durations, package digests и clean-profile state; выполнить missing/corrupt negative controls и opt-in lifecycle обоих candidates под qualified network profile. Любой отсутствующий prerequisite даёт `BLOCKED`/`NOT AVAILABLE`/`NOT VERIFIED` без successful artifact. Console logs содержат только IDs, digest prefixes, phases и outcomes. Зависит от Tasks 0, 3, 8 и 10.

- [ ] **Task 12: Выполнить, проверить и опубликовать real coding-pilot.** На том же clean Commit 3 SHA выполнить exact two-candidate matrix минимум с тремя independent repeat. Сначала сохранить output в ignored private workspace; run validity требует complete matrix/repeats, offline `PASS`, phase resource coverage, complete quality denominators, finite values и schema/privacy validation. После gates атомарно опубликовать v2 aggregate в `benchmarks/asr/results/` и обновить отдельный раздел `Coding Pilot Results — run_kind=coding_pilot` в `docs/research/local_asr_performance_benchmark_results.md` и factual lifecycle findings в `docs/research/local_asr_offline_package_prototype.md`. Partial/failed run не публиковать; full benchmark, `long_10m`, Windows, installer и model decision оставить `NOT RUN`/`NOT DECIDED`. Console/log output содержит только run/candidate IDs, aggregate metrics и outcomes. Зависит от Task 11.
