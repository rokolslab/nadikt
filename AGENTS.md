# AGENTS.md

> Обновляйте этот файл при существенном изменении структуры, стека или ключевых точек входа. Не описывайте здесь каталоги и компоненты, которых ещё нет в репозитории.

## Обзор проекта

Nadikt - автономная утилита голосового ввода для Windows 10/11 с локальным ASR, безопасной вставкой текста и будущим переносом общего ядра на Ubuntu. Законченное приложение ещё не создано; в репозитории есть начальный ASR contract/benchmark skeleton и изолированный disposable experiment безопасной Windows-вставки.

Подробное описание проекта находится в `.ai-factory/DESCRIPTION.md`, канонические продуктовые требования - в `docs/`.

## Технологический стек

- **Язык программирования:** Python.
- **Desktop UI:** PySide6 (Qt 6).
- **Локальное хранилище:** SQLite.
- **Доступ к данным:** стандартный модуль `sqlite3`, без ORM.
- **ASR-кандидаты:** GigaAM и faster-whisper; финальные модели выбираются после benchmark.
- **Целевая ОС MVP:** Windows 10/11 x64.
- **Перспективная ОС:** Ubuntu.

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
|   `-- nadikt/domain/ports/asr.py       # начальный ASR contract skeleton общего ядра
|-- benchmarks/
|   `-- asr/                             # manifest validation, dry-run и benchmark helpers
|-- model_packs/                         # docs и example manifests; без model weights
|-- tests/
|   `-- contract/                        # contract tests для ASR benchmark harness
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
| `src/nadikt/domain/ports/asr.py` | Начальный SDK-neutral ASR contract общего ядра. |
| `benchmarks/asr/dry_run.py` | Dry-run manifest validator без загрузки моделей и без сетевых вызовов. |
| `experiments/windows_insertion/README.md` | Команды, safety rules и versioned acceptance matrix disposable spike. |
| `experiments/windows_insertion/insertion_spike/cli.py` | Ручной двухэтапный capture/deliver harness; не является точкой входа приложения. |
| `.ai-factory/DESCRIPTION.md` | Краткий контекст продукта, выбранный стек и открытые технические решения. |
| `.ai-factory/ARCHITECTURE.md` | Целевая Explicit Architecture, структура слоёв и правила зависимостей. |
| `.ai-factory/ROADMAP.md` | Стратегическая последовательность от квалификации рисков до Windows MVP и Ubuntu-версии. |
| `.ai-factory/config.yaml` | Язык артефактов, пути и настройки git-aware workflow. |
| `.ai-factory/rules/base.md` | Начальные соглашения по модулям, ошибкам, журналированию и тестам. |
| `.opencode/skills/nadikt-offline-asr/SKILL.md` | Правила автономной интеграции GigaAM/faster-whisper и benchmark. |
| `opencode.json` | GitHub MCP для OpenCode; ожидает `GITHUB_TOKEN` в окружении. |

Точка входа приложения отсутствует. `benchmarks/asr/dry_run.py` запускает только benchmark dry run. `experiments/windows_insertion/insertion_spike/cli.py` запускает только disposable experiment и не переносится автоматически в production.

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
| Local ASR benchmark plan | `docs/research/local_asr_performance_benchmark_plan.md` | Protocol, manifests, offline/privacy gates и dry-run command. |
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
