# Model Package Inventory

Этот каталог хранит только documentation и example manifests для локальных ASR model packages. Model weights, tokenizer files, checkpoints и vendor artifacts не добавляются в Git. Для локальных экспериментов используйте ignored paths вроде `local-packages/` или controlled storage вне репозитория.

Delivery channels и trust model описаны в [`docs/requirements/model_package_delivery_policy.md`](../docs/requirements/model_package_delivery_policy.md). Runtime package validation не зависит от того, пришёл package из embedded installer, separate offline pack, removable media или explicitly requested online-installer fallback.

## Package Rules

- Runtime принимает только локальный directory/file path, прошедший manifest и checksum validation.
- Hub names, model aliases и repository IDs запрещены как runtime input, если они могут инициировать download.
- Expected manifest digest должен поступать из installer index или separately verified signed release index; digest внутри package не является trust anchor.
- Offline package является обязательным delivery channel; online acquisition разрешён только во время установки по явному запросу пользователя.
- Missing package, checksum mismatch и incompatible backend фиксируются отдельными safe outcome codes.
- Абсолютные пользовательские paths не печатаются в logs; используйте `package_id` и checksum prefix.
- License и third-party component notices обязательны до включения package в поставку.
- `.gitignore` запрещает типовые weights/tokenizer/checkpoint файлы и Hub caches; committed files здесь должны оставаться metadata-only.

## JSON Format

`model_inventory.example.json` is a local binding, not immutable model metadata:

```json
{
  "schema_version": 1,
  "manifest_kind": "example",
  "inventory_id": "nadikt-local-asr-packages-example",
  "packages": [
    {
      "package_id": "faster-whisper-small-int8-local",
      "package_path": "local-packages/faster-whisper-small-int8",
      "manifest_relative_path": "model_package_manifest.example.json",
      "manifest_sha256": "ac4625433d1c36245a7191b72502e91543312003bc18b3452f0947631a6652b0"
    }
  ]
}
```

Immutable package metadata lives in `model_package_manifest.example.json`; real package manifests are outside Git with model files or copied into controlled storage for validation. Non-example manifests must not use placeholder or all-zero digests.

## Required Fields

| Field | Rule |
|---|---|
| `schema_version` | Must be `1` |
| `inventory_id` | Stable inventory identifier |
| `package_id` | Stable safe ID used in logs and reports |
| `package_path` | Local path only; no Hub model name |
| `manifest_relative_path` | Sidecar manifest path inside the same controlled root |
| `manifest_sha256` | Expected sidecar digest from installer index or verified release index |

`model_package_manifest.v1` additionally requires backend, candidate/model revisions, Nadikt compatibility, rights statuses, capabilities, inference defaults, licenses/notices and critical files with `relative_path`, `sha256`, `size_bytes` and `role`.

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
