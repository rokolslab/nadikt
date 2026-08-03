# Benchmark Environment Locks

Эти файлы описывают benchmark-only environment для real ASR load/probe и coding pilot. Они не фиксируют runtime или installer dependencies Nadikt.

## Profiles

| File | Scope |
|---|---|
| `base.lock.txt` | Standard-library harness profile; no external runtime packages required |
| `faster-whisper.lock.txt` | Optional faster-whisper/CTranslate2 CPU INT8 profile |
| `gigaam.lock.txt` | Optional GigaAM/PyTorch CPU profile |

Real benchmark run не выполняет dependency resolution, `pip install` или network access. Environment должен быть создан заранее из offline wheelhouse, а run получает только already installed packages, model inventory, sidecar manifest, private dataset bindings и externally blocked network evidence.

## Concrete Runtime Settings

- Python minor: `3.12`.
- Locale: `C.UTF-8` or explicitly recorded equivalent.
- `cpu_threads`: `4` for current i3 12th gen pilot unless a run record states otherwise.
- `OMP_NUM_THREADS`: `4`.
- `OPENBLAS_NUM_THREADS`: `1`.
- `MKL_NUM_THREADS`: `1`.
- faster-whisper device: `cpu`.
- faster-whisper compute type: `int8`.
- GigaAM device: `cpu`.

Do not use `auto` thread settings in a measured run. If a backend requires a different value, record it in the benchmark result and lock profile before running.

## Offline Wheelhouse Procedure

1. On a connected preparation machine, resolve the selected profile and download wheels into a controlled wheelhouse.
2. Verify package hashes against the lock file.
3. Copy the wheelhouse to the benchmark machine by offline media or another approved install-time channel.
4. Create the virtual environment from the wheelhouse only with network disabled.
5. Run `python3 -m benchmarks.asr.environment_fingerprint` and store only the safe JSON fingerprint with the benchmark artifact.

The fingerprint contains package versions and lock digest prefixes only. It must not contain hostname, username, interpreter path, argv, environment values, wheel/cache paths or proxy/credential settings.

## Lock Status

Backend lock files are intentionally separate because faster-whisper and GigaAM may require incompatible native dependency closures. Before a real benchmark, replace any `REVIEW_REQUIRED` hash line with a generated hash-checked lock from the approved wheelhouse and keep the exact file digest in benchmark results.
