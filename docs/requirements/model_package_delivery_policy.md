# Model Package Delivery Policy

**Статус:** policy/amendment для ASR model package delivery. Основное ТЗ `Nadikt_TZ_v0.2.md` не изменяется этим документом.

## Назначение

Этот документ разделяет доставку модельного пакета во время установки и загрузку модели в runtime. Все каналы доставки должны приводить к одному результату: локальному проверенному model package, который runtime открывает только по local path после manifest, checksum, compatibility и license gates.

## Каналы Доставки

Поддерживаемые каналы являются взаимозаменяемыми относительно runtime:

- **Embedded installer:** installer содержит model package или переносит его из своего payload.
- **Separate offline pack:** model package поставляется отдельным файлом рядом с installer.
- **Removable media:** model package копируется с flash drive или другого локального носителя.
- **Online installer fallback:** installer явно по запросу пользователя получает package во время установки.

Offline package остаётся обязательным release channel. Online acquisition не может быть единственным способом установки и не является runtime fallback.

## Trust Model

Runtime не доверяет metadata внутри загруженного package как trust anchor. Expected manifest digest должен поступать из одного из внешних проверяемых источников:

- встроенный installer index;
- separately verified signed release index.

После получения package runtime или installer validation сравнивает sidecar manifest digest с expected digest, затем проверяет critical file SHA-256, package layout, backend compatibility, Nadikt compatibility и rights status для требуемого gate.

## Package Staging And Registration

Установка package выполняется по fail-closed схеме:

1. Stage package во временную локальную область вне runtime registry.
2. Проверить sidecar manifest digest по trust anchor.
3. Проверить schema version, package ID, model revision, backend, compatibility и critical file checksums.
4. Проверить licenses/notices и rights statuses.
5. Зарегистрировать package атомарно в local inventory только после успешных gates.
6. При ошибке удалить staged package или оставить его незарегистрированным с safe outcome code.

Local inventory не дублирует immutable package metadata. Он связывает `package_id` с локальным `package_path`, `manifest_relative_path` и `manifest_sha256`.

## Runtime Loading Rules

Runtime принимает только локальный package path из local inventory или явно выбранный local path, прошедший те же validation gates. Запрещены:

- Hub IDs, repository names, aliases и URLs вместо local path;
- implicit network download при отсутствии package;
- fallback к cloud ASR;
- использование package с checksum mismatch, incompatible backend или неподтверждённым local evaluation status.

Missing, corrupted, incompatible или unapproved package должен завершаться до ASR SDK import/load с typed safe outcome. Пользователь может выбрать другой установленный package вручную; автоматическая подмена модели во время активной диктовки запрещена.

## Rights Statuses

Legal/release review ведётся независимо по каналам и gate types:

| Status Field | Назначение |
|---|---|
| `local_evaluation` | Разрешение на локальный benchmark/prototype use |
| `redistribution` | Разрешение распространять package отдельно |
| `bundling` | Разрешение включить package в installer payload |
| `installer_download` | Разрешение installer-time download |

Каждое поле принимает только `approved`, `prohibited` или `review_required` и содержит `review_record_id`. Benchmark gate требует `local_evaluation=approved`. Release gate дополнительно требует approvals для выбранных delivery channels.

Статусы не утверждают конкретный installer, право распространения или финальный ASR choice до отдельного legal/product review.

## Rollback And Failure Behavior

- Failed installation не меняет active package registry.
- Failed runtime validation не импортирует backend SDK и не начинает dictation session.
- Failed switch сохраняет последнюю работоспособную конфигурацию, если она безопасна и совместима.
- Повреждённый package получает safe outcome code и понятное пользовательское сообщение без raw paths или SDK errors.

## Logging And Privacy

Разрешены только `package_id`, `candidate_id`, validation phase, outcome code, duration, checksum prefix и aggregate resource metrics. Запрещены URLs, tokens, absolute paths, model payload, audio/reference/transcript payload, license document content, raw exception text и backend stdout/stderr.

## Open Items

- Выбрать concrete model package formats после real local load/probe.
- Подтвердить redistribution/bundling/installer_download rights для каждого candidate.
- Выбрать Windows packaging mechanism, который поддержит offline pack import и checksum verification.
