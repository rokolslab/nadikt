"""Optional SDK-backed ASR adapters.

Importing this package must not import concrete ASR SDKs. Concrete modules keep
SDK imports inside load/probe paths so missing optional dependencies are safe.
"""

__all__ = ["faster_whisper", "gigaam"]
