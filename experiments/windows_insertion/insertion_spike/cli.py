"""Two-stage manual CLI for the Windows insertion safety spike."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
from time import sleep
from typing import Sequence
from uuid import uuid4

from .contracts import (
    InsertionMethod,
    InsertionRequest,
    OutcomeCode,
    TargetAdapter,
    ClipboardAdapter,
    InputInjector,
    get_logger,
)
from .service import InsertionService
from .windows_clipboard import CtypesClipboardApi, WindowsClipboardAdapter
from .windows_injector import CtypesInputApi, WindowsInputInjector
from .windows_target import CtypesWindowsTargetApi, TargetCaptureError, WindowsTargetAdapter


SYNTHETIC_PAYLOAD = "NADIKT_SPIKE_Русский_English_😀\nLINE_2"


@dataclass(frozen=True)
class RuntimeDependencies:
    target: TargetAdapter
    clipboard: ClipboardAdapter
    injector: InputInjector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nadikt insertion safety spike")
    parser.add_argument("--method", choices=[item.value for item in InsertionMethod], default="auto")
    parser.add_argument("--capture-countdown", type=int, default=3)
    parser.add_argument("--delivery-countdown", type=int, default=3)
    parser.add_argument("--paste-delay-ms", type=int, default=100)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hold", action="store_true")
    return parser


def create_runtime() -> RuntimeDependencies:
    return RuntimeDependencies(
        target=WindowsTargetAdapter(CtypesWindowsTargetApi()),
        clipboard=WindowsClipboardAdapter(CtypesClipboardApi()),
        injector=WindowsInputInjector(CtypesInputApi()),
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    dependencies: RuntimeDependencies | None = None,
    logger: logging.Logger | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    active_logger = logger or get_logger()
    active_logger.info("cli phase=start method=%s dry_run=%s", args.method, args.dry_run)
    if not args.confirm or args.cancel:
        print(f"outcome={OutcomeCode.CANCELLED.value}")
        return 2
    if args.dry_run:
        print("phase=capture dry_run=true")
        print("phase=deliver dry_run=true")
        print(f"outcome={OutcomeCode.CANCELLED.value}")
        return 0

    runtime = dependencies or create_runtime()
    print("phase=capture prepare_target=true")
    _countdown(args.capture_countdown, active_logger, "capture")
    try:
        captured_target = runtime.target.capture()
    except TargetCaptureError:
        print(f"outcome={OutcomeCode.TARGET_UNAVAILABLE.value}")
        return 1
    print("phase=capture complete=true")
    print("phase=deliver keep_or_change_focus=true")
    _countdown(args.delivery_countdown, active_logger, "deliver")

    request = InsertionRequest(
        request_id=f"manual-{uuid4().hex}",
        text=SYNTHETIC_PAYLOAD,
        method=InsertionMethod(args.method),
    )
    service = InsertionService(
        runtime.target,
        runtime.clipboard,
        runtime.injector,
        paste_restore_delay_ms=args.paste_delay_ms,
        logger=active_logger,
    )
    outcome = service.deliver(request, captured_target)
    print(f"outcome={outcome.code.value}")
    print(f"result_retained={str(outcome.retained_in_memory).lower()}")
    print(f"original_retained={str(outcome.original_snapshot_retained).lower()}")
    if args.hold:
        input("Press Enter to release retained in-memory state and exit: ")
    return 0 if outcome.code in {OutcomeCode.DISPATCHED, OutcomeCode.DIRECT_DISPATCHED} else 1


def _countdown(seconds: int, logger: logging.Logger, phase: str) -> None:
    duration = max(0, seconds)
    logger.debug("cli phase=%s countdown_seconds=%d", phase, duration)
    for _ in range(duration):
        sleep(1)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
