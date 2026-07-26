# План реализации: Windows Insertion Safety Spike

Branch: feature/windows-insertion-safety-spike
Created: 2026-07-26

## Original Request
согласен, планируй

## Настройки

- Testing: yes - обязательные unit/contract tests и ручная Windows acceptance matrix
- Logging: verbose - подробные lifecycle/outcome events без текста, clipboard payload, window title и других чувствительных данных
- Docs: yes - обязательный documentation checkpoint с результатами и решением GO/REWORK/NO-GO
- Timebox: 2 инженерных дня; production polishing и расширение scope запрещены

## Roadmap Linkage

Milestone: "Квалификация критических технических рисков"

Rationale: spike проверяет наиболее рискованную часть milestone - безопасную Windows-вставку до реализации ASR pipeline и desktop UI.

## Контекст Решения

Исследование репозиториев показало, что ни один кандидат не реализует полный контракт Nadikt: фиксацию исходного окна и control, отказ при смене цели, запрет protected fields, сохранение нескольких clipboard formats, fail-closed поведение при elevated target и восстановление результата при ошибке.

Текущая среда подходит для функционального spike: Windows 11 Pro x64, Intel Core i5-12500H, 16 ГБ RAM, Python 3.12. Она не заменяет целевой Intel Core i3 для performance benchmark.

Spike является disposable experiment. Его production code не переносится автоматически в `src/nadikt`; в основную архитектуру переходят только проверенные contracts, acceptance scenarios и отдельно перепроверенные решения.

## Границы

В scope:

- snapshot top-level window и focused control;
- повторная проверка цели непосредственно перед delivery;
- обнаружение classic и UI Automation protected/password fields;
- безопасный отказ при elevated или недоступной цели;
- clipboard transaction для Unicode text, image/DIB и file list;
- обнаружение unsupported/non-cloneable clipboard formats до изменения clipboard;
- `Ctrl+V` dispatch и Unicode `SendInput` fallback только при безопасной цели;
- сохранение synthetic result при любой ошибке;
- защита от повторной и параллельной вставки;
- автоматические tests и ручная matrix на доступных Windows-приложениях.

Вне scope:

- ASR, модели, аудиозахват, VAD и segmentation;
- PySide6, tray, overlay, settings и global hotkey;
- production history, SQLite и model packages;
- installer, signing, updater и автозапуск;
- обещание поддержки Word/1С до проверки на машинах, где они установлены;
- автоматическое повышение прав или обход UIPI;
- перенос стороннего application code.

## Приоритет Таймбокса

Два инженерных дня проверяют только две блокирующие гипотезы:

1. Windows target/protected/elevated checks могут fail-closed работать на controlled real fixtures.
2. Clipboard mutation/restoration не уничтожает исходное содержимое и не перезаписывает более новое внешнее изменение.

День 1: contracts, orchestration, target/protected/elevation probes и controlled fixtures. День 2: clipboard ownership/race probe, минимальный injection path, acceptance matrix и решение. Unicode fallback и расширенная application matrix являются вторичными: они не продлевают timebox.

## Инварианты Безопасности

1. При сомнении в идентичности или безопасности цели автоматическая вставка не выполняется.
2. HWND, COM и UI Automation objects не выходят за Windows adapter boundary.
3. Clipboard path не используется, если исходные formats нельзя безопасно snapshot/restore; при внешнем изменении clipboard после mutation restoration не перезаписывает более новые данные.
4. Protected field всегда даёт отказ; direct typing не является обходом запрета.
5. Elevated target при обычном запуске даёт controlled failure, а не retry с повышением прав.
6. Текст, clipboard payload, window title и content control не попадают в logs, exceptions или test artifacts.
7. Ошибка clipboard, target validation или key injection сохраняет synthetic result в памяти harness.
8. Один request создаёт не более одной попытки delivery; concurrent request отклоняется.

## Критерии Решения

### GO

- unit/contract tests проходят;
- Notepad и Chromium/Firefox на проверенной Windows 11 среде принимают Unicode и переносы строк при неизменной цели;
- смена окна и доступная смена control блокируют delivery;
- classic и browser password fields блокируют delivery;
- elevated target завершается safe outcome без зависания;
- text, Unicode, image и file-list clipboard восстанавливаются, а rich/unknown formats приводят к измеренному safe fallback/rejection до mutation;
- external clipboard change во время transaction не перезаписывается restoration;
- injection failure сохраняет result и не создаёт двойную вставку;
- logs не содержат sensitive payload;
- необходимые production ports можно сформулировать без Windows типов в core.

### REWORK

- базовая вставка работает, но identity одного из controls, UI Automation password detection или один clipboard format требует локального изменения adapter contract.

### NO-GO

- невозможно fail-closed отличить исходную цель от изменившейся;
- protected field нельзя надёжно заблокировать в browser/classic test cases;
- clipboard restoration нельзя гарантировать или безопасно отклонить до mutation;
- решение требует elevation, ASR/UI coupling или изменения общего core ради Win32 деталей.

## План Коммитов

- **Commit 1** (после задач 1-3): `test(windows): establish insertion safety contracts`
- **Commit 2** (после задач 4-7): `feat(windows): add insertion safety spike`
- **Commit 3** (после задач 8-9): `docs(windows): record insertion spike decision`

Коммиты выполняются только после проверки соответствующего checkpoint и отдельного подтверждения пользователя.

## Задачи

### Фаза 1. Контракт И Target Safety

- [x] **Задача 1. Создать изолированный spike harness и protocol**
  - Deliverable: добавить `experiments/windows_insertion/README.md`, `experiments/windows_insertion/insertion_spike/__init__.py`, `experiments/windows_insertion/insertion_spike/contracts.py` и минимальную test structure без production imports.
  - Поведение: определить platform-neutral `InsertionRequest`, opaque `TargetToken`, `InsertionOutcome`, adapter protocols и список safe error codes; зафиксировать disposable статус и команды запуска.
  - Зависимости: нет.
  - Проверки: package импортируется на Python 3.12; contracts не импортируют PySide6, pywin32, COM/Win32 types или application modules; уникальные canary payload не участвуют в `repr`, exception text или captured diagnostics.
  - Logging: создать spike-local logger с configurable level; DEBUG только для safe state transitions и outcome codes, ERROR для adapter failures; никогда не логировать request text, clipboard data, title или control content.
  - Files: `experiments/windows_insertion/README.md`, `experiments/windows_insertion/insertion_spike/__init__.py`, `experiments/windows_insertion/insertion_spike/contracts.py`, `experiments/windows_insertion/tests/`.

- [x] **Задача 2. Реализовать fail-closed insertion orchestration**
  - Deliverable: добавить `experiments/windows_insertion/insertion_spike/service.py` и contract tests с fake adapters.
  - Поведение: initial target захватывается отдельной операцией до countdown и передаётся в `deliver(request, captured_target)`; service не заменяет его новым target во время delivery. State flow: `retain result -> revalidate captured target -> check protected/elevation -> choose clipboard/direct path -> dispatch -> apply clipboard ownership policy -> outcome`; запрет concurrent/double request.
  - Зависимости: задача 1.
  - Проверки: tests покрывают target changed, protected, elevated, unsafe clipboard, external clipboard change, dispatch error, restoration error, cancellation и повторный request. При safe snapshot и failed paste synthetic result может остаться в clipboard, а original snapshot удерживается в памяти для явного restoration; при более новом внешнем clipboard service не перезаписывает его и сохраняет result только в памяти. Generic paste получает outcome `dispatched`, а не `inserted_confirmed`.
  - Logging: DEBUG для phase names и boolean safety decisions; INFO для финального outcome code/duration; WARN для safe rejection; ERROR для unexpected boundary failure без payload/trace locals с content.
  - Files: `experiments/windows_insertion/insertion_spike/service.py`, `experiments/windows_insertion/tests/test_service.py`.

- [x] **Задача 3. Реализовать Windows target, control, protected-field и elevation probes**
  - Deliverable: добавить `experiments/windows_insertion/insertion_spike/windows_target.py` с узким wrapper над Win32/UI Automation и adapter tests через injected API facade.
  - Поведение: snapshot top-level HWND, process/thread identity, focused control и доступный stable UI Automation identity; перед delivery повторно проверить доступные identities; detect classic `ES_PASSWORD`, UI Automation password property и higher-integrity target; unknown/denied access трактовать fail-closed.
  - Зависимости: задача 1; adapter реализуется независимо от service и других adapters.
  - Проверки: fake API tests покрывают same target, other window, another control in same window, destroyed handle, classic password, browser/UIA password, unavailable UIA и elevated process. Любая новая dependency допускается только после фиксации версии, лицензии и причины в README/isolated dependency manifest.
  - Logging: DEBUG только для наличия/изменения opaque identity и capability flags; WARN для unavailable UIA/access denied/elevated; не логировать HWND values, PID, process/window names, class names, titles или Automation properties с content.
  - Files: `experiments/windows_insertion/insertion_spike/windows_target.py`, `experiments/windows_insertion/tests/test_windows_target.py`, `experiments/windows_insertion/README.md`.

### Фаза 2. Clipboard И Injection

- [x] **Задача 4. Реализовать безопасную clipboard transaction**
  - Deliverable: добавить `experiments/windows_insertion/insertion_spike/windows_clipboard.py` с явным `prepare`, `commit_mutation`, `restore` и deterministic cleanup.
  - Поведение: enum formats и зафиксировать `GetClipboardSequenceNumber` до mutation; клонировать подтверждённо поддержанные Unicode text, DIB/image и file-list handles; при HTML/RTF/unknown/delayed-rendered/non-cloneable format вернуть `clipboard_unsafe` для выбора direct path без mutation. Перед restoration проверить sequence/ownership: более новый внешний clipboard никогда не перезаписывается.
  - Зависимости: задача 1; adapter реализуется независимо от service, target и injector.
  - Проверки: adapter tests покрывают empty/text/Unicode/image/file-list/multiple formats, HTML+text, RTF, unknown registered format, delayed rendering, lock contention, partial clone failure, mutation failure, external sequence change и restoration failure; исходные buffers не освобождаются преждевременно. Зафиксировать, что paste consumption подтверждается не всегда и conservative delay является измеряемым параметром, а не гарантией.
  - Logging: DEBUG для format count, known/unknown flags и transaction phase; WARN для unsupported/locked; ERROR для Win32 failure code без clipboard payload, filenames или byte dumps.
  - Files: `experiments/windows_insertion/insertion_spike/windows_clipboard.py`, `experiments/windows_insertion/tests/test_windows_clipboard.py`.

- [x] **Задача 5. Реализовать контролируемый paste и Unicode fallback**
  - Deliverable: добавить `experiments/windows_insertion/insertion_spike/windows_injector.py` с отдельными paste dispatch и Unicode `SendInput` paths.
  - Поведение: injector не импортирует target или clipboard adapters и выполняет только выданный service dispatch permit. Физически удерживаемые modifiers обнаруживаются и приводят к wait/rejection; injector освобождает только synthetic keys, которые нажал сам. `Ctrl+V` outcome считать `dispatched`; Unicode fallback разрешён orchestration только для safe non-protected target; surrogate pairs и newlines обрабатывать явно.
  - Зависимости: задачи 1 и 3; clipboard path не является обязательной зависимостью direct injection.
  - Проверки: fake API tests покрывают Cyrillic, newline, surrogate pair, physical modifier state, partial `SendInput` и dispatch exception; protected/elevated target никогда не получает fallback. Отдельно зафиксировать остаточный TOCTOU risk между финальной revalidation в service и обработкой input target application.
  - Logging: DEBUG для выбранного method, event count и dispatch phase без key/text values; INFO для safe outcome; ERROR для returned event-count mismatch и Win32 code без payload.
  - Files: `experiments/windows_insertion/insertion_spike/windows_injector.py`, `experiments/windows_insertion/tests/test_windows_injector.py`.

- [x] **Задача 6. Создать controlled Windows fixtures**
  - Deliverable: добавить `experiments/windows_insertion/fixtures/classic_target.py`, `experiments/windows_insertion/fixtures/password_form.html` и `experiments/windows_insertion/fixtures/clipboard_racer.py` без бинарных artifacts и сетевых зависимостей.
  - Поведение: classic target предоставляет обычный Win32 EDIT и `ES_PASSWORD` control, локальная HTML-страница - normal/password fields и два controls одного окна, clipboard racer - детерминированное внешнее изменение sequence. Elevated case запускается пользователем вручную через UAC; spike не инициирует elevation автоматически.
  - Зависимости: задача 1; fixtures могут разрабатываться параллельно adapters.
  - Проверки: fixture commands воспроизводимы на Windows 11/Python 3.12; содержат только synthetic canary data; normal/password controls различимы реальными Win32/UI Automation probes; cleanup не оставляет clipboard dumps или files с content.
  - Logging: fixture stdout сообщает только readiness/case ID; не печатает typed text, clipboard payload, HWND, PID, titles или control content.
  - Files: `experiments/windows_insertion/fixtures/classic_target.py`, `experiments/windows_insertion/fixtures/password_form.html`, `experiments/windows_insertion/fixtures/clipboard_racer.py`, `experiments/windows_insertion/README.md`.

- [x] **Задача 7. Добавить минимальный двухэтапный manual CLI harness**
  - Deliverable: добавить `experiments/windows_insertion/insertion_spike/cli.py` и команды README для раздельных `capture` и `deliver` phases с фиксированным synthetic Unicode payload.
  - Поведение: CLI после capture не активирует своё окно; countdown позволяет оставить или изменить focus, затем delivery использует только ранее captured token. Поддержать paste/direct/auto, explicit confirmation, cancel и interactive retention result/original snapshot до выхода процесса; не добавлять OS-level single-instance lifecycle или production exit taxonomy.
  - Зависимости: задачи 2-6.
  - Проверки: dry-run не касается clipboard/keyboard; cancel происходит до mutation; service-level concurrent/repeated request tests остаются источником защиты от double delivery; stdout/stderr не содержит canary payload.
  - Logging: INFO для phase start/end, method и outcome; DEBUG для safe timings; stdout/stderr не печатает synthetic payload, clipboard content, HWND, PID или title.
  - Files: `experiments/windows_insertion/insertion_spike/cli.py`, `experiments/windows_insertion/tests/test_cli.py`, `experiments/windows_insertion/README.md`.

### Фаза 3. Acceptance И Решение

- [ ] **Задача 8. Выполнить automated и manual acceptance matrix**
  - Deliverable: выполнить `python -m unittest discover -s tests` из `experiments/windows_insertion`; заполнить versioned matrix в `experiments/windows_insertion/README.md` для Notepad, Chromium/Firefox, classic password test app, browser password field, elevated test app и clipboard formats.
  - Поведение: отдельно проверить unchanged target, other window, another control in same window, target destroyed, protected field, elevated target, rich/unknown clipboard fallback, external clipboard race, injection failure, restoration failure и repeated request. Word, 1С, email client и editor пометить `not run`, если недоступны, без имитации результата.
  - Зависимости: задачи 1-7.
  - Проверки: записать Windows/Python/app versions, exact commands и pass/fail outcome codes; использовать уникальные canaries и автоматически подтвердить их отсутствие в logger output, exceptions, `repr`, stdout/stderr и application-generated diagnostics. Не заявлять проверку произвольных OS process dumps и не использовать реальные пользовательские данные.
  - Logging: сохранять только safe technical run log с case ID, environment version, outcome code и duration; WARN для skipped app; ERROR для failed invariant без payload.
  - Files: `experiments/windows_insertion/README.md`; test sources из задач 1-7.

- [ ] **Задача 9. Зафиксировать архитектурное решение spike**
  - Deliverable: через mandatory documentation checkpoint создать `docs/research/windows_insertion_spike_results.md` с environment, matrix, найденными ограничениями, предлагаемыми production ports и единственным решением `GO`, `REWORK` или `NO-GO`.
  - Поведение: отделить проверенные факты от предположений; не объявлять generic paste подтверждённым, если API даёт только dispatch; перечислить residual TOCTOU risk и deferred Word/1С/Windows 10 checks; формулировать `GO` только как разрешение продолжить design на проверенной Windows 11 matrix, не как MVP acceptance; предложить изменения `.ai-factory/ARCHITECTURE.md` только если experiment доказал необходимость.
  - Зависимости: задача 8.
  - Проверки: решение соответствует критериям этого плана; roadmap milestone не закрывается целиком, поскольку ASR/VAD часть остаётся; `git diff --check` проходит; Git не содержит clipboard dumps, screenshots, user text, binaries или стороннего кода.
  - Logging: в документ переносить только safe aggregate metrics и outcome codes; не вставлять raw logs с потенциальным payload.
  - Files: `docs/research/windows_insertion_spike_results.md`; при подтверждённом архитектурном изменении - отдельный owner-command follow-up для `.ai-factory/ARCHITECTURE.md`.

## Verification Gate

- Все 9 задач выполнены и отмечены в плане.
- Unit/contract tests проходят на Windows 11/Python 3.12.
- Manual matrix содержит фактические результаты и явные `not run`.
- Проверенные failure paths fail-closed блокируют changed/protected/elevated target; остаточный Windows input TOCTOU risk явно задокументирован.
- Clipboard либо восстанавливается при сохранённом ownership, либо не изменяется при unsafe snapshot, либо не перезаписывает более новое внешнее изменение.
- Logs и Git artifacts не содержат sensitive payload.
- Итоговое решение одно: environment-qualified `GO`, `REWORK` или `NO-GO`.
- Реализация ASR/UI не начата, milestone не закрыт преждевременно.

## Точка Остановки

После создания плана не выполнять `/aif-implement`. Пользователь должен отдельно согласовать реализацию spike.
