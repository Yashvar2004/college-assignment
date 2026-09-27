import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid.uuid4())


class Role(str, enum.Enum): ADMIN = "admin"; OPERATOR = "operator"
class CameraStatus(str, enum.Enum): ONLINE = "online"; OFFLINE = "offline"; DEGRADED = "degraded"
class AlertStatus(str, enum.Enum): NEW = "new"; ACKNOWLEDGED = "acknowledged"; RESOLVED = "resolved"
class Severity(str, enum.Enum): LOW = "low"; MEDIUM = "medium"; HIGH = "high"; CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    camera_type: Mapped[str] = mapped_column(String(60))
    source_protocol: Mapped[str] = mapped_column(String(30))
    stream_endpoint_secret: Mapped[str] = mapped_column(String(500), default="simulated://generated")
    status: Mapped[CameraStatus] = mapped_column(Enum(CameraStatus), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    zone: Mapped[str] = mapped_column(String(80), index=True)
    storage_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Watchlist(Base):
    __tablename__ = "watchlist"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    entity_type: Mapped[str] = mapped_column(String(40), default="vehicle")
    identifier: Mapped[str] = mapped_column(String(80))
    normalized_identifier: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (Index("ix_watchlist_match", "normalized_identifier", "active"),)


class DetectionEvent(Base):
    __tablename__ = "detection_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    external_event_id: Mapped[str] = mapped_column(String(120), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    vehicle_number: Mapped[str] = mapped_column(String(80))
    normalized_vehicle_number: Mapped[str] = mapped_column(String(80), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    vehicle_type: Mapped[str] = mapped_column(String(40))
    bounding_box: Mapped[dict] = mapped_column(JSON)
    event_type: Mapped[str] = mapped_column(String(50), default="anpr")
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    camera: Mapped[Camera] = relationship()
    __table_args__ = (Index("ix_events_vehicle_time", "normalized_vehicle_number", "occurred_at"), Index("ix_events_camera_time", "camera_id", "occurred_at"))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event_id: Mapped[str] = mapped_column(ForeignKey("detection_events.id"), unique=True)
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlist.id"))
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), index=True)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.NEW, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    event: Mapped[DetectionEvent] = relationship()
    camera: Mapped[Camera] = relationship()
    watchlist: Mapped[Watchlist] = relationship()
    __table_args__ = (Index("ix_alert_status_time", "status", "created_at"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(60), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

