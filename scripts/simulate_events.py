"""Inject demo ANPR and heartbeat events. Uses only Python's standard library."""
import argparse, json, time, urllib.request
from datetime import datetime, timezone

def call(url,data,token=None):
    req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={"Content-Type":"application/json",**({"Authorization":f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req) as response:return json.load(response)
def get(url,token):
    req=urllib.request.Request(url,headers={"Authorization":f"Bearer {token}"})
    with urllib.request.urlopen(req) as response:return json.load(response)
def main():
    p=argparse.ArgumentParser();p.add_argument("--base",default="http://localhost:8000/api/v1");p.add_argument("--vehicle",default="GJ01XX0001");a=p.parse_args()
    auth=call(f"{a.base}/auth/login",{"email":"admin@okdriver.local","password":"AdminDemo123!"});token=auth["access_token"];camera=get(f"{a.base}/cameras",token)[0]
    event={"external_event_id":f"sim-{int(time.time()*1000)}","camera_id":camera["id"],"timestamp":datetime.now(timezone.utc).isoformat(),"vehicle_number":a.vehicle,"confidence":.97,"vehicle_type":"car","bounding_box":{"x":.2,"y":.3,"width":.4,"height":.3},"event_type":"anpr","source_metadata":{"adapter":"cli-simulator","synthetic":True}}
    print(json.dumps(call(f"{a.base}/events/ingest",event,token),indent=2));print("Event injected. Watch the dashboard update without refresh.")
if __name__=="__main__":main()
