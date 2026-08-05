"""Windows input dispatch adapter boundary."""

from __future__ import annotations

import logging
import os
from typing import Protocol

from nadikt.domain.ports.insertion import InputDispatchOutcomeCode, InputDispatchPort, InputDispatchRequest, InputDispatchResult

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


class InputFacade(Protocol):
    """Injected Windows input facade; no handles/PIDs leave this boundary."""

    def modifiers_safe(self) -> bool:
        """Return whether active modifiers make dispatch safe."""

    def dispatch_clipboard_paste(self) -> bool:
        """Dispatch paste and return low-level send confirmation."""

    def dispatch_direct_unicode(self, text: str) -> bool:
        """Dispatch direct Unicode only when explicitly permitted."""


class WindowsInputDispatchAdapter(InputDispatchPort):
    """Fail-closed input adapter with optional direct Unicode fallback."""

    def __init__(self, facade: InputFacade | None = None) -> None:
        self._facade = facade

    def dispatch_text(self, request: InputDispatchRequest) -> InputDispatchResult:
        LOGGER.debug(
            "input.dispatch.start",
            extra={
                "token": "<opaque>",
                "text_chars": len(request.text),
                "permit_direct_unicode_fallback": request.permit_direct_unicode_fallback,
            },
        )
        if self._facade is None:
            return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_UNCONFIRMED, "none", False)
        if not self._facade.modifiers_safe():
            return InputDispatchResult(InputDispatchOutcomeCode.MODIFIER_UNSAFE, "preflight", False)
        if self._facade.dispatch_clipboard_paste():
            return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_CONFIRMED, "clipboard_paste", True)
        if not request.permit_direct_unicode_fallback:
            return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_UNCONFIRMED, "clipboard_paste", False)
        if self._facade.dispatch_direct_unicode(request.text):
            return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_CONFIRMED, "direct_unicode", True)
        return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_FAILED, "direct_unicode", False)


__all__ = ["InputFacade", "WindowsInputDispatchAdapter"]
