"""Privacy-safe environment fingerprint for ASR benchmark runs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import locale
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .logging_config import get_logger
from .package_integrity import checksum_prefix

LOGGER = get_logger(__name__)

DEFAULT_PACKAGE_NAMES = (
    "faster-whisper",
    "ctranslate2",
    "gigaam",
    "torch",
    "numpy",
)


@dataclass(frozen=True)
class BenchmarkEnvironmentProfile:
    profile_id: str
    python_version: str
    python_implementation: str
    platform_system: str
    platform_release: str
    platform_machine: str
    locale_encoding: str
    package_versions: dict[str, str]
    lock_digests: dict[str, str]
    cpu_threads: int
    openmp_num_threads: int
    blas_num_threads: int

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "profile_id": self.profile_id,
            "python": {
                "version": self.python_version,
                "implementation": self.python_implementation,
            },
            "platform": {
                "system": self.platform_system,
                "release": self.platform_release,
                "machine": self.platform_machine,
            },
            "locale_encoding": self.locale_encoding,
            "package_versions": dict(sorted(self.package_versions.items())),
            "lock_digests": dict(sorted(self.lock_digests.items())),
            "inference_defaults": {
                "cpu_threads": self.cpu_threads,
                "openmp_num_threads": self.openmp_num_threads,
                "blas_num_threads": self.blas_num_threads,
            },
        }


def build_environment_fingerprint(
    *,
    lock_files: Iterable[Path] = (),
    package_names: Iterable[str] = DEFAULT_PACKAGE_NAMES,
    cpu_threads: int = 4,
    openmp_num_threads: int = 4,
    blas_num_threads: int = 1,
) -> BenchmarkEnvironmentProfile:
    """Build an allowlisted benchmark environment profile without sensitive paths."""

    lock_paths = tuple(lock_files)
    LOGGER.debug("environment_fingerprint_start", extra={"lock_count": len(lock_paths)})
    locks = {path.name: checksum_prefix(_sha256_file(path)) for path in lock_paths if path.is_file()}
    package_versions = _installed_versions(package_names)
    profile_seed = "|".join(
        [
            platform.python_version(),
            platform.python_implementation(),
            platform.system(),
            platform.release(),
            platform.machine(),
            *[f"{name}:{digest}" for name, digest in sorted(locks.items())],
            *[f"{name}:{version}" for name, version in sorted(package_versions.items())],
        ]
    )
    profile_id = checksum_prefix(hashlib.sha256(profile_seed.encode("utf-8")).hexdigest())
    profile = BenchmarkEnvironmentProfile(
        profile_id=profile_id,
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        platform_system=platform.system(),
        platform_release=platform.release(),
        platform_machine=platform.machine(),
        locale_encoding=locale.getencoding(),
        package_versions=package_versions,
        lock_digests=locks,
        cpu_threads=cpu_threads,
        openmp_num_threads=openmp_num_threads,
        blas_num_threads=blas_num_threads,
    )
    LOGGER.info(
        "environment_fingerprint_done",
        extra={
            "profile_id": profile.profile_id,
            "python_version": profile.python_version,
            "platform_system": profile.platform_system,
            "lock_count": len(profile.lock_digests),
            "package_count": len(profile.package_versions),
        },
    )
    return profile


def _installed_versions(package_names: Iterable[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in package_names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path.cwd()
    lock_files = sorted((root / "requirements" / "benchmark").glob("*.lock.txt"))
    print(__import__("json").dumps(build_environment_fingerprint(lock_files=lock_files).to_json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
