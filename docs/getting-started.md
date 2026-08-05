[← Центр документации](README.md) · [К проекту](../README.md) · [Тестирование →](testing.md)

# Начало Работы

## Что Доступно Сейчас

Nadikt находится на стадии исследования и квалификации технических рисков.
Готового desktop-приложения, installer и production entry point пока нет.

В репозитории доступны:

- согласованные требования Windows MVP;
- Explicit Architecture и roadmap;
- исследования ASR-кандидатов и открытых приложений;
- ранний production skeleton для bounded Windows dictation slice;
- disposable Windows insertion spike с automated tests.

## Требования К Окружению

Для чтения документации достаточно Git. Для automated experiment checks нужны:

| Компонент | Требование |
|---|---|
| ОС | Windows 11 Pro host с WSL2 Ubuntu для разработки; Windows 10/11 x64 для real Win32 checks |
| Текущая машина | Mini PC, Intel Core i3 12-го поколения, 16 ГБ ОЗУ |
| Python | 3.12 x64 |
| Сеть | Не нужна для tests/runtime experiment |
| Внешние Python packages | Не нужны |

Общие будущие модули разрабатываются в WSL2 Ubuntu. Win32 experiment и будущие
проверки hotkey, target window, clipboard и insertion запускаются на Windows
host или Windows CI, а не внутри WSL.

ASR benchmark имеет отдельный benchmark-only environment contract в
[`requirements/benchmark/`](../requirements/benchmark/). Dry-run и contract tests
остаются standard-library only; real ASR load/probe должен запускаться в заранее
подготовленном Python 3.12 environment из offline wheelhouse и lock profile, без
dependency resolution или network access во время run.

## Клонирование

```powershell
git clone https://github.com/rokolslab/nadikt.git
cd nadikt
```

Проверка состояния:

```powershell
git status
python --version
```

## Первый Automated Run

```powershell
cd experiments/windows_insertion
python -m unittest discover -s tests
```

Tests используют injected API facades и synthetic canaries. Они не должны
вводить текст в пользовательские приложения или менять реальный clipboard.

ASR benchmark contract tests запускаются из корня репозитория:

```powershell
python3 -m unittest discover -s tests/contract
```

Новые fake-backed tests минимального dictation slice запускаются вместе с общим
test discovery и не требуют реальных ASR packages, микрофона или Windows UIA:

```powershell
python3 -m unittest discover -s tests
```

Privacy-safe fingerprint benchmark environment:

```powershell
python3 -m benchmarks.asr.environment_fingerprint
```

## Controlled Windows Check

```powershell
python fixtures/classic_target.py --self-check
```

Fixture создаёт собственные native `EDIT` и `ES_PASSWORD`, проверяет
foreground/focus перед input и завершает процесс с non-zero code при любом
нарушенном case.

## Controlled Windows Dictation Slice

Ранний CLI harness находится в `nadikt.presentation.cli.windows_dictation_slice`.
Он предназначен для operator-controlled Windows host и принимает только explicit
validated local model binding. Команда требует private inventory/model package и
non-scored warm-up audio вне Git:

```powershell
python -m nadikt.presentation.cli.windows_dictation_slice --inventory <private-inventory> --package-id <package-id> --candidate-id <candidate-id> --backend faster-whisper --warm-up-audio-file <private-warmup-wav>
```

Пути в примере являются placeholders: реальные private paths не фиксируются в
Git, logs, stdout или acceptance notes. Пока Windows UIA/clipboard/input facades
не подключены в controlled host, production adapters fail closed.

## Что Не Запускать Без Подготовки

Manual CLI и clipboard racer предназначены для контролируемого experiment, а
не повседневного ввода. Перед использованием прочитайте:

- [experiment README](../experiments/windows_insertion/README.md);
- [результаты spike](research/windows_insertion_spike_results.md);
- [acceptance matrix slice](research/windows_dictation_slice_acceptance.md);
- [правила безопасности](../SECURITY.md).

## Следующий Шаг

Выберите задачу из [roadmap](../.ai-factory/ROADMAP.md), создайте отдельную
ветку и сверяйте поведение с ТЗ, а не только с `AGENTS.md` или AI-контекстом.

## См. Также

- [Тестирование](testing.md)
- [Участие в разработке](../CONTRIBUTING.md)
- [Стратегия разработки](architecture/Nadikt_development_strategy.md)
