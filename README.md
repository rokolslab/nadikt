# Nadikt

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4.svg)](docs/requirements/Nadikt_TZ_v0.2.md)
[![Status: research](https://img.shields.io/badge/status-research-orange.svg)](.ai-factory/ROADMAP.md)

> Автономный голосовой ввод для Windows с локальным распознаванием речи,
> безопасной вставкой текста и переносимым Python-ядром.

Nadikt проектируется как фоновая desktop-утилита для Windows 10/11 x64. Она
должна локально распознавать преимущественно русскую речь с английскими
терминами, не передавать пользовательские данные во внешние сервисы и не
вставлять текст в неподтверждённое или защищённое поле.

**English summary:** Nadikt is an offline-first Windows voice input utility
with local ASR, safety-focused text insertion, and a portable Python core. The
project is currently in the research and risk-qualification phase; no end-user
application release is available yet.

> [!IMPORTANT]
> Исходный код приложения ещё не создан. В репозитории находятся требования,
> архитектурные решения, исследования и disposable Windows insertion spike.
> Spike завершён с решением **REWORK** и не является production-компонентом.

## Зачем Nadikt

- **Локальная обработка** — аудио и распознанный текст не уходят в облако.
- **Русский + English** — отдельный режим для смешанной технической речи.
- **Безопасная вставка** — проверка target, protected fields, integrity level и
  clipboard ownership.
- **Сохранение результата** — ошибка отдельного этапа не должна уничтожать
  готовый или частичный текст.
- **Переносимое ядро** — общий ASR/VAD/text pipeline не зависит от Windows API
  и PySide6; Ubuntu adapter запланирован после Windows MVP.

## Текущий Статус

| Область | Статус |
|---|---|
| Требования Windows MVP | Согласованы, ТЗ v0.2 |
| Архитектура | Explicit Architecture, стратегия `HYBRID` |
| Windows insertion spike | `REWORK`, controlled classic Win32 cases пройдены |
| GigaAM/faster-whisper benchmark | Запланирован |
| Переносимое ядро | Не начато |
| PySide6 desktop shell | Не начат |
| Installer / release | Отсутствует |

## Быстрый Старт Для Разработчика

```powershell
git clone https://github.com/rokolslab/nadikt.git
cd nadikt
cd experiments/windows_insertion
python -m unittest discover -s tests
```

Ожидаемый результат на Python 3.12: все unit/contract tests проходят. Команда
проверяет experiment и не устанавливает приложение.

Для controlled Windows self-check:

```powershell
python fixtures/classic_target.py --self-check
```

Fixture использует только synthetic payload. Не запускайте manual insertion
CLI в пользовательские приложения без изучения
[`experiments/windows_insertion/README.md`](experiments/windows_insertion/README.md).

## Документация

| Раздел | Назначение |
|---|---|
| [Центр документации](docs/README.md) | Полная карта требований, архитектуры и исследований |
| [Начало работы](docs/getting-started.md) | Клонирование, окружение и доступные команды |
| [Тестирование](docs/testing.md) | Automated checks, controlled fixtures и safety rules |
| [Техническое задание](docs/requirements/Nadikt_TZ_v0.2.md) | Канонические требования Windows MVP |
| [Архитектура](docs/architecture/Nadikt_development_strategy.md) | Стратегия общего ядра и platform adapters |
| [ADR-001](docs/architecture/ADR-001-codebase-strategy.md) | Решение `HYBRID` и условия пересмотра |
| [Windows insertion spike](docs/research/windows_insertion_spike_results.md) | Evidence, ограничения и решение `REWORK` |
| [Участие в разработке](CONTRIBUTING.md) | Workflow, quality gates и правила изменений |
| [Безопасность](SECURITY.md) | Как сообщить об уязвимости |

## Принципы Конфиденциальности

- не журналировать аудио, transcript, словарь и clipboard payload;
- не добавлять автоматическую телеметрию;
- не загружать модели или данные из сети в основном runtime;
- использовать только synthetic fixtures в automated tests;
- трактовать неизвестную target/clipboard capability как fail-closed.

## Участие

Перед изменениями прочитайте [CONTRIBUTING.md](CONTRIBUTING.md). Для ошибок и
предложений используйте GitHub Issues. Уязвимости и возможные утечки данных не
публикуйте в открытых issues — следуйте [SECURITY.md](SECURITY.md).

## Лицензия

Собственный код и документация Nadikt распространяются по лицензии
[MIT](LICENSE). Сторонние зависимости, модели и assets сохраняют собственные
лицензии и должны проходить отдельную provenance-проверку.
