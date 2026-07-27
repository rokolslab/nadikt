# Model Package Inventory

Этот каталог хранит только documentation и example manifests для локальных ASR model packages. Model weights, tokenizer files, checkpoints и vendor artifacts не добавляются в Git.

## Package Rules

- Runtime принимает только локальный directory/file path, прошедший manifest и checksum validation.
- Hub names, model aliases и repository IDs запрещены как runtime input, если они могут инициировать download.
- Missing package, checksum mismatch и incompatible backend фиксируются отдельными safe outcome codes.
- Абсолютные пользовательские paths не печатаются в logs; используйте `package_id` и checksum prefix.
- License и third-party component notices обязательны до включения package в поставку.

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
        {"relative_path": "model.bin", "sha256": "example-not-a-real-checksum"}
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

## Candidate Notes

- GigaAM `.transcribe` is limited to short audio; long dictation must go through Nadikt segmentation.
- GigaAM local loading API must be confirmed by offline prototype before production adapter work.
- faster-whisper receives a local CTranslate2 directory, not `small` or a Hugging Face repository name.
- T-one stays optional until local package lifecycle and redistribution terms are proven.
