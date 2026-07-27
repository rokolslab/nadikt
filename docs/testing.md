[← Начало работы](getting-started.md) · [К проекту](../README.md) · [ТЗ →](requirements/Nadikt_TZ_v0.2.md)

# Тестирование

## Текущий Test Suite

Production test suite ещё не создан. Единственный исполняемый набор относится
к disposable Windows insertion spike и использует стандартный `unittest`.

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
