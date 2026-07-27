"""Apply a deterministic external clipboard mutation after a fixed delay."""

from __future__ import annotations

import argparse
from time import sleep

from insertion_spike.cli import SYNTHETIC_PAYLOAD
from insertion_spike.windows_clipboard import CF_UNICODETEXT, CtypesClipboardApi


SYNTHETIC_EXTERNAL_VALUE = "NADIKT_EXTERNAL_CLIPBOARD_CHANGE"
SYNTHESIZED_TEXT_FORMATS = frozenset({1, 7, 16})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay-ms", type=int, default=500)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        print("CANCELLED case=clipboard_race confirmation_required=true", flush=True)
        return 2
    print("READY case=clipboard_race", flush=True)
    sleep(max(0, args.delay_ms) / 1000)
    encoded = SYNTHETIC_EXTERNAL_VALUE.encode("utf-16-le") + b"\x00\x00"
    api = CtypesClipboardApi()
    try:
        with api.opened():
            formats = set(api.list_formats())
            allowed_formats = SYNTHESIZED_TEXT_FORMATS | {CF_UNICODETEXT}
            current = api.read_format(CF_UNICODETEXT)
            if (
                CF_UNICODETEXT not in formats
                or not formats.issubset(allowed_formats)
                or current is None
                or not _matches_cli_synthetic_payload(current)
            ):
                print("PRECONDITION_FAILED case=clipboard_race", flush=True)
                return 1
            api.replace_contents({CF_UNICODETEXT: encoded})
    finally:
        api.close()
    print("CHANGED case=clipboard_race", flush=True)
    return 0


def _matches_cli_synthetic_payload(payload: bytes) -> bool:
    try:
        value = payload.decode("utf-16-le").split("\x00", 1)[0]
    except UnicodeDecodeError:
        return False
    return value == SYNTHETIC_PAYLOAD


if __name__ == "__main__":
    raise SystemExit(main())
