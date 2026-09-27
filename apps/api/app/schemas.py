from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import AlertStatus, CameraStatus, Severity


class LoginIn(BaseModel): email: str; password: str
class UserOut(BaseModel):
    id: str; email: str; name: str; role: str
    model_config = ConfigDict(from_attributes=True)
class TokenOut(BaseModel): access_token: str; token_type: str = "bearer"; user: UserOut

class CameraIn(BaseModel):
    code: str = Field(min_length=2, max_length=60); name: str = Field(min_length=2, max_length=160)
    department: str; latitude: float = Field(ge=-90, le=90); longitude: float = Field(ge=-180, le=180)
    camera_type: str = "ANPR"; source_protocol: str = "SIMULATED"; stream_endpoint: str = "simulated://generated"
    status: CameraStatus = CameraStatus.ONLINE; enabled: bool = True; simulated: bool = True; zone: str
    storage_metadata: dict = {}
class CameraPatch(BaseModel):
    name: str | None = None; department: str | None = None; status: CameraStatus | None = None
    enabled: bool | None = None; zone: str | None = None; latitude: float | None = None; longitude: float | None = None
    camera_type: str | None = None; source_protocol: str | None = None; stream_endpoint: str | None = None; storage_metadata: dict | None = None
class CameraOut(BaseModel):
    id: str; code: str; name: str; department: str; latitude: float; longitude: float; camera_type: str
    source_protocol: str; status: CameraStatus; enabled: bool; simulated: bool; last_heartbeat: datetime | None
    zone: str; storage_metadata: dict; created_at: datetime; updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
class HeartbeatIn(BaseModel): status: CameraStatus; latency_ms: int = Field(ge=0, le=120000); metadata: dict = {}

class WatchlistIn(BaseModel):
    entity_type: str = "vehicle"; identifier: str = Field(min_length=3, max_length=80); category: str
    reason: str; severity: Severity; active: bool = True; valid_from: datetime | None = None
    valid_until: datetime | None = None; notes: str | None = None
class WatchlistOut(WatchlistIn):
    id: str; normalized_identifier: str; created_at: datetime; updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1); y: float = Field(ge=0, le=1); width: float = Field(gt=0, le=1); height: float = Field(gt=0, le=1)
class EventIn(BaseModel):
    external_event_id: str = Field(min_length=4, max_length=120); camera_id: str; timestamp: datetime
    vehicle_number: str = Field(min_length=3, max_length=30); confidence: float = Field(ge=0, le=1)
    vehicle_type: str = "car"; bounding_box: BoundingBox; event_type: str = "anpr"; source_metadata: dict = {}
    @field_validator("vehicle_number")
    @classmethod
    def useful_identifier(cls, value):
        if len("".join(ch for ch in value if ch.isalnum())) < 3: raise ValueError("vehicle number must contain at least 3 alphanumeric characters")
        return value
class EventOut(BaseModel):
    id: str; external_event_id: str; camera_id: str; occurred_at: datetime; vehicle_number: str
    normalized_vehicle_number: str; confidence: float; vehicle_type: str; bounding_box: dict; event_type: str; created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class IngestOut(BaseModel): event: EventOut; alert_id: str | None; duplicate: bool = False

class AlertOut(BaseModel):
    id: str; event_id: str; watchlist_id: str; camera_id: str; severity: Severity; status: AlertStatus
    created_at: datetime; occurred_at: datetime; confidence: float; acknowledged_by: str | None; acknowledged_at: datetime | None; resolved_by: str | None
    resolved_at: datetime | None; resolution_note: str | None; vehicle_number: str; camera_name: str; latitude: float; longitude: float; reason: str
class AlertAction(BaseModel): note: str | None = Field(default=None, max_length=500)
class AuditOut(BaseModel):
    id: int; actor_id: str | None; action: str; resource_type: str; resource_id: str | None; details: dict; created_at: datetime
    model_config = ConfigDict(from_attributes=True)

