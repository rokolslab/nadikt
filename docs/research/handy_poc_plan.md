# План ограниченного proof of concept Handy

Дата: 26 июля 2026 г.

Статус: предложен, не выполнялся

## Назначение

PoC проверяет оставшиеся технические неизвестные Handy на Ubuntu и Windows. Он не разрешает fork, перенос кода в Nadikt, распространение моделей или изменение ADR-001.

Проверяемая ревизия: [`cjpais/Handy@6cad594cdba3aaa99555183fcb1e7b5a3967168e`](https://github.com/cjpais/Handy/commit/6cad594cdba3aaa99555183fcb1e7b5a3967168e).

Основные вопросы:

1. Насколько ASR boundary изолирован при добавлении локального adapter с lifecycle Nadikt?
2. Можно ли исключить сетевую загрузку и запускать только проверенный локальный model package?
3. Как растут RAM и latency при длинной записи?
4. Выполняет ли Windows insertion минимальные safety invariants?
5. Какие части Handy являются полезными reference tests, даже если fork остаётся отклонённым?

## Ограничения

- Работать только в отдельном временном checkout, не в репозитории Nadikt.
- Не создавать GitHub fork и не добавлять submodule.
- Не использовать administrator/root и не устанавливать system packages без отдельного согласования.
- Не скачивать model weights до проверки их точной revision, license и checksum.
- Использовать только обезличенное тестовое аудио и synthetic clipboard data.
- Не вводить API keys и не включать cloud postprocessing.
- Заблокировать исходящий network на offline-этапе после подготовки зависимостей.
- Не переносить результаты эксперимента как production code.

## Среды

### Ubuntu

- Ubuntu 24.04 x64, предпочтительно отдельная VM или чистый WSL2 image.
- Зафиксировать CPU, RAM, kernel, desktop/compositor, Rust, Node/Bun и system library versions.
- Для UI runtime требуется реальная GNOME/KDE session; WSL без desktop подходит только для build/static tests.
- Отдельно проверить X11 session и Wayland session; результат одной display system не распространять на другую.

### Windows

- Windows 10 x64 и Windows 11 x64.
- Отдельный тест на Intel Core i3 10-го поколения, 16 ГБ RAM, без discrete GPU.
- Обычная user session без elevation.
- Notepad, Word, Chromium/Firefox, 1С, почтовый клиент, editor, terminal и тестовое password field.

## Этап 0. License и supply-chain gate

1. Зафиксировать SHA приложения, Cargo.lock/package lock и model catalog revision.
2. Выбрать один GigaAM artifact только после фиксации license, checksum и права локального использования.
3. Составить список native binaries и build-time downloads.
4. Отключить cloud providers, updater и history до functional tests.

Критерий успеха: для каждого используемого artifact есть source URL, immutable revision, license и checksum. Неизвестная или non-commercial license останавливает соответствующий model experiment.

## Этап 1. Ubuntu build и offline запуск

1. Собрать frontend и Rust backend на чистой Ubuntu по документированным командам.
2. Зафиксировать необходимые system packages и все network requests build-процесса.
3. Повторить build из подготовленного cache с заблокированным исходящим network.
4. Запустить unit tests и отделить existing failures от PoC changes.
5. Проверить Linux package contents на незаявленные models, logs и downloaders.
6. В реальной desktop VM отдельно проверить hotkey, overlay и insertion в X11.
7. Повторить runtime matrix в Wayland GNOME и, если доступно, KDE; зафиксировать требуемые portals/tools/permissions.

Метрики:

- cold build time и размер cache;
- список system packages и downloaded artifacts;
- pass/fail tests с точными версиями;
- размер deb/AppImage;
- network requests при offline run.
- pass/fail hotkey, no-focus overlay и insertion отдельно для X11 и Wayland.

Критерий успеха: build воспроизводим на pinned dependencies; основной локальный сценарий после установки не выполняет network requests. Если build требует mutable downloads без checksum, результат отрицательный.

## Этап 2. ASR boundary experiment

1. В disposable branch временного checkout добавить fake local engine без ML runtime.
2. Реализовать operations `load`, `ready`, `warm_up`, `transcribe_segment`, `cancel`, `close` и capabilities.
3. Проверить, какие файлы вне ASR/model registration пришлось изменить.
4. Проверить запрет switch во время active recording и rollback после load failure.
5. Проверить, что одновременно существует только один engine instance.

Метрики:

- число изменённых production modules вне ASR/model catalog;
- необходимость менять audio, overlay, hotkeys, insertion или frontend workflow;
- число engine-specific типов, вышедших за adapter boundary;
- RAM до/после unload fake/real engine.

Критерий успеха: audio/hotkeys/overlay/insertion не меняются, SDK types не выходят из ASR layer, switch во время записи отклоняется, failure сохраняет работоспособный engine. Изменение coordinator/audio/UI control flow означает отрицательный результат для fork suitability.

## Этап 3. Длинная диктовка и ресурсы

1. Использовать synthetic 1, 10 и 30 minute audio с паузами и речевыми сегментами.
2. Измерить resident RAM во время capture, после stop, во время ASR и после cleanup.
3. Проверить наличие bounded segment queue, порядок результатов и поведение при ошибке среднего сегмента.
4. Зафиксировать пропуски/повторы на заранее размеченных границах.

Критерии успеха для Nadikt:

- RAM не растёт линейно с полной длительностью сессии сверх ограниченного буфера/queue;
- один segment failure не удаляет предыдущие результаты;
- порядок стабилен, границы не создают пропусков и повторов;
- пользовательская сессия не имеет artificial duration limit.

Текущий source audit предсказывает отрицательный результат из-за единого `Vec<f32>` всей записи. PoC должен измерить проблему, а не маскировать её увеличением лимита RAM.

## Этап 4. Windows hotkey, overlay и insertion

### Hotkey и overlay

1. Проверить toggle, push-to-talk, cancel и повторные быстрые нажатия.
2. Проверить overlay на двух мониторах, negative coordinates и mixed DPI.
3. Убедиться, что overlay не получает keyboard focus и не меняет target control.

Критерий успеха: состояние меняется менее чем за 1 s, второй session не создаётся, overlay не активируется и корректно возвращается на доступный monitor.

### Target safety

Для каждого приложения начать запись в поле A, затем выполнить сценарии:

1. оставить focus без изменений;
2. перейти в другое окно;
3. перейти в другое поле того же окна;
4. открыть overlay/settings во время ASR;
5. выбрать password/protected field;
6. использовать elevated target при обычном запуске Handy.

Критерий успеха Nadikt: автоматическая вставка выполняется только в подтверждённую исходную цель; protected/elevated/changed target дают safe failure и сохраняют результат без вставки.

### Clipboard

Проверить text, Unicode, HTML+text, RTF, image, file list и custom format. Для каждого формата выполнить success, paste failure, focus change и exception during key injection.

Критерий успеха: исходный набор formats восстанавливается после подтверждённой вставки; при невозможности безопасного snapshot исходный clipboard не уничтожается; transcript остаётся доступен при failure.

## Этап 5. CPU-only GigaAM

Выполнять только после отдельного согласования model artifact.

1. Запустить GigaAM INT8/Q8 на target i3 без discrete GPU.
2. Измерить cold load, first transcription, RTF, stop latency, average/max CPU и peak RAM.
3. Повторить для 10-minute segmented session.
4. Полностью выгрузить model и подтвердить освобождение RAM.

Минимальный продуктовый ориентир: остаточная обработка записи до 60 s не более 30 s, UI остаётся responsive, система пригодна для Word/browser/1С. Качество оценивается отдельным benchmark Nadikt; Handy PoC не выбирает финальную модель.

## Stop conditions

PoC прекращается без расширения scope, если:

- обнаружена несовместимая или неясная license используемого artifact;
- build требует administrator/root, mutable unsigned binary или незаявленную модель;
- experiment требует менять core audio/hotkey/insertion ради нового engine;
- memory линейно растёт с duration и исправление требует нового segmentation pipeline;
- target/protected-field safety отсутствует и требует отдельного Windows subsystem;
- за два инженерных дня не получен воспроизводимый build и один end-to-end local scenario.

## Итоговые критерии

Handy может быть повторно рассмотрен как основа только при одновременном результате:

- architecture reuse не менее 70% по той же 20-area матрице;
- новый engine добавлен без core/UI/platform rewrite;
- offline package lifecycle воспроизводим;
- long dictation bounded по памяти;
- Windows insertion проходит target/clipboard/protected-field matrix;
- license closure подтверждена;
- удаление history/cloud/updater проще собственного Nadikt core.

Если хотя бы одно условие не выполнено, ADR-001 не пересматривается. Полезные результаты PoC переносятся только как requirements, tests и provenance-reviewed решения.

## Результаты, которые следует сохранить

- environment manifest и точные команды;
- pass/fail matrix без пользовательского аудио и текста;
- aggregate CPU/RAM/latency;
- список network requests и artifacts;
- список изменённых modules disposable experiment;
- license/provenance table;
- краткое заключение о подтверждённых и опровергнутых гипотезах.
