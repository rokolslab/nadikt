# Benchmark Environment Locks

Эти файлы описывают benchmark-only environment для real ASR load/probe и coding pilot. Они не фиксируют runtime или installer dependencies Nadikt.

## Coding Pilot Readiness Contract

The first real coding pilot is fail-closed until every item below is true:

- frozen candidate pair is exactly `gigaam-multilingual-220m` and `faster-whisper-small-int8`;
- each candidate uses its own interpreter profile and its own complete transitive `--require-hashes` lock;
- backend profile locks contain no `REVIEW_REQUIRED`, floating ranges, editable installs, URLs or index-dependent requirements;
- Python/platform ABI is fixed to Python `3.12` on Linux/WSL2 x86_64 for the WSL2 pilot;
- the benchmark environment is installed from an approved offline wheelhouse with `--no-index --require-hashes` before the run;
- controlled private model packages, dataset bindings, audio/reference files and local-evaluation approval records exist outside Git;
- WSL2 network evidence uses a qualified external default-deny plus process-tree observation profile with positive and negative controls.

If any item is missing, the operator records `BLOCKED`, `NOT AVAILABLE` or `NOT VERIFIED` and does not publish placeholder metrics.

## Profiles

| File | Scope |
|---|---|
| `base.lock.txt` | Standard-library harness profile; no external runtime packages required |
| `faster-whisper.lock.txt` | Optional faster-whisper/CTranslate2 CPU INT8 profile recipe; not a real-run lock until materialized |
| `gigaam.lock.txt` | Optional GigaAM/PyTorch CPU profile recipe; not a real-run lock until materialized |

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
2. Generate a complete transitive hash lock for the selected backend profile.
3. Copy the wheelhouse to the benchmark machine by offline media or another approved install-time channel.
4. Create the virtual environment from the wheelhouse only with network disabled: `python -m pip install --no-index --find-links <wheelhouse> --require-hashes -r <materialized-lock>`.
5. Run `python3 -m benchmarks.asr.environment_fingerprint` and store only the safe JSON fingerprint with the benchmark artifact.

The fingerprint contains package versions and lock digest prefixes only. It must not contain hostname, username, interpreter path, argv, environment values, wheel/cache paths or proxy/credential settings.

For the first faster-whisper coding pilot, the connected preparation step starts
from `faster-whisper==1.1.1`, `ctranslate2==4.6.0`, `tokenizers==0.21.0` and
`numpy==2.2.2`, then resolves every transitive wheel into the materialized lock.
The run artifact records only package/version IDs and lock or wheelhouse digest
prefixes, never the wheelhouse path.

For the first GigaAM coding pilot, the connected preparation step starts from
`gigaam==0.1.0`, `torch==2.6.0`, `torchaudio==2.6.0` and `numpy==2.2.2`, then
resolves every transitive wheel into a separate materialized lock. The GigaAM
profile is isolated from the faster-whisper profile because their native
dependency closures can conflict.

## Network Evidence Profile

The WSL2 coding pilot uses readiness profile `qualified-wsl2-default-deny-v1`.
It is not satisfied by an environment variable or self-declared offline marker.
The profile must provide:

- default-deny outbound enforcement before worker spawn;
- process-tree observation until after worker reap;
- positive control proving a blocked network attempt is observed as `FAIL`;
- negative control proving a no-network worker produces finalized zero-attempt evidence;
- evidence binding to run nonce, full Git SHA, package digest prefixes, lock digest prefixes and monitor interval.

If the observer is unavailable, stale, unbound, self-declared or partial, the run
status is `NOT VERIFIED` and the aggregate is not publishable as an accepted
coding-pilot result.

## Lock Status

Backend lock files are intentionally separate because faster-whisper and GigaAM may require incompatible native dependency closures. Current backend files are recipes, not approved real-run locks. Before a real benchmark, replace each recipe with a generated full transitive hash lock from the approved wheelhouse and keep the exact file digest in benchmark results. A backend profile containing `Status: NOT_MATERIALIZED` is a readiness blocker.
