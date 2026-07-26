# ADR-001: стратегия кодовой базы

Дата: 26 июля 2026 г.

Статус: принято

## Контекст

Nadikt должен стать автономным приложением голосового ввода для Windows 10/11 x64 с будущим Ubuntu port. Общее Python-ядро не зависит от PySide6, Windows API и конкретного ASR SDK. Обязательны GigaAM/faster-whisper adapters, одна загруженная модель, bounded-memory segmentation длинной речи, privacy-safe logging и безопасная вставка с проверкой целевого окна и восстановлением clipboard.

Исследованы Handy, Voxtype, Whisper Key Local, VoiceType AI, VoxType, nerd-dictation и OpenWhispr на зафиксированных commit SHA. Подробные evidence, лицензии и оценки находятся в [`docs/research/repository_assessment.md`](../research/repository_assessment.md).

## Рассмотренные варианты

### Самостоятельная разработка без использования найденных решений

Преимущество - полный контроль над стеком и границами. Недостаток - повторное обнаружение уже известных failure modes в hotkeys, overlay, model lifecycle, Wayland output и clipboard races.

### Fork существующего приложения

Handy и OpenWhispr имеют зрелую cross-platform поставку, Voxtype - сильные ASR/output boundaries, Whisper Key - Python и Windows/faster-whisper. Однако ни один проект одновременно не выполняет обязательные условия fork:

- подтверждённое повторное использование не менее 70% архитектуры;
- Windows 10/11 и будущий Ubuntu port из общего ядра;
- GigaAM и faster-whisper без переделки core;
- bounded-memory long dictation;
- полная offline/privacy модель Nadikt;
- безопасный Windows insertion contract;
- удаление лишних функций дешевле собственного минимального ядра.

У VoxType отсутствует лицензия приложения, nerd-dictation использует GPL, а остальные проекты имеют неоднородные model/assets/binary licenses.

### Собственная кодовая база с выборочным использованием решений

Nadikt сохраняет утверждённый стек и архитектуру. Сторонние проекты используются как evidence для contracts, failure modes, experiments и, после отдельной проверки происхождения, отдельных permissive-компонентов.

## Критерии

1. Совместимость с автономностью и privacy требованиями.
2. Реальная Windows 10/11 интеграция и ранняя проверка вставки.
3. Переносимое core для последующего Ubuntu adapter.
4. Engine-neutral GigaAM/faster-whisper lifecycle.
5. Работа на CPU-only Intel Core i3 с одной моделью.
6. Bounded-memory VAD/segmentation без лимита сессии.
7. Контролируемая license closure приложения, моделей, ресурсов и binaries.
8. Сопровождаемость без постоянного разрешения конфликтов с unrelated upstream.

## Решение

`HYBRID`

Разрабатывать Nadikt как самостоятельную Python/PySide6 кодовую базу в текущем репозитории и выборочно использовать проверенные архитектурные решения либо отдельно одобренные permissive-компоненты.

Основные ориентиры:

- Handy - one-engine ownership, GigaAM integration evidence, VAD/hotkey scenarios, Windows no-activate overlay и package smoke tests;
- Voxtype - ASR capabilities, model lifecycle, eager chunking, Linux output fallback и Wayland OSD protocol;
- VoiceType AI - target HWND guard и negative insertion cases;
- Whisper Key - WASAPI/soxr, faster-whisper CPU INT8, Unicode SendInput и tray/hotkey scenarios;
- OpenWhispr - Linux X11/Wayland adapters, native helper CI и external ASR shim;
- VoxType и nerd-dictation - только read-only идеи из-за отсутствующей лицензии и GPL соответственно.

Сторонний application code не переносится автоматически. Перед любым переносом создаётся provenance record: repository, file, commit SHA, license, copyright notice, характер изменения и место использования. После первого одобренного переноса создаётся `THIRD_PARTY_NOTICES.md`; до этого файл не заполняется предположениями.

## Аргументы

1. Ни один кандидат не прошёл независимый fork gate; лучший общий балл Handy 3,40/5 не устраняет reuse ниже 70%, privacy conflicts и unsafe insertion gaps.
2. Утверждённый Python/PySide6 стек и Explicit Architecture позволяют изолировать ASR/platform dependencies лучше, чем глубокая переделка Tauri, Rust daemon или Electron продукта.
3. Выборочное использование уже найденных failure modes снижает риск greenfield-разработки без наследования cloud/history/meeting scope и mixed-license release bundles.

## Последствия

Положительные:

- contracts Nadikt определяются требованиями продукта, а не API одного upstream;
- GigaAM и faster-whisper можно benchmark и заменять независимо;
- Windows insertion и Linux adapter получают собственные acceptance criteria;
- приложение не наследует постоянную историю, cloud fallback, telemetry или unrelated product modes;
- model packages и third-party notices проектируются с начала поставки.

Отрицательные:

- потребуется реализовать desktop shell, platform adapters и orchestration самостоятельно;
- нельзя считать наличие функции у конкурента доказательством её надёжности;
- отдельные permissive-компоненты потребуют provenance, notices и regression tests;
- packaging/signing/Wayland integration нельзя получить бесплатно из одного upstream.

## Риски

1. Windows insertion может оказаться сложнее оценённого из-за UI Automation, UIPI, browser controls, 1С и нескольких clipboard formats.
2. GigaAM/faster-whisper могут не уложиться в latency/RAM цели на Intel Core i3; решение модели остаётся за benchmark.
3. Linux hotkeys/output на Wayland потребуют compositor-specific capabilities и документированных ограничений.
4. Лицензии конкретных model weights и native binaries могут ограничить выбранную схему offline-поставки.
5. Избыточное заимствование идей без строгих ports может повторно создать coupling исследованных проектов.

## Условия пересмотра

Решение пересматривается, если новый или существенно изменившийся кандидат одновременно предоставляет:

- совместимую license closure кода и распространяемых artifacts;
- не менее 70% подтверждённого architecture reuse;
- production Windows 10/11 и общий Linux-portable core;
- заменяемый GigaAM/faster-whisper boundary;
- bounded-memory segmentation и сохранение частичных результатов;
- insertion safety по acceptance matrix Nadikt;
- доказательство, что удаление unrelated scope дешевле собственного core.

Отдельный успешный build, ASR benchmark или MIT-файл в root не является достаточным основанием для пересмотра.
