# План теста производительности: локальные ASR-модели

Branch: none
Created: 2026-07-27

## Original Request

пиши план теста производительности для локальных моделей, как ты предлагал

## Настройки

- Testing: yes - план включает проверяемый benchmark protocol, smoke checks runner, offline checks и повторяемые контрольные запуски.
- Logging: verbose - подробные технические события, длительности, версии, ресурсы и outcome codes; аудио, транскрипты, пользовательский словарь, clipboard и исходные тексты не логируются.
- Docs: yes - итоговый benchmark protocol и результаты должны быть опубликованы в `docs/research/` перед выбором модели.

## Roadmap Linkage

Milestone: "Квалификация критических технических рисков"

Rationale: performance benchmark локальных ASR-моделей закрывает риск выбора GigaAM/faster-whisper/VAD на CPU-only mini PC до реализации production pipeline.

## Цель

Получить воспроизводимый и privacy-safe протокол проверки локальных ASR-моделей на текущей машине разработки: Windows 11 Pro host, WSL2 Ubuntu, mini PC Intel Core i3 12-го поколения, 16 ГБ ОЗУ, без дискретной GPU. Результаты этого этапа маркируются как измерения на `i3 12-го поколения`; они не подменяют отдельное решение о минимальной hardware baseline MVP.

План не выбирает победителя заранее. Он задаёт одинаковые условия, метрики, ограничения и критерии допуска кандидатов к дальнейшему Windows vertical slice.

## Scope

В scope:

- GigaAM-v3-e2e CTC;
- GigaAM-v3-e2e RNN-T;
- GigaAM Multilingual 220M;
- faster-whisper Whisper small INT8 через локальный CTranslate2 package;
- T-one только при наличии локального package и понятного offline lifecycle;
- CPU-only запуск;
- короткие фразы, смешанная русско-английская речь, паузы, офисный шум и длинная диктовка не менее 10 минут;
- WER, CER, accuracy английских терминов, latin preservation, cold load, warm run, first result latency, RTF, stop-to-text latency, CPU, peak RSS/RAM;
- проверка отсутствия сетевых зависимостей runtime.

Вне scope:

- облачный ASR;
- автоматическая загрузка моделей по имени из Hub;
- diarization, перевод, LLM-постобработка и смысловая коррекция;
- выбор final MVP model без сопоставления качества, лицензий, packaging и Windows-проверки;
- постоянное хранение пользовательских аудио или транскриптов.

## Инварианты

1. Runtime принимает только локальный model package path, прошедший manifest/checksum validation.
2. Benchmark не использует model identifiers, которые могут инициировать сетевую загрузку.
3. Outbound network должен быть заблокирован или явно контролируем во время offline acceptance run.
4. В памяти одновременно находится не более одной основной ASR-модели.
5. GigaAM `.transcribe` получает только сегменты допустимой длительности; long dictation проверяется через общий segmentation manifest, а не через неподтверждённый cloud/Hugging Face-dependent longform path.
6. faster-whisper benchmark полностью потребляет lazy `segments` generator; иначе измерение недействительно.
7. Logs и result artifacts содержат только обезличенные IDs, агрегаты, метрики, версии, checksums и outcome codes.
8. Ошибка одного сегмента фиксируется как handled outcome и не уничтожает уже измеренные успешные сегменты.

## Тестовый Набор

Минимальный dataset должен быть версионирован как manifest без чувствительных данных:

- `ru_short`: короткие русские резолюции 5-20 секунд;
- `ru_en_terms`: русская речь с английскими терминами из требований ASR;
- `names_abbrev_numbers`: фамилии, аббревиатуры, номера документов, даты и суммы;
- `pauses_noise`: речь с паузами и умеренным офисным шумом;
- `long_10m`: непрерывная или близкая к реальной диктовка не менее 10 минут;
- `boundary_cases`: фразы, разрезанные на сегменты с overlap/no-overlap variants для проверки пропусков и повторов.

Каждый sample получает стабильный anonymous ID, длительность, language profile, expected transcript reference и список ожидаемых английских терминов. User-provided raw audio и transcript не попадают в Git без явного обезличивания и отдельного решения.

## Измеряемые Метрики

Для каждого кандидата и каждого run фиксируются:

- environment: OS, WSL version/kernel, CPU, RAM, Python, backend versions, thread settings;
- model package: exact model name, revision, license marker, manifest checksum, critical file checksums;
- inference config: device, precision, compute type, beam size, batch size, VAD/segmentation config;
- cold load seconds;
- warm-up seconds;
- first segment latency seconds;
- per-segment inference seconds;
- RTF per sample and aggregate RTF;
- stop-to-text latency for 60-second and 10-minute scenarios;
- peak RSS MiB and process memory high watermark;
- average and max CPU utilization;
- WER/CER for Russian references;
- English term accuracy;
- latin preservation rate;
- punctuation/normalization notes as non-blocking qualitative fields;
- handled failures, cancellations and corrupted package outcomes.

## Acceptance Gates

Кандидат допускается к следующему этапу только если:

- запускается offline из локального model package;
- не инициирует сетевую загрузку при отсутствующем или повреждённом package;
- работает на CPU без дискретной GPU;
- освобождает ресурсы перед загрузкой другого кандидата;
- проходит long dictation через segmentation без программного лимита ASR-модели;
- не теряет порядок сегментов и не даёт систематических пропусков/повторов на границах;
- даёт измеримые CPU/RAM/RTF/latency на i3 12-го поколения;
- сохраняет английские термины с качеством, достаточным для дальнейшего сравнения;
- не пишет аудио или транскрипты в logs, crashes или benchmark stdout.

## Commit Plan

- **Commit 1** (после задач 1-3): `docs(asr): define local model benchmark protocol`
- **Commit 2** (после задач 4-6): `feat(asr): add benchmark contracts and runner skeleton`
- **Commit 3** (после задач 7-9): `test(asr): validate offline benchmark harness`
- **Commit 4** (после задач 10-11): `docs(asr): publish benchmark results and decision inputs`

## Задачи

### Фаза 1. Protocol И Dataset

- [x] **Задача 1. Зафиксировать benchmark protocol document**
  - Deliverable: создать `docs/research/local_asr_performance_benchmark_plan.md` с scope, environment, model candidates, metrics, acceptance gates и privacy rules.
  - Поведение: документ должен явно различать текущую measurement machine (`i3 12-го поколения`) и минимальную MVP hardware baseline, если она будет утверждаться отдельно.
  - Зависимости: нет.
  - Проверки: protocol покрывает требования `docs/requirements/Nadikt_TZ_v0.2.md` и `docs/requirements/Nadikt_multilingual_ASR_requirements.md`; отсутствуют обещания выбора модели до измерений.
  - Logging: описать допустимые log fields: run ID, anonymized sample ID, durations, resource aggregates, versions, checksums, outcome codes; запретить audio/transcript payload.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`.

- [x] **Задача 2. Определить dataset manifest format**
  - Deliverable: спроектировать `benchmarks/asr/datasets/README.md` и schema для обезличенного manifest, не добавляя пользовательские аудио в Git.
  - Поведение: manifest описывает anonymous sample IDs, duration, category, expected-language profile, reference location policy и expected English terms без раскрытия пользовательских данных.
  - Зависимости: задача 1.
  - Проверки: schema поддерживает `ru_short`, `ru_en_terms`, `names_abbrev_numbers`, `pauses_noise`, `long_10m`, `boundary_cases`; отсутствуют реальные sensitive paths или transcripts в committed fixtures.
  - Logging: log runner читает только sample IDs и категории; file paths печатаются только как безопасные anonymized labels или hashed IDs.
  - Files: `benchmarks/asr/datasets/README.md`, будущий `benchmarks/asr/datasets/*.example.json`.

- [x] **Задача 3. Определить model package inventory format**
  - Deliverable: описать manifest для локальных model packages: model name, revision, backend, license marker, checksums, local path, capabilities и inference defaults.
  - Поведение: package inventory запрещает Hub names как runtime input и требует локальный directory/file path.
  - Зависимости: задача 1.
  - Проверки: отсутствующий package, повреждённый checksum и несовместимый backend имеют отдельные failure outcomes; model weights не добавляются в Git.
  - Logging: разрешены model ID, backend version, checksum prefix и outcome; запрещены абсолютные пользовательские пути, если они раскрывают личные данные.
  - Files: `model_packs/README.md`, будущий `model_packs/*.example.json`.

### Фаза 2. Benchmark Harness Design

- [x] **Задача 4. Создать ASR benchmark contract skeleton**
  - Deliverable: спроектировать минимальные контракты для benchmark runner: engine lifecycle, segment input, normalized transcript result, capabilities и failure codes.
  - Поведение: контракты не импортируют GigaAM, faster-whisper, PyTorch, CTranslate2, PySide6, Windows API или SDK-specific result objects.
  - Зависимости: задачи 1 и 3.
  - Проверки: один контракт выражает load, readiness, warm-up, transcribe segment, cancel/current-run stop, close и metadata; одна model active at a time.
  - Logging: lifecycle logs на DEBUG/INFO только с engine ID, phase, duration и outcome code; transcript text не передаётся в logger.
  - Files: будущие `src/nadikt/domain/ports/asr.py`, `benchmarks/asr/`.

- [x] **Задача 5. Спроектировать resource measurement method**
  - Deliverable: выбрать метод измерения wall-clock, CPU utilization и peak RSS для WSL2 Ubuntu, с fallback на Windows host measurement notes для будущего этапа.
  - Поведение: cold load, warm-up, inference и result assembly измеряются отдельно; background load фиксируется в run metadata.
  - Зависимости: задача 1.
  - Проверки: протокол различает cold run и warm run; runner не смешивает model load time с segment inference time.
  - Logging: resource logs содержат timestamps, phase IDs, CPU/RAM aggregates и measurement backend; не содержат sample text или audio content.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`, будущий `benchmarks/asr/metrics.py`.

- [x] **Задача 6. Спроектировать segmentation comparison policy**
  - Deliverable: определить, как один и тот же segmentation manifest применяется ко всем кандидатам, включая GigaAM limit до 25 секунд и faster-whisper VAD options.
  - Поведение: сравнение не считается честным, если один engine получает заранее очищенные сегменты, а другой - raw long audio без эквивалентной политики.
  - Зависимости: задачи 1 и 2.
  - Проверки: protocol фиксирует segment length, overlap, pause handling, boundary IDs и long dictation ordering; GigaAM longform path не используется как основание autonomous runtime.
  - Logging: logs содержат segment IDs, duration buckets, boundary policy ID и outcome; не содержат распознанный текст.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`, будущий `benchmarks/asr/segmentation_manifest.py`.

### Фаза 3. Offline И Quality Checks

- [x] **Задача 7. Определить offline acceptance run**
  - Deliverable: описать командный сценарий запуска benchmark с заблокированным исходящим доступом и чистым cache/profile для каждого backend.
  - Поведение: отсутствующая модель даёт понятную ошибку и не скачивается; faster-whisper получает только local CTranslate2 path; GigaAM local loading проверяется отдельным prototype note.
  - Зависимости: задачи 3 и 4.
  - Проверки: run fails if network access is attempted or if model package path is missing; failure recorded as safe outcome.
  - Logging: log network/offline check only as boolean/outcome and backend ID; не логировать URLs с токенами, пути профиля пользователя или payload.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`, будущий `benchmarks/asr/offline_check.py`.

- [x] **Задача 8. Определить privacy audit для benchmark artifacts**
  - Deliverable: checklist проверки stdout/stderr, log files, result JSON/CSV и crash artifacts на отсутствие audio/transcript/user dictionary payload.
  - Поведение: result artifacts содержат aggregate quality metrics и anonymous sample IDs; reference transcripts остаются в controlled dataset storage с отдельными правилами доступа.
  - Зависимости: задачи 1 и 2.
  - Проверки: synthetic canary phrase не появляется в logs/results; runner не вызывает `repr()` объектов, содержащих transcript text.
  - Logging: audit logs содержат только checked artifact names/categories, canary absence result и counts; canary value не печатается.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`, будущие `benchmarks/asr/privacy_audit.py`, `tests/contract/`.

- [x] **Задача 9. Определить quality metrics implementation rules**
  - Deliverable: описать правила расчёта WER, CER, English term accuracy и latin preservation, включая normalization до сравнения.
  - Поведение: одна и та же normalization policy применяется ко всем candidate outputs; постобработка Nadikt отделяется от raw ASR comparison.
  - Зависимости: задачи 1 и 2.
  - Проверки: metrics на synthetic examples дают ожидаемые значения; punctuation-sensitive и punctuation-insensitive views явно различаются.
  - Logging: metric logs содержат sample ID, metric name, numeric value и version; не содержат hypothesis/reference text.
  - Files: `docs/research/local_asr_performance_benchmark_plan.md`, будущий `benchmarks/asr/quality_metrics.py`.

### Фаза 4. Execution И Решение

- [x] **Задача 10. Выполнить пилотный dry run без реальных моделей**
  - Deliverable: dry-run сценарий, который проходит manifests, validates packages as missing/placeholder, генерирует safe failure report и проверяет privacy/logging constraints.
  - Поведение: dry run не требует скачивания models и не создаёт production source без согласованной задачи реализации.
  - Зависимости: задачи 2, 3, 7, 8.
  - Проверки: no network, no model download, no sensitive payload in logs, deterministic failure outcomes for missing packages.
  - Logging: DEBUG для phases и validation decisions; INFO для итоговых counts; ERROR только для unexpected runner failures без payload.
  - Files: будущие `benchmarks/asr/`, `tests/contract/`, `docs/research/local_asr_performance_benchmark_plan.md`.

- [x] **Задача 11. Опубликовать benchmark results template и decision matrix**
  - Deliverable: создать шаблон `docs/research/local_asr_performance_benchmark_results.md` с таблицами по моделям, environment, metrics, limitations и recommendation fields.
  - Поведение: шаблон не выбирает модель без фактических запусков; он фиксирует, какие данные нужны для выбора Russian и Russian+English modes.
  - Зависимости: задачи 1-10.
  - Проверки: template содержит отдельные разделы для GigaAM CTC/RNN-T, GigaAM Multilingual 220M, faster-whisper small INT8 и optional T-one; ограничения WSL2/Windows runtime явно указаны.
  - Logging: итоговый report включает только агрегаты и anonymized sample IDs; raw transcripts остаются вне публичного report.
  - Files: `docs/research/local_asr_performance_benchmark_results.md`.

## Ожидаемый Результат

После выполнения плана у проекта будет воспроизводимый протокол и harness design для честного CPU-only сравнения локальных ASR-кандидатов. Только после фактических запусков можно будет выбрать кандидата для режима «Русский», кандидата для режима «Русский + English» и границы дальнейшего Windows vertical slice.
