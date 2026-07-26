# Результаты Windows Insertion Safety Spike

## Решение

**REWORK**

Разрешается локально доработать adapter contract для UI Automation и повторить
изолированную application/clipboard matrix. Текущий результат не разрешает
перенос experiment code в `src/nadikt`, не является приёмкой MVP и не
подтверждает безопасную вставку в Notepad, браузеры или Word.

## Среда

- Дата: 2026-07-26.
- Windows 11 Pro x64, версия `10.0.22621`, build `22621`.
- Python `3.12.0`.
- Controlled fixture: native Win32 `EDIT` и `ES_PASSWORD`.
- Automated suite: 39 unit/contract tests на injected API facades.
- Установлены: Notepad `10.0.22621.3672`, Edge `150.0.4078.99`, Chrome
  `150.0.7871.125`, Firefox `147.0.2`, Word `16.0.17932.20884`.
- 1C не найдена через Windows App Paths.

## Проверенные Факты

- Неизменный native `EDIT` распознаётся как безопасная цель.
- Смена focused control внутри того же окна даёт `target_changed` до delivery.
- Native `ES_PASSWORD` даёт `target_protected`; попытка direct delivery не
  меняет control.
- Уничтоженный target даёт `target_unavailable`.
- Direct `SendInput` доставил в controlled fixture кириллицу, emoji и перенос
  строки; сравнение выполнено внутри fixture без вывода payload.
- Partial/failed dispatch, restoration failure, external clipboard change,
  cancellation, повторный и concurrent request покрыты contract tests.
- Поддержанные clipboard representations в injected API (`CF_UNICODETEXT`,
  `CF_DIB`, `CF_DIBV5`, `CF_HDROP`) клонируются и восстанавливаются вместе.
- HTML, RTF, unknown, delayed-rendered и partial-clone cases отклоняются до
  mutation.
- Реальный текущий clipboard содержал unsupported format. `prepare()` вернул
  `clipboard_unsafe` без mutation, поэтому пользовательские данные не были
  перезаписаны ради теста.
- `Ctrl+V` outcome называется только `dispatched`; подтверждение consumption
  destination application отсутствует.
- Canary payload отсутствовал в проверенных `repr`, boundary logs, CLI
  stdout/stderr и controlled fixture diagnostics.

Подробная versioned matrix и точные команды находятся в
`experiments/windows_insertion/README.md`.

## Не Выполнено

- Notepad insertion не запускалась: существующий пользовательский процесс не
  использовался как fixture, а UI Automation protection probe отсутствует.
- Browser normal/password cases не запускались в Edge/Chrome/Firefox: без UIA
  identity и `IsPassword` adapter обязан отказать fail-closed.
- Word не проверен без изолированного документа и UIA provider.
- 1C, email client и отдельный editor не проверены.
- Elevated case не запускался без отдельного operator-approved UAC session.
- Реальное восстановление image/file-list не проверено, потому что исходный
  clipboard нельзя было безопасно snapshot.
- Windows 10 не проверена.

Эти пункты имеют статус `not run`, а не `pass` или имитированный результат.

## Причина REWORK

Первая блокирующая гипотеза подтверждена только для controlled classic Win32
controls: identity, changed control, protected field и destroyed target
работают fail-closed. Для non-classic/browser controls защита недоступна без
UI Automation, поэтому обязательная application matrix не может быть
выполнена безопасно.

Вторая блокирующая гипотеза подтверждена контрактно и частично на реальном
clipboard: unsupported source безопасно отклоняется до mutation. Реальные
text/image/file-list restoration и external-race cases не были выполнены при
безопасно клонируемом исходном clipboard.

Это локальные пробелы adapter capability и acceptance setup, а не доказанная
невозможность fail-closed design. Поэтому выбран `REWORK`, а не `NO-GO`.

## Предлагаемые Production Ports

Ни один порт не должен раскрывать HWND, PID, COM object, UI Automation element
или clipboard handle:

1. `TargetCapturePort.capture() -> TargetToken` возвращает opaque token.
2. `TargetSafetyPort.assess(token) -> TargetAssessment` нормализует `safe`,
   `changed`, `protected`, `elevated` и `unavailable`.
3. `ClipboardTransactionPort.prepare() -> ClipboardPreparation` доказывает
   cloneability всех formats до mutation.
4. `ClipboardTransactionPort.commit_mutation(text)` и `restore(snapshot)`
   применяют sequence/ownership policy и никогда не перезаписывают более новое
   внешнее изменение.
5. `InputDispatchPort.dispatch_paste()` возвращает только `dispatched`, а
   `dispatch_unicode(text)` доступен лишь после отдельного safety permit.
6. Application service удерживает synthetic result до outcome, запрещает
   concurrent/repeated delivery и выполняет не более одной попытки.

Текущая Explicit Architecture уже предусматривает platform ports и узкие
Windows adapters. Изменение `.ai-factory/ARCHITECTURE.md` по результату spike
не требуется.

## Следующая Итерация

1. Выбрать и изолировать UI Automation provider с зафиксированными версией,
   лицензией и offline/runtime последствиями.
2. Добавить stable UIA runtime identity и `IsPassword` contract tests.
3. Запустить browser password fixture и isolated Notepad/Word cases.
4. Повторить real clipboard matrix из controlled synthetic initial states,
   включая image, file list и внешний sequence race.
5. Отдельно выполнить elevated case, Windows 10 и deferred Word/1C checks.

Residual TOCTOU между финальной revalidation и обработкой input целевым
приложением остаётся даже после REWORK и должен быть явно принят либо
дополнительно ограничен в production design.

## См. Также

- [Стратегия разработки](../architecture/Nadikt_development_strategy.md) - место Windows validation в общей последовательности.
- [ADR-001: стратегия кодовой базы](../architecture/ADR-001-codebase-strategy.md) - почему experiment не переносится как production subsystem.
- [Оценка репозиториев](repository_assessment.md) - исходные failure modes и решение `HYBRID`.
