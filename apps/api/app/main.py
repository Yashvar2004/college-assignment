from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .database import Base, engine, get_db
from .models import Alert, AlertStatus, AuditLog, Camera, CameraStatus, DetectionEvent, User, Watchlist
from .realtime import hub
from .schemas import (
    AlertAction,
    AlertOut,
    AuditOut,
    CameraIn,
    CameraOut,
    CameraPatch,
    EventIn,
    EventOut,
    HeartbeatIn,
    IngestOut,
    LoginIn,
    TokenOut,
    WatchlistIn,
    WatchlistOut,
)
from .security import create_token, current_user, require_admin, verify_password
from .services import audit, ingest, normalize_vehicle

limiter = Limiter(key_func=get_remote_address, default_limits=["600/minute"])

app = FastAPI(title="okDriver Command Center API", version="1.0.0", description="Central CCTV, ANPR, GIS, watchlist and real-time alert prototype")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
MEDIA_DIR = Path(__file__).resolve().parents[1] / "media"
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="synthetic-media")

@app.on_event("startup")
def startup(): Base.metadata.create_all(engine)
@app.get("/health")
def health(): return {"status":"healthy", "service":"okdriver-api"}
@app.post("/api/v1/auth/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Invalid email or password")
    audit(db, "auth.login", "user", user.id, user.id, ip=request.client.host if request.client else None); db.commit()
    return TokenOut(access_token=create_token(user), user=user)
@app.get("/api/v1/auth/me", response_model=dict)
def me(user: User = Depends(current_user)): return {"id":user.id,"email":user.email,"name":user.name,"role":user.role.value}

@app.get("/api/v1/cameras", response_model=list[CameraOut])
def cameras(q: str | None=None, status_filter: CameraStatus | None=Query(None, alias="status"), department: str | None=None, limit: int=Query(50,le=100), offset: int=0, db: Session=Depends(get_db), _=Depends(current_user)):
    stmt=select(Camera).order_by(Camera.name).offset(offset).limit(limit)
    if q: stmt=stmt.where(or_(Camera.name.ilike(f"%{q}%"),Camera.code.ilike(f"%{q}%"),Camera.zone.ilike(f"%{q}%")))
    if status_filter: stmt=stmt.where(Camera.status==status_filter)
    if department: stmt=stmt.where(Camera.department==department)
    return db.scalars(stmt).all()
@app.get("/api/v1/cameras/{camera_id}/stream")
def camera_stream(camera_id: str, request: Request, db: Session=Depends(get_db), _=Depends(current_user)):
    camera=db.get(Camera,camera_id)
    if not camera or not camera.enabled: raise HTTPException(404,"Camera not found or disabled")
    default_asset="rto-checkpoint.mp4" if "RTO" in camera.code else "ahmedabad-junction.mp4"
    asset=camera.storage_metadata.get("video_asset",default_asset)
    if Path(asset).name != asset or not (MEDIA_DIR / asset).exists(): raise HTTPException(404,"Configured media asset is unavailable")
    return {"camera_id":camera.id,"adapter":"recorded_file","delivery":"http_mp4","playback_url":f"{str(request.base_url).rstrip('/')}/media/{asset}","simulated":camera.simulated,"loop":True,"notice":"Original synthetic recorded asset; no private surveillance footage."}
@app.post("/api/v1/cameras", response_model=CameraOut, status_code=201)
def create_camera(data: CameraIn, db: Session=Depends(get_db), user: User=Depends(require_admin)):
    if db.scalar(select(Camera).where(Camera.code==data.code)): raise HTTPException(409,"Camera code already exists")
    values=data.model_dump(); endpoint=values.pop("stream_endpoint"); camera=Camera(**values,stream_endpoint_secret=endpoint)
    db.add(camera);db.flush();audit(db,"camera.created","camera",camera.id,user.id,{"code":camera.code});db.commit();db.refresh(camera);return camera
@app.patch("/api/v1/cameras/{camera_id}", response_model=CameraOut)
def patch_camera(camera_id:str,data:CameraPatch,db:Session=Depends(get_db),user:User=Depends(require_admin)):
    camera=db.get(Camera,camera_id)
    if not camera: raise HTTPException(404,"Camera not found")
    changes=data.model_dump(exclude_none=True); endpoint=changes.pop("stream_endpoint",None)
    for k,v in changes.items(): setattr(camera,k,v)
    if endpoint: camera.stream_endpoint_secret=endpoint
    audit(db,"camera.updated","camera",camera.id,user.id,data.model_dump(exclude_none=True));db.commit();db.refresh(camera);return camera
@app.post("/api/v1/cameras/{camera_id}/heartbeat", response_model=CameraOut)
async def heartbeat(camera_id:str,data:HeartbeatIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    camera=db.get(Camera,camera_id)
    if not camera: raise HTTPException(404,"Camera not found")
    camera.status=data.status;camera.last_heartbeat=datetime.now(timezone.utc);audit(db,"camera.heartbeat","camera",camera.id,user.id,{"status":data.status.value,"latency_ms":data.latency_ms});db.commit();db.refresh(camera)
    await hub.broadcast("camera.health",{"camera_id":camera.id,"status":camera.status.value,"last_heartbeat":camera.last_heartbeat.isoformat()});return camera

@app.get("/api/v1/watchlist",response_model=list[WatchlistOut])
def list_watchlist(q:str|None=None,active:bool|None=None,limit:int=Query(50,le=100),offset:int=0,db:Session=Depends(get_db),_=Depends(current_user)):
    stmt=select(Watchlist).order_by(Watchlist.created_at.desc()).offset(offset).limit(limit)
    if q: stmt=stmt.where(or_(Watchlist.identifier.ilike(f"%{q}%"),Watchlist.reason.ilike(f"%{q}%")))
    if active is not None: stmt=stmt.where(Watchlist.active==active)
    return db.scalars(stmt).all()
@app.post("/api/v1/watchlist",response_model=WatchlistOut,status_code=201)
def create_watchlist(data:WatchlistIn,db:Session=Depends(get_db),user:User=Depends(require_admin)):
    item=Watchlist(**data.model_dump(),normalized_identifier=normalize_vehicle(data.identifier));db.add(item);db.flush();audit(db,"watchlist.created","watchlist",item.id,user.id,{"identifier":item.normalized_identifier});db.commit();db.refresh(item);return item
@app.patch("/api/v1/watchlist/{item_id}",response_model=WatchlistOut)
def update_watchlist(item_id:str,data:WatchlistIn,db:Session=Depends(get_db),user:User=Depends(require_admin)):
    item=db.get(Watchlist,item_id)
    if not item: raise HTTPException(404,"Watchlist entry not found")
    for k,v in data.model_dump().items(): setattr(item,k,v)
    item.normalized_identifier=normalize_vehicle(data.identifier);audit(db,"watchlist.updated","watchlist",item.id,user.id);db.commit();db.refresh(item);return item

def alert_view(a:Alert):
    return AlertOut(id=a.id,event_id=a.event_id,watchlist_id=a.watchlist_id,camera_id=a.camera_id,severity=a.severity,status=a.status,created_at=a.created_at,occurred_at=a.event.occurred_at,confidence=a.event.confidence,acknowledged_by=a.acknowledged_by,acknowledged_at=a.acknowledged_at,resolved_by=a.resolved_by,resolved_at=a.resolved_at,resolution_note=a.resolution_note,vehicle_number=a.event.normalized_vehicle_number,camera_name=a.camera.name,latitude=a.camera.latitude,longitude=a.camera.longitude,reason=a.watchlist.reason)
@app.post("/api/v1/events/ingest",response_model=IngestOut,status_code=201)
@limiter.limit("120/minute")
async def ingest_event(request:Request,data:EventIn,db:Session=Depends(get_db),_=Depends(current_user)):
    try: event,alert,duplicate=ingest(db,data)
    except ValueError as e: raise HTTPException(422,str(e))
    if not duplicate:
        await hub.broadcast("detection.created",EventOut.model_validate(event).model_dump(mode="json"))
        if alert:
            alert=db.scalar(select(Alert).options(joinedload(Alert.event),joinedload(Alert.camera),joinedload(Alert.watchlist)).where(Alert.id==alert.id)); await hub.broadcast("alert.created",alert_view(alert).model_dump(mode="json"))
    return IngestOut(event=event,alert_id=alert.id if alert else None,duplicate=duplicate)
@app.get("/api/v1/events",response_model=list[EventOut])
def events(vehicle:str|None=None,camera_id:str|None=None,event_type:str|None=None,time_from:datetime|None=None,time_to:datetime|None=None,limit:int=Query(50,le=200),offset:int=0,db:Session=Depends(get_db),_=Depends(current_user)):
    stmt=select(DetectionEvent).order_by(DetectionEvent.occurred_at.desc()).offset(offset).limit(limit)
    if vehicle: stmt=stmt.where(DetectionEvent.normalized_vehicle_number==normalize_vehicle(vehicle))
    if camera_id: stmt=stmt.where(DetectionEvent.camera_id==camera_id)
    return db.scalars(stmt).all()
@app.get("/api/v1/vehicles/{vehicle}/movement")
def movement(vehicle:str,db:Session=Depends(get_db),_=Depends(current_user)):
    rows=db.scalars(select(DetectionEvent).options(joinedload(DetectionEvent.camera)).where(DetectionEvent.normalized_vehicle_number==normalize_vehicle(vehicle)).order_by(DetectionEvent.occurred_at.asc()).limit(200)).all()
    return {"vehicle_number":normalize_vehicle(vehicle),"route_note":"Straight lines connect detection points; this is not road-network reconstruction.","detections":[{"id":e.id,"timestamp":e.occurred_at,"confidence":e.confidence,"camera_id":e.camera_id,"camera_name":e.camera.name,"latitude":e.camera.latitude,"longitude":e.camera.longitude} for e in rows]}

@app.get("/api/v1/alerts",response_model=list[AlertOut])
def alerts(status_filter:AlertStatus|None=Query(None,alias="status"),limit:int=Query(50,le=100),offset:int=0,db:Session=Depends(get_db),_=Depends(current_user)):
    stmt=select(Alert).options(joinedload(Alert.event),joinedload(Alert.camera),joinedload(Alert.watchlist)).order_by(Alert.created_at.desc()).offset(offset).limit(limit)
    if status_filter:stmt=stmt.where(Alert.status==status_filter)
    return [alert_view(a) for a in db.scalars(stmt).unique().all()]
async def set_alert_state(alert_id:str,new_status:AlertStatus,data:AlertAction,db:Session,user:User):
    alert=db.get(Alert,alert_id)
    if not alert:raise HTTPException(404,"Alert not found")
    now=datetime.now(timezone.utc)
    if new_status==AlertStatus.ACKNOWLEDGED:
        if alert.status!=AlertStatus.NEW:raise HTTPException(409,"Only new alerts can be acknowledged")
        alert.status=new_status;alert.acknowledged_by=user.id;alert.acknowledged_at=now
    else:
        if alert.status==AlertStatus.RESOLVED:raise HTTPException(409,"Alert already resolved")
        alert.status=new_status;alert.resolved_by=user.id;alert.resolved_at=now;alert.resolution_note=data.note
    audit(db,f"alert.{new_status.value}","alert",alert.id,user.id,{"note":data.note});db.commit()
    await hub.broadcast("alert.updated",{"id":alert.id,"status":alert.status.value});return {"id":alert.id,"status":alert.status.value}
@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge(alert_id:str,data:AlertAction,db:Session=Depends(get_db),user:User=Depends(current_user)):return await set_alert_state(alert_id,AlertStatus.ACKNOWLEDGED,data,db,user)
@app.post("/api/v1/alerts/{alert_id}/resolve")
async def resolve(alert_id:str,data:AlertAction,db:Session=Depends(get_db),user:User=Depends(current_user)):return await set_alert_state(alert_id,AlertStatus.RESOLVED,data,db,user)
@app.get("/api/v1/audit",response_model=list[AuditOut])
def audit_history(q:str|None=None,action:str|None=None,limit:int=Query(50,le=100),offset:int=0,db:Session=Depends(get_db),_=Depends(current_user)):
    stmt=select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    if q:stmt=stmt.where(or_(AuditLog.resource_type.ilike(f"%{q}%"),AuditLog.resource_id.ilike(f"%{q}%")))
    if action:stmt=stmt.where(AuditLog.action==action)
    return db.scalars(stmt).all()
@app.get("/api/v1/dashboard")
def dashboard(db:Session=Depends(get_db),_=Depends(current_user)):
    counts={s.value:db.scalar(select(func.count()).select_from(Camera).where(Camera.status==s)) for s in CameraStatus}
    return {"cameras":{"total":db.scalar(select(func.count()).select_from(Camera)),**counts},"active_alerts":db.scalar(select(func.count()).select_from(Alert).where(Alert.status!=AlertStatus.RESOLVED)),"detections_24h":db.scalar(select(func.count()).select_from(DetectionEvent)),"watchlist_active":db.scalar(select(func.count()).select_from(Watchlist).where(Watchlist.active.is_(True)))}
@app.websocket("/api/v1/ws")
async def websocket(ws:WebSocket,token:str):
    try:
        import jwt
        jwt.decode(token,get_settings().jwt_secret,algorithms=["HS256"])
    except Exception: await ws.close(code=4401);return
    await hub.connect(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: hub.disconnect(ws)

