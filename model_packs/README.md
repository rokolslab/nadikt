# Model Package Inventory

Этот каталог хранит только documentation и example manifests для локальных ASR model packages. Model weights, tokenizer files, checkpoints и vendor artifacts не добавляются в Git. Для локальных экспериментов используйте ignored paths вроде `local-packages/` или controlled storage вне репозитория.

## Package Rules

- Runtime принимает только локальный directory/file path, прошедший manifest и checksum validation.
- Hub names, model aliases и repository IDs запрещены как runtime input, если они могут инициировать download.
- Missing package, checksum mismatch и incompatible backend фиксируются отдельными safe outcome codes.
- Абсолютные пользовательские paths не печатаются в logs; используйте `package_id` и checksum prefix.
- License и third-party component notices обязательны до включения package в поставку.
- `.gitignore` запрещает типовые weights/tokenizer/checkpoint файлы и Hub caches; committed files здесь должны оставаться metadata-only.

## JSON Format

```json
{
  "schema_version": 1,
  "inventory_id": "nadikt-local-asr-packages-example",
  "packages": [
    {
      "package_id": "faster-whisper-small-int8-local",
      "candidate_id": "faster-whisper-small-int8",
      "backend": "faster-whisper",
      "model_name": "Whisper small CTranslate2 INT8",
      "model_revision": "example-revision",
      "package_path": "local-packages/faster-whisper-small-int8",
      "license_marker": "TO_BE_VERIFIED",
      "compatible_nadikt_versions": ["0.x-prototype"],
      "capabilities": {
        "languages": ["ru", "en"],
        "punctuation": true,
        "max_segment_seconds": 25.0,
        "streaming": false
      },
      "inference_defaults": {
        "device": "cpu",
        "compute_type": "int8",
        "beam_size": 5,
        "cpu_threads": "auto"
      },
      "critical_files": [
        {"relative_path": "model.bin", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
      ]
    }
  ]
}
```

## Required Fields

| Field | Rule |
|---|---|
| `schema_version` | Must be `1` |
| `inventory_id` | Stable inventory identifier |
| `package_id` | Stable safe ID used in logs and reports |
| `candidate_id` | Benchmark candidate ID |
| `backend` | `gigaam`, `faster-whisper`, or explicitly documented local backend |
| `model_name` | Exact model/package name for reports |
| `model_revision` | Exact revision or version marker |
| `package_path` | Local path only; no Hub model name |
| `license_marker` | License status marker or exact license identifier |
| `compatible_nadikt_versions` | Supported Nadikt version range |
| `capabilities` | Languages, max segment length and optional features |
| `inference_defaults` | CPU/precision/threads/beam/VAD config used by benchmark |
| `critical_files` | Relative paths and expected SHA-256 values for validation |

## Failure Outcomes

| Outcome | Meaning |
|---|---|
| `missing_package` | `package_path` does not exist locally |
| `invalid_package_path` | Runtime input is not a local path or is a forbidden model identifier |
| `checksum_mismatch` | Critical file hash differs from manifest |
| `missing_critical_file` | Manifest references a required file that is absent |
| `incompatible_backend` | Backend/package does not match runner contract |
| `license_not_verified` | Package cannot advance to MVP packaging gate |

## Local Payload Policy

- Не храните real model packages, Hub caches, raw audio, reference transcripts или generated probe outputs в Git.
- Разрешены только example manifests, documentation и tiny synthetic text fixtures, которые не похожи на реальные model weights.
- Для проверки ignore policy используйте synthetic paths under ignored directories, например `local-packages/<package-id>/` и `benchmarks/asr/runs/<run-id>/`.
- Reports и logs должны ссылаться на `package_id`, `candidate_id`, backend, phase/outcome codes и checksum prefixes, но не на абсолютные локальные пути.

## Candidate Notes

- GigaAM `.transcribe` is limited to short audio; long dictation must go through Nadikt segmentation.
- GigaAM package layout follows SDK cache-style loading: critical files must include the expected `<gigaam_model_name>.ckpt` and, for `e2e`/`v1_rnnt` models, `<gigaam_model_name>_tokenizer.model`; the adapter passes `download_root` only after package validation.
- faster-whisper receives a local CTranslate2 directory, not `small` or a Hugging Face repository name.
- T-one stays optional until local package lifecycle and redistribution terms are proven.
