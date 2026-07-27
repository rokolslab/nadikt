# Windows Insertion Safety Spike

Disposable experiment for validating Windows target identity, protected-field
detection, clipboard ownership, and input dispatch. Code in this directory is
not production code and must not be imported by `src/nadikt`.

The spike uses only Python 3.12 standard-library modules. Win32 calls are kept
behind injected API facades so contract tests do not manipulate the desktop.

## Safety Rules

- Never print or log request text, clipboard payloads, window titles, process
  names, handles, process IDs, control content, or filenames.
- Reject delivery when target identity, protection state, integrity level, or
  clipboard restorability is uncertain.
- Keep the synthetic result in memory after every failure.
- Never overwrite a newer external clipboard change during restoration.
- Never retry a delivery request.

## Commands

Run the automated contracts from this directory:

```powershell
python -m unittest discover -s tests -v
```

Set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` to
control spike diagnostics. Logs contain only safe state and outcome codes.

No network access or external package installation is required.

## Controlled Fixtures

From `experiments/windows_insertion`:

```powershell
python fixtures/classic_target.py
start fixtures/password_form.html
python -m fixtures.clipboard_racer --confirm --delay-ms 0
```

`classic_target.py` exposes one native `EDIT` and one native `ES_PASSWORD`
control. The local HTML page exposes two normal controls and one password
control in the same browser window. `clipboard_racer.py` writes only a fixed
synthetic value and reports readiness/case IDs without printing the value. It
must run during a CLI clipboard transaction: `--confirm` is mandatory, and the
fixture refuses mutation unless the current clipboard contains exactly the
known CLI synthetic payload (plus Windows-synthesized text formats).
Run it from a second terminal while the CLI is waiting for explicit clipboard
restoration; standalone or early execution fails the synthetic precondition.

An elevated case is started manually from an elevated terminal. The spike
never requests elevation or bypasses UIPI.

## Manual CLI

Review the fixed synthetic payload in `insertion_spike/cli.py`, focus the
target during the first countdown, and use the second countdown to keep or
intentionally change focus:

```powershell
python -m insertion_spike.cli --confirm --method auto --hold
python -m insertion_spike.cli --confirm --method paste --hold
python -m insertion_spike.cli --confirm --method direct
python -m insertion_spike.cli --confirm --dry-run
python -m insertion_spike.cli --confirm --cancel
```

`Ctrl+V` success means only `dispatched`, never confirmed insertion. The service
does not restore the original clipboard on a timer: synthetic text and the
in-memory original snapshot remain until the operator verifies target handling
and types `RESTORE`. `Ctrl+C`/EOF cannot bypass this pending decision;
`DISCARD_ORIGINAL` is the explicit destructive alternative. A newer external
clipboard change is never overwritten.

There remains an unavoidable TOCTOU interval between final target validation
and processing of synthetic input by the destination application.

## Acceptance Matrix

Matrix revision: `2026-07-27-1`.
Merged baseline revision: `5ee5726` (`feat(windows): qualify insertion safety spike`).

Environment:

- Windows 11 Pro x64, version `10.0.22621`, build `22621`.
- Python `3.12.0`.
- Notepad `10.0.22621.3672` (installed; an existing user instance was not
  reused for synthetic input).
- Microsoft Edge `150.0.4078.99`, Chrome `150.0.7871.125`, Firefox `147.0.2`,
  and Word `16.0.17932.20884` are installed according to App Paths.
- 1C was not found through App Paths.

Commands executed from `experiments/windows_insertion`:

```powershell
python -m unittest discover -s tests
python fixtures/classic_target.py --self-check
python -m insertion_spike.cli --confirm --dry-run
```

The current real clipboard was also probed with
`WindowsClipboardAdapter.prepare()`. It contained an unsupported format, so
the adapter returned `clipboard_unsafe` before mutation. No payload or format
name was printed.

| Case | Layer | Result | Observed outcome |
|---|---|---|---|
| Contracts and boundary failures | automated, injected APIs | PASS | 63 tests passed |
| Unchanged native `EDIT` target | controlled Win32 fixture | PASS | `safe` |
| Direct Cyrillic, emoji, newline | controlled Win32 fixture | PASS | `direct_dispatched`, content matched internally |
| Another control in same window | controlled Win32 fixture | PASS | `target_changed` |
| Classic password field | controlled Win32 fixture | PASS | `target_protected` |
| Delivery attempt to classic password | controlled Win32 fixture | PASS | `target_protected`, control unchanged |
| Destroyed target | controlled Win32 fixture | PASS | `target_unavailable` |
| Current rich/unknown clipboard | real clipboard, read-only prepare | PASS | `clipboard_unsafe`, no mutation |
| Text/Unicode/DIB/DIBV5/file-list round trip | automated, injected API | PASS | restored for every supported combination |
| HTML/RTF/unknown/delayed clipboard | automated, injected API | PASS | rejected before mutation |
| External clipboard sequence change | automated, injected API | PASS | restoration skipped, external value retained |
| Dispatch/restoration failure | automated, injected API | PASS | no timer restoration after queued input; original retained for explicit restoration |
| Repeated/concurrent request | automated, injected API | PASS | `already_delivered` / `busy` |
| CLI dry-run and cancel | automated and CLI smoke | PASS | no clipboard or keyboard access |
| Notepad paste/direct insertion | installed application | NOT RUN | UIA protection probe unavailable; fail-closed delivery prohibited |
| Browser normal/password fields | installed Edge/Chrome/Firefox | NOT RUN | no UI Automation provider in this spike |
| Word | installed application | NOT RUN | no isolated document and UIA provider unavailable |
| 1C | application | NOT RUN | application not found |
| Elevated target | manual UAC case | NOT RUN | no operator-approved elevated fixture run |
| Real image/file-list restoration | real clipboard | NOT RUN | original clipboard was not safely cloneable |
| Email client/editor | application | NOT RUN | no isolated application fixture selected |

The automated privacy contracts verify that canary request data is absent
from `repr`, boundary error logs, CLI stdout, and CLI stderr. Controlled fixture
output contains only case IDs, outcome codes, booleans, and aggregate lengths.
This does not claim inspection of arbitrary OS process dumps.

## Measured Limitations

- The standard-library target facade detects native `EDIT`/`ES_PASSWORD` and
  process integrity, but has no UI Automation provider. Non-classic controls
  therefore fail closed as `target_unavailable`.
- Platform identities remain inside the Windows adapter; the portable token
  carries only a random opaque key. Modifier wait/preflight happens before the
  final target assessment; dispatch then performs only a non-blocking modifier
  check before direct or paste input.
- The controlled native fixture verifies actual foreground/focus before
  capture and guards every real `SendInput` call against its own HWND/control.
- Real clipboard access uses a private message-only owner window. The window
  is closed deterministically when CLI delivery ends; `OpenClipboard(NULL)` is
  never used for mutation/restoration.
- All clipboard handles are allocated before `EmptyClipboard`; a partial
  multi-format write gets one bounded retry and preserves a retryable ownership
  marker if recovery still fails.
- Unconfirmed synthetic-key cleanup poisons the injector and blocks every
  subsequent dispatch in that process.
- Real `Ctrl+V` and clipboard restoration were not exercised because the
  pre-existing clipboard included an unsupported format. Overwriting it would
  violate the spike's own safety invariant.
- A complete Notepad/browser/Word matrix requires an isolated operator session
  after adding and testing UI Automation identity/password probes.
- Generic paste can prove only input dispatch, not destination consumption.
- A TOCTOU interval remains between final revalidation and destination input
  processing.
