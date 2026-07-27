"""Segmentation policy validation for fair ASR candidate comparison."""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from .logging_config import get_logger

LOGGER = get_logger(__name__)


@dataclass(frozen=True, repr=False)
class SegmentDescriptor:
    sample_id: str
    segment_id: int
    start_seconds: float
    end_seconds: float
    overlap_left_seconds: float
    overlap_right_seconds: float
    boundary_policy_id: str

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    def __repr__(self) -> str:
        return (
            "SegmentDescriptor("
            f"sample_id={self.sample_id!r}, segment_id={self.segment_id!r}, "
            f"duration_seconds={self.duration_seconds:.3f}, "
            f"boundary_policy_id={self.boundary_policy_id!r})"
        )


def validate_segments(
    segments: list[SegmentDescriptor],
    *,
    max_segment_seconds: float,
) -> list[str]:
    """Validate ordering and per-engine segment length limits."""

    errors: list[str] = []
    previous_by_sample: dict[str, SegmentDescriptor] = {}
    for segment in segments:
        if segment.segment_id < 0:
            errors.append(f"{segment.sample_id}:{segment.segment_id}:negative_id")
        if segment.start_seconds < 0 or segment.end_seconds <= segment.start_seconds:
            errors.append(f"{segment.sample_id}:{segment.segment_id}:invalid_bounds")
        if segment.duration_seconds > max_segment_seconds:
            errors.append(f"{segment.sample_id}:{segment.segment_id}:segment_too_long")
        previous = previous_by_sample.get(segment.sample_id)
        if previous is not None and segment.segment_id <= previous.segment_id:
            errors.append(f"{segment.sample_id}:{segment.segment_id}:non_monotonic_id")
        if previous is not None and segment.start_seconds < previous.start_seconds:
            errors.append(f"{segment.sample_id}:{segment.segment_id}:non_monotonic_time")
        previous_by_sample[segment.sample_id] = segment

    LOGGER.info(
        "segmentation_manifest_validated",
        extra={"segment_count": len(segments), "error_count": len(errors)},
    )
    return errors


def default_single_segment(sample_id: str, duration_seconds: float, policy_id: str) -> SegmentDescriptor:
    """Create a safe placeholder segment descriptor for dry-run manifests."""

    return SegmentDescriptor(
        sample_id=sample_id,
        segment_id=0,
        start_seconds=0.0,
        end_seconds=duration_seconds,
        overlap_left_seconds=0.0,
        overlap_right_seconds=0.0,
        boundary_policy_id=policy_id,
    )
