"""Safe insertion contracts for platform adapters.

All target internals, HWND/PID/thread IDs, UIA/COM objects, clipboard payloads
and process/window names stay inside adapter-owned stores. Public DTO reprs are
redacted by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from secrets import token_urlsafe
from typing import Protocol


class TargetSafetyOutcome(str, Enum):
    """Fail-closed target capture and revalidation outcomes."""

    SAFE = "safe"
    TARGET_CHANGED = "target_changed"
    TARGET_UNAVAILABLE = "target_unavailable"
    TARGET_PROTECTED = "target_protected"
    TARGET_ELEVATED = "target_elevated"
    UNKNOWN_PROVIDER = "unknown_provider"
    STALE_TOKEN = "stale_token"


class ClipboardOutcomeCode(str, Enum):
    """Safe clipboard transaction outcomes."""

    PREPARED = "prepared"
    COMMITTED = "committed"
    RESTORED = "restored"
    DISCARDED = "discarded"
    CLIPBOARD_UNSAFE = "clipboard_unsafe"
    SEQUENCE_CHANGED = "sequence_changed"
    PENDING_CLIPBOARD_RESTORE = "pending_clipboard_restore"
    RESTORE_FAILED = "restore_failed"


class InputDispatchOutcomeCode(str, Enum):
    """Safe input dispatch outcomes."""

    DISPATCH_CONFIRMED = "dispatch_confirmed"
    DISPATCH_UNCONFIRMED = "dispatch_unconfirmed"
    DIRECT_UNICODE_NOT_PERMITTED = "direct_unicode_not_permitted"
    MODIFIER_UNSAFE = "modifier_unsafe"
    DISPATCH_FAILED = "dispatch_failed"


class InsertionFailureCode(str, Enum):
    """Application-visible insertion failure codes."""

    TARGET_CHANGED = "target_changed"
    TARGET_UNAVAILABLE = "target_unavailable"
    TARGET_PROTECTED = "target_protected"
    TARGET_ELEVATED = "target_elevated"
    CLIPBOARD_UNSAFE = "clipboard_unsafe"
    DISPATCH_UNCONFIRMED = "dispatch_unconfirmed"
    PENDING_CLIPBOARD_RESTORE = "pending_clipboard_restore"
    STALE_TOKEN = "stale_token"


@dataclass(frozen=True, repr=False)
class TargetToken:
    """Random opaque key for an adapter-owned target snapshot."""

    value: str = field(default_factory=lambda: token_urlsafe(24))

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("target token value is required")

    def __repr__(self) -> str:
        return "TargetToken(value=<opaque>)"


@dataclass(frozen=True, repr=False)
class TargetCaptureResult:
    """Result of focused target capture with no platform internals exposed."""

    token: TargetToken
    outcome: TargetSafetyOutcome
    provider: str
    protection_known: bool
    safe_to_insert: bool

    def __repr__(self) -> str:
        return (
            "TargetCaptureResult("
            f"token=<opaque>, outcome={self.outcome.value!r}, "
            f"provider={self.provider!r}, "
            f"protection_known={self.protection_known!r}, "
            f"safe_to_insert={self.safe_to_insert!r})"
        )


@dataclass(frozen=True, repr=False)
class TargetRevalidationResult:
    """Result of fail-closed target revalidation before mutation."""

    token: TargetToken
    outcome: TargetSafetyOutcome
    identity_stable: bool
    protection_known: bool
    safe_to_insert: bool

    def __repr__(self) -> str:
        return (
            "TargetRevalidationResult("
            f"token=<opaque>, outcome={self.outcome.value!r}, "
            f"identity_stable={self.identity_stable!r}, "
            f"protection_known={self.protection_known!r}, "
            f"safe_to_insert={self.safe_to_insert!r})"
        )


@dataclass(frozen=True, repr=False)
class ClipboardSnapshot:
    """Opaque adapter-owned snapshot handle for restore/discard decisions."""

    snapshot_id: str
    format_count: int
    has_private_or_delayed_formats: bool = False

    def __repr__(self) -> str:
        return (
            "ClipboardSnapshot("
            f"snapshot_id={self.snapshot_id!r}, "
            f"format_count={self.format_count!r}, "
            f"has_private_or_delayed_formats={self.has_private_or_delayed_formats!r})"
        )


@dataclass(frozen=True, repr=False)
class ClipboardTransactionResult:
    """Clipboard operation result without clipboard contents."""

    outcome: ClipboardOutcomeCode
    snapshot: ClipboardSnapshot | None = None
    sequence_changed: bool = False
    retained_original: bool = False

    def __repr__(self) -> str:
        return (
            "ClipboardTransactionResult("
            f"outcome={self.outcome.value!r}, "
            f"snapshot={'<opaque>' if self.snapshot else None!r}, "
            f"sequence_changed={self.sequence_changed!r}, "
            f"retained_original={self.retained_original!r})"
        )


@dataclass(frozen=True, repr=False)
class InputDispatchRequest:
    """Request to deliver already prepared text; repr hides the text."""

    token: TargetToken
    text: str
    permit_direct_unicode_fallback: bool = False

    def __repr__(self) -> str:
        return (
            "InputDispatchRequest("
            f"token=<opaque>, text_chars={len(self.text)!r}, "
            f"permit_direct_unicode_fallback={self.permit_direct_unicode_fallback!r})"
        )


@dataclass(frozen=True, repr=False)
class InputDispatchResult:
    """Dispatch result with method/outcome metadata only."""

    outcome: InputDispatchOutcomeCode
    method: str
    confirmed: bool

    def __repr__(self) -> str:
        return (
            "InputDispatchResult("
            f"outcome={self.outcome.value!r}, method={self.method!r}, "
            f"confirmed={self.confirmed!r})"
        )


class TargetCapturePort(Protocol):
    """Capture and revalidate the current insertion target."""

    def capture_current_target(self) -> TargetCaptureResult:
        """Capture focused target into an adapter-owned opaque store."""

    def revalidate_target(self, token: TargetToken) -> TargetRevalidationResult:
        """Fail closed if identity, protection or integrity changed."""

    def invalidate_target(self, token: TargetToken) -> None:
        """Invalidate the token after terminal outcome or user cancellation."""


class ClipboardTransactionPort(Protocol):
    """Prepare, commit and settle clipboard-backed insertion."""

    def prepare_text(self, token: TargetToken, text: str) -> ClipboardTransactionResult:
        """Snapshot current clipboard and place insertion text if safe."""

    def commit(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        """Mark the prepared insertion transaction as committed."""

    def restore_original(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        """Restore original clipboard only when the sequence is safe."""

    def discard_original(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        """Forget retained original clipboard data by explicit decision."""


class InputDispatchPort(Protocol):
    """Dispatch prepared text input to the captured target."""

    def dispatch_text(self, request: InputDispatchRequest) -> InputDispatchResult:
        """Send paste/direct Unicode input according to adapter policy."""


def safe_target_log_context(result: TargetCaptureResult | TargetRevalidationResult) -> dict[str, object]:
    """Build allowlisted target safety context."""

    context: dict[str, object] = {
        "token": "<opaque>",
        "outcome": result.outcome.value,
        "protection_known": result.protection_known,
        "safe_to_insert": result.safe_to_insert,
    }
    if isinstance(result, TargetCaptureResult):
        context["provider"] = result.provider
    else:
        context["identity_stable"] = result.identity_stable
    return context


__all__ = [
    "ClipboardOutcomeCode",
    "ClipboardSnapshot",
    "ClipboardTransactionPort",
    "ClipboardTransactionResult",
    "InputDispatchOutcomeCode",
    "InputDispatchPort",
    "InputDispatchRequest",
    "InputDispatchResult",
    "InsertionFailureCode",
    "TargetCapturePort",
    "TargetCaptureResult",
    "TargetRevalidationResult",
    "TargetSafetyOutcome",
    "TargetToken",
    "safe_target_log_context",
]
