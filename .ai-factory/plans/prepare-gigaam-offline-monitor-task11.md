# План реализации: подготовка GigaAM package и offline monitor для Task 11 preflight

Branch: main
Created: 2026-08-03

## Original Request

создай план сам

## Settings

- Testing: yes
- Logging: verbose
- Docs: no

## Roadmap Linkage

Milestone: "Квалификация критических технических рисков"
Rationale: План закрывает внешние prerequisites для реального ASR coding-pilot preflight перед публикацией результатов benchmark.

## Контекст и текущий статус

- Controlled root: `<controlled-root>`; текущая operator-директория: `/home/oitroot/nadikt-controlled`.
- Текущий status artifact: `<controlled-root>/runs/task11-preflight-status.json`.
- Сейчас доступны валидные dataset bindings и faster-whisper package для `faster-whisper-small-int8`.
- `faster-whisper` lifecycle проходит только через controlled venv: `<controlled-root>/venv-benchmark-fw/bin/python`.
- Публикация benchmark пока запрещена: matrix incomplete, GigaAM package отсутствует, offline evidence `NOT VERIFIED`, full hash-locked wheel closure не материализован.
- Этот план не публикует benchmark results и не меняет ASR decision; он готовит prerequisites для возврата к Task 11 основного плана.

## Границы и критерии готовности

- Frozen pair остаётся exact: `gigaam-multilingual-220m` + `faster-whisper-small-int8`.
- Все model weights, WAV/reference payload, wheelhouse/cache и private configs остаются вне Git.
- В Git можно менять только план/документацию/код валидаторов при необходимости; raw controlled payload не копировать.
- GigaAM package должен быть представлен как local controlled package с sidecar manifest, exact checksum/size для critical files, `local_evaluation=approved` и compatible backend metadata.
- Offline evidence для acceptance требует qualified WSL2/Linux default-deny profile: positive/negative controls, process-tree observation, finalized-after-reap, zero attempts, zero missed events.
- Если GigaAM assets или qualified monitor недоступны, итогом является явный `BLOCKED`/`NOT VERIFIED` status artifact, а не placeholder metrics.

## Tasks

### Фаза 1: GigaAM controlled package

- [x] **Task 1: Материализовать GigaAM Multilingual 220M package вне Git.** Подготовить `<controlled-root>/models/packages/gigaam-multilingual-220m-local/` в cache-style layout, совместимом с текущим `src/nadikt/infrastructure/asr/gigaam.py`: ожидаемый loader name `multilingual_ctc`, обязательный файл `multilingual_ctc.ckpt` и любые дополнительные SDK-required local files, если они нужны для реального load. Не использовать Hub ID/runtime download path. Логировать только `candidate_id`, `package_id`, safe file role counts и checksum prefixes; не логировать source URLs, private acquisition paths или credentials.

- [x] **Task 2: Создать GigaAM sidecar manifest и обновить trusted inventory.** Добавить `<controlled-root>/models/gigaam-multilingual-220m-local.manifest.json`, обновить `<controlled-root>/models/trusted-index.local-2026-08-03.json` и `<controlled-root>/models/inventory.json`: `candidate_id=gigaam-multilingual-220m`, `backend=gigaam`, `package_id=gigaam-multilingual-220m-local`, exact `manifest_sha256`, `trusted_index_sha256`, `package_format`, Nadikt/backend compatibility, critical file roles, full SHA-256/size, licenses/notices и `local_evaluation=approved`. Проверить, что `benchmarks.asr.manifests.load_model_inventory` и `benchmarks.asr.local_model_probe --dry-run --offline-required` принимают оба packages. Логировать только IDs, digest prefixes, warning counts и validation outcomes.

### Фаза 2: Environment и lifecycle gates

- [x] **Task 3: Материализовать GigaAM benchmark environment без сетевого resolver.** Подготовить controlled venv/wheelhouse для GigaAM (`<controlled-root>/venv-benchmark-gigaam/` или документированный equivalent) из hash-locked offline wheel closure. Использовать `--no-index --require-hashes`; не выполнять dependency resolution во время benchmark/lifecycle runs. Зафиксировать safe evidence: Python/platform ABI, lock file ID/digest prefix, package versions и отсутствие `REVIEW_REQUIRED`/`NOT_MATERIALIZED` markers в применяемом profile. Логировать только profile IDs, version strings и digest prefixes.

- [x] **Task 4: Запустить package probes и opt-in lifecycle для обоих candidates.** Для faster-whisper использовать `<controlled-root>/venv-benchmark-fw/bin/python`; для GigaAM использовать controlled GigaAM interpreter. Проверить package validation, load, readiness, warm-up/short-transcribe, close и process outcome на sample `warmup_001` или другом safe configured sample. Создать/обновить private config так, чтобы exact two-candidate matrix была заявлена, но не публиковалась. Если qualified offline monitor ещё не готов, `require_offline_evidence_pass` можно временно ставить `false` только для diagnostic lifecycle run; acceptance run должен вернуть `PASS`. Логировать только candidate IDs, phases, durations, outcome codes и safe prerequisite codes.

### Фаза 3: Qualified offline evidence

- [ ] **Task 5: Подготовить qualified WSL2/Linux default-deny evidence profile.** Реализовать или подключить operator-level mechanism `qualified-wsl2-default-deny-v1`, который блокирует исходящую сеть для полного worker process tree и наблюдает попытки до reap/finalize. Выполнить positive control (synthetic network attempt observed -> `FAIL`/control pass) и negative control (zero attempts -> eligible `PASS`). Raw packet/socket/process captures хранить только в private workspace и уничтожать/не публиковать после audit. Логировать только mechanism/version, monitor interval, aggregate attempt/missed counts и outcome.

- [ ] **Task 6: Связать offline evidence с lifecycle/preflight identity.** Для acceptance run evidence должен быть связан с run nonce, full clean Git SHA, lock digest prefix, package digest prefixes, process start identity и monitor interval. `PASS` допустим только при finalized-after-reap, zero attempts, zero missed events и passed controls; observed attempt -> `FAIL`; stale/self-declared/partial evidence -> `NOT VERIFIED`. Обновить `<controlled-root>/runs/task11-preflight-status.json` безопасными aggregate fields без raw evidence.

### Фаза 4: Exact two-candidate preflight status

- [ ] **Task 7: Выполнить exact two-candidate Task 11 preflight без публикации benchmark.** На clean SHA основного repo запустить validators: inventory/package integrity, dataset bindings, оба package probes, opt-in lifecycle и offline evidence self-test. Если все prerequisites выполнены, status artifact должен показать `candidate_matrix_complete`, package/lifecycle success для обоих candidates и `offline_evidence.status=PASS`. Если нет, status artifact должен явно перечислить blockers без placeholder metrics. Логировать только IDs, phases, digest prefixes, aggregate counts/outcomes.

- [ ] **Task 8: Сформировать решение о возврате к основному Task 11/12.** Если preflight complete и evidence `PASS`, вернуться к основному `.ai-factory/PLAN.md` Task 11 и выполнить clean-SHA real preflight; затем Task 12 measured pilot. Если остались blockers, оставить основной Task 11 неотмеченным и сохранить `<controlled-root>/runs/task11-preflight-status.json` как private status для следующей сессии. Не публиковать `benchmarks/asr/results/` и не обновлять public benchmark results до complete v2 matrix.

## Commit Plan

- **Commit 1** (после Tasks 1-4, если менялся repo код/docs): `chore(asr-benchmark): prepare gigaam controlled preflight`
- **Commit 2** (после Tasks 5-8, если менялся repo код/docs): `test(asr-benchmark): qualify offline preflight evidence`

Если изменения происходят только внутри `<controlled-root>`, commit в Git не требуется; вместо этого обновить private status artifact и сообщить safe outcome.

## Verification Commands

```bash
python3 -m benchmarks.asr.local_model_probe --models <controlled-root>/models/inventory.json --dry-run --offline-required
```

```bash
python3 - <<'PY'
from pathlib import Path
from benchmarks.asr.dataset_bindings import validate_dataset_bindings
result = validate_dataset_bindings(
    Path('benchmarks/asr/datasets/coding_pilot.v1.json'),
    Path('<controlled-root>/datasets/bindings.json'),
    Path('<controlled-root>/datasets'),
)
print({'outcome': result.outcome, 'binding_count': result.binding_count, 'error_count': len(result.errors)})
PY
```

```bash
NADIKT_REAL_ASR_ASSETS=1 NADIKT_REAL_ASR_CONFIG=<controlled-root>/private-config.json <controlled-python> -B -m unittest tests.integration.test_real_local_asr_load
```

## Notes For Next Session

- Сначала прочитать `<controlled-root>/runs/task11-preflight-status.json` и этот план.
- Не запускать measured `benchmark_runner` как publishable run, пока GigaAM package и offline evidence не готовы.
- Не копировать WAV/reference/model files или raw evidence в repository.

## Session Notes 2026-08-04

- Task 3 completed outside Git: materialized `gigaam-cpu-python312-wsl2-v1` wheelhouse, hash lock and `/home/oitroot/nadikt-controlled/venv-benchmark-gigaam`; install passed with `--no-index --require-hashes`.
- GigaAM package validation, load, readiness and close passed for `gigaam-multilingual-220m` with checksum prefix `24aa92be5994`.
- Exact two-candidate load/readiness/close probe passed for GigaAM and faster-whisper; no benchmark results were published.
- Materialized controlled WSL2 ffmpeg tool outside Git: `ffmpeg 7.0.2-static`, archive checksum prefix `abda8d77ce83`, binary checksum prefix `e7e7fb30477f`. This is approved only for controlled WSL2 preflight; Windows MVP packaging still requires separate artifact and license review.
- `warmup_001` transcribe probe passed for both `gigaam-multilingual-220m` and `faster-whisper-small-int8`; no transcript, reference text or metrics were published.
- Exact two-candidate dry-run preflight passed with `outcome=dry_run`, `binding_status=bindings_valid` and `offline_evidence.status=NOT VERIFIED`.
- Private measured coding-pilot run completed outside Git at `/home/oitroot/nadikt-controlled/runs/pilot-ru-coding-measured-private.json`: both candidates completed 3/3 repeats with `outcome=success`; output remains non-publishable because `offline_evidence.status=NOT VERIFIED` and Git worktree is dirty.
- Task 5 is blocked in the current WSL2 environment: `unshare -n` returns `Operation not permitted`, and `strace`/iptables/nft are not available. Current code path also keeps `WorkerSupervisor` evidence fail-closed as `qualified_monitor_not_configured` until a qualified monitor is wired.
