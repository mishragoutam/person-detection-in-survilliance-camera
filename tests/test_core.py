from pathlib import Path

from core.threat_engine import ThreatEngine
from services.evidence import EvidenceManager
from storage.database import EventStore


def test_threat_score_and_severity():
    assessment = ThreatEngine(5).assess(
        is_person=True,
        authorized=False,
        confidence=0.95,
        distance_m=2.0,
        in_restricted_zone=True,
    )
    assert assessment.score == 93
    assert assessment.severity == "CRITICAL"
    assert assessment.event_type == "RESTRICTED_ZONE_INTRUSION"


def test_authorized_person_is_not_a_threat():
    assessment = ThreatEngine(5).assess(
        is_person=True,
        authorized=True,
        confidence=1.0,
        distance_m=1.0,
    )
    assert assessment.score == 0
    assert assessment.severity == "NORMAL"


def test_event_store_and_evidence(tmp_path: Path):
    store = EventStore(tmp_path / "events.db")
    event_id = store.add_event({
        "camera_id": "CAM-01",
        "event_type": "EXCESSIVE_PROXIMITY",
        "severity": "WARNING",
        "score": 70,
        "distance_m": 2.4,
    })
    assert store.list_events(1)[0]["event_id"] == event_id
    store.update_status(event_id, "ACKNOWLEDGED")
    assert store.list_events(1)[0]["status"] == "ACKNOWLEDGED"

    manager = EvidenceManager(tmp_path / "evidence")
    folder = manager.event_directory(event_id)
    metadata = manager.write_metadata({"event_id": event_id}, folder)
    assert metadata.name == "metadata.json"
    assert metadata.exists()
    store.close()
