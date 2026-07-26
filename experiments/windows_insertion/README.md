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
python fixtures/clipboard_racer.py --delay-ms 500
```

`classic_target.py` exposes one native `EDIT` and one native `ES_PASSWORD`
control. The local HTML page exposes two normal controls and one password
control in the same browser window. `clipboard_racer.py` writes only a fixed
synthetic value and reports readiness/case IDs without printing the value.

An elevated case is started manually from an elevated terminal. The spike
never requests elevation or bypasses UIPI.

## Manual CLI

Review the fixed synthetic payload in `insertion_spike/cli.py`, focus the
target during the first countdown, and use the second countdown to keep or
intentionally change focus:

```powershell
python -m insertion_spike.cli --confirm --method auto --hold
python -m insertion_spike.cli --confirm --method paste --paste-delay-ms 100
python -m insertion_spike.cli --confirm --method direct
python -m insertion_spike.cli --confirm --dry-run
python -m insertion_spike.cli --confirm --cancel
```

`--paste-delay-ms` is a conservative, measurable wait before clipboard
restoration. It does not prove that the destination consumed the paste.
`Ctrl+V` success therefore means only `dispatched`, never confirmed insertion.

There remains an unavoidable TOCTOU interval between final target validation
and processing of synthetic input by the destination application.

## Acceptance Matrix

Matrix revision: `2026-07-26-1`.

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
| Contracts and boundary failures | automated, injected APIs | PASS | 39 tests passed |
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
| Dispatch/restoration failure | automated, injected API | PASS | result retained; original snapshot retained when needed |
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
- Real `Ctrl+V` and clipboard restoration were not exercised because the
  pre-existing clipboard included an unsupported format. Overwriting it would
  violate the spike's own safety invariant.
- A complete Notepad/browser/Word matrix requires an isolated operator session
  after adding and testing UI Automation identity/password probes.
- Generic paste can prove only input dispatch, not destination consumption.
- A TOCTOU interval remains between final revalidation and destination input
  processing.
