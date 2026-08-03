# План benchmark локальных ASR-моделей

## Статус

- Дата: 2026-07-27.
- Назначение: воспроизводимый protocol для сравнения локальных ASR-кандидатов Nadikt до выбора моделей Windows MVP.
- Стадия: protocol и dry-run harness; фактические измерения с реальными моделями пока не выполнены.

## Цель

Benchmark должен измерить качество, задержки и потребление ресурсов локальных ASR-кандидатов на текущей машине разработки и подготовить данные для последующей проверки на целевом Windows hardware baseline.

Текущая measurement machine: WSL2 Ubuntu на Windows 11 Pro, mini PC Intel Core i3 12-го поколения, 16 ГБ ОЗУ, без дискретной GPU.

Целевой baseline MVP из ТЗ: Windows 10/11 x64, Intel Core i3 10-го поколения, 16 ГБ ОЗУ, без дискретной GPU. Измерения на i3 12-го поколения не заменяют отдельное утверждение минимальных требований MVP.

## Scope

В benchmark входят:

- GigaAM-v3-e2e CTC для режима «Русский»;
- GigaAM-v3-e2e RNN-T для режима «Русский»;
- GigaAM Multilingual 220M для режима «Русский + English»;
- Whisper small INT8 через `faster-whisper` и локальный CTranslate2 package;
- T-one только при наличии локального package, понятной лицензии и offline lifecycle;
- CPU-only запуск без дискретной GPU;
- короткие фразы, смешанная русско-английская речь, фамилии, аббревиатуры, номера, паузы, офисный шум и длинная диктовка не менее 10 минут;
- WER, CER, accuracy английских терминов, latin preservation, cold load, warm-up, first result latency, RTF, stop-to-text latency, CPU utilization и peak RSS/RAM;
- проверка отсутствия сетевых зависимостей runtime.

Вне scope:

- облачный ASR;
- автоматическая загрузка моделей из Hub по model name;
- diarization, перевод, LLM-постобработка и смысловая коррекция;
- выбор финальной MVP-модели без фактических измерений, licensing review, packaging review и Windows-проверки;
- постоянное хранение пользовательских аудио или transcript payload.

## Coding Pilot Scope

Первый real run profile `coding-pilot-v1` является отдельным pilot, а не полным benchmark из этого документа.

- Frozen pair: `gigaam-multilingual-220m` и `faster-whisper-small-int8`.
- Dataset categories: отдельный non-scored `warmup`, scored `ru_short` и `ru_coding_terms`.
- Repeats: минимум три независимых repeat на candidate.
- Environment: отдельный per-candidate interpreter profile, complete transitive hash lock, offline wheelhouse install with `--no-index --require-hashes`.
- Evidence: qualified WSL2 default-deny enforcement plus process-tree observation profile `qualified-wsl2-default-deny-v1`.
- Publication: only schema v2 aggregate with finite metrics, complete matrix, validated privacy/offline evidence and no private paths or payload.
- Run profile artifact: `benchmarks/asr/run_profiles/coding_pilot.v1.json`; schema: `benchmarks/asr/schemas/run_profile.v1.schema.json`.
- Result schema artifact: `benchmarks/asr/schemas/benchmark_result.v2.schema.json`; v1 result schema remains unchanged for legacy validation.

Missing model package, hash lock, local-evaluation approval, controlled dataset or qualified offline evidence blocks publication. Poor measured WER/CER/RTF is a valid result; incomplete matrix, schema/privacy failure or `NOT VERIFIED` offline evidence is not publishable.

## Кандидаты

| Candidate ID | Назначение | Runtime input | Обязательные условия |
|---|---|---|---|
| `gigaam-v3-e2e-ctc` | Русский режим | Проверенный локальный package path | Сегменты не длиннее 25 секунд; не использовать longform path как autonomous runtime основание |
| `gigaam-v3-e2e-rnnt` | Русский режим | Проверенный локальный package path | Те же ограничения GigaAM; фиксировать CTC/RNN-T отдельно |
| `gigaam-multilingual-220m` | Русский + English | Проверенный локальный package path | Проверить сохранение английских терминов латиницей |
| `faster-whisper-small-int8` | Русский + English | Локальный CTranslate2 directory | `device="cpu"`, `compute_type="int8"`; полностью потреблять lazy `segments` generator |
| `tone-optional` | Перспективный лёгкий режим | Проверенный локальный package path | Только после подтверждения offline package и законного распространения |

Ни один runtime путь не должен быть заменён строкой `small`, Hub repository ID или другим identifier, который может инициировать сетевую загрузку.

## Dataset

Dataset описывается manifest без пользовательских payload. Обязательные категории:

- `ru_short`: короткие русские резолюции 5-20 секунд;
- `ru_en_terms`: русская речь с английскими терминами;
- `names_abbrev_numbers`: фамилии, аббревиатуры, номера документов, даты и суммы;
- `pauses_noise`: речь с паузами и умеренным офисным шумом;
- `long_10m`: непрерывная или близкая к реальной диктовка не менее 10 минут;
- `boundary_cases`: фразы, разрезанные на сегменты с overlap/no-overlap variants.

Каждый sample получает stable anonymous ID, duration bucket, language profile, reference label и список ожидаемых английских терминов. Raw audio, raw transcript и реальные пользовательские пути не коммитятся.

Manifest format описан в `benchmarks/asr/datasets/README.md`.

## Измеряемые Метрики

Для каждого candidate и run фиксируются:

- environment: OS, WSL version/kernel, CPU, RAM, Python, backend versions, thread settings;
- model package: exact model name, revision, backend, license marker, manifest checksum, critical file checksum prefixes;
- inference config: device, precision, compute type, beam size, batch size, VAD/segmentation config;
- cold load seconds;
- warm-up seconds;
- first segment latency seconds;
- per-segment inference seconds;
- RTF per sample and aggregate RTF;
- stop-to-text latency for 60-second and 10-minute scenarios;
- peak RSS MiB and process memory high watermark;
- average and max CPU utilization;
- WER and CER for Russian references;
- English term accuracy;
- latin preservation rate;
- punctuation and normalization notes as qualitative non-blocking fields;
- handled failures, cancellations and corrupted package outcomes.

## Resource Measurement

Wall-clock phases измеряются монотонным таймером. Cold load, warm-up, segment inference и result assembly измеряются отдельно.

На WSL2 Ubuntu baseline runner использует standard-library таймеры и доступные OS counters. Если `resource.getrusage()` доступен, peak RSS фиксируется как `ru_maxrss` с явной единицей платформы. CPU utilization для точного отчёта фиксируется внешним sampler или будущим adapter, а dry-run harness сохраняет только метод измерения и безопасные placeholders.

Windows host measurement выполняется отдельным запуском на целевой ОС: нужно явно указать Windows version, power plan, background load profile, Defender/Indexing state и список параллельных офисных приложений. WSL2 results не считаются Windows acceptance results.

## Segmentation Policy

Все кандидаты должны получать один и тот же segmentation manifest. Сравнение недействительно, если один engine получает заранее очищенные короткие сегменты, а другой получает raw long audio без эквивалентной политики.

Policy фиксирует:

- segment ID и monotonic order;
- duration seconds и duration bucket;
- overlap policy ID;
- pause handling;
- boundary case ID;
- max segment length per backend;
- сборку результата в исходном порядке.

Для GigaAM `.transcribe` используются только сегменты допустимой длительности, с целевым лимитом 25 секунд или меньше. Официальный GigaAM longform path не используется как основание autonomous runtime Nadikt, пока не подтверждён offline lifecycle без Hugging Face token и внешних условий доступа.

Для faster-whisper встроенный VAD считается отдельной конфигурацией и сравнивается только при явно зафиксированной parity policy.

## Offline Acceptance Run

Offline acceptance выполняется после подготовки локальных package manifests:

1. Подготовить clean cache/profile без Hub cache и пользовательских credentials.
2. Установить или смонтировать model packages локально.
3. Заблокировать исходящий сетевой доступ средствами ОС или изолированной среды.
4. Запустить dry-run validation manifests.
5. Запустить cold load, warm-up, короткие samples и long dictation для каждого candidate.
6. Проверить отсутствующий package и повреждённый checksum: результатом должен быть handled failure, не download.
7. Проверить, что перед загрузкой следующего candidate предыдущий engine закрыт и ресурсы освобождены.
8. Просмотреть stdout/stderr, logs, JSON/CSV results и crash artifacts на отсутствие audio/transcript/user dictionary payload.

Run считается failed, если runtime пытается открыть сеть, принимает Hub model name как package path или пишет sensitive payload в artifact.

For `coding-pilot-v1`, `offline_evidence.status=NOT VERIFIED` is a blocker for publication even if local load and transcription phases report success.

## Privacy Rules

Разрешённые log fields:

- run ID;
- engine ID;
- anonymized sample ID;
- dataset category;
- phase ID;
- durations;
- resource aggregates;
- backend and package versions;
- checksum prefixes;
- outcome codes;
- counts and boolean audit outcomes.

Запрещено логировать:

- audio bytes или audio file content;
- transcript, hypothesis, reference text или raw prompt;
- user dictionary entries;
- clipboard content;
- абсолютные пользовательские пути, если они раскрывают имя пользователя, клиента или документ;
- URLs или tokens.

Privacy audit использует canary phrase как controlled secret: audit может фиксировать только факт отсутствия/наличия canary и count, но не печатать сам canary.

## Quality Metrics

WER и CER считаются после одинаковой normalization policy для всех candidates. Нужно публиковать две view, если включается пунктуация:

- punctuation-insensitive raw ASR comparison;
- punctuation-sensitive diagnostic view.

English term accuracy считается по заранее заданному списку expected terms для sample. Latin preservation rate считает долю expected terms, которые появились в латинице, когда такое написание является требованием.

Постобработка Nadikt, пользовательский словарь и нормализация должны измеряться отдельно от raw ASR comparison, чтобы не скрыть качество backend.

## Acceptance Gates

Candidate допускается к следующему этапу только если:

- запускается offline из локального model package;
- не инициирует сетевую загрузку при отсутствующем или повреждённом package;
- работает на CPU без дискретной GPU;
- освобождает ресурсы перед загрузкой другого candidate;
- проходит long dictation через segmentation без программного лимита ASR-модели;
- не теряет порядок сегментов и не даёт систематических пропусков/повторов на границах;
- даёт измеримые CPU/RAM/RTF/latency на i3 12-го поколения и затем на Windows target baseline;
- сохраняет английские термины с качеством, достаточным для дальнейшего сравнения;
- не пишет audio или transcript payload в logs, crashes, stdout или result artifacts.

## Dry-Run Command

Минимальная проверка без моделей:

```bash
python3 -m benchmarks.asr.dry_run --dataset benchmarks/asr/datasets/dataset.example.json --models model_packs/model_inventory.example.json
```

Ожидаемый результат: безопасный JSON summary с deterministic missing-package outcomes, без скачивания моделей и без вывода transcript/audio payload.

Для controlled offline acceptance можно выставить `NADIKT_BENCHMARK_OFFLINE_REQUIRED=1`; dry-run отразит это в safe summary, но реальную блокировку исходящей сети всё равно должна обеспечить внешняя ОС/среда запуска.

## Local Package Probe Command

Prototype package lifecycle gate до реального benchmark:

```bash
python3 -m benchmarks.asr.local_model_probe --models model_packs/model_inventory.example.json --dry-run --offline-required
```

При наличии real packages вне Git dry-run убирается, а `--audio-file` допускается только для controlled audio outside Git вместе с safe `--audio-label`. JSON summary не должен содержать audio path или transcript payload.

Связанный prototype findings: `docs/research/local_asr_offline_package_prototype.md`.

## Prototype Gate To Real Benchmark

- faster-whisper допускается к real quality benchmark только после успешного local CTranslate2 load/warm-up/close under blocked-network policy и license/package review.
- GigaAM допускается к следующему package-lifecycle spike только через prefilled SDK cache-style package: `<gigaam_model_name>.ckpt` plus required tokenizer files under the validated package directory passed as `download_root`. A missing file must fail at package validation before `gigaam.load_model` can attempt download.
- Missing/corrupted packages должны завершаться safe outcome до backend import/load.
- В памяти одновременно может быть только один backend object; runner обязан закрыть текущий probe перед следующим package.
- Финальный ASR model остаётся `NOT DECIDED` до quality/resource результатов и Windows baseline checks.
