from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Camera, CameraStatus, DetectionEvent, Role, Severity, User, Watchlist
from .schemas import BoundingBox, EventIn
from .security import hash_password
from .services import ingest

CAMERAS = [
    dict(code="AMD-JN-001", name="Ahmedabad Riverfront Junction", department="Ahmedabad Traffic Police", latitude=23.0304, longitude=72.5684, camera_type="ANPR + PTZ", source_protocol="RECORDED_FILE", status=CameraStatus.ONLINE, enabled=True, simulated=True, zone="Central", storage_metadata={"retention_days": 7, "tier": "hot", "video_asset": "ahmedabad-junction.mp4"}),
    dict(code="RTO-CHK-007", name="Subhash Bridge RTO Checkpoint", department="Gujarat RTO", latitude=23.0675, longitude=72.5851, camera_type="Fixed ANPR", source_protocol="RECORDED_FILE", status=CameraStatus.DEGRADED, enabled=True, simulated=True, zone="North", storage_metadata={"retention_days": 14, "tier": "hot", "video_asset": "rto-checkpoint.mp4"}),
    dict(code="SGH-ENT-012", name="S.G. Highway Entry", department="Ahmedabad Traffic Police", latitude=23.0753, longitude=72.5258, camera_type="Fixed ANPR", source_protocol="SIMULATED", status=CameraStatus.ONLINE, enabled=True, simulated=True, zone="West", storage_metadata={"retention_days": 7, "tier": "hot"}),
]

def seed():
    Base.metadata.create_all(engine); db = SessionLocal()
    try:
        if not db.scalar(select(User).limit(1)):
            db.add_all([User(email="admin@okdriver.local", name="Demo Administrator", password_hash=hash_password("AdminDemo123!"), role=Role.ADMIN), User(email="operator@okdriver.local", name="Control Room Operator", password_hash=hash_password("OperatorDemo123!"), role=Role.OPERATOR)])
        if not db.scalar(select(Camera).limit(1)):
            db.add_all([Camera(**c, stream_endpoint_secret=f"simulated://{c['code'].lower()}", last_heartbeat=datetime.now(timezone.utc)) for c in CAMERAS])
        if not db.scalar(select(Watchlist).limit(1)):
            db.add_all([Watchlist(entity_type="vehicle", identifier="GJ01XX0001", normalized_identifier="GJ01XX0001", category="Stolen vehicle", reason="Synthetic demo: reported stolen", severity=Severity.CRITICAL, active=True, notes="Demonstration data only"), Watchlist(entity_type="vehicle", identifier="GJ-18-BL-4420", normalized_identifier="GJ18BL4420", category="Blacklisted vehicle", reason="Synthetic demo: repeated permit violation", severity=Severity.HIGH, active=True, notes="Demonstration data only")])
        db.commit()
        cameras = db.scalars(select(Camera).order_by(Camera.code)).all()
        templates = {item["code"]: item for item in CAMERAS}
        for camera in cameras:
            template = templates.get(camera.code)
            if template:
                camera.source_protocol = template["source_protocol"]
                camera.storage_metadata = template["storage_metadata"]
        db.commit()
        if not db.scalar(select(DetectionEvent).limit(1)):
            base = datetime.now(timezone.utc) - timedelta(minutes=45)
            for i, camera in enumerate(cameras):
                ingest(db, EventIn(external_event_id=f"seed-route-{i}", camera_id=camera.id, timestamp=base + timedelta(minutes=i*14), vehicle_number="GJ01XX0001", confidence=.91 + i*.02, vehicle_type="car", bounding_box=BoundingBox(x=.22,y=.34,width=.33,height=.28), source_metadata={"adapter":"seed"}))
    finally: db.close()

if __name__ == "__main__": seed(); print("Demo data ready")

