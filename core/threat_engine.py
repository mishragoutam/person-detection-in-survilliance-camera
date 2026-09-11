"""Configurable threat scoring kept separate from object detection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThreatAssessment:
    score: int
    severity: str
    event_type: str


class ThreatEngine:
    """Turn detection context into a bounded, explainable threat score."""

    def __init__(self, proximity_limit_m: float = 5.0) -> None:
        self.proximity_limit_m = max(0.1, proximity_limit_m)

    def assess(
        self,
        *,
        is_person: bool,
        authorized: bool,
        confidence: float,
        distance_m: float | None,
        in_restricted_zone: bool = False,
        dwell_seconds: float = 0.0,
    ) -> ThreatAssessment:
        if not is_person or authorized:
            return ThreatAssessment(0, "NORMAL", "AUTHORIZED_PERSON")

        score = min(35, max(0, int(confidence * 35)))
        event_type = "UNKNOWN_PERSON"
        if distance_m is not None and distance_m <= self.proximity_limit_m:
            score += 35
            event_type = "EXCESSIVE_PROXIMITY"
        if in_restricted_zone:
            score += 25
            event_type = "RESTRICTED_ZONE_INTRUSION"
        if dwell_seconds >= 10:
            score += 10
            event_type = "LOITERING"

        score = min(100, score)
        severity = (
            "CRITICAL" if score >= 81 else
            "WARNING" if score >= 61 else
            "SUSPICIOUS" if score >= 31 else
            "NORMAL"
        )
        return ThreatAssessment(score, severity, event_type)
