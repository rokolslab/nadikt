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

Not executed yet. Manual results must be recorded only after running each case
on the named application and environment.
