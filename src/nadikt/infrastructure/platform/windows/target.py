"""Windows target adapter facade for safe insertion."""

from __future__ import annotations

from nadikt.infrastructure.platform.windows.uia import UiaFacade, UiaTargetSafetyProvider


class WindowsTargetAdapter(UiaTargetSafetyProvider):
    """Target adapter backed by UIA safety probes.

    Without an injected facade it inherits UIA fail-closed behavior.
    """

    def __init__(self, facade: UiaFacade | None = None) -> None:
        super().__init__(facade=facade)


__all__ = ["WindowsTargetAdapter"]
