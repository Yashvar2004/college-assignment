import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alert, AuditLog, Camera, DetectionEvent, Watchlist
from .schemas import EventIn


def normalize_vehicle(value: str) -> str: return re.sub(r"[^A-Z0-9]", "", value.upper())
def audit(db: Session, action: str, resource_type: str, resource_id=None, actor_id=None, details=None, ip=None):
    db.add(AuditLog(actor_id=actor_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details or {}, ip_address=ip))
def ingest(db: Session, data: EventIn):
    existing = db.scalar(select(DetectionEvent).where(DetectionEvent.external_event_id == data.external_event_id))
    if existing: return existing, db.scalar(select(Alert).where(Alert.event_id == existing.id)), True
    normalized = normalize_vehicle(data.vehicle_number)
    bucket = int(data.timestamp.timestamp() // 10)
    fingerprint = hashlib.sha256(f"{data.camera_id}:{normalized}:{bucket}".encode()).hexdigest()
    existing = db.scalar(select(DetectionEvent).where(DetectionEvent.fingerprint == fingerprint))
    if existing: return existing, db.scalar(select(Alert).where(Alert.event_id == existing.id)), True
    camera = db.get(Camera, data.camera_id)
    if not camera or not camera.enabled: raise ValueError("Camera does not exist or is disabled")
    event = DetectionEvent(external_event_id=data.external_event_id, fingerprint=fingerprint, camera_id=data.camera_id,
        occurred_at=data.timestamp, vehicle_number=data.vehicle_number.upper(), normalized_vehicle_number=normalized,
        confidence=data.confidence, vehicle_type=data.vehicle_type, bounding_box=data.bounding_box.model_dump(),
        event_type=data.event_type, source_metadata=data.source_metadata)
    db.add(event); db.flush()
    now = datetime.now(timezone.utc)
    matches = db.scalars(select(Watchlist).where(Watchlist.normalized_identifier == normalized, Watchlist.active.is_(True))).all()
    match = next((w for w in matches if (not w.valid_from or w.valid_from <= now) and (not w.valid_until or w.valid_until >= now)), None)
    alert = None
    if match:
        alert = Alert(event_id=event.id, watchlist_id=match.id, camera_id=camera.id, severity=match.severity)
        db.add(alert); db.flush()
    audit(db, "event.ingested", "detection_event", event.id, details={"matched": bool(alert)})
    db.commit(); db.refresh(event)
    return event, alert, False

