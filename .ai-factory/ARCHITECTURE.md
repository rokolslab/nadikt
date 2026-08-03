# Архитектура: Explicit Architecture (Technical Layer)

## Обзор

Nadikt строится как единое desktop-приложение с явными внутренними слоями и портами/адаптерами. Домен и application layer описывают состояния диктовки, сценарии, правила обработки текста и контракты внешних возможностей. PySide6, Windows API, SQLite, аудиобиблиотеки и ASR SDK являются заменяемыми внешними деталями.

Шаблон выбран из-за обязательной переносимости общего ядра, нескольких ASR backend, сложного lifecycle ресурсов и критичных границ безопасности вставки. Microservices не нужны: приложение развёртывается одним автономным процессом и не имеет серверного масштаба.

## Обоснование решения

- **Тип проекта:** автономное однопользовательское desktop-приложение с потоковой обработкой аудио и системной интеграцией.
- **Технологический стек:** Python, PySide6, SQLite через `sqlite3`, GigaAM и faster-whisper за адаптерами.
- **Ключевой фактор:** внутренние правила не должны зависеть от ОС, UI, хранилища или конкретного ASR SDK.
- **Дополнительный фактор:** ошибки одного сегмента или внешнего API должны локализоваться без потери результата и завершения фонового процесса.

## Целевая структура каталогов

Это целевая структура для начала реализации. `aif init` её не создаёт.

```text
src/
`-- nadikt/
    |-- domain/                         # чистые модели, правила и порты
    |   |-- dictation/                  # состояния, сегменты, результаты, ошибки
    |   |-- text/                       # команды, словарь и нормализация
    |   |-- model_packages/             # манифесты и правила совместимости
    |   `-- ports/                      # Protocol/ABC внешних возможностей
    |       |-- asr.py
    |       |-- audio.py
    |       |-- platform.py
    |       `-- repositories.py
    |-- application/                    # use cases и orchestration
    |   |-- commands/                   # start, stop, cancel, switch model
    |   |-- services/                   # pipeline, diagnostics, model lifecycle
    |   `-- dto/                        # данные на границах application layer
    |-- infrastructure/                 # outbound adapters
    |   |-- asr/
    |   |   |-- gigaam.py
    |   |   `-- faster_whisper.py
    |   |-- audio/                      # capture, pre-buffer, VAD, segmentation
    |   |-- persistence/                # sqlite3, migrations, atomic settings
    |   |-- model_packages/             # локальная установка и checksum
    |   `-- platform/
    |       |-- windows/                # WindowsAdapter и системные API
    |       `-- linux/                  # будущий LinuxAdapter
    |-- presentation/                   # inbound adapters
    |   |-- qt/                         # tray, settings, overlay, notifications
    |   `-- cli/                        # ранний прототип и benchmark entry point
    `-- bootstrap.py                    # composition root, единственное связывание
tests/
|-- unit/                               # domain/application без SDK и ОС
|-- contract/                           # одинаковые проверки реализаций портов
|-- integration/                        # SQLite, ASR package, audio pipeline
`-- windows/                            # hotkey, focus, clipboard, insertion
benchmarks/                             # воспроизводимые ASR/VAD испытания
model_packs/                            # схемы и тестовые метаданные, не веса в Git
packaging/
|-- windows/
`-- linux/
docs/
```

Не создавайте пустые каталоги заранее. Добавляйте часть структуры вместе с первым реальным use case или адаптером.

## Текущие реализованные элементы

На 2026-07-27 создана первая минимальная часть целевой структуры для ASR benchmark:

- `src/nadikt/domain/ports/asr.py` - SDK-neutral контракт ASR engine lifecycle, metadata, capabilities и segment transcript result.
- `src/nadikt/infrastructure/asr/` - optional SDK-backed ASR probe adapters для GigaAM/faster-whisper с lazy imports; fake-backed на текущем этапе, не composition root.
- `benchmarks/asr/` - standard-library helpers для dataset/model manifests, versioned run profiles/result schemas, dry-run, local package probe runner, resource timing, segmentation validation, package integrity, privacy audit и quality metrics.
- `model_packs/` - documentation и example inventory manifests без model weights.
- `tests/contract/` - contract tests для benchmark harness без реальных моделей.

Эти элементы не являются точкой входа приложения и не фиксируют финальный выбор ASR backend.

## Правила зависимостей

Зависимости направлены внутрь:

```text
bootstrap -> presentation -> application -> domain
bootstrap -> infrastructure -> application/domain
```

- Разрешено: `domain` импортирует только Python standard library и собственные доменные модули.
- Разрешено: `application` импортирует `domain` и получает реализации портов через конструкторы.
- Разрешено: `infrastructure` импортирует контракты `domain`/`application` и внешние SDK.
- Разрешено: `presentation` вызывает application use cases и отображает DTO/состояния.
- Разрешено: `bootstrap.py` импортирует все слои для сборки object graph.
- Запрещено: `domain` или `application` импортируют PySide6, `sqlite3`, Windows API, GigaAM, faster-whisper или библиотеку аудиозахвата.
- Запрещено: ASR-адаптер обращается к Qt, буферу обмена, пользовательскому словарю или платформенному окну.
- Запрещено: Qt widget выполняет SQL, распознавание, нормализацию либо системную вставку напрямую.
- Запрещено: адаптеры импортируют друг друга или становятся неявным composition root.

`sqlite3` входит в standard library, но остаётся инфраструктурной зависимостью: домен не должен знать SQL, таблицы, connection или row.

## Взаимодействие слоёв

- UI преобразует Qt events в application commands; application публикует собственные состояния или DTO. Qt signals не проходят внутрь application/domain.
- Application service координирует порты аудио, ASR, хранения и платформы. Бизнес-инварианты состояния остаются в domain objects.
- Аудиосегменты получают монотонный идентификатор. Сборщик результата принимает результаты по контракту и восстанавливает порядок независимо от backend.
- ASR adapters возвращают собственный тип результата Nadikt, а не объекты SDK.
- Платформенный порт разделяет операции hotkey, target window, clipboard, insertion, autostart и notification; крупный `WindowsAdapter` допустим только как facade над узкими реализациями.
- Долгие и блокирующие операции выполняются вне GUI thread. Выбор конкретного worker-механизма принадлежит presentation/bootstrap и не меняет application API.
- Смена модели является отдельным use case с явным запретом во время активной диктовки и rollback к последней работоспособной конфигурации.

## Ключевые принципы

1. **Чистое ядро:** переносимая логика не зависит от Qt, ОС, SQLite и ML SDK.
2. **Явный lifecycle:** загрузка, прогрев, отмена, выгрузка модели и переходы состояния диктовки представлены явными операциями.
3. **Одна модель:** composition/application layer гарантирует не более одной загруженной основной ASR-модели.
4. **Ограниченная память:** pipeline обрабатывает сегменты потоково и не накапливает полное аудио длительного сеанса.
5. **Сохранение результата:** успешные сегменты и последний итог переживают обработанную ошибку до безопасной выдачи пользователю.
6. **Privacy by construction:** чувствительные payload не передаются в logging API; журналы получают только безопасные технические поля.
7. **Offline by construction:** runtime открывает только локальные проверенные модельные пакеты и не подменяет их автоматической сетевой загрузкой.
8. **Контрактные тесты:** все реализации одного порта проходят общий набор тестов, а системная интеграция дополнительно проверяется на целевой ОС.

## Примеры кода

### Порт ASR внутри ядра

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SegmentTranscript:
    segment_id: int
    text: str


class AsrEngine(Protocol):
    def load(self, model_package: Path) -> None: ...
    def warm_up(self) -> None: ...
    def transcribe(self, segment_id: int, audio_path: Path) -> SegmentTranscript: ...
    def cancel(self) -> None: ...
    def close(self) -> None: ...
```

Этот модуль не импортирует типы GigaAM или faster-whisper. Если backend поддерживает дополнительные функции, он объявляет их через нормализованные capabilities, а не расширяет core типами SDK.

### Application service с внедрёнными портами

```python
class FinishDictation:
    def __init__(self, engine: AsrEngine, result_store: LastResultStore) -> None:
        self._engine = engine
        self._result_store = result_store

    def execute(self, session: DictationSession) -> FinalTranscript:
        session.require_recording()
        session.begin_recognition()

        for segment in session.pending_segments():
            transcript = self._engine.transcribe(segment.id, segment.audio_path)
            session.accept(transcript)

        result = session.finish()
        self._result_store.replace(result)
        return result
```

Конкретный ASR SDK и способ хранения последнего результата связываются в `bootstrap.py`. Обработанная ошибка преобразуется в application outcome на границе use case; UI не анализирует исключения SDK.

## Антипаттерны

- Не создавать модуль `utils.py` как место для несвязанных функций и обхода границ.
- Не передавать Qt objects, SQLite rows или SDK result objects в domain/application.
- Не строить один глобальный service locator с доступом из любого модуля.
- Не размещать весь pipeline в Qt slot или worker class.
- Не дублировать бизнес-логику для Windows и Linux.
- Не выполнять автоматическую загрузку модели при отсутствии локального пакета.
- Не логировать аудио, транскрипцию, словарь или clipboard даже на уровне `DEBUG`.
- Не добавлять CQRS, domain events или отдельный repository для каждого типа автоматически; вводить их только при реальной пользе.
- Не превращать технические подсистемы в microservices: сетевое разделение противоречит автономности и усложняет поставку.
