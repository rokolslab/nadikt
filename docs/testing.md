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
