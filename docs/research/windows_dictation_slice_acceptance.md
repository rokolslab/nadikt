# Windows Dictation Slice Acceptance Matrix

Version: `windows-dictation-slice-acceptance.v1`  
Status: `NOT RUN`  
Created: 2026-08-05

This matrix is for the controlled minimal Windows dictation vertical slice. It is
not MVP acceptance and does not supersede the disposable insertion spike results.
Every `NOT RUN` row is a blocker for claiming that target category as accepted.

Allowed evidence fields: safe outcome code, duration bucket, target category,
OS/app category, backend/candidate ID, package ID, blocker status and operator
decision code. Do not record transcript text, audio paths, clipboard contents,
window titles, process names, filenames, handles, PIDs, local model paths, user
names or private asset locations.

## Harness Scope

- Entry point: `python -m nadikt.presentation.cli.windows_dictation_slice`.
- One bounded microphone recording only; no tray, overlay, global hotkey or full desktop shell.
- Target is captured before dictation and revalidated before mutation.
- ASR uses exactly one explicit `candidate_id` plus validated local package binding.
- Final ASR winner remains `NOT DECIDED` until benchmark and Windows evidence exist.
- Pending clipboard restore requires explicit `restore_original` or `discard_original` operator decision.

## Matrix

| ID | Scenario | Expected Safe Outcome | Status | Evidence |
|---|---|---|---|---|
| WDS-001 | Notepad normal text field | `completed` or safe typed blocker | `NOT RUN` | blocker |
| WDS-002 | Classic Win32 `EDIT` fixture | `completed` for normal, no target change | `NOT RUN` | blocker |
| WDS-003 | Classic `ES_PASSWORD` fixture | `target_protected`, no mutation | `NOT RUN` | blocker |
| WDS-004 | Edge normal field | `completed` only if UIA protection known false | `NOT RUN` | blocker |
| WDS-005 | Edge password field | `target_protected`, no mutation | `NOT RUN` | blocker |
| WDS-006 | Chrome normal field | `completed` only if UIA protection known false | `NOT RUN` | blocker |
| WDS-007 | Chrome password field | `target_protected`, no mutation | `NOT RUN` | blocker |
| WDS-008 | Firefox normal field | `completed` only if UIA protection known false | `NOT RUN` | blocker |
| WDS-009 | Firefox password field | `target_protected`, no mutation | `NOT RUN` | blocker |
| WDS-010 | Word isolated document | `completed` only after isolated document setup | `NOT RUN` | blocker |
| WDS-011 | 1C text field if installed | `completed` only if UIA safety proven | `NOT RUN` | blocker |
| WDS-012 | Elevated target | `target_elevated`, no mutation | `NOT RUN` | blocker |
| WDS-013 | Windows 10 host | Same scenario outcomes as Windows 11 baseline | `NOT RUN` | blocker |
| WDS-014 | Target changed within same window/control family | `target_changed`, retained result | `NOT RUN` | blocker |
| WDS-015 | Captured target destroyed before insertion | `target_unavailable`, retained result | `NOT RUN` | blocker |
| WDS-016 | Clipboard text/Unicode restoration | `restored` after explicit restore | `NOT RUN` | blocker |
| WDS-017 | Clipboard image restoration | `restored` or `clipboard_unsafe` before mutation | `NOT RUN` | blocker |
| WDS-018 | Clipboard file-list restoration | `restored` or `clipboard_unsafe` before mutation | `NOT RUN` | blocker |
| WDS-019 | Unknown/HTML/RTF/delayed-rendered clipboard formats | `clipboard_unsafe`, no mutation | `NOT RUN` | blocker |
| WDS-020 | External clipboard sequence race | no overwrite of newer external clipboard | `NOT RUN` | blocker |
| WDS-021 | Default microphone unavailable | `device_unavailable`, no insertion | `NOT RUN` | blocker |
| WDS-022 | Short utterance | no empty insert unless ASR returns non-empty final text | `NOT RUN` | blocker |
| WDS-023 | Silence | no empty insert | `NOT RUN` | blocker |
| WDS-024 | Pre-buffer first-word behavior | first word not clipped in controlled phrase category | `NOT RUN` | blocker |
| WDS-025 | Microphone disconnect during capture | `device_disconnected` or safe capture failure | `NOT RUN` | blocker |

## Run Notes Template

```text
Run ID:
Date:
OS category:
App category:
Scenario IDs:
Candidate ID:
Package ID:
Safe outcome codes:
Duration buckets:
Operator decision codes:
Blockers:
```

No private ASR paths/assets, sample transcripts, audio labels, clipboard data,
window/process names, filenames, handles or PIDs belong in this file.
