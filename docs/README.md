[← К проекту](../README.md) · [Начало работы →](getting-started.md)

# Документация Nadikt

Этот каталог содержит канонические продуктовые документы, архитектурные
решения и проверяемые исследования. Корневой README служит landing page; здесь
находится полная карта материалов.

## Порядок Чтения

1. [Начало работы](getting-started.md) — текущее состояние и доступные команды.
2. [Техническое задание](requirements/Nadikt_TZ_v0.2.md) — поведение Windows MVP.
3. [Требования к multilingual ASR](requirements/Nadikt_multilingual_ASR_requirements.md).
4. [Стратегия разработки](architecture/Nadikt_development_strategy.md).
5. [ADR-001](architecture/ADR-001-codebase-strategy.md) — стратегия кодовой базы.
6. [Roadmap](../.ai-factory/ROADMAP.md) — последовательность milestones.

## Руководства

| Документ | Содержание |
|---|---|
| [Начало работы](getting-started.md) | Окружение, clone и первые проверки |
| [Тестирование](testing.md) | Unit/contract tests и controlled Windows checks |
| [Участие в разработке](../CONTRIBUTING.md) | Branch, commit, PR и privacy rules |
| [Безопасность](../SECURITY.md) | Private vulnerability reporting |

## Требования

| Документ | Статус |
|---|---|
| [ТЗ Windows MVP v0.2](requirements/Nadikt_TZ_v0.2.md) | Канонический источник поведения MVP |
| [Multilingual ASR](requirements/Nadikt_multilingual_ASR_requirements.md) | Русская и смешанная речь, engine contracts |

## Архитектура

| Документ | Назначение |
|---|---|
| [Стратегия разработки](architecture/Nadikt_development_strategy.md) | Общее ядро, Windows MVP и будущая Ubuntu-версия |
| [ADR-001](architecture/ADR-001-codebase-strategy.md) | Решение `HYBRID` и fork/reuse gates |
| [AI Factory Architecture](../.ai-factory/ARCHITECTURE.md) | Слои, зависимости и целевая структура |

## Исследования

| Документ | Результат |
|---|---|
| [Анализ конкурентов](research/Nadikt_competitor_analysis.md) | Требования и границы MVP |
| [Оценка репозиториев](research/repository_assessment.md) | Лицензии, reuse и fork gate |
| [Handy PoC plan](research/handy_poc_plan.md) | Ограниченный план дополнительной проверки |
| [Windows insertion spike](research/windows_insertion_spike_results.md) | `REWORK`, evidence и deferred matrix |

## Иерархия Источников

1. `docs/requirements/` определяет продуктовые требования.
2. `docs/architecture/` фиксирует согласованные архитектурные решения.
3. `docs/research/` хранит evidence, оценки и планы экспериментов.
4. `.ai-factory/` содержит рабочий контекст и roadmap для разработки.
5. `experiments/` содержит disposable code и не является production source.

## См. Также

- [README проекта](../README.md)
- [Карта репозитория для агентов](../AGENTS.md)
- [Roadmap](../.ai-factory/ROADMAP.md)
