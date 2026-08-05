# AGENTS.md

> Обновляйте этот файл при существенном изменении структуры, стека или ключевых точек входа. Не описывайте здесь каталоги и компоненты, которых ещё нет в репозитории.

## Обзор проекта

Nadikt - автономная утилита голосового ввода для Windows 10/11 с локальным ASR, безопасной вставкой текста и будущим переносом общего ядра на Ubuntu. Законченное приложение ещё не создано; в репозитории есть ранний bounded Windows dictation slice skeleton, ASR contract/benchmark skeleton и изолированный disposable experiment безопасной Windows-вставки.

Подробное описание проекта находится в `.ai-factory/DESCRIPTION.md`, канонические продуктовые требования - в `docs/`.

## Технологический стек

- **Язык программирования:** Python.
- **Desktop UI:** PySide6 (Qt 6).
- **Локальное хранилище:** SQLite.
- **Доступ к данным:** стандартный модуль `sqlite3`, без ORM.
- **ASR-кандидаты:** GigaAM и faster-whisper; финальные модели выбираются после benchmark.
- **Целевая ОС MVP:** Windows 10/11 x64.
- **Перспективная ОС:** Ubuntu.
- **Текущая среда разработки:** WSL2 Ubuntu на Windows 11 Pro, mini PC Intel Core i3 12-го поколения, 16 ГБ ОЗУ.

## Структура проекта

```text
nadikt/
|-- .agents/
|   `-- skills/python-testing-patterns/  # внешний навык по Python-тестированию
|-- .ai-factory/
|   |-- ARCHITECTURE.md                 # целевая Explicit Architecture
|   |-- config.yaml                     # настройки AI Factory
|   |-- DESCRIPTION.md                  # сводное описание продукта и стека
|   |-- ROADMAP.md                      # стратегические milestones проекта
|   |-- plans/                          # долгоживущие планы feature-веток
|   `-- rules/base.md                   # базовые инженерные правила
|-- .github/                            # issue forms и pull request template
|-- .opencode/
|   `-- skills/
|       |-- aif*/                       # встроенные проектные AI Factory навыки
|       `-- nadikt-offline-asr/         # проектный навык интеграции и benchmark ASR
|-- docs/
|   |-- README.md                       # публичный индекс документации
|   |-- getting-started.md              # текущее окружение и первые команды
|   |-- testing.md                      # test strategy и команды experiment
|   |-- architecture/                   # согласованная стратегия разработки
|   |-- requirements/                   # техническое задание и ASR-требования
|   `-- research/                       # анализ аналогов
|-- experiments/
|   `-- windows_insertion/              # disposable spike target/clipboard/input safety
|-- src/
|   `-- nadikt/
|       |-- domain/
|       |   |-- dictation/               # state machine bounded dictation session
|       |   |-- ports/                   # ASR/audio/insertion contracts
|       |   `-- text/                    # deterministic text normalization
|       |-- application/services/        # dictation pipeline и insertion orchestration
|       |-- infrastructure/
|       |   |-- asr/                     # optional SDK probe/runtime adapters
|       |   |-- audio/                   # opt-in Windows bounded capture adapter
|       |   |-- model_packages/          # runtime local package validation boundary
|       |   `-- platform/windows/        # UIA/clipboard/input adapter boundaries
|       |-- presentation/cli/            # controlled CLI harnesses
|       `-- bootstrap.py                 # early composition helpers
|-- benchmarks/
|   `-- asr/                             # manifests, run profiles, dry-run и benchmark helpers
|-- model_packs/                         # docs и example manifests; без model weights
|-- tests/
|   |-- unit/                            # fake-backed domain/application tests
|   |-- contract/                        # ASR benchmark и slice port contracts
|   |-- integration/                     # runtime model package validation tests
|   `-- windows/                         # opt-in Windows host checks
|-- .ai-factory.json                    # метаданные установки AI Factory
|-- AGENTS.md                           # карта проекта для агентов
|-- CONTRIBUTING.md                     # правила contribution и pull requests
|-- LICENSE                             # MIT License
|-- README.md                           # публичная landing page проекта
|-- SECURITY.md                         # private vulnerability reporting
|-- opencode.json                       # проектная конфигурация OpenCode и MCP
`-- skills-lock.json                    # lock-файл внешних навыков
```

## Ключевые точки входа

| Файл | Назначение |
|---|---|
| `README.md` | Публичный обзор, статус, quick start и навигация. |
| `docs/README.md` | Полный индекс требований, архитектуры, исследований и руководств. |
| `docs/research/local_asr_performance_benchmark_plan.md` | Protocol локального ASR benchmark, метрики, offline/privacy gates и dry-run command. |
| `docs/research/local_asr_performance_benchmark_results.md` | Шаблон результатов benchmark и decision matrix без выбора модели до измерений. |
| `docs/research/windows_dictation_slice_acceptance.md` | Versioned manual acceptance matrix для controlled Windows dictation slice; `NOT RUN` rows являются blockers. |
| `src/nadikt/domain/ports/asr.py` | Начальный SDK-neutral ASR contract общего ядра. |
| `src/nadikt/domain/dictation/session.py` | Explicit bounded dictation session state machine, retained-result invariants и privacy-safe context. |
| `src/nadikt/domain/ports/audio.py` | Bounded one-shot audio capture contract, compatible with `AsrSegmentInput`, with redacted DTO repr. |
| `src/nadikt/domain/ports/insertion.py` | Safe insertion contracts для target capture/revalidation, clipboard transaction и input dispatch с opaque tokens. |
| `src/nadikt/domain/text/normalization.py` | Minimal deterministic whitespace/newline normalization без user dictionary и benchmark mappings. |
| `src/nadikt/application/services/dictation_pipeline.py` | One-shot `capture -> transcribe_segment -> normalize -> insert` orchestration через injected ports. |
| `src/nadikt/application/services/insertion_service.py` | Safe one-shot insertion orchestration с target revalidation, clipboard restore/discard и retained-result outcomes. |
| `src/nadikt/infrastructure/asr/faster_whisper.py` | Lazy optional faster-whisper local CTranslate2 probe adapter; не импортирует SDK до load path. |
| `src/nadikt/infrastructure/asr/gigaam.py` | Lazy optional GigaAM local loading probe wrapper; фиксирует `local_loading_unconfirmed` без подтверждённого local API. |
| `src/nadikt/infrastructure/audio/windows_capture.py` | Opt-in Windows bounded microphone capture adapter; lazy optional `sounddevice` import and fail-closed behavior. |
| `src/nadikt/infrastructure/model_packages/validation.py` | Runtime local model package binding validator; rejects example/unsafe packages before ASR SDK import/load. |
| `src/nadikt/infrastructure/platform/windows/uia.py` | UIA target-safety boundary with injected facade, stable identity hash and fail-closed protected/changed/stale outcomes. |
| `src/nadikt/infrastructure/platform/windows/clipboard.py` | Clipboard transaction boundary with injected facade, cloneability/sequence restore policy and redacted DTOs. |
| `src/nadikt/infrastructure/platform/windows/input.py` | Input dispatch boundary with modifier preflight and explicit direct Unicode fallback policy. |
| `src/nadikt/bootstrap.py` | Composition helpers for explicit local ASR candidate loading and controlled Windows dictation slice wiring. |
| `src/nadikt/presentation/cli/windows_dictation_slice.py` | Operator-controlled CLI harness for one bounded Windows dictation run; not a desktop entry point. |
| `benchmarks/asr/dry_run.py` | Dry-run manifest validator без загрузки моделей и без сетевых вызовов. |
| `benchmarks/asr/local_model_probe.py` | Offline local package lifecycle probe runner без transcript/audio paths в JSON summary. |
| `benchmarks/asr/run_profiles/coding_pilot.v1.json` | Versioned coding-pilot matrix profile: frozen two-candidate pair, repeats, dataset revision, warm-up/scored samples and policy IDs. |
| `benchmarks/asr/schemas/run_profile.v1.schema.json` | JSON Schema для benchmark run-profile manifests; runtime validation дополнительно выполняется в `benchmarks/asr/manifests.py`. |
| `benchmarks/asr/schemas/benchmark_result.v2.schema.json` | Immutable schema для publishable coding-pilot aggregate v2 с typed repeat/sample/metric outcomes. |
| `docs/research/local_asr_offline_package_prototype.md` | Findings package integrity/lifecycle prototype, fake-backed checks и blockers. |
| `experiments/windows_insertion/README.md` | Команды, safety rules и versioned acceptance matrix disposable spike. |
| `experiments/windows_insertion/insertion_spike/cli.py` | Ручной двухэтапный capture/deliver harness; не является точкой входа приложения. |
| `.ai-factory/DESCRIPTION.md` | Краткий контекст продукта, выбранный стек и открытые технические решения. |
| `.ai-factory/ARCHITECTURE.md` | Целевая Explicit Architecture, структура слоёв и правила зависимостей. |
| `.ai-factory/ROADMAP.md` | Стратегическая последовательность от квалификации рисков до Windows MVP и Ubuntu-версии. |
| `.ai-factory/config.yaml` | Язык артефактов, пути и настройки git-aware workflow. |
| `.ai-factory/rules/base.md` | Начальные соглашения по модулям, ошибкам, журналированию и тестам. |
| `.opencode/skills/nadikt-offline-asr/SKILL.md` | Правила автономной интеграции GigaAM/faster-whisper и benchmark. |
| `opencode.json` | GitHub MCP для OpenCode; ожидает `GITHUB_TOKEN` в окружении. |

Точка входа законченного desktop-приложения отсутствует. `src/nadikt/presentation/cli/windows_dictation_slice.py` запускает только controlled vertical-slice harness and fails closed without injected/verified Windows capabilities. `benchmarks/asr/dry_run.py` запускает только benchmark dry run. `experiments/windows_insertion/insertion_spike/cli.py` запускает только disposable experiment и не переносится автоматически в production.

## Документация

| Документ | Путь | Описание |
|---|---|---|
| README | `README.md` | Публичная landing page проекта. |
| Центр документации | `docs/README.md` | Индекс всех публичных материалов. |
| Начало работы | `docs/getting-started.md` | Окружение, clone и первые проверки. |
| Тестирование | `docs/testing.md` | Automated tests и controlled fixtures. |
| Техническое задание | `docs/requirements/Nadikt_TZ_v0.2.md` | Функциональные, нефункциональные и приёмочные требования MVP. |
| Требования к ASR | `docs/requirements/Nadikt_multilingual_ASR_requirements.md` | Смешанная русско-английская речь и сменные движки. |
| Стратегия разработки | `docs/architecture/Nadikt_development_strategy.md` | Этапы Ubuntu core, Windows prototype, Windows MVP и Ubuntu version. |
| Анализ аналогов | `docs/research/Nadikt_competitor_analysis.md` | Обоснование функций, рисков и границ MVP. |
| Оценка репозиториев | `docs/research/repository_assessment.md` | Сравнение лицензий, архитектуры, платформ, оценок и fork gate. |
| ADR стратегии кодовой базы | `docs/architecture/ADR-001-codebase-strategy.md` | Принятое решение HYBRID и условия пересмотра. |
| Handy PoC | `docs/research/handy_poc_plan.md` | Измеримый план проверки оставшихся рисков Handy. |
| Windows insertion spike | `docs/research/windows_insertion_spike_results.md` | Проверенные факты, ограничения, production ports и решение REWORK. |
| Windows dictation slice acceptance | `docs/research/windows_dictation_slice_acceptance.md` | Versioned manual matrix и blocker semantics. |
| Local ASR benchmark plan | `docs/research/local_asr_performance_benchmark_plan.md` | Protocol, manifests, offline/privacy gates и dry-run command. |
| Local ASR offline package prototype | `docs/research/local_asr_offline_package_prototype.md` | Package integrity, local probe lifecycle, fake-backed adapter checks и blockers. |
| Local ASR benchmark results | `docs/research/local_asr_performance_benchmark_results.md` | Шаблон результатов и decision matrix. |
| Участие | `CONTRIBUTING.md` | Workflow и pull request checklist. |
| Безопасность | `SECURITY.md` | Private vulnerability reporting. |
| Лицензия | `LICENSE` | MIT License для собственного кода и документации. |
| Roadmap | `.ai-factory/ROADMAP.md` | Milestones исследования, прототипов, Windows MVP и Ubuntu-версии. |

## Контекст AI

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Фактическая карта репозитория и ключевых документов. |
| `.ai-factory/DESCRIPTION.md` | Сводное описание продукта и технологических решений. |
| `.ai-factory/ARCHITECTURE.md` | Архитектурный шаблон, границы и правила зависимостей после генерации. |
| `.ai-factory/ROADMAP.md` | Текущие стратегические milestones и прогресс проекта. |
| `.ai-factory/rules/base.md` | Базовые правила реализации. |
| `.opencode/skills/nadikt-offline-asr/` | Проектные знания по offline ASR. |

`CLAUDE.md` на момент этой карты отсутствует.

## Правила для агентов

- Не начинайте реализацию только на основании этой карты; сверяйте поведение с техническим заданием.
- Не добавляйте облачную обработку, автоматическую телеметрию или сетевую загрузку моделей в основной runtime.
- Не журналируйте аудио, распознанный текст, пользовательский словарь или содержимое буфера обмена.
- Сохраняйте независимость общего ядра от PySide6, Windows API и конкретных ASR SDK.
- Не фиксируйте победителя ASR, VAD, упаковщик или системные библиотеки до воспроизводимого прототипа.
- Разбивайте зависимые shell-команды на отдельные вызовы: сначала `git checkout main`, затем `git pull origin main`; не объединяйте их через `&&`.
- Не создавайте исходные каталоги и проектный код в рамках контекстных команд AI Factory.
