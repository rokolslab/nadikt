# ASR Dataset Manifest

Этот каталог хранит только schema, examples и обезличенные manifests для benchmark. Пользовательские audio files, raw transcripts, reference text и реальные пути к ним не коммитятся.

## Privacy Rules

- Sample IDs должны быть anonymous и стабильными, например `ru_short_001`.
- `audio_label` и `reference_label` являются opaque labels, а не абсолютными путями.
- Raw audio хранится вне Git в controlled storage.
- Reference transcripts хранятся вне публичных artifacts; manifest указывает только policy/label.
- `benchmarks/asr/datasets/audio/`, `benchmarks/asr/datasets/references/` и generated `benchmarks/asr/runs/` игнорируются Git и предназначены только для локальных controlled checks.
- Expected English terms можно указывать, если они не раскрывают пользовательские данные и нужны для ASR acceptance.
- Runner logs используют только `sample_id`, `category`, duration bucket и outcome codes.

## Categories

| Category | Назначение |
|---|---|
| `ru_short` | Короткие русские резолюции 5-20 секунд |
| `ru_en_terms` | Русская речь с английскими терминами |
| `names_abbrev_numbers` | Фамилии, аббревиатуры, номера документов, даты и суммы |
| `pauses_noise` | Паузы и умеренный офисный шум |
| `long_10m` | Диктовка не менее 10 минут |
| `boundary_cases` | Проверка стыков сегментов, overlap и no-overlap variants |

## JSON Format

```json
{
  "schema_version": 1,
  "dataset_id": "nadikt-local-asr-benchmark-example",
  "dataset_revision": "example-2026-07-27",
  "storage_policy": "Raw audio and reference transcripts are stored outside Git in controlled storage.",
  "samples": [
    {
      "sample_id": "ru_short_001",
      "category": "ru_short",
      "duration_seconds": 12.4,
      "language_profile": "ru",
      "audio_label": "controlled-audio:ru_short_001",
      "reference_label": "controlled-reference:ru_short_001",
      "expected_english_terms": [],
      "segmentation_policy_id": "seg-25s-no-overlap-v1",
      "notes": "Synthetic or anonymized office phrase. No transcript here."
    }
  ]
}
```

## Required Fields

| Field | Type | Rule |
|---|---|---|
| `schema_version` | integer | Must be `1` |
| `dataset_id` | string | Stable dataset identifier without user names |
| `dataset_revision` | string | Exact revision used in benchmark reports |
| `storage_policy` | string | Must state that raw payload is outside Git |
| `samples` | array | Non-empty list of sample metadata |
| `sample_id` | string | Stable anonymous ID |
| `category` | string | One of the required categories |
| `duration_seconds` | number | Positive duration; `long_10m` must be at least `600` |
| `language_profile` | string | `ru`, `ru_en`, or a documented profile ID |
| `audio_label` | string | Opaque controlled-storage label, not an absolute path |
| `reference_label` | string | Opaque reference label, not transcript text |
| `expected_english_terms` | array | Expected terms for mixed speech checks |
| `segmentation_policy_id` | string | Links sample to segmentation manifest/policy |

## Validation Rules

- Manifest must include every required category before a full benchmark is valid.
- Example manifests may be incomplete only when `manifest_kind` is `example`.
- No field may contain transcript text, raw audio content, user dictionary entries or clipboard data.
- Absolute paths are rejected by the dry-run validator because they can reveal local user or client names.
- Sample IDs and labels are safe to print; references and hypotheses are not printed.
- Committed fixtures must stay synthetic metadata-only; real audio, raw transcript, reference text and user dictionary material are never committed.
