# AGENTS.md

> Обновляйте этот файл при существенном изменении структуры, стека или ключевых точек входа. Не описывайте здесь каталоги и компоненты, которых ещё нет в репозитории.

## Обзор проекта

Nadikt - автономная утилита голосового ввода для Windows 10/11 с локальным ASR, безопасной вставкой текста и будущим переносом общего ядра на Ubuntu. Сейчас репозиторий находится на стадии спецификации и настройки контекста: исходный код приложения ещё не создан.

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
|-- .opencode/
|   `-- skills/
|       |-- aif*/                       # встроенные проектные AI Factory навыки
|       `-- nadikt-offline-asr/         # проектный навык интеграции и benchmark ASR
|-- docs/
|   |-- architecture/                   # согласованная стратегия разработки
|   |-- requirements/                   # техническое задание и ASR-требования
|   `-- research/                       # анализ аналогов
|-- .ai-factory.json                    # метаданные установки AI Factory
|-- AGENTS.md                           # карта проекта для агентов
|-- opencode.json                       # проектная конфигурация OpenCode и MCP
`-- skills-lock.json                    # lock-файл внешних навыков
```

## Ключевые точки входа

| Файл | Назначение |
|---|---|
| `docs/requirements/Nadikt_TZ_v0.2.md` | Основное согласованное техническое задание Windows MVP. |
| `docs/requirements/Nadikt_multilingual_ASR_requirements.md` | Требования к смешанной речи, движкам и модельным пакетам. |
| `docs/architecture/Nadikt_development_strategy.md` | Стратегия общего ядра, раннего Windows-прототипа и последующей Ubuntu-версии. |
| `docs/architecture/ADR-001-codebase-strategy.md` | Решение HYBRID по собственной кодовой базе и выборочному использованию сторонних решений. |
| `docs/research/repository_assessment.md` | Технический и лицензионный анализ открытых приложений голосового ввода. |
| `docs/research/handy_poc_plan.md` | Ограниченный план проверки Handy на Ubuntu и Windows. |
| `.ai-factory/DESCRIPTION.md` | Краткий контекст продукта, выбранный стек и открытые технические решения. |
| `.ai-factory/ARCHITECTURE.md` | Целевая Explicit Architecture, структура слоёв и правила зависимостей. |
| `.ai-factory/ROADMAP.md` | Стратегическая последовательность от квалификации рисков до Windows MVP и Ubuntu-версии. |
| `.ai-factory/config.yaml` | Язык артефактов, пути и настройки git-aware workflow. |
| `.ai-factory/rules/base.md` | Начальные соглашения по модулям, ошибкам, журналированию и тестам. |
| `.opencode/skills/nadikt-offline-asr/SKILL.md` | Правила автономной интеграции GigaAM/faster-whisper и benchmark. |
| `opencode.json` | GitHub MCP для OpenCode; ожидает `GITHUB_TOKEN` в окружении. |

Точка входа приложения отсутствует, потому что реализация ещё не начата.

## Документация

| Документ | Путь | Описание |
|---|---|---|
| Техническое задание | `docs/requirements/Nadikt_TZ_v0.2.md` | Функциональные, нефункциональные и приёмочные требования MVP. |
| Требования к ASR | `docs/requirements/Nadikt_multilingual_ASR_requirements.md` | Смешанная русско-английская речь и сменные движки. |
| Стратегия разработки | `docs/architecture/Nadikt_development_strategy.md` | Этапы Ubuntu core, Windows prototype, Windows MVP и Ubuntu version. |
| Анализ аналогов | `docs/research/Nadikt_competitor_analysis.md` | Обоснование функций, рисков и границ MVP. |
| Оценка репозиториев | `docs/research/repository_assessment.md` | Сравнение лицензий, архитектуры, платформ, оценок и fork gate. |
| ADR стратегии кодовой базы | `docs/architecture/ADR-001-codebase-strategy.md` | Принятое решение HYBRID и условия пересмотра. |
| Handy PoC | `docs/research/handy_poc_plan.md` | Измеримый план проверки оставшихся рисков Handy. |
| Roadmap | `.ai-factory/ROADMAP.md` | Milestones исследования, прототипов, Windows MVP и Ubuntu-версии. |

README пока отсутствует.

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
