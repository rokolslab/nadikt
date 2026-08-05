"""Windows platform adapter boundaries."""

from nadikt.infrastructure.platform.windows.uia import UiaElementProbe, UiaTargetSafetyProvider
from nadikt.infrastructure.platform.windows.clipboard import ClipboardSafeSnapshot, WindowsClipboardTransactionAdapter
from nadikt.infrastructure.platform.windows.input import WindowsInputDispatchAdapter
from nadikt.infrastructure.platform.windows.target import WindowsTargetAdapter

__all__ = [
    "ClipboardSafeSnapshot",
    "UiaElementProbe",
    "UiaTargetSafetyProvider",
    "WindowsClipboardTransactionAdapter",
    "WindowsInputDispatchAdapter",
    "WindowsTargetAdapter",
]
