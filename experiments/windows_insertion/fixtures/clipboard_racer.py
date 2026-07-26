"""Apply a deterministic external clipboard mutation after a fixed delay."""

from __future__ import annotations

import argparse
from time import sleep

from insertion_spike.windows_clipboard import CF_UNICODETEXT, CtypesClipboardApi


SYNTHETIC_EXTERNAL_VALUE = "NADIKT_EXTERNAL_CLIPBOARD_CHANGE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay-ms", type=int, default=500)
    args = parser.parse_args()
    print("READY case=clipboard_race", flush=True)
    sleep(max(0, args.delay_ms) / 1000)
    encoded = SYNTHETIC_EXTERNAL_VALUE.encode("utf-16-le") + b"\x00\x00"
    api = CtypesClipboardApi()
    with api.opened():
        api.replace_contents({CF_UNICODETEXT: encoded})
    print("CHANGED case=clipboard_race", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
