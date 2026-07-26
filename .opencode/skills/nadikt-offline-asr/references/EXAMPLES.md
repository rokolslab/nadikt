# Примеры интеграции и benchmark

## Минимальный контракт

Это проектный пример границы, а не утверждённая финальная структура модулей:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AsrSegmentResult:
    text: str
    start_seconds: float
    end_seconds: float


class AsrEngine(Protocol):
    def load(self, model_package: Path) -> None: ...
    def warm_up(self) -> None: ...
    def transcribe_segment(self, audio_path: Path) -> AsrSegmentResult: ...
    def cancel(self) -> None: ...
    def close(self) -> None: ...
```

Реальный контракт должен также выражать readiness, метаданные и capabilities. Не добавляй методы только ради конкретного SDK.

## Локальный faster-whisper

```python
from pathlib import Path

from faster_whisper import WhisperModel


def transcribe_local(model_dir: Path, audio_path: Path) -> str:
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Local model package is missing: {model_dir}")

    model = WhisperModel(
        str(model_dir),
        device="cpu",
        compute_type="int8",
    )
    segments, _ = model.transcribe(
        str(audio_path),
        beam_size=5,
        language="ru",
    )
    return "".join(segment.text for segment in segments).strip()
```

Ключевые свойства примера: локальный путь вместо Hub name, CPU INT8 и полное потребление ленивого генератора. Для production добавь lifecycle, отмену, нормализованный результат и безопасные ошибки без текста пользователя.

## Некорректный offline-вызов

```python
# Нельзя использовать в runtime Nadikt: имя может вызвать сетевую загрузку.
model = WhisperModel("small", device="cpu", compute_type="int8")
```

## Запись результата benchmark

```text
run_id: fw-small-int8-001
os: Windows 11 x64
cpu: Intel Core i3 10th Gen
ram_gib: 16
engine: faster-whisper <exact version>
model: Whisper small <exact revision and checksum>
device: cpu
compute_type: int8
threads: <value>
beam_size: <value>
vad: <configuration>
dataset_revision: <value>
cold_load_seconds: <value>
first_result_seconds: <value>
rtf: <value>
peak_rss_mib: <value>
wer_ru: <value>
cer_ru: <value>
english_term_accuracy: <value>
latin_preservation_rate: <value>
```

## Offline acceptance

1. Подготовить чистый профиль без кешей Hub.
2. Установить приложение и модельный пакет локально.
3. Заблокировать исходящий сетевой доступ.
4. Выполнить холодный запуск, прогрев, короткую и длинную диктовку.
5. Переключить режимы и убедиться, что прежняя модель освобождена.
6. Повредить копию модельного пакета и проверить отказ до загрузки.
7. Просмотреть журналы на отсутствие аудио и транскрипции.
8. Повторить диктовку после обработанной ошибки.
