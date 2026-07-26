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

Manual fixture and CLI commands are added with their corresponding spike
phases. No network access or external package installation is required.

## Acceptance Matrix

Not executed yet. Manual results must be recorded only after running each case
on the named application and environment.
