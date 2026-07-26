# Оценка открытых репозиториев голосового ввода

Дата проверки: 26 июля 2026 г.

Статус: завершено, решение принято в ADR-001

## Цель и границы

Цель исследования - выбрать стратегию кодовой базы Nadikt: `GREENFIELD`, `FORK <repository>` или `HYBRID`. Исследование не разрешает перенос стороннего кода, создание fork, подключение Git submodule, использование GPL-кода, кода без лицензии или распространение весов моделей.

Лицензионные выводы ниже являются технической оценкой первичных источников, а не юридической гарантией. Неоднозначные условия должны быть отдельно проверены до распространения производного продукта или стороннего компонента.

## Методика

### Источники и воспроизводимость

Для каждого проекта фиксируются URL, владелец, проверенная ветка, полный commit SHA и дата проверки. Приоритет источников:

1. файлы репозитория на зафиксированном commit;
2. release и release assets;
3. GitHub Actions и иная CI-конфигурация;
4. issue и pull request проекта;
5. документация владельца проекта, связанная с репозиторием.

README используется как заявление проекта, но не как единственное доказательство реализации. Рекламные страницы и поисковые сниппеты не являются достаточным источником. Отсутствие найденного доказательства описывается как `не найдено в проверенной ревизии`, а отсутствие измерений - как `данные отсутствуют`.

В таблицах применяются обозначения:

- **Факт** - прямо подтверждён исходным кодом, manifest, CI, release или лицензией на зафиксированной ревизии.
- **Вывод** - инженерная интерпретация нескольких фактов; приводится обоснование.
- **Оценка** - балл по шкале ниже с указанием причины.
- **Неизвестно** - первичного доказательства недостаточно; значение не заменяется предположением.

### Оценочная шкала

Каждый критерий получает балл от 0 до 5:

| Балл | Интерпретация |
|---:|---|
| 0 | Требование не поддерживается либо имеется блокирующее противоречие. |
| 1 | Поддержка номинальная; требуется почти полная замена подсистемы. |
| 2 | Есть отдельные полезные части, но необходима крупная переделка. |
| 3 | Частичное соответствие; нужны ограниченные, но существенные изменения. |
| 4 | Хорошее соответствие; остаются локальные пробелы и проверки. |
| 5 | Требование подтверждено реализацией и воспроизводимыми проверками. |

Итог рассчитывается в диапазоне 0-5:

```text
total = license * 0.20
      + architecture * 0.20
      + windows * 0.15
      + ubuntu * 0.10
      + asr_extensibility * 0.15
      + cpu * 0.10
      + insertion * 0.05
      + maturity * 0.05
```

Веса суммируются до 100%. В таблице итог отображается с двумя десятичными знаками с десятичным округлением `HALF_UP`, но сравнение выполняется по неокруглённому значению. Неизвестные benchmark-показатели не получают балл как за подтверждённую поддержку.

### Оценка повторного использования

Процент повторного использования относится к архитектуре и поведению, а не к строкам кода. Для сопоставимости проверяются 20 областей Nadikt:

1. lifecycle и состояния диктовки;
2. захват аудио;
3. предварительный буфер;
4. VAD;
5. сегментация длинной речи;
6. абстракция ASR;
7. lifecycle одной загруженной модели;
8. автономные модельные пакеты;
9. сборка текста сегментов;
10. нормализация;
11. голосовые команды форматирования;
12. пользовательский словарь;
13. глобальные горячие клавиши;
14. сохранение и проверка целевого окна;
15. безопасный clipboard и вставка;
16. плавающее окно без захвата фокуса;
17. tray, настройки и диагностика;
18. Windows platform adapter;
19. Linux platform adapter;
20. автономная упаковка, privacy-safe logging и CI.

Область получает 1, если применима с локальными изменениями, 0,5 при существенной адаптации и 0 при замене. Оценка равна сумме баллов, делённой на 20, и приводится как ориентировочный диапазон с шагом 5%. Совпадение UI или наличие функции без подходящей границы зависимостей не считается архитектурным reuse.

### Независимый fork gate

Рекомендация `FORK` допустима только при одновременном выполнении всех условий:

1. однозначная совместимая лицензия кода и нужных распространяемых компонентов;
2. повторно используется не менее 70% архитектуры;
3. GigaAM или иной ASR adapter добавляется без переписывания ядра;
4. обязательная облачная зависимость отсутствует;
5. Windows 10/11 реально поддерживается;
6. будущий Ubuntu port возможен без отдельного ядра;
7. удаление лишних функций проще собственного минимального ядра;
8. сопровождение не требует постоянного конфликтного слияния upstream.

Провал одного условия блокирует `FORK` независимо от общего балла. `HYBRID` означает собственную кодовую базу Nadikt и только выборочное использование разрешённых компонентов или архитектурных идей с последующей таблицей происхождения.

## Проверенные ревизии

Все репозитории проверены на 26 июля 2026 г. Ссылки на commit неизменяемы.

| Проект | Официальный репозиторий | Default branch | Проверенный commit и дата | Release status |
|---|---|---|---|---|
| Handy | [`cjpais/Handy`](https://github.com/cjpais/Handy) | `main` | [`6cad594cdba3aaa99555183fcb1e7b5a3967168e`](https://github.com/cjpais/Handy/commit/6cad594cdba3aaa99555183fcb1e7b5a3967168e), 2026-07-25 | [`v0.9.4`](https://github.com/cjpais/Handy/releases/tag/v0.9.4), 2026-07-21 |
| Voxtype | [`peteonrails/voxtype`](https://github.com/peteonrails/voxtype) | `dev` | [`f97276661d9b723aa3236f03879650a2a06c3ec3`](https://github.com/peteonrails/voxtype/commit/f97276661d9b723aa3236f03879650a2a06c3ec3), 2026-07-16 | [`v1.0.0-rc1`](https://github.com/peteonrails/voxtype/releases/tag/v1.0.0-rc1), 2026-06-04 |
| Whisper Key | [`PinW/whisper-key-local`](https://github.com/PinW/whisper-key-local) | `master` | [`86ce94f2c18811b7d359a38b4423ae225916279d`](https://github.com/PinW/whisper-key-local/commit/86ce94f2c18811b7d359a38b4423ae225916279d), 2026-07-02 | [`v0.8.2`](https://github.com/PinW/whisper-key-local/releases/tag/v0.8.2), 2026-06-12 |
| VoiceType AI | [`devaxl/VoiceType-AI`](https://github.com/devaxl/VoiceType-AI) | `main` | [`26334e5143cddc28bfa6351751df36b67efdac4f`](https://github.com/devaxl/VoiceType-AI/commit/26334e5143cddc28bfa6351751df36b67efdac4f), 2026-07-09 | [`v0.1.6`](https://github.com/devaxl/VoiceType-AI/releases/tag/v0.1.6) |
| VoxType | [`melody0709/VoxType`](https://github.com/melody0709/VoxType) | `cpp-integration` | [`be65fcca35669d94af86cc563551b8ac940106dc`](https://github.com/melody0709/VoxType/commit/be65fcca35669d94af86cc563551b8ac940106dc), 2026-07-12 | README указывает 0.9.7; последний опубликованный release [`v0.9.3`](https://github.com/melody0709/VoxType/releases/tag/v0.9.3) |
| nerd-dictation | [`ideasman42/nerd-dictation`](https://github.com/ideasman42/nerd-dictation) | `main` | [`41f372789c640e01bb6650339a78312661530843`](https://github.com/ideasman42/nerd-dictation/commit/41f372789c640e01bb6650339a78312661530843), 2025-10-10 | GitHub releases и tags отсутствуют |
| OpenWhispr | [`OpenWhispr/openwhispr`](https://github.com/OpenWhispr/openwhispr) | `main` | [`ab201b3900caf582e9d70448414c83935fd7c595`](https://github.com/OpenWhispr/openwhispr/commit/ab201b3900caf582e9d70448414c83935fd7c595), 2026-07-23 | [`v1.7.6`](https://github.com/OpenWhispr/openwhispr/releases/tag/v1.7.6) |

На момент проверки все семь репозиториев публичны, не архивированы и не помечены GitHub как fork. Официальность OpenWhispr подтверждают принадлежность репозитория организации [OpenWhispr](https://github.com/OpenWhispr), взаимная ссылка с [официальным сайтом](https://openwhispr.com) и документация платформ, направляющая пользователей к releases этого репозитория.

## Лицензионная инвентаризация

Лицензия корневого репозитория не применяется автоматически к внешним моделям, товарным знакам и скачиваемым бинарникам. Таблица отражает только найденные первичные сведения на проверенных ревизиях.

| Проект | Код приложения | ASR/VAD runtime | Веса моделей | Ресурсы и распространяемые компоненты | Вывод для Nadikt |
|---|---|---|---|---|---|
| Handy | [MIT](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/LICENSE) | Основные `transcribe-cpp`, `transcribe-rs`, Silero VAD и ONNX Runtime имеют permissive-лицензии, но конкретные версии и notices требуют SBOM-проверки | Каталог содержит MIT, Apache-2.0, CC-BY-4.0, CC-BY-NC-4.0 и `other`; единая лицензия отсутствует | [README](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/README.md#L496-L500) исключает название, logo, icon и brand assets из open source; полный notices-комплект не найден | Код технически доступен по MIT, но брендинг, каждый model package и native binary должны проверяться отдельно |
| Voxtype | [MIT](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/LICENSE) | whisper.cpp/whisper-rs, ONNX Runtime, Silero VAD и несколько engines используют permissive-лицензии; Soniox является внешним сервисом | Встречаются MIT, Apache-2.0, CC-BY-4.0 и Moonshine Community License с non-commercial ограничениями | [`THIRD_PARTY.md`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/THIRD_PARTY.md) неполон; происхождение engine logos и части OSD assets не установлено | Архитектурные идеи пригодны; перенос компонента требует проверки его точной dependency/model closure |
| Whisper Key | [MIT](https://github.com/PinW/whisper-key-local/blob/86ce94f2c18811b7d359a38b4423ae225916279d/LICENSE) | faster-whisper и CTranslate2 - MIT, sherpa-onnx - Apache-2.0; [TEN-VAD](https://github.com/TEN-framework/ten-vad/blob/22a3bcd4509d0faaa8eef4881e8af5f39c178950/LICENSE) содержит дополнительные ограничения и не должен автоматически считаться permissive | Настроенные Whisper/Distil model cards преимущественно MIT; streaming Zipformer указан как Apache-2.0; revision не закрепляется приложением | WAV/icons не имеют отдельного provenance; включён `portaudio.dll`, но в проекте не найден полный PortAudio notice или SBOM | Возможны отдельные MIT-фрагменты, но TEN-VAD и состав release EXE требуют отдельного анализа |
| VoiceType AI | [MIT](https://github.com/devaxl/VoiceType-AI/blob/26334e5143cddc28bfa6351751df36b67efdac4f/LICENSE) | Локального ASR runtime нет; OpenAI/Groq и postprocessing providers регулируются своими условиями | Локальные веса не распространяются | Отдельные лицензии icons/assets не найдены; права на товарные знаки MIT не предоставляет | Разрешённый код не решает offline ASR; полезны только идеи и тестовые сценарии вставки |
| VoxType | **LICENSE отсутствует**: запрос GitHub API `LICENSE` на проверенном SHA вернул `Not Found` | sherpa-onnx/kaldi-native-fbank - Apache-2.0, ONNX Runtime/Silero VAD - MIT, Opus - BSD-style; aria2 имеет GPL-2.0 и требует проверки способа поставки | SenseVoice использует custom FunASR Model License; статус FireRed VAD/ASR artifacts должен проверяться отдельно | Нет единого notices/SBOM; downloader не доказывает право перераспространения моделей | Публичность репозитория не разрешает копирование, модификацию или fork; использовать только как источник идей до явной лицензии |
| nerd-dictation | Source headers указывают `GPL-2.0-or-later`, а root [`LICENSE`](https://github.com/ideasman42/nerd-dictation/blob/41f372789c640e01bb6650339a78312661530843/LICENSE) содержит GPLv3; точную project declaration следует уточнить | Vosk API - Apache-2.0 | Модели устанавливает пользователь; конкретная модель и лицензия не закреплены | Bundled icons, sounds и модели отсутствуют; recorder/output tools являются внешними зависимостями | Copyleft-код не подключать по установленному пользователем ограничению; допустимо изучение поведения |
| OpenWhispr | [MIT](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/LICENSE) | whisper.cpp/llama.cpp - MIT, sherpa-onnx/Qdrant - Apache-2.0; состав также включает компоненты с иными условиями | Parakeet/Nemotron и local LLM имеют model-specific лицензии, включая CC-BY-4.0 и NVIDIA-specific terms | `ffmpeg-static@5.2.0` заявляет GPL-3.0-or-later; NirCmd имеет custom freeware terms; artifact-level compliance требует проверки | MIT app code не устраняет GPL/custom/model obligations большой supply-chain поверхности |

### Лицензионные блокеры

1. VoxType не имеет лицензии приложения, поэтому code reuse и fork запрещены без отдельного разрешения.
2. nerd-dictation использует GPL; по условиям задачи его код не подключается.
3. Whisper Key зависит от TEN-VAD с дополнительными ограничениями, которые требуют отдельной юридической оценки.
4. Handy, Voxtype и OpenWhispr предлагают модели с неоднородными лицензиями; каталог нельзя распространять как единый MIT-компонент.
5. У OpenWhispr наиболее широкая supply-chain поверхность, включая GPL/custom бинарники; у проектов в целом нет достаточного единого SBOM/notices для автоматического переноса release состава.

### Компонентная трассировка лицензий

В таблице перечислены проверенные компоненты, которые существенны для возможной поставки. `Не установлено` является результатом проверки, а не разрешением на использование.

| Проект | Компонент | Точная лицензия или статус | Первичный источник |
|---|---|---|---|
| Handy | Application code | MIT | [`LICENSE`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/LICENSE) |
| Handy | `transcribe-rs`, `transcribe-cpp`, ONNX paths | Версии зафиксированы manifest; license metadata заявляет MIT, но release closure требует notices | [`Cargo.toml`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/Cargo.toml#L72-L86) |
| Handy | Model weights | Mixed: MIT, Apache-2.0, CC-BY-4.0, CC-BY-NC-4.0, `other`; единой лицензии нет | [`catalog.json`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/catalog/catalog.json) |
| Handy | Name/logo/icon/brand | Не входят в open-source grant | [`README.md`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/README.md#L496-L500) |
| Voxtype | Application code | MIT | [`LICENSE`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/LICENSE) |
| Voxtype | whisper/ONNX/Parakeet engines | Versions/features зафиксированы; конкретная closure требует SBOM | [`Cargo.toml`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/Cargo.toml#L82-L93) |
| Voxtype | Model weights | Model-specific: встречаются MIT, Apache-2.0, CC-BY-4.0 и non-commercial Moonshine Community License | [`model.rs`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/src/setup/model.rs#L240-L377) |
| Voxtype | GTCRN и assets | GTCRN указан как MIT; полный provenance icons/logos не установлен | [`THIRD_PARTY.md`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/THIRD_PARTY.md) |
| Whisper Key | Application code | MIT | [`LICENSE`](https://github.com/PinW/whisper-key-local/blob/86ce94f2c18811b7d359a38b4423ae225916279d/LICENSE) |
| Whisper Key | faster-whisper/CTranslate2 | MIT; версия и extra зафиксированы package metadata | [`pyproject.toml`](https://github.com/PinW/whisper-key-local/blob/86ce94f2c18811b7d359a38b4423ae225916279d/pyproject.toml) |
| Whisper Key | TEN-VAD | Custom terms с дополнительными ограничениями | [`TEN-VAD LICENSE`](https://github.com/TEN-framework/ten-vad/blob/22a3bcd4509d0faaa8eef4881e8af5f39c178950/LICENSE) |
| Whisper Key | Model weights | Model-specific; application downloads не pin-ят immutable revision | [`model_registry.py`](https://github.com/PinW/whisper-key-local/blob/86ce94f2c18811b7d359a38b4423ae225916279d/src/whisper_key/model_registry.py) |
| Whisper Key | WAV/icons/PortAudio DLL | Per-asset provenance и полный PortAudio notice не найдены | [Repository tree](https://github.com/PinW/whisper-key-local/tree/86ce94f2c18811b7d359a38b4423ae225916279d) |
| VoiceType AI | Application code | MIT | [`LICENSE`](https://github.com/devaxl/VoiceType-AI/blob/26334e5143cddc28bfa6351751df36b67efdac4f/LICENSE) |
| VoiceType AI | ASR/model weights | Локальный runtime и локальные weights отсутствуют; cloud providers имеют внешние terms | [`stt.rs`](https://github.com/devaxl/VoiceType-AI/blob/26334e5143cddc28bfa6351751df36b67efdac4f/src-tauri/src/stt.rs) |
| VoiceType AI | Icons/assets | Отдельная license/provenance не найдена | [Repository tree](https://github.com/devaxl/VoiceType-AI/tree/26334e5143cddc28bfa6351751df36b67efdac4f) |
| VoxType | Application code/assets | License отсутствует | [Repository tree](https://github.com/melody0709/VoxType/tree/be65fcca35669d94af86cc563551b8ac940106dc) |
| VoxType | sherpa-onnx/ONNX Runtime/Silero | Upstream Apache-2.0/MIT, но точная distributed closure и notices не установлены | [`ARCHITECTURE.md`](https://github.com/melody0709/VoxType/blob/be65fcca35669d94af86cc563551b8ac940106dc/ARCHITECTURE.md) |
| VoxType | FireRed/SenseVoice weights | Custom/model-specific; redistribution status выбранных artifacts не установлен | [`download_models.ps1`](https://github.com/melody0709/VoxType/blob/be65fcca35669d94af86cc563551b8ac940106dc/download_models.ps1) |
| nerd-dictation | Application code | Source headers: GPL-2.0-or-later; root text: GPLv3, требуется уточнение декларации | [`LICENSE`](https://github.com/ideasman42/nerd-dictation/blob/41f372789c640e01bb6650339a78312661530843/LICENSE) |
| nerd-dictation | Vosk API | Apache-2.0 | [`vosk-api COPYING`](https://github.com/alphacep/vosk-api/blob/e61c01d4968b6efe6abe72909860554a3eba1c24/COPYING) |
| nerd-dictation | Model weights | Не закреплены проектом; license зависит от вручную выбранной модели | [Model setup documentation](https://github.com/ideasman42/nerd-dictation/blob/41f372789c640e01bb6650339a78312661530843/README.md) |
| OpenWhispr | Application code | MIT | [`LICENSE`](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/LICENSE) |
| OpenWhispr | whisper.cpp/llama.cpp/sherpa-onnx/Qdrant | MIT/Apache-2.0 upstream; versions и downloads требуют artifact-level notices | [`package.json`](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/package.json) |
| OpenWhispr | `ffmpeg-static@5.2.0` | GPL-3.0-or-later metadata | [`package.json`](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/package.json#L150-L163) |
| OpenWhispr | NirCmd | Custom freeware redistribution terms; packaged composition требует проверки | [`download-nircmd.js`](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/scripts/download-nircmd.js) |
| OpenWhispr | Parakeet/Nemotron/LLM weights | Model-specific, включая CC-BY-4.0 и NVIDIA-specific terms; единой license нет | [Download scripts](https://github.com/OpenWhispr/openwhispr/tree/ab201b3900caf582e9d70448414c83935fd7c595/scripts) |

## Технический анализ

### Единообразная матрица подсистем

| Проект | Audio | VAD/segments | ASR/lifecycle | Postprocess/commands/dictionary | Hotkeys | Overlay/tray | Insertion/focus | Platform adapters | Models | Config/logging |
|---|---|---|---|---|---|---|---|---|---|---|
| Handy | CPAL/16 kHz | Silero; whole-session RAM | Engine enum; one model | Replacements/cloud LLM; dictionary incomplete | Toggle/PTT/cancel | Оба, mature | Clipboard/direct; no target/protected guard | Windows/Linux/macOS, Tauri-coupled | Network catalog/checksums, mixed licenses | Store/SQLite; transcript/history privacy conflict |
| Voxtype | CPAL | Energy/Silero; eager/streaming paths | Явный `Transcriber`; mixed managers | Punctuation/replacements/external commands | evdev toggle/PTT/cancel | Wayland OSD; Linux tray нет | Tool fallback/clipboard; no target/protected guard | Linux/macOS, Windows нет | Setup/download/integrity varies by engine | TOML/profiles; transcript INFO log |
| Whisper Key | sounddevice/WASAPI/soxr | TEN-VAD; whole-session RAM | Concrete faster-whisper | Corrections/hotwords; executable commands | Toggle/PTT/cancel | Tray да, overlay нет | SendInput/clipboard; no target/protected guard | Windows/macOS; Linux broken | HF registry, unpinned downloads | YAML; startup network/console transcript |
| VoiceType AI | CPAL | VAD/segments нет | Cloud STT only | Cloud refinement, limited local rules | Global shortcut | HUD/tray/settings present | HWND guard partial; protected behavior incompatible | Windows/macOS; Linux нет | Local model management нет | Local settings; provider secrets/cloud logs risk |
| VoxType | WASAPI/waveIn | Silero/FireRed; bounded long pipeline не найден | sherpa/native sessions | CT punctuation; dictionary/commands не найдены | Low-level Windows hook | Native HUD/tray | Clipboard/Unicode to current window | Windows-only | Download script, no app checksum closure | Native config/logs; persistent WAV |
| nerd-dictation | External parec/sox/pw-cat | Vosk endpointing, continuous | Vosk-coupled monolith | Numbers/custom Python; dictionary grammar | Внешняя привязка WM | Нет | Direct Linux tools to current focus | X11/Wayland tool branches | Manual path, no integrity metadata | CLI/executable config; minimal logs |
| OpenWhispr | Native/Electron helpers | VAD/meeting segments | Local/cloud/shim, broad lifecycle | Dictionary/AI/history/commands, overbroad | Cross-platform helpers | Tray/overlay/UI mature | Many fallbacks; strict target/protected guard not proven | Windows/X11/Wayland/macOS | Many download scripts and mixed models | Large config/history/cloud surface |

### Handy

#### Архитектура и границы

Handy - Tauri 2 приложение: Rust backend выполняет audio capture, VAD, ASR, hotkeys, insertion, persistence и platform integration, React/TypeScript frontend реализует настройки и overlay. Composition находится в [`src-tauri/src/lib.rs`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/lib.rs), сериализация recording/processing - в [`transcription_coordinator.rs`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/transcription_coordinator.rs).

Разделение managers лучше монолитного desktop handler, однако граница ASR представлена enum `LoadedEngine`, а managers зависят от Tauri state/events и конкретных SDK. Это не чистый порт уровня Nadikt: новый backend требует изменений enum, factory, model catalog, settings, packaging и frontend capabilities.

| Область | Факт на проверенном SHA | Значение для Nadikt |
|---|---|---|
| Audio | CPAL, mono conversion, resampling 16 kHz, reset VAD/resampler между сессиями | Полезный reference, но Rust implementation не переносится в Python напрямую |
| VAD/prebuffer | Silero VAD; около 450 ms prefill, onset и hangover разделены | Стоит проверить параметры в собственном benchmark, не копировать как норматив |
| Long dictation | [`recorder.rs`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/audio_toolkit/audio/recorder.rs#L600-L688) накапливает `processed_samples` всей сессии и после stop возвращает один `Vec<f32>` | Не выполняет bounded-memory segmentation, сохранение частичных результатов и проверку стыков |
| ASR | `transcribe-rs` для ONNX engines и `transcribe-cpp` для GGUF/GGML; faster-whisper отсутствует | ASR boundary полезна как reference, но не соответствует двум обязательным adapters Nadikt |
| Model lifecycle | Одна `Option<LoadedEngine>`; перед новой загрузкой прежний engine удаляется ([`transcription.rs`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/managers/transcription.rs#L510-L523)) | Выполняет основную идею одной модели, но rollback и запрет switch во время записи недостаточны |
| Model packages | Сетевой catalog/downloader, checksum и варианты quantization | Не является локальным versioned model package с обязательной license sidecar |
| Postprocessing | Есть substitutions и optional external/cloud LLM postprocessing | Cloud и смысловая коррекция исключаются; детерминированную часть нужно отделять |
| Commands/dictionary | Функции уже и иначе организованы, чем требования Nadikt | Требуется собственный engine-independent слой |
| Hotkeys | Tauri/global shortcut, PTT/toggle, debounce/cancellation | Сильный набор race-сценариев для Windows prototype |
| Overlay | На Windows применены no-focus/no-activate и mixed-DPI handling | Один из лучших reference для плавающего окна |
| Tray/settings | Зрелая desktop shell, single instance, updater и autostart | Функционально полезно, но связано с Tauri |
| History/logging | SQLite history хранит WAV и transcript; [`actions.rs`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/actions.rs#L738-L744) пишет transcript в debug log | Прямо противоречит privacy и отсутствию постоянной истории Nadikt |

#### GigaAM и CPU

Handy уже содержит GigaAM v3 ONNX INT8 и GigaAM GGUF CTC/RNN-T варианты. В [`catalog.json`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/catalog/catalog.json#L902-L1123) доступны quantization `Q4_K_M` - `F32`; default указан `Q8_0`. Это подтверждает техническую реализуемость GigaAM вне Python SDK, но не заменяет проверку официального model package и качества mixed RU/EN.

Whisper-family реализован через `transcribe-cpp`, не faster-whisper/CTranslate2. Добавление именно faster-whisper наиболее реалистично через отдельный локальный process adapter; иначе потребуется новый Rust binding и изменение build matrix. GigaAM как семейство уже подключён, но API Nadikt всё равно нельзя строить по внутренним типам Handy.

CPU-only поддержан, включая ONNX INT8 и GGUF quantization. Заявление README о скорости около 5x real-time на неопределённом i5 не содержит достаточной конфигурации. Данные холодной загрузки, RTF, peak RAM, WER/CER и RU/EN accuracy на Intel Core i3 10-го поколения отсутствуют.

#### Windows-вставка

[`clipboard.rs`](https://github.com/cjpais/Handy/blob/6cad594cdba3aaa99555183fcb1e7b5a3967168e/src-tauri/src/clipboard.rs) поддерживает clipboard paste, direct typing и восстановление непустого text/image. Не найдены:

- snapshot исходного HWND и проверка foreground window перед вставкой;
- различение поля внутри того же окна;
- запрет вставки в password/protected fields;
- сохранение file list, HTML/RTF и произвольных clipboard formats;
- подтверждение факта вставки до восстановления;
- гарантированное restoration при ошибке отправки клавиш;
- обработка UIPI/elevated target как отдельный outcome.

Риски подтверждают issues [#502](https://github.com/cjpais/Handy/issues/502) о вставке прежнего clipboard, [#434](https://github.com/cjpais/Handy/issues/434) о работе с elevated application и [#1755](https://github.com/cjpais/Handy/issues/1755) о зависимости paste methods от Enigo state. Overlay сам не крадёт focus, но это не защищает от пользовательской смены целевого окна во время ASR.

#### Платформы и зрелость

Handy выпускает Windows x64/ARM64 MSI и NSIS, macOS artifacts и Linux deb/rpm/AppImage. CI собирает Windows и Linux, выполняет package smoke checks, Windows signing и signed updater artifacts. Windows 10 не выделен в CI и не подтверждён отдельной acceptance matrix; Linux overlay выключен по умолчанию из-за риска focus stealing, Wayland insertion зависит от compositor/tools. Issue [#1742](https://github.com/cjpais/Handy/issues/1742) фиксирует Wayland auto-paste failure.

Проект активен: 752 commits с февраля 2025 г., 62 releases, `v0.9.4` от 2026-07-21. На HEAD cross-platform builds прошли, но Linux Rust test job имел 127 passed и 1 failed из-за catalog architecture `moss`. Автоматических acceptance tests для Word, browser, 1С, protected fields и clipboard formats нет.

#### Пригодность

- **Как основа fork:** нет.
- **Как архитектурный пример:** высокая для model ownership, VAD, hotkey races, no-activate overlay и packaging.
- **Ориентировочный architecture reuse:** 40-50%; прямой code reuse при Python/PySide6 близок к 0%.
- **Объём переделки:** 60-75%, включая core boundaries, long dictation, privacy, insertion и model packages.
- **Нежелательные зависимости/функции:** Tauri/Rust/React при принятом Python-стеке, cloud LLM, network catalog, persistent history, updater.
- **Upstream:** активная разработка и широкий scope создадут постоянные конфликты в глубоко изменённом fork.

### Voxtype

Voxtype - Rust daemon для Wayland с наиболее явными в выборке контрактами [`Transcriber`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/src/transcribe/mod.rs#L94-L335), VAD и [`TextOutput`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/src/output/mod.rs#L238-L551). Поддерживаются Whisper, Parakeet и несколько ONNX engines, preload/on-demand, idle eviction, eager chunking и streaming capabilities. GigaAM и faster-whisper можно добавить за существующей границей, предпочтительно как локальные subprocess adapters, но Whisper-specific `ModelManager`, config, setup и packaging потребуется расширить.

| Область | Результат |
|---|---|
| Audio/VAD | CPAL capture thread; energy/Silero/whisper VAD; обычный VAD часто отбрасывает пустую запись, а не выполняет полный segment lifecycle |
| Long dictation | Default `max_duration_secs=60`; есть eager chunking/streaming и отдельный тяжёлый meeting pipeline. Искусственный default limit конфликтует с Nadikt |
| Text pipeline | Spoken punctuation, replacements, filler filtering, profiles и external postprocess; external commands и англоцентричная пунктуация не переносятся как есть |
| Hotkeys | Linux evdev, PTT/toggle/cancel; требует доступа к `/dev/input` |
| UI | Wayland OSD через layer-shell/GTK/Quickshell; Linux tray отсутствует |
| Insertion | Fallback chain `wtype`, `eitype`, `dotool`, `ydotool`, `wl-copy`, `xclip`; clipboard restoration есть, target/focus/protected guard нет |
| Privacy | Local mode доступен, но есть remote/Soniox engines; [`daemon.rs`](https://github.com/peteonrails/voxtype/blob/f97276661d9b723aa3236f03879650a2a06c3ec3/src/daemon.rs#L1952-L1971) пишет transcript в INFO log |
| Platforms | Ubuntu Wayland является основной целью; X11 частичен; Windows implementation и packaging отсутствуют |
| CPU | CPU builds, ONNX INT8/Q4; авторские цифры на Ryzen 9 9900X3D не воспроизводят целевой i3 и не содержат RU/EN quality |
| Maturity | Активный проект, 63 releases; CI fmt/clippy/tests успешен, Nix job на HEAD упал при внешней подготовке |

- **Как основа fork:** нет, поскольку Windows отсутствует и Rust/Wayland shell противоречат MVP.
- **Как архитектурный пример:** очень высокая для ASR capabilities, lifecycle, chunking и output fallback.
- **Architecture reuse:** 60-70% как набор идей, 0-5% прямого Python code reuse.
- **Переделка:** 70-85% для Windows Nadikt.
- **Нежелательные зависимости:** evdev permissions, compositor tools, cloud engines, meeting/diarization scope, transcript logging.

### Whisper Key Local

Whisper Key - Python utility для Windows/macOS на faster-whisper. Это ближайший проект по языку и Windows prototype, но `StateManager` напрямую зависит от concrete `WhisperEngine`; самостоятельного `AsrEngine` contract нет.

| Область | Результат |
|---|---|
| Audio | sounddevice/PortAudio, WASAPI/CoreAudio, mono; Windows native rate конвертируется через soxr |
| VAD/long dictation | TEN-VAD precheck и silence timeout; default maximum 900 s, `0` означает unlimited; вся запись остаётся в RAM и передаётся одним массивом |
| ASR/models | faster-whisper уже встроен, default CPU/INT8; HF auto-download не pin-ит revision и не использует application checksum |
| GigaAM | После выделения небольшого `AsrEngine` protocol можно сохранить audio/tray/hotkeys, но segmentation и model lifecycle потребуют переработки |
| Commands | Сильный dispatcher `run`/`hotkey`/`type`, однако `shell=True` создаёт ненужный риск и системные команды запрещены Nadikt |
| UI | pystray, state icons, model/audio selection; overlay отсутствует |
| Insertion | Windows Unicode `SendInput` и clipboard+paste; clipboard восстанавливается после fixed delay, но исходный HWND и protected fields не проверяются |
| Privacy/network | File transcript logging default off, но полный transcript выводится в console; startup обращается к PyPI до применения update preference |
| Platforms | Windows implementation и release EXE есть без CI-подтверждения Windows 10/11; Linux selector ошибочно выбирает Windows adapter, Ubuntu не поддерживается |
| Maturity | 16 releases, но нет test suite, lint/type/build CI, lock hashes и воспроизводимой сборки EXE |

- **Как основа fork:** нет для долгосрочного ядра; возможен только disposable Windows experiment.
- **Как архитектурный пример:** средняя; полезны WASAPI/soxr, SendInput Unicode, tray и hotkey modes.
- **Architecture reuse:** 45-55%; прямой code reuse 20-30% только после component-level license review.
- **Переделка:** 45-60%.
- **Нежелательные зависимости:** TEN-VAD, concrete Whisper coupling, network updater/downloads, shell commands, отсутствие Linux/tests/CI.

### VoiceType AI

VoiceType AI - небольшой Tauri/Rust/React проект, но pipeline использует только облачные OpenAI/Groq STT и OpenAI/Anthropic refinement. В [`stt.rs`](https://github.com/devaxl/VoiceType-AI/blob/26334e5143cddc28bfa6351751df36b67efdac4f/src-tauri/src/stt.rs) нет локального ASR, VAD или bounded-memory segmentation. Добавление GigaAM/faster-whisper означает замену ASR и model lifecycle, а не новый adapter к готовому offline core.

Главная ценность - негативные сценарии Windows insertion в [`inject.rs`](https://github.com/devaxl/VoiceType-AI/blob/26334e5143cddc28bfa6351751df36b67efdac4f/src-tauri/src/inject.rs) и [`winfocus.rs`](https://github.com/devaxl/VoiceType-AI/blob/26334e5143cddc28bfa6351751df36b67efdac4f/src-tauri/src/winfocus.rs):

- исходный HWND сохраняется и перед вставкой сравнивается, но смена поля внутри того же окна не обнаруживается;
- clipboard guard сохраняет text либо image, но не совокупность HTML/RTF/file-list/custom formats;
- вставка подтверждается fixed delay, а не фактом принятия целевым control;
- общего character fallback после paste failure нет;
- classic Win32 `EDIT + ES_PASSWORD` распознаётся, но текст вводится посимвольно, тогда как Nadikt должен отказаться от автоматической вставки;
- browser/Electron/UWP protected fields не покрыты.

CI собирает frontend и Rust на Windows/macOS, но не запускает tests и не проверяет Linux. Проект молод: 12 commits, release `v0.1.6`; app-level CPU metrics неприменимы из-за cloud ASR.

- **Как основа fork:** нет из-за обязательного cloud pipeline и отсутствия Linux/offline core.
- **Как архитектурный пример:** средняя для target-window guard и тестовых сценариев вставки.
- **Architecture reuse:** 20-30%; прямой reuse при Python/PySide6 минимален.
- **Переделка:** 75-90%.
- **Нежелательные зависимости:** cloud providers, Tauri stack, semantic refinement.

### VoxType для Windows

VoxType - native C++/Win32 pipeline с WASAPI, Silero/FireRed VAD, sherpa-onnx, FireRedASR2/SenseVoice, CT-Transformer punctuation, HUD, tray и low-level keyboard hook. Общая схема подтверждена [`ARCHITECTURE.md`](https://github.com/melody0709/VoxType/blob/be65fcca35669d94af86cc563551b8ac940106dc/ARCHITECTURE.md).

Сильные стороны: Windows-native audio, CPU-only INT8 models, model preload/cache, batch/streaming sessions, serial fallback, clipboard paste и Unicode input. Ограничения:

- LICENSE отсутствует, поэтому код и ресурсы нельзя копировать или модифицировать;
- README ориентирован на Windows 11, Windows 10 не подтверждён;
- Linux отсутствует;
- GigaAM/faster-whisper и engine-neutral model packages отсутствуют;
- модели ориентированы преимущественно на китайский/английский;
- bounded-memory long-dictation pipeline не найден;
- запись сохраняется как `%APPDATA%\VoxType\last_recording.wav`;
- вставка использует текущее окно без строгого source-target guard;
- CI и полноценные tests отсутствуют, `_test_compile.bat` является ручным compile helper;
- [`download_models.ps1`](https://github.com/melody0709/VoxType/blob/be65fcca35669d94af86cc563551b8ac940106dc/download_models.ps1) не проверяет application-owned checksums.

- **Как основа fork:** юридически заблокирован отсутствием лицензии.
- **Как архитектурный пример:** средняя для WASAPI/VAD/native HUD и CPU ONNX; только read-only изучение.
- **Architecture reuse:** технически 35-45%, разрешённый code reuse 0%.
- **Переделка:** 60-75% плюс неизвестный лицензионный результат.
- **Нежелательные зависимости:** language-specific models, aria2 distribution risk, persistent WAV, Windows-only native coupling.

### nerd-dictation

nerd-dictation - Linux/Python CLI, в котором audio process control, Vosk streaming recognition, postprocessing и output собраны в одном скрипте. Длинная диктовка поддерживается потоковым `KaldiRecognizer` без общего duration limit; output adapters включают `xdotool`, `ydotool`, `dotool` и `wtype` ([основной цикл](https://github.com/ideasman42/nerd-dictation/blob/41f372789c640e01bb6650339a78312661530843/nerd-dictation#L928-L1264)).

Отдельных VAD, ASR abstraction, model registry/checksum, hotkey registration, overlay, tray и clipboard safety нет. GigaAM/faster-whisper требуют нового recorder-to-segmenter pipeline и engine contract, поскольку текущий loop зависит от Vosk `PartialResult`/`FinalResult`/`Reset`. Windows не поддерживается; X11/Wayland зависят от внешних tools и permissions. Performance measurements отсутствуют. CI отсутствует; единственный test проверяет английские числа; release/tag отсутствуют, последний commit от 2025-10-10.

- **Как основа fork:** нет из-за GPL, Linux-only монолита и Vosk coupling.
- **Как архитектурный пример:** ограниченная ценность для continuous partial/final loop и Linux output tools.
- **Architecture reuse:** 20-30%; code reuse исключён установленным запретом GPL.
- **Переделка:** 75-90%.
- **Нежелательные зависимости:** Vosk semantics, shell tools, executable Python config, отсутствие desktop shell.

### OpenWhispr

OpenWhispr - Electron/Node/React продукт существенно шире Nadikt: диктовка, translation, AI agent/chat, meetings/AEC/diarization, notes/semantic search, cloud sync, import, API и MCP. Широкий scope увеличивает technical coverage, но делает удаление функций и supply-chain сопровождение отдельным крупным проектом.

| Область | Результат |
|---|---|
| ASR | Local whisper.cpp и sherpa-onnx, cloud/BYOK и self-hosted endpoint; [`custom-asr-shim`](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/examples/custom-asr-shim/README.md) даёт OpenAI-compatible batch contract |
| GigaAM/faster-whisper | Можно подключить локальным HTTP shim без UI/core rewrite, но это добавляет отдельный process/IPC и не выражает lifecycle одного in-process engine Nadikt |
| Audio/VAD/long speech | Есть mature local paths, VAD, meeting/segment pipelines, но они смешаны с существенно более широкими сценариями и persistent storage |
| Dictionary/postprocessing | Функционально развитые profiles/history/AI flows, многие не соответствуют deterministic offline scope |
| Hotkeys/tray/overlay | Cross-platform desktop integration присутствует; архитектура связана с Electron main/renderer/native helpers |
| Windows insertion | `SendInput`, terminal-specific `Ctrl+Shift+V`, PowerShell/NirCmd fallbacks; строгий source-window/protected-field contract Nadikt не подтверждён |
| Linux | PulseAudio/PipeWire; X11 `xdotool`, Wayland `wtype`/`ydotool`, GNOME/KDE/Hyprland-specific paths - ценный reference будущего `LinuxAdapter` |
| Packaging | Windows 10+, Linux AppImage/deb/rpm/tar.gz и macOS; build scripts собирают/скачивают множество native helpers |
| Privacy/network | Local mode существует, но cloud providers, sync, updater, history и model downloads входят в продуктовую архитектуру |
| CPU | Local quantized engines поддерживаются; воспроизводимых данных i3/RU+EN WER/CER/RTF/RAM нет |
| Maturity | 1 612 commits, release `v1.7.6`, 138 open issues, tests/typecheck/lint и cross-platform release workflow |

[`package.json`](https://github.com/OpenWhispr/openwhispr/blob/ab201b3900caf582e9d70448414c83935fd7c595/package.json) показывает особенно высокий build surface: prebuild загружает whisper.cpp, llama-server, sherpa-onnx, yt-dlp, Qdrant, AEC/VAD/embedding/diarization assets. Это прямо противоречит минимальному model-package surface Nadikt и усложняет offline reproducibility.

- **Как основа fork:** нет, несмотря на MIT и cross-platform maturity; удаление unrelated scope и supply chain не проще собственного core.
- **Как архитектурный пример:** высокая для Linux adapters, native helper packaging, CI и external ASR shim.
- **Architecture reuse:** 50-60%; прямой Python code reuse минимален.
- **Переделка:** 65-80%.
- **Нежелательные зависимости:** Electron footprint, cloud/agent/meeting/sync/history, Qdrant/LLM, многочисленные download scripts и mixed licenses.

## Сквозные выводы

### Платформенная матрица

| Проект | Windows 10/11 | Ubuntu X11 | Ubuntu Wayland | Основная разработка core на Ubuntu |
|---|---|---|---|---|
| Handy | Windows artifacts и CI есть; Windows 10 отдельно не доказан | Частично | Частично, есть известные ограничения | Возможно, но стек Rust/Tauri и core связан с desktop runtime |
| Voxtype | Нет | Частично | Да, основная цель | Да |
| Whisper Key | Реализован Windows, без OS-version CI | Нет | Нет | Нет: Linux выбирает Windows adapters |
| VoiceType AI | Windows build есть; cloud-only | Нет | Нет | Только неплатформенная часть, которой почти нет |
| VoxType | Windows 11 заявлен; Windows 10 не доказан | Нет | Нет | Нет |
| nerd-dictation | Нет | Через внешние tools | Через внешние tools | Да, но без portable core |
| OpenWhispr | Windows 10+ заявлен и собирается | Через adapters/tools | Через adapters/tools | Возможно, но Electron core перегружен unrelated scope |

### Надёжность вставки

Ни один проект не подтверждает полный контракт Nadikt: snapshot окна и по возможности control, отказ при смене цели, запрет protected fields, сохранение набора clipboard formats, подтверждённая вставка, restoration при всех outcomes и обработка UIPI. VoiceType AI ближе других по HWND guard, Handy и Whisper Key - по clipboard/direct typing, OpenWhispr и Voxtype - по fallback chains. Эти решения следует использовать для формирования негативных tests, а не как готовую безопасную подсистему.

### Работа на слабом CPU

Handy, Voxtype, Whisper Key, VoxType и OpenWhispr имеют CPU-only и/или INT8/quantized paths. Однако ни один репозиторий не публикует воспроизводимый протокол на Intel Core i3 10-го поколения с фиксированным RU/RU+EN corpus, cold load, RTF, stop latency, CPU, peak RAM, WER/CER и сохранением английских терминов. Опубликованные цифры других CPU не используются как результат Nadikt.

### Подключаемость GigaAM и faster-whisper

| Проект | GigaAM | faster-whisper | Итог |
|---|---|---|---|
| Handy | Уже есть ONNX/GGUF GigaAM | Нет, есть transcribe-cpp | Новый adapter затрагивает catalog/factory/settings/build, core boundary недостаточно чиста |
| Voxtype | Можно добавить через `Transcriber` | Можно добавить через subprocess | Лучший reference контракта, но model manager частично Whisper-specific |
| Whisper Key | Нужен новый protocol и segmentation | Уже основной engine | Умеренный refactor, но lifecycle и Linux всё равно переделываются |
| VoiceType AI | Полная замена cloud STT | Полная замена cloud STT | Offline ASR core отсутствует |
| VoxType | Новый native backend | Новый native backend | Возможность ограничена Windows/C++ и отсутствием лицензии |
| nerd-dictation | Переписывание Vosk loop | Переписывание Vosk loop | ASR abstraction отсутствует |
| OpenWhispr | Local HTTP shim возможен | Local HTTP shim возможен | Хорошая внешняя граница, но не lifecycle contract Nadikt |

## Зрелость и практическая воспроизводимость

### Сопровождаемость

| Проект | Activity/releases | Tests и CI | Packaging/signing/update | Основной риск сопровождения |
|---|---|---|---|---|
| Handy | Очень высокая активность, 62 releases | Cross-platform build matrix; 1 Rust test failed на проверенном HEAD; Windows app acceptance отсутствует | MSI/NSIS, deb/rpm/AppImage; Windows signing и signed updater | Быстро меняющийся широкий Tauri codebase и открытые clipboard/model/Wayland bugs |
| Voxtype | Очень высокая активность, 63 releases | fmt/clippy/test CI успешен; Nix workflow упал при внешней подготовке; optional engines не собраны в одной полной matrix | Linux packages, Nix/Homebrew, signed checksums; Windows artifacts нет | Большое число engines/features и Wayland/system dependency matrix |
| Whisper Key | Активен, 16 releases | App CI и test suite отсутствуют | Windows bootstrap EXE и PyPI/pipx; точный EXE состав/signing не подтверждён | Невоспроизводимая упаковка, unpinned downloads и platform selector |
| VoiceType AI | Молодой проект, 12 commits, release 0.1.6 | CI компилирует Windows/macOS, tests отсутствуют | Desktop artifacts; signing/update evidence недостаточно | Cloud API core и малая история эксплуатации |
| VoxType | 78 commits, release metadata расходится с README | GitHub Actions и полный test suite отсутствуют | Ручные Windows scripts; signing/update не подтверждены | Нет лицензии, Windows-only native stack, language-specific models |
| nerd-dictation | Последний commit 2025-10-10, releases нет | CI нет; один test английских чисел | Минимальный setuptools, user-installed tools/models | Низкая активность, монолит и внешние desktop tools |
| OpenWhispr | 1 612 commits, release 1.7.6, 138 open issues | Node tests, lint/typecheck и cross-platform build workflow | Windows/Linux/macOS, electron-updater, notarization/build automation | Очень большая supply chain и unrelated product scope |

Число issues само по себе не является показателем низкого качества: у активных Handy и OpenWhispr оно также отражает размер аудитории. Для Nadikt важнее характер issues в критичных границах. У Handy найдены проблемы clipboard, elevated targets, model switching, long recordings и Wayland paste; у OpenWhispr высокий риск создаёт не один issue, а совокупность native helpers, downloads и product modes.

### Локальная практическая проверка

Checkout выполнен 26 июля 2026 г. только во временный каталог `C:\Users\RAV\AppData\Local\Temp\opencode`. В Git worktree Nadikt сторонние репозитории не добавлялись.

| Проект | Checkout SHA | Проверка | Результат |
|---|---|---|---|
| Handy | `6cad594cdba3aaa99555183fcb1e7b5a3967168e` | Inspect `package.json`, `src-tauri/Cargo.toml`; WSL `npm run build` | **Проверено частично:** manifest читается, command дошёл до `tsc`; local dependencies отсутствуют. Cargo/Rust в WSL не установлен, backend build не запускался |
| Voxtype | `f97276661d9b723aa3236f03879650a2a06c3ec3` | Inspect `Cargo.toml`; WSL `cargo check --locked` | **Не проверено:** `cargo: command not found`; системные пакеты и Rust toolchain не устанавливались |
| OpenWhispr | `ab201b3900caf582e9d70448414c83935fd7c595` | Inspect `package.json`; WSL `npm run build:renderer` | **Проверено частично:** command дошёл до `vite`; local dependencies отсутствуют. Полный build не запускался, поскольку `prebuild` скачивает многочисленные binaries/models |

Среда: WSL2 Ubuntu 24.04, Linux kernel `6.18.33.2-microsoft-standard-WSL2`, Python 3.12.3, Git 2.43.0. В WSL не установлены Rust/Cargo, Node.js и CMake. Windows host имеет Node.js 24.13.1, npm 11.8.0 и Python 3.12.0, но Windows build не заменяет требуемую Ubuntu-проверку.

Зависимости не устанавливались по следующим причинам:

- установка Rust/Node/CMake является изменением системной среды и требует отдельного согласования;
- Handy требует одновременно frontend dependencies и Rust/Tauri/native Linux dependencies;
- OpenWhispr `prebuild` запускает native compilation и downloads whisper.cpp, llama-server, sherpa-onnx, Qdrant, AEC/VAD/embedding/diarization assets;
- загрузка моделей и крупных runtime assets явно исключена условиями исследования.

Поэтому локальный результат не доказывает build compatibility или incompatibility проектов. Он фиксирует воспроизводимый environment blocker. Дополнительное evidence взято из CI самих проектов и отделено от локального запуска.

### Что не проверено практически

- Реальная работа hotkey, overlay, tray, clipboard и insertion в Windows 10/11.
- Word, browser, 1С, email clients, editors, terminals, protected fields и elevated targets.
- X11/Wayland runtime в GNOME/KDE и permissions для evdev/ydotool/wtype.
- CPU/RAM/RTF и качество ASR на целевом Intel Core i3.
- Offline network-blocked scenario и integrity model packages.

Эти проверки не подменяются чтением исходного кода и включены в отдельный Handy PoC plan.

## Сравнительная оценка

Обозначения колонок: `Lic` - лицензионная пригодность, `Arch` - архитектура, `Win` - Windows 10/11, `Ubu` - будущий Ubuntu port, `ASR` - подключаемость GigaAM/faster-whisper, `CPU` - CPU-only, `Ins` - надёжность вставки, `Mat` - зрелость.

| Проект | Lic 20% | Arch 20% | Win 15% | Ubu 10% | ASR 15% | CPU 10% | Ins 5% | Mat 5% | Итог / 5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Handy** | 3,5 | 3,0 | 4,0 | 3,0 | 3,5 | 3,5 | 2,0 | 4,5 | **3,40** |
| **OpenWhispr** | 3,0 | 3,0 | 4,0 | 4,0 | 3,5 | 3,0 | 2,5 | 4,5 | **3,38** |
| **Voxtype** | 3,5 | 4,0 | 0,0 | 4,5 | 4,0 | 4,0 | 2,5 | 4,0 | **3,28** |
| Whisper Key | 2,5 | 2,5 | 3,5 | 0,0 | 3,0 | 3,5 | 2,5 | 2,0 | **2,55** |
| VoiceType AI | 4,0 | 1,5 | 3,0 | 0,0 | 0,5 | 0,0 | 3,0 | 2,0 | **1,88** |
| VoxType | 0,0 | 2,5 | 3,0 | 0,0 | 2,0 | 3,5 | 2,0 | 1,5 | **1,78** |
| nerd-dictation | 1,0 | 1,5 | 0,0 | 3,5 | 1,0 | 3,0 | 1,0 | 1,5 | **1,43** |

Независимый расчёт по исходным баллам дал: Handy 3,400; OpenWhispr 3,375; Voxtype 3,275; Whisper Key 2,550; VoiceType AI 1,875; VoxType 1,775; nerd-dictation 1,425. Рейтинг отражает общую полезность, но не решение о fork.

### Обоснование каждого subscore

| Проект | Lic | Arch | Win | Ubu | ASR | CPU | Ins | Mat |
|---|---|---|---|---|---|---|---|---|
| Handy | 3,5: MIT code, brand/mixed models | 3,0: managers, но Tauri/privacy/long gaps | 4,0: signed packages/CI, Win10 не отдельно | 3,0: packages есть, Wayland limits | 3,5: GigaAM есть, faster-whisper нет | 3,5: INT8/GGUF, i3 data нет | 2,0: restore partial, no target/protected | 4,5: active/releases/CI, один test fail |
| OpenWhispr | 3,0: MIT app, GPL/custom/model closure | 3,0: broad modules, excessive coupling/scope | 4,0: Windows 10+ build paths | 4,0: X11/Wayland packages/adapters | 3,5: local engines/shim, no Nadikt lifecycle | 3,0: quantized paths, target data нет | 2,5: many fallbacks, safety contract не доказан | 4,5: 1 612 commits, tests/builds, large issue surface |
| Voxtype | 3,5: MIT app, mixed model/assets | 4,0: strongest contracts/chunking | 0,0: implementation отсутствует | 4,5: primary Wayland, X11 partial | 4,0: adapter boundary good | 4,0: CPU/INT8 paths, wrong benchmark CPU | 2,5: fallback/restore, no target/protected | 4,0: active/releases/CI, Nix failure |
| Whisper Key | 2,5: MIT app, TEN-VAD/assets risk | 2,5: Python modules, concrete engine/whole RAM | 3,5: implementation/releases, CI отсутствует | 0,0: selector не поддерживает Linux | 3,0: faster-whisper есть, GigaAM needs refactor | 3,5: CPU INT8 default, measurements нет | 2,5: SendInput/restore, no target/protected | 2,0: releases, no tests/build CI |
| VoiceType AI | 4,0: MIT app, assets/provider caveats | 1,5: small pipeline, offline core отсутствует | 3,0: Windows build/guard, weak tests | 0,0: Linux нет | 0,5: cloud STT must be replaced | 0,0: local CPU ASR отсутствует | 3,0: best HWND guard, incomplete formats/protected | 2,0: young, CI compile only |
| VoxType | 0,0: application license отсутствует | 2,5: useful native pipeline, key gaps | 3,0: Win11 path, Win10/CI not proven | 0,0: Linux нет | 2,0: engines coupled, both candidates absent | 3,5: CPU INT8, protocol data нет | 2,0: current-window methods, no strict guard | 1,5: no CI/tests, release mismatch |
| nerd-dictation | 1,0: GPL incompatible with task | 1,5: monolith, useful streaming loop | 0,0: Windows нет | 3,5: X11/Wayland tools | 1,0: Vosk loop rewrite required | 3,0: CPU works, metrics/quantization control нет | 1,0: current focus, no clipboard safety | 1,5: stale, no releases/CI |

## Пригодность и объём повторного использования

| Проект | Основа fork | Архитектурный пример | Architecture reuse | Прямой code reuse в Python/PySide6 | Переделка |
|---|---|---|---:|---:|---:|
| Handy | Нет | Высокая | 40-50% | около 0% | 60-75% |
| Voxtype | Нет | Очень высокая | 60-70% | 0-5% | 70-85% |
| Whisper Key | Нет | Средняя | 45-55% | 20-30% после component audit | 45-60% |
| VoiceType AI | Нет | Средняя для insertion cases | 20-30% | около 0% | 75-90% |
| VoxType | Нет, license blocker | Средняя, read-only | 35-45% технически | 0% без лицензии | 60-75% |
| nerd-dictation | Нет, GPL blocker | Ограниченная | 20-30% | 0% по условиям задачи | 75-90% |
| OpenWhispr | Нет | Высокая | 50-60% | около 0% | 65-80% |

`Architecture reuse` измеряет покрытие областей Nadikt идеями и существующими boundaries. `Прямой code reuse` дополнительно учитывает Python/PySide6, лицензию и реальную переносимость. Ни один кандидат не достигает подтверждённых 70% архитектуры, пригодной для сохранения в fork Nadikt.

## Проверка условий fork

Значения: `Да` - подтверждено; `Нет` - условие провалено; `?` - требуется дополнительное доказательство и для строгого gate считается непрохождением.

| Проект | Совместимая license closure | Reuse >=70% | Новый ASR без core rewrite | Нет mandatory cloud | Windows реально поддержан | Ubuntu port | Удаление проще greenfield | Upstream без постоянных конфликтов | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Handy | ? | Нет | Да/частично | Да | ? | Да | Нет | Нет | **FAIL** |
| Voxtype | ? | Нет | Да | Да | Нет | Да | Нет | ? | **FAIL** |
| Whisper Key | Нет | Нет | Частично | Да | ? | Нет | ? | ? | **FAIL** |
| VoiceType AI | Да для app code | Нет | Нет | Нет | ? | Нет | Нет | ? | **FAIL** |
| VoxType | Нет | Нет | Частично | Да | ? | Нет | Нет | ? | **FAIL** |
| nerd-dictation | Нет по ограничениям задачи | Нет | Нет | Да | Нет | Да | Нет | ? | **FAIL** |
| OpenWhispr | ? | Нет | Частично | Да | Да | Да | Нет | Нет | **FAIL** |

Ни один проект не проходит все восемь условий. Следовательно, `FORK` исключён независимо от позиции в рейтинге.

## Архитектурное решение

**Решение: `HYBRID`.** Nadikt сохраняет собственную Python/PySide6 кодовую базу и Explicit Architecture. Сторонние проекты используются как источники проверяемых решений, failure modes и, после отдельного component audit, отдельных permissive-компонентов.

### Что использовать как ориентир

| Источник | Полезные решения | Что не переносить |
|---|---|---|
| Handy | one-engine ownership, GigaAM ONNX/GGUF evidence, Silero VAD scenarios, PTT races, Win32 no-activate mixed-DPI overlay, package smoke tests | clipboard/insertion, history, transcript logging, network model catalog, cloud LLM, full-recording accumulation |
| Voxtype | `Transcriber` capabilities, model lifecycle, eager chunking, output fallback chain, Wayland OSD protocol | evdev/tool coupling, transcript INFO logs, cloud/meeting scope, Rust implementation |
| Whisper Key | WASAPI/soxr, faster-whisper CPU INT8, Unicode SendInput, tray/hotkey modes | TEN-VAD, startup network request, shell commands, unpinned model downloads |
| VoiceType AI | target HWND snapshot и negative cases для protected fields/clipboard formats | cloud STT/refinement и ошибочную character insertion в password field |
| VoxType | WASAPI/VAD/native HUD/ONNX CPU design как read-only reference | любой код или asset до появления лицензии |
| nerd-dictation | continuous partial/final semantics и каталог Linux output tools | GPL-код, Vosk-specific monolith |
| OpenWhispr | Linux X11/Wayland adapter inventory, native helper CI, external ASR shim pattern | Electron product shell, cloud/agent/meeting/sync/history и release dependency bundle |

### Почему не GREENFIELD в строгом смысле

Собственная кодовая база необходима, но игнорирование проверенных failure modes увеличит риск. Поэтому `HYBRID` точнее `GREENFIELD`: архитектура, требования и glue code создаются для Nadikt, а permissive libraries и отдельные решения выбираются после benchmark и provenance review. До такого review сторонний application code не переносится.

### Дополнительные проекты

Дополнительные репозитории не добавлялись. Обязательная выборка уже покрывает основные архитектуры (Tauri, Rust daemon, Python utility, native Win32, Electron и Linux CLI). Добавление ещё трёх проектов не устранило бы главные неизвестные - benchmark GigaAM/faster-whisper на целевом i3 и acceptance tests безопасной Windows-вставки.

Windows insertion spike от 2026-07-26 получил решение [`REWORK`](windows_insertion_spike_results.md): classic Win32 target/protected/direct-input contracts подтверждены, но UI Automation и real application/clipboard matrix остаются открытыми. Результат не меняет решение `HYBRID` и подтверждает, что решения исследованных приложений нельзя переносить как готовую подсистему.

### Условия пересмотра

Решение следует пересмотреть, только если одновременно появится кандидат с совместимой полной license closure, подтверждённым architecture reuse не менее 70%, production Windows 10/11, общим Linux-portable core, заменяемым ASR, bounded-memory segmentation и insertion contract Nadikt. Высокий benchmark одного ASR или один успешный Windows build недостаточны.

## Следующий этап AI Factory

Insertion spike выполнен и верифицирован отдельно. Следующие независимые исследовательские ветки:

- локальный REWORK UI Automation и повторная Windows application/clipboard matrix;
- ASR/VAD benchmark на целевом CPU;
- отдельное решение пользователя о Handy PoC.

Реализацию приложения автоматически не начинать только на основании этого исследования.

## Вопросы пользователю

1. Одобрить ли отдельный Handy PoC после verification?
2. Разрешить ли для PoC установку Rust/Node/system build dependencies в изолированной Ubuntu-среде?
3. Какую изолированную Windows 10/11 среду использовать для повторной insertion matrix и CPU benchmark?

## Ограничения исследования

- Текущая среда OpenCode работает на Windows; результаты Ubuntu и целевого Windows hardware нельзя имитировать.
- Модели и крупные runtime-ресурсы без отдельного согласования не загружаются.
- Опубликованные авторами показатели производительности не считаются измерениями на Intel Core i3 10-го поколения.
