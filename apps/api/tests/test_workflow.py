import os

os.environ["DATABASE_URL"]="sqlite:///./test_okdriver.db"
os.environ["JWT_SECRET"]="test-secret-at-least-thirty-two-characters"

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Alert, AlertStatus, DetectionEvent
from app.seed import seed
from app.services import normalize_vehicle

client=TestClient(app)

def setup_module():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);seed()
def teardown_module():
    Base.metadata.drop_all(engine)
    try: os.remove("test_okdriver.db")
    except OSError: pass
def login(email="admin@okdriver.local",password="AdminDemo123!"):
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password});assert response.status_code==200;return {"Authorization":f"Bearer {response.json()['access_token']}"}

def test_authentication_and_permissions():
    assert client.get("/api/v1/cameras").status_code==401
    operator=login("operator@okdriver.local","OperatorDemo123!")
    payload={"code":"DENIED-1","name":"Denied","department":"Test","latitude":23,"longitude":72,"zone":"Test"}
    assert client.post("/api/v1/cameras",json=payload,headers=operator).status_code==403

def test_admin_can_onboard_camera():
    response=client.post("/api/v1/cameras",headers=login(),json={"code":"TEST-API-01","name":"API Onboarded Camera","department":"Test Control","latitude":23.1,"longitude":72.6,"zone":"Test"})
    assert response.status_code==201
    assert "stream_endpoint" not in response.json()

def test_normalization():
    assert normalize_vehicle(" gj-01 xx 0001 ")=="GJ01XX0001"

def test_validation_rejects_bad_event():
    response=client.post("/api/v1/events/ingest",headers=login(),json={"external_event_id":"bad","camera_id":"missing"})
    assert response.status_code==422

def test_ingestion_watchlist_alert_dedup_and_lifecycle():
    headers=login();camera=client.get("/api/v1/cameras",headers=headers).json()[0]
    payload={"external_event_id":"integration-match-100","camera_id":camera["id"],"timestamp":datetime.now(timezone.utc).isoformat(),"vehicle_number":"GJ-01-XX-0001","confidence":.98,"vehicle_type":"car","bounding_box":{"x":.2,"y":.2,"width":.3,"height":.3},"event_type":"anpr","source_metadata":{"synthetic":True}}
    response=client.post("/api/v1/events/ingest",headers=headers,json=payload);assert response.status_code==201
    body=response.json();assert body["alert_id"] and body["duplicate"] is False
    duplicate=client.post("/api/v1/events/ingest",headers=headers,json=payload).json();assert duplicate["duplicate"] is True;assert duplicate["event"]["id"]==body["event"]["id"]
    ack=client.post(f"/api/v1/alerts/{body['alert_id']}/acknowledge",headers=headers,json={"note":"Unit response"});assert ack.status_code==200;assert ack.json()["status"]=="acknowledged"
    resolved=client.post(f"/api/v1/alerts/{body['alert_id']}/resolve",headers=headers,json={"note":"Verified synthetic event"});assert resolved.status_code==200;assert resolved.json()["status"]=="resolved"
    with SessionLocal() as db:
        assert db.get(Alert,body["alert_id"]).status==AlertStatus.RESOLVED
        assert len(db.scalars(select(DetectionEvent).where(DetectionEvent.external_event_id=="integration-match-100")).all())==1

def test_movement_history_is_chronological():
    data=client.get("/api/v1/vehicles/GJ01XX0001/movement",headers=login()).json();times=[row["timestamp"] for row in data["detections"]]
    assert len(times)>=3;assert times==sorted(times);assert "not road-network" in data["route_note"]


def test_recorded_stream_adapter_and_media_delivery():
    headers=login();camera=client.get("/api/v1/cameras",headers=headers).json()[0]
    response=client.get(f"/api/v1/cameras/{camera['id']}/stream",headers=headers)
    assert response.status_code==200
    stream=response.json();assert stream["adapter"]=="recorded_file";assert stream["playback_url"].endswith(".mp4")
    media=client.get(stream["playback_url"])
    assert media.status_code==200;assert media.headers["content-type"]=="video/mp4";assert len(media.content)>10000


def test_alert_contains_operational_evidence():
    rows=client.get("/api/v1/alerts",headers=login()).json();assert rows
    assert 0 <= rows[0]["confidence"] <= 1
    assert rows[0]["occurred_at"] and rows[0]["latitude"] and rows[0]["longitude"]
